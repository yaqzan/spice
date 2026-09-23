"""The recipe contract: the JSON the model must return, and how it is checked.

The app is a *visual* — a rack diagram with jars lit up, a blend table, a step
list with heat guidance attached. None of that can be built from prose, so the
model never writes prose. It fills in this shape, and every spice it names is
resolved against the registry before anything reaches the screen.

`normalise()` is deliberately forgiving in one direction and strict in the other:
it will happily accept "ground cumin" or "Kashmiri chilli" and map them onto the
right jar, but a name it genuinely cannot place is moved out of the blend and
into the shopping list with a warning, rather than silently rendering as a jar
that does not exist.
"""

from __future__ import annotations

import re

from . import rack

HEATS = ('none', 'low', 'medium_low', 'medium', 'medium_high', 'high')
CONFIDENCE = ('proven', 'well_trodden', 'adaptation', 'experiment')

# OpenRouter passes this to providers that support strict JSON schema output.
# Strict mode requires every property to be listed in `required` and
# `additionalProperties: false` throughout — optional fields are expressed as a
# nullable type or an empty array instead.
RECIPE_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['title', 'cuisine', 'protein', 'portion_lb', 'confidence', 'why_this',
                 'heat_level', 'pan', 'times', 'blend', 'salt', 'from_kitchen',
                 'steps', 'salt_check', 'serve_with', 'leftovers'],
    'properties': {
        'title': {'type': 'string',
                  'description': 'Short dish name, 2-5 words. No filler like "delicious".'},
        'cuisine': {'type': 'string',
                    'description': 'One of the tracked cuisines, or a new one named plainly.'},
        'protein': {'type': 'string'},
        'portion_lb': {'type': 'number',
                       'description': 'Weight of protein these amounts are written for.'},
        'confidence': {'type': 'string', 'enum': list(CONFIDENCE),
                       'description': 'proven = close to something already rated well. '
                                      'well_trodden = a classic combination. '
                                      'adaptation = a classic bent to fit the rack. '
                                      'experiment = genuinely untested. Be honest; '
                                      '"experiment" is a useful answer, not a failure.'},
        'why_this': {'type': 'string',
                     'description': 'One or two sentences addressed TO the cook, in the '
                                    'second person: why this dish, now. Say what it is and '
                                    'what makes it worth cooking tonight. A nod to the '
                                    'rotation or a past rating is welcome when there is a '
                                    'real one to point at, but it is not required and an '
                                    'invented one is worse than none. Never write about '
                                    'the cook in the third person.'},
        'heat_level': {'type': 'integer', 'minimum': 1, 'maximum': 5},
        'pan': {'type': 'string',
                'description': 'Which pan and why, e.g. "carbon steel wok - fast, very hot '
                               'centre" or "cast iron - holds heat through three batches".'},
        'times': {
            'type': 'object', 'additionalProperties': False,
            'required': ['prep_min', 'marinate_min', 'cook_min', 'total_min'],
            'properties': {
                'prep_min': {'type': 'integer'},
                'marinate_min': {'type': 'integer', 'description': '0 if no marinade.'},
                'cook_min': {'type': 'integer'},
                'total_min': {'type': 'integer'},
            },
        },
        'blend': {
            'type': 'array',
            'description': 'Every jar this recipe needs, in the order it enters the pan. '
                           'Salt and MSG do NOT go here - they belong in `salt`.',
            'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['spice', 'amount', 'tsp', 'stage', 'step', 'why'],
                'properties': {
                    'spice': {'type': 'string',
                              'description': 'Exact name from the inventory list.'},
                    'amount': {'type': 'string',
                               'description': 'Human measurement, e.g. "1 1/2 tsp", "a pinch".'},
                    'tsp': {'type': 'number',
                            'description': 'Same amount as a decimal number of teaspoons, '
                                           'so the app can rescale. Use 0.06 for a pinch.'},
                    'stage': {'type': 'string', 'enum': list(rack.STAGES)},
                    'step': {'type': 'integer',
                             'description': 'Which numbered step this goes in. 0 if it is '
                                            'premixed rather than added at a moment.'},
                    'why': {'type': 'string',
                            'description': 'Half a sentence on what this one is doing here.'},
                },
            },
        },
        'salt': {
            'type': 'object', 'additionalProperties': False,
            'required': ['grams', 'msg_grams', 'when', 'rationale'],
            'properties': {
                'grams': {'type': 'number',
                          'description': 'The salt you physically ADD, in grams, across the '
                                         'whole dish. This exact number is shown to the cook '
                                         'as the amount to measure out, so it must ALREADY '
                                         'have had any salt inside a pre-salted blend '
                                         '(Cajun, NOLA Cajun, Tex Mex, BBQ, Jerk, Umami Steak '
                                         'Seasoning) and any MSG reduction subtracted from '
                                         'it. Show that subtraction in `rationale`.'},
                'msg_grams': {'type': 'number', 'description': '0 if no MSG.'},
                'when': {'type': 'string',
                         'description': 'When the salt goes on, e.g. "45 min ahead, dry, '
                                        'on the bare protein".'},
                'rationale': {'type': 'string',
                              'description': 'The reasoning: the target rate as a percentage '
                                             'of the meat, and any deduction for a pre-salted '
                                             'blend or MSG. Amounts in spoons - no gram '
                                             'figures, they are for the fields above.'},
            },
        },
        'from_kitchen': {
            'type': 'array',
            'description': 'Everything needed that is NOT on the spice rack - fresh '
                           'aromatics, fats, liquids, sides. Do not leave these implied. '
                           'Salt and MSG do NOT go here either - they belong in `salt`, '
                           'and the card gives them their own panel.',
            'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['item', 'amount'],
                'properties': {
                    'item': {'type': 'string',
                             'description': 'The ingredient, named and nothing more - '
                                            '"yellow onion", not "yellow onion, finely '
                                            'diced". Knife work belongs in `amount`.'},
                    'amount': {'type': 'string',
                               'description': 'How much, and how it should arrive: '
                                              '"1 medium, finely diced".'},
                },
            },
        },
        'steps': {
            'type': 'array',
            'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['n', 'title', 'body', 'minutes', 'heat', 'watch_for'],
                'properties': {
                    'n': {'type': 'integer'},
                    'title': {'type': 'string', 'description': '2-4 words, e.g. "Sear in batches".'},
                    'body': {'type': 'string',
                             'description': 'What to do, in the order to do it. Name a bowl '
                                            '("add BOWL 2") rather than listing what is in '
                                            'it - the card prints the contents beneath the '
                                            'step. Never spend a step reciting which spice '
                                            'is in which bowl.'},
                    'minutes': {'type': 'integer', 'description': '0 if not time-bound.'},
                    'heat': {'type': 'string', 'enum': list(HEATS)},
                    'watch_for': {'type': 'string',
                                  'description': 'The sensory checkpoint - what it should look, '
                                                 'smell or sound like, and the failure sign. '
                                                 'Empty string if there genuinely is not one.'},
                },
            },
        },
        'salt_check': {'type': 'string',
                       'description': 'When to taste and exactly how to correct. Spoons '
                                      'and pinches, never grams.'},
        'serve_with': {'type': 'string',
                       'description': 'What completes the plate. Never leave this blank.'},
        'leftovers': {'type': 'string',
                      'description': 'What to do with leftover blend or cooked food.'},
    },
}


