"""OpenRouter client, with the structured-output fallbacks that make it reliable.

The whole UI is driven by a JSON object, so the one thing this module must never
do is hand back prose. It tries three increasingly blunt approaches in order:

1. `response_format: json_schema` with `strict: true` — enforced by the provider,
   which is the only approach that genuinely cannot drift.
2. Plain `json_object` mode, for models that support JSON but not schemas.
3. A bare request with the schema pasted into the prompt.

Between them, anything that comes back still goes through a lenient parser,
because a model that wraps perfect JSON in a markdown fence should not cost a
recipe.
"""

from __future__ import annotations

import json
import re
import time

import requests

from . import config, schema

_FENCE = re.compile(r'```(?:json)?\s*(.*?)```', re.DOTALL)

# A 429 from OpenRouter is usually not "you have run out" — it is a free or
# shared provider pool being briefly busy, and it comes with a Retry-After of a
# few seconds. Treating that as terminal turns a five-second wait into a failed
# recipe, so it is retried. Capped so a genuinely exhausted quota still fails
# fast instead of hanging the request for minutes.
RATE_LIMIT_ATTEMPTS = 3
MAX_BACKOFF_SECONDS = 20


class OpenRouterError(RuntimeError):
    """Anything that stops a recipe coming back, phrased for the user.

    `terminal` says whether retrying the same request differently could possibly
    help. Credentials, credit and rate limits will not improve because we asked
    for the JSON a different way; a schema the provider would not honour might.
    Carried as a flag rather than sniffed out of the message text, because error
    strings are for humans and change freely.
    """

    def __init__(self, message: str, terminal: bool = False):
        super().__init__(message)
        self.terminal = terminal


def _headers(key: str) -> dict:
    return {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        # Attribution headers. Only cosmetic, but they make the OpenRouter usage
        # dashboard legible when one account serves several projects.
        'HTTP-Referer': config.APP_REFERER,
        'X-Title': config.APP_TITLE,
    }


def extract_json(text: str) -> dict:
    """Pull an object out of whatever the model actually said.

    Handles a clean object, a fenced block, and the common failure where a model
    adds a sentence of preamble before the brace.
    """
    if not text:
        raise OpenRouterError('The model returned an empty response.')
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = _FENCE.search(text)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise OpenRouterError('The model did not return valid JSON. Try again, or '
                          'switch to a model that supports structured output.')


def _error_detail(response) -> str:
    """The most specific explanation the response carries.

    OpenRouter nests the useful sentence under `error.metadata.raw` — the
    top-level message is often just "Provider returned error", which tells a user
    nothing about whether to wait, switch model, or add credit.
    """
    try:
        error = response.json().get('error', {}) or {}
    except ValueError:
        return response.text[:300]
    metadata = error.get('metadata') or {}
    for candidate in (metadata.get('raw'), metadata.get('remedy_hint'),
                      error.get('message')):
        if candidate:
            return str(candidate)[:400]
    return ''


def _retry_after(response, default: int = 5) -> int:
    """Seconds to wait, from the header or the body, clamped.

    A rate-limit response is not guaranteed to be JSON — an edge proxy can answer
    429 with HTML. Parsing it outside a guard turned a retryable wait into a 500.
    """
    candidates = [response.headers.get('Retry-After')]
    try:
        body = response.json() if response.content else {}
        candidates.append((body.get('error') or {}).get('metadata', {})
                          .get('retry_after_seconds'))
    except (ValueError, AttributeError):
        pass
    for source in candidates:
        if source is None:
            continue
        try:
            return max(1, min(int(float(source)), MAX_BACKOFF_SECONDS))
        except (TypeError, ValueError):
            continue
    return default


def _post(body: dict, key: str) -> dict:
    last_rate_limit = ''
    for attempt in range(RATE_LIMIT_ATTEMPTS):
        try:
            response = requests.post(config.OPENROUTER_URL, headers=_headers(key),
                                     json=body, timeout=config.REQUEST_TIMEOUT)
        except requests.Timeout:
            raise OpenRouterError(
                f'OpenRouter did not answer within {config.REQUEST_TIMEOUT}s.',
                terminal=True) from None
        except requests.RequestException as exc:
            raise OpenRouterError(f'Could not reach OpenRouter: {exc}', terminal=True) from None

        if response.status_code == 401:
            raise OpenRouterError('OpenRouter rejected the API key.', terminal=True)
        if response.status_code == 402:
            raise OpenRouterError(
                'OpenRouter says this account is out of credit. Add credit, or '
                'switch to a model whose id ends in ":free" in Settings.',
                terminal=True)

        if response.status_code == 429:
            last_rate_limit = _error_detail(response)
            if attempt < RATE_LIMIT_ATTEMPTS - 1:
                time.sleep(_retry_after(response))
                continue
            raise OpenRouterError(
                f'Rate limited by OpenRouter after {RATE_LIMIT_ATTEMPTS} tries. '
                f'{last_rate_limit}'.strip(), terminal=True)

        if response.status_code >= 400:
            raise OpenRouterError(
                f'OpenRouter returned {response.status_code}: {_error_detail(response)}')

        try:
            return response.json()
        except ValueError:
            raise OpenRouterError(
                'OpenRouter returned a response that was not JSON.') from None

    raise OpenRouterError(f'Rate limited by OpenRouter. {last_rate_limit}'.strip(),
                          terminal=True)


