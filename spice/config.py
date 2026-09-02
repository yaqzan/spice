"""Paths, ports, and the OpenRouter credential lookup.

No secret is written down in this file. The OpenRouter key is read from the
environment or from `data/openrouter.key`, which is gitignored — so this module
is safe to commit and the key never ends up in a prompt, a log or a diff.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── serving ──────────────────────────────────────────────────────────────────
# One port serves both /api and the built SPA, so whatever fronts this needs
# exactly one hostname (the Curator/Scribe pattern). 5003 is the next free slot
# after trader-api (5000), fantasy-api (5001) and curator-api (5002).
#
# **127.0.0.1, never `localhost`.** On Windows `localhost` resolves to `::1`
# first and these services bind IPv4 only, so every probe against a dead service
# burns the IPv6 timeout before it even tries the real address.
API_HOST = os.environ.get('SPICE_HOST', '127.0.0.1')
API_PORT = int(os.environ.get('SPICE_PORT', '5003'))
PUBLIC_ORIGIN = os.environ.get('SPICE_PUBLIC_ORIGIN', 'https://spice.yaqzan.dev')

# ── storage ──────────────────────────────────────────────────────────────────
DATA_DIR = Path(os.environ.get('SPICE_DATA_DIR', ROOT / 'data'))
DB_PATH = Path(os.environ.get('SPICE_DB', DATA_DIR / 'spice.db'))
FRONTEND_DIST = ROOT / 'frontend' / 'dist'

# The rating reminder, in the owner's Obsidian vault. A real default rather than
# an empty one that has to be switched on: this feature's whole failure mode is
# doing nothing quietly, and a path that must be exported before it works would
# behave differently from a shell than from the service wrapper. If the folder
# is not there, spice/vault.py stays silent -- see .claude/docs/vault.md.
TODO_FILE = Path(os.environ.get(
    'SPICE_TODO_FILE', r'C:\Obsidian\Mycelium\To Do\Recipes.md'))

# ── OpenRouter ───────────────────────────────────────────────────────────────
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_MODELS_URL = 'https://openrouter.ai/api/v1/models'

# Changeable from the app's settings screen; this is only the fallback for a
# fresh database. Any OpenRouter model id works — what matters is that it holds
# a JSON schema reliably, because the whole UI is driven by structured output.
DEFAULT_MODEL = os.environ.get('SPICE_MODEL', 'openai/gpt-5.6-luna')

# Sent as OpenRouter's attribution headers. Harmless, and it makes the usage
# dashboard readable when several projects share one account.
APP_TITLE = 'Spice'
APP_REFERER = PUBLIC_ORIGIN

REQUEST_TIMEOUT = int(os.environ.get('SPICE_TIMEOUT', '180'))

KEY_FILE = Path(os.environ.get('SPICE_KEY_FILE', DATA_DIR / 'openrouter.key'))

# ── Tailscale ────────────────────────────────────────────────────────────────
# The app listens on loopback AND on this machine's Tailscale address. Arriving
# from a tailnet peer is the ONLY way to reach anything private — there is no
# passphrase to fall back on — so this bind is not a convenience, it is the lock.
#
# Deliberately NOT 0.0.0.0. Binding every interface would let the LAN reach the
# port too, and the whole guarantee here is that the SOCKET proves where a
# request came from. Two named binds keep that true: nothing but loopback and
# the tailnet can connect at all.
TAILSCALE_EXE = os.environ.get(
    'SPICE_TAILSCALE', 'C:/Program Files/Tailscale/tailscale.exe')
TRUST_TAILNET = os.environ.get('SPICE_TRUST_TAILNET', '1') != '0'

# Development only, and off unless explicitly set. A laptop running the Vite dev
# server talks to a loopback API, which by the rule above is a stranger — so
# without this there is no way to build the owner-side screens at all. Never set
# it in server.ps1: loopback is also where the public tunnel arrives, so this
# flag opens the app to the internet.
OPEN_ACCESS = os.environ.get('SPICE_OPEN', '') == '1'

_TAILSCALE_IP_CACHE = []


def tailscale_ip() -> str:
    """This machine's tailnet IPv4, or '' if Tailscale is not running.

    Returns empty rather than raising so the app still boots on a box with no
    Tailscale — the second bind is simply skipped and the app serves its public
    read-only face to everyone, including the owner.
    """
    if _TAILSCALE_IP_CACHE:
        return _TAILSCALE_IP_CACHE[0]
    address = os.environ.get('SPICE_TAILSCALE_IP', '').strip()
    if not address:
        try:
            out = subprocess.run([TAILSCALE_EXE, 'ip', '-4'],
                                 capture_output=True, text=True, timeout=10)
            address = (out.stdout or '').strip().splitlines()[0].strip()
        except (OSError, subprocess.SubprocessError, IndexError):
            address = ''
    _TAILSCALE_IP_CACHE.append(address)
    return address


_TAILNET_URL_CACHE = []


def tailnet_url() -> str:
    """The address a tailnet peer should use, or '' if Tailscale is not running.

    Prefers the MagicDNS name over the raw 100.x address — it is the difference
    between something you can tell someone and something you have to look up.

    This matters because the public hostname CANNOT auto-authenticate: it is a
    CNAME to the Cloudflare tunnel, so a phone on the tailnet still reaches the
    app through Cloudflare, and the app sees loopback. Being on the tailnet only
    helps if you connect to the tailnet address.

    Printed on startup and nowhere else. It used to be handed to anonymous
    callers through the API so the unlock sheet could offer it as a way around
    typing a code; with the code gone that sheet is gone, and the address is now
    the only route to anything private — so it stays off the public surface.
    """
    if _TAILNET_URL_CACHE:
        return _TAILNET_URL_CACHE[0]
    host = ''
    try:
        out = subprocess.run([TAILSCALE_EXE, 'status', '--json'],
                             capture_output=True, text=True, timeout=10)
        host = (json.loads(out.stdout or '{}')
                .get('Self', {}).get('DNSName', '') or '').rstrip('.')
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
        host = ''
    host = host or tailscale_ip()
    url = f'http://{host}:{API_PORT}' if host else ''
    _TAILNET_URL_CACHE.append(url)
    return url


def openrouter_key() -> str:
    """The API key, from the environment or the gitignored key file.

    Returns '' rather than raising so the app boots, serves the rack and shows a
    clear "no key configured" state instead of crashing on import.
    """
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