# ── shape checking and repair ────────────────────────────────────────────────
# A model can return perfectly valid JSON that is nevertheless the wrong object,
# and a weaker model reliably will: hoisting per-item fields like `heat` and
# `stage` to the top level, renaming `salt.grams` to `salt.amount_g`, dropping
# `steps` entirely. Parsing succeeds, so without an explicit shape check the
# fallback chain never fires and the wrong object gets stored and rendered.

REQUIRED_TOP = tuple(RECIPE_SCHEMA['required'])

# Near-misses seen from real models, mapped back onto the contract. Cheap to
# repair and not worth spending another API call on.
TOP_ALIASES = {
    'name': 'title', 'dish': 'title', 'recipe_title': 'title',
    'style': 'cuisine', 'main': 'protein', 'protein_type': 'protein',
    'weight_lb': 'portion_lb', 'lb': 'portion_lb',
    'spices': 'blend', 'seasoning': 'blend', 'spice_blend': 'blend',
    'method': 'steps', 'instructions': 'steps', 'directions': 'steps',
    'reason': 'why_this', 'rationale': 'why_this',
    'heat': 'heat_level', 'spice_level': 'heat_level',
    'shopping': 'from_kitchen', 'other_ingredients': 'from_kitchen',
    'pan_notes': 'pan', 'cookware': 'pan',
    'saltcheck': 'salt_check', 'taste_check': 'salt_check',
    'serving': 'serve_with', 'sides': 'serve_with',
    'storage': 'leftovers', 'leftover': 'leftovers',
}