def _content(data: dict) -> str:
    try:
        return data['choices'][0]['message']['content'] or ''
    except (KeyError, IndexError, TypeError):
        raise OpenRouterError('OpenRouter returned no message content.') from None


def _meta(data: dict, model: str) -> dict:
    usage = data.get('usage') or {}
    return {
        'model': data.get('model') or model,
        'prompt_tokens': usage.get('prompt_tokens'),
        'output_tokens': usage.get('completion_tokens'),
        'cost_usd': usage.get('cost'),
    }


def generate(system_prompt: str, user_message: str, model: str,
             on_attempt=None) -> tuple:
    """Ask for a recipe. Returns `(payload_dict, meta_dict)`.

    The three attempts are tried in order and only a *schema-shaped* failure
    falls through to the next one — an auth error or an empty wallet raises
    immediately rather than burning two more calls to say the same thing.

    `on_attempt(model)` fires immediately BEFORE each billed completion, so the
    caller's spend ledger records the call even when it goes on to fail. Counting
    after the fact made failures free, which is how the daily cap ended up blind
    to a retry loop.
    """
    key = config.openrouter_key()
    if not key:
        raise OpenRouterError(
            'No OpenRouter API key configured. Put it in data/openrouter.key or '
            'set OPENROUTER_API_KEY.', terminal=True)

    base = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ],
        'temperature': 0.8,   # recipes should vary between asks; the schema holds the shape
        'max_tokens': 4000,
    }

    attempts = [
        dict(base, response_format={
            'type': 'json_schema',
            'json_schema': {'name': 'recipe', 'strict': True,
                            'schema': schema.RECIPE_SCHEMA},
        }),
        dict(base, response_format={'type': 'json_object'}),
        dict(base, messages=[
            base['messages'][0],
            {'role': 'user', 'content':
             f'{user_message}\n\nReturn ONLY a JSON object matching this schema, '
             f'with no commentary and no markdown fence:\n'
             f'{json.dumps(schema.RECIPE_SCHEMA)}'},
        ]),
    ]

    last_error = None
    best = None            # the least-wrong payload seen, in case all attempts miss
    for index, attempt in enumerate(attempts):
        try:
            if on_attempt:
                on_attempt(model)
            data = _post(attempt, key)
            payload = schema.repair(extract_json(_content(data)))
        except OpenRouterError as exc:
            if exc.terminal:
                raise
            last_error = exc
            continue

        # Valid JSON is not the same as the right object. A weaker model will
        # happily return a well-formed thing with `steps` missing and `heat`
        # hoisted to the top level -- without this check the fallback chain never
        # fires, because nothing ever raised.
        problems = schema.shape_errors(payload)
        if not problems:
            return payload, _meta(data, model)

        if best is None or len(problems) < len(best[2]):
            best = (payload, _meta(data, model), problems)
        last_error = OpenRouterError(
            'The model returned JSON in the wrong shape (' +
            ', '.join(problems[:4]) + ').')
        if index < len(attempts) - 1:
            continue

    # Every attempt missed. A partial recipe that renders with a visible warning
    # beats an error page -- normalise() fills the gaps and says which ones.
    if best is not None:
        return best[0], best[1]
    raise last_error or OpenRouterError('Could not get a usable recipe.')


def list_models() -> list:
    """Model ids that can hold a schema, for the settings screen.

    Filtered to those OpenRouter advertises as supporting structured outputs —
    picking a model that cannot is the fastest way to a blank screen.
    """
    key = config.openrouter_key()
    headers = _headers(key) if key else {}
    try:
        response = requests.get(config.OPENROUTER_MODELS_URL, headers=headers, timeout=30)
        response.raise_for_status()
        models = response.json().get('data', [])
    except (requests.RequestException, ValueError) as exc:
        raise OpenRouterError(f'Could not list models: {exc}', terminal=True) from None

    out = []
    for model in models:
        params = model.get('supported_parameters') or []
        pricing = model.get('pricing') or {}
        out.append({
            'id': model.get('id'),
            'name': model.get('name'),
            'structured': 'structured_outputs' in params or 'response_format' in params,
            'prompt_price': pricing.get('prompt'),
            'completion_price': pricing.get('completion'),
        })
    out.sort(key=lambda m: (not m['structured'], m['id'] or ''))
    return out