SALT_ALIASES = {'amount_g': 'grams', 'grams_total': 'grams', 'salt_grams': 'grams',
                'total_grams': 'grams', 'msg': 'msg_grams', 'msg_g': 'msg_grams',
                'timing': 'when', 'why': 'rationale'}

BLEND_ALIASES = {'name': 'spice', 'spice_name': 'spice', 'ingredient': 'spice',
                 'quantity': 'amount', 'measure': 'amount', 'teaspoons': 'tsp',
                 'when': 'stage', 'step_number': 'step', 'reason': 'why'}

STEP_ALIASES = {'number': 'n', 'index': 'n', 'step': 'n', 'heading': 'title',
                'text': 'body', 'instruction': 'body', 'description': 'body',
                'time_min': 'minutes', 'duration_min': 'minutes',
                'heat_level': 'heat', 'watch': 'watch_for', 'note': 'watch_for'}

DEFAULTS = {
    'title': 'Untitled recipe', 'cuisine': '', 'protein': '', 'portion_lb': 1.0,
    'confidence': 'experiment', 'why_this': '', 'heat_level': 3, 'pan': '',
    'blend': [], 'from_kitchen': [], 'steps': [],
    'salt_check': '', 'serve_with': '', 'leftovers': '',
}


def _rename(obj: dict, aliases: dict) -> dict:
    """Apply an alias map without ever clobbering a correctly-named field."""
    if not isinstance(obj, dict):
        return obj
    for wrong, right in aliases.items():
        if wrong in obj and right not in obj:
            obj[right] = obj.pop(wrong)
    return obj


def repair(payload: dict) -> dict:
    """Best-effort coercion of a near-miss response onto the contract.

    Only renames and type-coerces — it never invents content. Anything genuinely
    absent stays absent so `shape_errors()` can still report it honestly.
    """
    if not isinstance(payload, dict):
        return {}
    _rename(payload, TOP_ALIASES)

    if isinstance(payload.get('salt'), dict):
        _rename(payload['salt'], SALT_ALIASES)
    elif isinstance(payload.get('salt'), (int, float)):
        # Some models answer `"salt": 8.4` and mean grams.
        payload['salt'] = {'grams': float(payload['salt'])}

    if isinstance(payload.get('blend'), list):
        payload['blend'] = [_rename(item, BLEND_ALIASES)
                            for item in payload['blend'] if isinstance(item, dict)]
    if isinstance(payload.get('steps'), list):
        payload['steps'] = [_rename(item, STEP_ALIASES)
                            for item in payload['steps'] if isinstance(item, dict)]

    times = payload.get('times')
    if not isinstance(times, dict):
        payload['times'] = {'prep_min': 0, 'marinate_min': 0,
                            'cook_min': 0, 'total_min': 0}
    return payload


def shape_errors(payload: dict) -> list:
    """Required fields that are missing or unusable. Empty means it conforms.

    Used to decide whether the fallback chain should try again, so it checks the
    things that make a recipe renderable rather than every leaf of the schema.
    """
    if not isinstance(payload, dict):
        return ['response was not a JSON object']
    problems = [field for field in REQUIRED_TOP if field not in payload]

    blend = payload.get('blend')
    if not isinstance(blend, list) or not blend:
        problems.append('blend is empty')
    steps = payload.get('steps')
    if not isinstance(steps, list) or not steps:
        problems.append('steps is empty')
    salt = payload.get('salt')
    # `not salt.get('grams')` rather than a None/'' check: a zero passed the old
    # test, and zero is the one salt figure that must never reach a plate. It
    # renders as an empty string, so the biggest number on the card becomes
    # blank space -- an unseasoned dinner with nothing on screen to explain it.
    # Failing the shape check instead sends it back through the fallback chain.
    if not isinstance(salt, dict) or not salt.get('grams'):
        problems.append('salt.grams missing')
    return problems


# ── when each spice goes in ──────────────────────────────────────────────────
# The cook measures everything out before starting. That is the right habit, and
# it is also how a dish gets ruined: tip garam masala into the bowl with the
# cumin and it spends forty minutes boiling instead of five, and tastes of dust.
#
# So the blend is never presented as one flat list. It is grouped by the moment a
# spice enters the pan, in order, and each group says whether its contents can
# share a bowl. Same stage, same bowl, same moment. Different stage, different
# bowl, no exceptions.

STAGE_WHEN = {
    'marinade':  'In the marinade, hours ahead',
    'dry_rub':   'Rubbed on before the sear',
    'temper':    'Into hot fat first, before anything else',
    'bloom':     'Bloomed in fat, 30-60 seconds',
    'early':     'Early, in with the aromatics',
    'mid':       'After the sear, once the pan has come down',
    'last_five': 'The last five minutes',
    'off_heat':  'Off the heat, at the very end',
    'garnish':   'On the plate, not in the pan',
}

# Why a group must not be folded into the one before it. Only the stages where
# combining early is an actual mistake carry a reason; the rest are simply a
# different moment.
STAGE_KEEP_APART = {
    'temper':    'Whole seeds need bare hot fat to pop. Anything ground in with '
                 'them burns while they are still working.',
    'last_five': 'Volatile aromatics. Boil them with the rest and they go flat '
                 'and dusty — the exact failure garam masala is famous for.',
    'off_heat':  'Heat destroys what makes these worth having. They go in after '
                 'the pan is off the burner.',
    'garnish':   'These are already cooked, or are texture rather than '
                 'seasoning. They meet the food on the plate.',
}

_STAGE_ORDER = {stage: index for index, stage in enumerate(rack.STAGES)}


def group_blend(items: list) -> list:
    """Split the blend into bowls, in the order they enter the pan.

    Returns one group per stage present, chronologically. `premix` is true when
    a group holds more than one jar — that is a bowl worth measuring out ahead.
    A single jar needs no bowl, only a reminder of when it goes in.
    """
    buckets = {}
    for item in items:
        buckets.setdefault(item.get('stage') or 'mid', []).append(item)

    groups = []
    for stage in sorted(buckets, key=lambda s: _STAGE_ORDER.get(s, 99)):
        members = buckets[stage]
        groups.append({
            'stage': stage,
            'when': STAGE_WHEN.get(stage, stage.replace('_', ' ')),
            'items': members,
            'premix': len(members) > 1,
            'keep_apart': STAGE_KEEP_APART.get(stage, ''),
        })

    # Which of these can be measured out before the heat goes on: everything.
    # The point is that it is several bowls, not one.
    for index, group in enumerate(groups):
        group['bowl'] = index + 1
    return groups


def _number(value, default: float = 0.0) -> float:
    """Whatever the model sent, as a finite float. Never raises."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out or out in (float('inf'), float('-inf')):
        return default
    return out


def _dedupe_blend(items: list) -> list:
    """Fold repeat mentions of one jar into a single row.

    Models like to list a spice twice when it goes in at two moments. The rack
    visual highlights a jar once, so the second mention has to merge into the
    first or the count on screen disagrees with the count in the list.
    """
    merged = {}
    order = []
    for item in items:
        key = item['spice_key']
        if key in merged:
            first = merged[key]
            first['tsp'] = round(_number(first.get('tsp')) + _number(item.get('tsp')), 3)
            extra = item.get('stage')
            if extra and extra not in first['stages']:
                first['stages'].append(extra)
            # A jar can enter the pan twice. Keep the FIRST step for the rack
            # badge order, but remember the rest so the later step still lists it.
            step = item.get('step')
            if step and step != first.get('step'):
                first.setdefault('also_steps', []).append(step)
            why, first_why = str(item.get('why') or ''), str(first.get('why') or '')
            if why and why not in first_why:
                first['why'] = f'{first_why} Then: {why}'.strip()
            # The row now means MORE than it says. `tsp` has just been summed but
            # `amount` is the string the card actually shows, so leaving it is a
            # twofold under-measure of a jar the model listed twice -- and the
            # model listing a jar twice is precisely why this function exists.
            # Any qualifier ("cracked", "crushed between your palms") is carried
            # across: it describes the spice, not the quantity.
            first['amount'] = _restate(first['tsp'], first.get('amount'))
            continue
        item['stages'] = [item['stage']] if item.get('stage') else []
        merged[key] = item
        order.append(key)
    return [merged[key] for key in order]


# The stages whose entire purpose is "after the heat". A jar defaulting to one
# of these is saying heat destroys it, in the only place that is recorded.
FINISHING_STAGES = ('last_five', 'off_heat', 'garnish')

# Plain salt or MSG, however the model chose to describe the box. Narrow on
# purpose: "onion salt" and "salted butter" are real, separate ingredients and
# must survive this filter.
_SALT_ROW = re.compile(
    r'^(?:fine|coarse|flaky|fine[ -]grain|table|kosher|sea|iodi[sz]ed|'
    r'diamond\s+crystal|morton|maldon)?[\s-]*'
    r'(?:table|kosher|sea|flake)?[\s-]*salt$', re.I)
_MSG_ROW = re.compile(r'^(?:msg|monosodium\s+glutamate|aji-?no-?moto)$', re.I)


def is_salt_row(item) -> bool:
    """Is this shopping-list line just the salt (or MSG) said again?"""
    name = str(item or '').strip().strip('.,')
    return bool(_SALT_ROW.match(name) or _MSG_ROW.match(name))


def normalise(payload: dict, out_of_stock=None) -> dict:
    """Resolve every named spice onto a real jar; collect warnings for the UI.

    Returns the payload mutated in place with `spice_key`, `name`, `note`,
    `is_pantry` and `burns` added to each blend row, plus a top-level `warnings`
    list. Never raises on bad model output — a broken recipe still has to render,
    because a warning on screen is more useful than a 500.
    """
    out_of_stock = out_of_stock or set()
    warnings = []

    payload = repair(payload if isinstance(payload, dict) else {})

    # Whatever is still absent gets a safe default, so the frontend is never
    # handed an undefined. The gaps are surfaced as a warning rather than hidden:
    # a recipe with no method is worth showing *and* worth flagging.
    gaps = [field for field in REQUIRED_TOP if field not in payload]
    for field, fallback in DEFAULTS.items():
        if payload.get(field) in (None, ''):
            payload[field] = list(fallback) if isinstance(fallback, list) else fallback
    if not isinstance(payload.get('salt'), dict):
        payload['salt'] = {}
    payload['salt'].setdefault('grams', 0)
    payload['salt'].setdefault('msg_grams', 0)
    payload['salt'].setdefault('when', '')
    payload['salt'].setdefault('rationale', '')
    if gaps:
        warnings.append('The model left out: ' + ', '.join(sorted(gaps)) +
                        '. Try again, or switch to a model that holds a JSON schema.')

    resolved, unplaceable = [], []
    for item in payload.get('blend') or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('spice') or '').strip()
        spice = rack.resolve(name)
        if spice is None:
            unplaceable.append(item)
            continue
        item['spice_key'] = spice.key
        item['name'] = spice.name
        item['note'] = spice.note
        item['burns'] = spice.burns
        # Anything that is not a wall-rack jar: the stove shelf and the
        # sauce shelf both hold containers rather than spice jars.
        item['is_pantry'] = (spice.key in rack.STOVE_BY_KEY
                             or spice.key in rack.SAUCE_BY_KEY)
        item['heat'] = spice.heat
        item['color'] = spice.color
        if not item.get('stage') or item['stage'] not in rack.STAGES:
            item['stage'] = spice.stage
        # A jar with no measurement is useless on a rack diagram. Rebuild it from
        # the numeric field when the model filled in one but not the other.
        if not item.get('amount'):
            item['amount'] = format_tsp(item.get('tsp')) or 'to taste'
        else:
            item['amount'] = canonical_units(item['amount'])
        item['tsp'] = _number(item.get('tsp'))
        item['step'] = item.get('step') or 0
        item['why'] = item.get('why') or ''
        resolved.append(item)

    if not isinstance(payload.get('from_kitchen'), list):
        payload['from_kitchen'] = []
    # Salt and MSG have their own panel, carrying the number that was actually
    # converted for the brand in the cupboard. A model that also lists them here
    # writes them in grams, so the same seasoning appears twice on one card in
    # two different units -- the exact confusion this card is built to prevent.
    payload['from_kitchen'] = [
        item for item in payload['from_kitchen']
        if not (isinstance(item, dict) and is_salt_row(item.get('item')))]
    for item in payload.get('from_kitchen') or []:
        if isinstance(item, dict):
            item['amount'] = canonical_units(item.get('amount'))
    for item in unplaceable:
        label = str(item.get('spice') or 'unknown').strip()
        warnings.append(f'"{label}" is not on the rack - moved to the shopping list.')
        payload['from_kitchen'].append(
            {'item': label, 'amount': item.get('amount', ''), 'off_rack': True})

    resolved = _dedupe_blend(resolved)

    for item in resolved:
        if item['spice_key'] in out_of_stock:
            item['out_of_stock'] = True
            warnings.append(f"{item['name']} is marked out of stock.")
        # The one rule that turns a good recipe into a bitter one: a spice that
        # scorches, told to go on before the sear.
        #
        # Unless that IS the jar's own default. Hing and fenugreek seeds both burn
        # and both must hit hot fat at the start — that is the whole technique.
        # Warning about them meant the registry contradicted itself on screen.
        spice = rack.ALL_BY_KEY.get(item['spice_key'])
        default_stage = spice.stage if spice else None
        if (item.get('burns') and item.get('stage') in ('dry_rub', 'temper')
                and item.get('stage') != default_stage):
            warnings.append(
                f"{item['name']} scorches easily - it is listed for the sear. "
                'Salt first, sear, then add it once the pan comes down.')

        # A separate failure, and the one `burns` cannot see. Urfa, Silk Chili,
        # sumac and kasuri methi do not scorch -- heat simply erases them, which
        # is why they carry a finishing stage instead of a burns flag. Nothing
        # was checking that the model respected it, so Urfa could be scheduled at
        # `bloom` in silence. That used to be bad advice; since group_blend()
        # turns a stage into a physical bowl, it is now a jar tipped into the
        # wrong dish before the stove is even on, and Urfa's own note reads
        # "NEVER toast it and never put it in the pan".
        if (default_stage in FINISHING_STAGES and item.get('stage')
                and item['stage'] != default_stage
                and _STAGE_ORDER.get(item['stage'], 99) < _STAGE_ORDER[default_stage]):
            warnings.append(
                f"{item['name']} is a finishing spice and is listed for "
                f"{item['stage'].replace('_', ' ')}. Heat destroys it - keep it "
                f'out of that bowl. {spice.note}'
                if spice and spice.note else
                f"{item['name']} is a finishing spice and is listed for "
                f"{item['stage'].replace('_', ' ')}. Heat destroys it.")

    payload['blend'] = resolved
    payload['blend_groups'] = group_blend(resolved)
    payload['warnings'] = warnings

    steps = [s for s in (payload.get('steps') or []) if isinstance(s, dict)]
    for index, step in enumerate(steps, start=1):
        step['n'] = step.get('n') or index
        step['title'] = step.get('title') or f'Step {step["n"]}'
        step['body'] = canonical_units(step.get('body') or '')
        step['watch_for'] = canonical_units(step.get('watch_for') or '')
        try:
            step['minutes'] = int(step.get('minutes') or 0)
        except (TypeError, ValueError):
            step['minutes'] = 0
        if step.get('heat') not in HEATS:
            step['heat'] = 'none'
        # Attach each spice to its step so the step list can show the jars in
        # place rather than making the cook scroll back up mid-sear.
        step['spices'] = [
            {'spice_key': item['spice_key'], 'name': item['name'],
             'amount': item.get('amount', ''), 'color': item.get('color', '#888')}
            for item in resolved
            if item.get('step') == step['n'] or step['n'] in (item.get('also_steps') or [])]
    payload['steps'] = steps

    payload.setdefault('from_kitchen', [])
    payload.setdefault('serve_with', '')
    return payload


def scale(payload: dict, factor: float) -> dict:
    """Rescale a stored recipe to a different weight of protein.

    Spice amounts scale linearly and salt scales with them; times do not, which
    is why they are left alone. Below a quarter teaspoon the numbers stop being
    measurable so they are shown as fractions of a pinch rather than decimals.
    """
    if factor == 1:
        return payload
    for item in payload.get('blend', []):
        tsp = float(item.get('tsp') or 0) * factor
        item['tsp'] = round(tsp, 3)
        item['amount'] = format_tsp(tsp)
    salt = payload.get('salt') or {}
    for field in ('grams', 'msg_grams'):
        if salt.get(field):
            salt[field] = round(float(salt[field]) * factor, 1)
    payload['portion_lb'] = round(float(payload.get('portion_lb') or 1) * factor, 2)
    return payload


# Only fractions that exist on a spoon, and quarters ahead of thirds.
#
# 3/8 used to be in this table and is not a spoon in any set -- it is "1/4 plus
# 1/8, twice, carefully", read off a phone over a hot pan.
#
# The third column is a penalty, not a value. Quarters and halves are the
# spoons that come to hand; thirds exist on the set but are the ones you have to
# hunt for, so a third only wins when it is clearly closer, not when it is
# marginally closer. An exact 0.333 still renders as 1/3 -- the penalty bends the
# rounding, it does not ban the fraction.
_FRACTIONS = ((1.0, '1', 0.0), (0.75, '3/4', 0.0), (0.6667, '2/3', 0.04),
              (0.5, '1/2', 0.0), (0.3333, '1/3', 0.04), (0.25, '1/4', 0.0),
              (0.125, '1/8', 0.02), (0.0625, 'pinch of', 0.0))

# "1 tsp" and "1 tbsp" differ by one character, and confusing them is a
# THREEFOLD error — in an app built around not making twofold ones, that is the
# largest mistake on offer. So the two are never allowed to look alike: the
# distinguishing syllable is capitalised in each, giving TEAsp and TBsp, which
# differ at a glance in shape rather than in one easily-missed letter. The
# frontend adds a colour on top of that.
#
# Written once here so the same convention reaches the CLI, the prompt, the API
# and the screen. A unit that renders differently in two places is the same bug
# wearing a hat.
TSP = 'TEAsp'
TBSP = 'TBsp'

# Whatever the model writes, normalised to the house convention. Longest forms
# first so "tablespoon" is not eaten by a shorter pattern.
_UNIT_FORMS = (
    (re.compile('(?<![a-z])table[ -]?spoons?(?![a-z])', re.I), TBSP),
    (re.compile('(?<![a-z])tbsps?(?![a-z])', re.I), TBSP),
    (re.compile('(?<![a-z])tbs(?![a-z])', re.I), TBSP),
    (re.compile('(?<![a-z])tea[ -]?spoons?(?![a-z])', re.I), TSP),
    (re.compile('(?<![a-z])tsps?(?![a-z])', re.I), TSP),
)


def canonical_units(text) -> str:
    """Rewrite any spelling of the two spoon units into the house convention.

    The model writes `amount` as free text, so it will say "tbsp", "Tbsp",
    "tablespoon" and "1 T" on different days. Left alone, the screen would show
    the two units in a dozen shapes and the distinction that stops a threefold
    error would only hold some of the time.
    """
    out = str(text or '')
    for pattern, unit in _UNIT_FORMS:
        out = pattern.sub(unit, out)
    return out


def _spoons(value: float, unit: str) -> str:
    """Render a spoon count as whole-plus-fraction.

    The nearest fraction to a remainder of, say, 0.97 is 1 — which naively
    printed "1 1 tsp". When the fraction rounds to a whole it has to be carried
    into the whole number instead.
    """
    whole = int(value)
    remainder = value - whole
    best = min(_FRACTIONS, key=lambda f: abs(f[0] - remainder) + f[2])
    if best[0] == 1.0:                      # rounded up to a whole unit
        return f'{whole + 1} {unit}'
    if remainder < 0.06:
        return f'{whole} {unit}'
    if best[1] == 'pinch of':
        return f'{whole} {unit} + a pinch' if whole else 'a pinch'
    return f'{whole} {best[1]} {unit}' if whole else f'{best[1]} {unit}'


_QUALIFIER = re.compile(r'^[\d\s./]*(?:teasp|tbsp|tsp|tablespoons?|teaspoons?)?\s*[,;-]?\s*',
                        re.I)


def _restate(tsp, previous) -> str:
    """Rewrite an amount for a new total, keeping any note about the spice.

    "1 TEAsp, cracked" summed to 2 becomes "2 TEAsp, cracked" - the crack is a
    property of the peppercorn, not of how many there are.
    """
    tail = _QUALIFIER.sub('', str(previous or ''), count=1).strip(' ,;-')
    amount = format_tsp(tsp)
    return f'{amount}, {tail}' if tail else amount


def format_tsp(tsp) -> str:
    """Turn 1.75 into "1 3/4 tsp" — spoons, not decimals, because spoons exist.

    Takes whatever the model sent: a model that writes `"tsp": "1.5"` or
    `"tsp": null` should cost a tidy label, not a 500 after the call is paid for.
    """
    try:
        tsp = float(tsp)
    except (TypeError, ValueError):
        return ''
    if tsp != tsp or tsp in (float('inf'), float('-inf')):   # NaN / infinity
        return ''
    if tsp <= 0:
        return ''
    # Below a pinch there is no honest spoon to name, and "0 tsp" reads as none.
    if tsp < 0.06:
        return 'a pinch'
    if tsp >= 3:
        # Tablespoons get their own ladder, and it is only halves.
        #
        # This used to reuse the teaspoon fractions on tsp/3, which quietly
        # reopened the hole that deleting 3/8 was meant to close: an eighth of a
        # TABLESPOON is 0.375 tsp -- the exact unmeasurable amount -- and a third
        # of one is 1 tsp dressed up as a fraction nobody owns a spoon for. So
        # 3.5 tsp printed "1 1/8 TBsp".
        #
        # A tablespoon measure comes in whole and half. Anything left over is
        # said in teaspoons, which is how a person would say it out loud.
        tbsp = int(tsp / 3)
        rest = round(tsp - tbsp * 3, 3)
        if rest > 2.87:                       # the remainder rounds up to a whole
            return f'{tbsp + 1} {TBSP}'
        if rest < 0.06:
            return f'{tbsp} {TBSP}'
        if abs(rest - 1.5) < 0.06:            # the only fraction on the measure
            return f'{tbsp} 1/2 {TBSP}'
        # Everything else is said the way a person says it: whole tablespoons,
        # then the leftover in teaspoons. Rounding the remainder to the nearest
        # half tablespoon instead would have made 5 tsp and 5 1/2 tsp both print
        # "1 1/2 TBsp" - a fifth of the spice, silently.
        return f'{tbsp} {TBSP} + {_spoons(rest, TSP)}'
    return _spoons(tsp, TSP)


def salt_spoons(grams: float, grams_per_tsp: float) -> str:
    """Grams -> spoons of the salt actually on this shelf.

    The single most valuable conversion in the app. A recipe written in teaspoons
    of Diamond Crystal and executed with Morton is 70% over-salted, and that is
    almost certainly what happened to the 2/10 steak.
    """
    if not grams:
        return ''
    return format_tsp(grams / grams_per_tsp)


def salt_display(grams: float, grams_per_tsp: float, label: str) -> str:
    """The same conversion, with the brand named — what the salt panel shows.

    The gram figure used to lead this line. It no longer appears anywhere the
    cook reads: two units side by side on one line is an invitation to measure
    the wrong one, and there is no scale on this counter to make the first
    number actionable. Grams stay where they are useful — inside `salt.grams`,
    as the brand-independent truth the app converts from.
    """
    spoons = salt_spoons(grams, grams_per_tsp)
    return f'{spoons} {label}' if spoons else ''


# Any gram figure small enough to be a seasoning rather than a piece of meat.
# 454 g of beef stays 454 g; 7.5 g of salt becomes spoons.
_SEASONING_GRAMS = 30
_GRAMS = re.compile(r'(\d+(?:\.\d+)?)\s*(?:g|gm|grams?|gr)(?![a-z])', re.I)
# A sentence ends at a full stop, not at the dot inside "7.5" -- which is
# precisely the number this function exists to catch, so the split has to see
# the difference.
_SENTENCE = re.compile(r'(?:[^.;!?]|(?<=\d)\.(?=\d))+[.;!?]*')
_SALTY = re.compile(r'\b(salt|salted|salting|season|seasoning|brine|msg|'
                    r'monosodium)\b', re.I)
_MSG_ONLY = re.compile(r'\b(msg|monosodium)\b', re.I)

_OF_NEXT = re.compile(r'\s+(salt|msg|more)\b', re.I)

# MSG is roughly the density of table salt by volume.
MSG_GRAMS_PER_TSP = 5.5


def spoonify(text, grams_per_tsp: float) -> str:
    """Rewrite gram figures the cook is meant to measure into spoons.

    The model answers in grams because grams are the only brand-independent way
    to say how much salt a dish needs. It then repeats those figures in prose --
    "sprinkle 7.5g over the beef" -- and prose is where the two units end up
    side by side, which is the confusion this app exists to remove.

    Deliberately narrow: only a seasoning-sized number, and only where salt or
    MSG is the subject — the sentence itself, or the one that set it up ("Measure
    out the salt. Sprinkle 7.5g over the beef."). A gram figure anywhere else is
    somebody's weight of meat, and converting that would be nonsense.
    """
    text = str(text or '')
    if not text or 'g' not in text.lower():
        return text
    out, carried = [], False
    for sentence in _SENTENCE.findall(text):
        salty = bool(_SALTY.search(sentence))
        if not (salty or carried):
            out.append(sentence)
            continue
        msg = _MSG_ONLY.search(sentence)
        per_tsp = MSG_GRAMS_PER_TSP if msg else grams_per_tsp
        carried = salty

        def convert(match, sentence=sentence, per_tsp=per_tsp):
            grams = float(match.group(1))
            if not 0 < grams <= _SEASONING_GRAMS:
                return match.group(0)
            spoons = salt_spoons(grams, per_tsp)
            if not spoons:
                return match.group(0)
            # "add 0.5g salt" becomes "add a pinch salt" without this. The gram
            # figure was a quantity; the smallest spoon is a phrase, and it needs
            # the preposition the number did not.
            if spoons == 'a pinch' and _OF_NEXT.match(sentence[match.end():]):
                return 'a pinch of'
            return spoons

        out.append(_GRAMS.sub(convert, sentence))
    return ''.join(out)
