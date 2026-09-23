"""Recipe generation, decoration, and the re-shelving proposal.

Two jobs live here. The first is the request pipeline: build the prompt, call
OpenRouter, resolve every named spice onto a real jar, store it. The second is
the thing that makes the rack physical — watching which jars actually get used
and proposing a better arrangement once the evidence is in.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import db, openrouter, prompt, rack, schema, vault

# A real generated recipe, frozen at build time. Ships inside the package rather
# than living in `data/` so a fresh checkout has one without an API key.
DEMO_PATH = Path(__file__).resolve().parent / 'demo.json'
_DEMO_CACHE: dict = {}


def demo_recipe():
    """The frozen example, put through the same pipeline as a live response.

    It must go through `normalise()` and not just `decorate()`: normalise is what
    attaches `spice_key`, `name` and `color` to every blend row, and those are
    what let the rack light up. A decorated-but-unnormalised payload renders as a
    list of nameless rows over a rack with nothing highlighted — which is exactly
    the thing this page exists to show off.

    Re-run per request rather than cached in its finished form, so the salt line
    always quotes whichever salt is currently configured.
    """
    if 'raw' not in _DEMO_CACHE:
        try:
            _DEMO_CACHE['raw'] = json.loads(DEMO_PATH.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            _DEMO_CACHE['raw'] = None
    raw = _DEMO_CACHE['raw']
    if raw is None:
        return None
    fresh = json.loads(json.dumps(raw))
    return decorate(schema.normalise(fresh, out_of_stock=db.out_of_stock()))


def decorate(payload: dict) -> dict:
    """Add the derived fields the frontend shows but the model never writes.

    Salt in particular: the model answers in grams, and this is the last moment
    before the screen — where grams become spoons of the salt that is actually
    on the shelf, and where any gram figure the model repeated in its prose is
    converted with them. Grams are a storage unit here, not a reading unit: the
    card never shows the cook two units for one thing.

    Idempotent, and run on the way out rather than at generation, so a recipe
    saved under one salt brand reads correctly after the box changes.
    """
    label, grams_per_tsp = db.salt_brand()
    salt = payload.get('salt') or {}
    grams = salt.get('grams') or 0
    salt['display'] = schema.salt_display(grams, grams_per_tsp, label)
    # The rack draws this under the salt jar, where the jar is already labelled
    # with the brand — so it gets the spoons alone.
    salt['spoons'] = schema.salt_spoons(grams, grams_per_tsp)
    salt['brand'] = label
    if salt.get('msg_grams'):
        salt['msg_display'] = schema.salt_display(
            salt['msg_grams'], schema.MSG_GRAMS_PER_TSP, 'MSG')
        salt['msg_spoons'] = schema.salt_spoons(
            salt['msg_grams'], schema.MSG_GRAMS_PER_TSP)
    for field in ('when', 'rationale'):
        salt[field] = schema.spoonify(salt.get(field), grams_per_tsp)
    payload['salt'] = salt

    for step in payload.get('steps') or []:
        if not isinstance(step, dict):
            continue
        for field in ('body', 'watch_for'):
            step[field] = schema.spoonify(step.get(field), grams_per_tsp)
    payload['salt_check'] = schema.spoonify(payload.get('salt_check'), grams_per_tsp)

    # The salt panel already carries the only number that matters, converted for
    # this cupboard. A shopping-list line repeating it in grams is the same
    # seasoning twice, in two units.
    payload['from_kitchen'] = [
        item for item in (payload.get('from_kitchen') or [])
        if not (isinstance(item, dict) and schema.is_salt_row(item.get('item')))]
    return payload


def generate(query: str, portion_lb: float = 1.0, servings: int = 2,
             extra: str = '', model: str = None) -> dict:
    """One ask, end to end. Returns the saved recipe row, ready to render."""
    model = model or db.setting('model')
    system_prompt = prompt.build_system_prompt()
    user_message = prompt.build_user_message(query, portion_lb, servings, extra)

    payload, meta = openrouter.generate(system_prompt, user_message, model,
                                        on_attempt=db.record_api_call)
    payload = schema.normalise(payload, out_of_stock=db.out_of_stock())
    payload = decorate(payload)

    meta['query'] = query
    recipe_id = db.save_recipe(payload, meta)
    vault.add_recipe(recipe_id, payload.get('title', 'Untitled'))
    return db.recipe(recipe_id)


def rate(recipe_id: int, overall, salt_delta: int = 0, heat_delta: int = 0,
         would_repeat=None, notes: str = '') -> None:
    """Record a rating and sweep its reminder, in that order.

    Both the CLI and the API route through here rather than calling db.rate
    directly, so the reminder cannot be ticked in one place and left standing in
    the other. `spice log` deliberately does NOT: a dish cooked before this app
    existed never opened a reminder, so there is nothing to close.
    """
    db.rate(recipe_id, overall, salt_delta, heat_delta, would_repeat, notes)
    vault.mark_rated(recipe_id)


# ── the rack, as furniture ───────────────────────────────────────────────────

def rack_view(include_private: bool = True) -> dict:
    """Everything the visual needs in one payload: jars, positions, state, usage.

    `include_private=False` is what an anonymous visitor gets. The rack is the
    showpiece and is meant to be seen, but which jars are running low and how
    often each one gets reached for is a picture of somebody's kitchen habits —
    it is not interesting to a stranger and it is not theirs to read. The drawing
    is identical either way.
    """
    layout = db.layout()
    states = db.spice_states() if include_private else {}
    counts = db.usage_counts() if include_private else {}

    # The salt jar is labelled from settings rather than from the registry. The
    # rack used to say "Kosher Salt" while every recipe said fine table salt --
    # and a mismatch about WHICH salt is the exact error behind the one 2/10
    # dish on record, so the two now read from one place.
    salt_label = db.salt_brand()[0]
    salt_label = salt_label[0].upper() + salt_label[1:]

    jars = []
    for key, spice in rack.ALL_BY_KEY.items():
        place = layout.get(key)
        if not place:
            continue
        state = states.get(key, {})
        jars.append({
            'spice_key': key,
            'name': salt_label if key == 'salt' else spice.name,
            'form': spice.form,
            'stage': spice.stage,
            'burns': spice.burns,
            'heat': spice.heat,
            'color': spice.color,
            'note': spice.note,
            'rack': place['rack'],
            'row': place['row'],
            'col': place['col'],
            'stock': state.get('stock', 'ok'),
            'opened_on': state.get('opened_on'),
            'uses': counts.get(key, 0),
        })
    jars.sort(key=lambda j: (j['rack'], j['row'], j['col']))
    return {
        'jars': jars,
        'racks': list(rack.RACKS),
        'rack_labels': rack.RACK_LABELS,
        'row_labels': list(rack.ROW_LABELS),
        # Which shelves those row labels describe. Sent rather than
        # assumed, so no screen has to hardcode a shelf name to work out
        # whether 'Daily' means anything on it.
        'wall_racks': list(rack.wall_racks()),
        'stages': list(rack.STAGES),
    }


def reshelve_proposal(mode: str = 'balanced') -> dict:
    """Propose a frequency-sorted rack, and show exactly what would move.

    Two modes, because "most used on top" has two honest readings:

    * `balanced` (default) keeps each jar on the rack it already lives on and
      only re-sorts rows within that rack. That preserves the left-is-savoury /
      right-is-heat split, which is what makes a two-handed grab work.
    * `strict` ranks all 56 jars globally and fills left row 1, then right row 1,
      then left row 2, and so on — the literal reading, at the cost of the split.

    Ties break on the current position, so an unused jar never shuffles for no
    reason and the proposal stays readable as a small diff instead of a reshuffle
    of everything.
    """
    layout = db.layout()
    counts = db.usage_counts()
    # Selected by where a jar SITS, not by which tuple it is declared in. Zanzibar
    # pepper is a rack spice by nature but lives above the stove because its jar
    # is too tall for a slot; sorting by declaration would keep dragging it back
    # onto a wall it does not fit.
    wall = rack.wall_racks()
    rack_keys = [k for k, place in layout.items() if place['rack'] in wall]

    def rank(key):
        place = layout[key]
        return (-counts.get(key, 0), place['row'], place['col'])

    placements = []
    if mode == 'strict':
        ordered = sorted(rack_keys, key=rank)
        for index, key in enumerate(ordered):
            row, within = divmod(index, 14)
            side, col = ('left', within) if within < 7 else ('right', within - 7)
            placements.append({'spice_key': key, 'rack': side, 'row': row, 'col': col})
    else:
        for side in ('left', 'right'):
            ordered = sorted([k for k in rack_keys if layout[k]['rack'] == side], key=rank)
            for index, key in enumerate(ordered):
                placements.append({'spice_key': key, 'rack': side,
                                   'row': index // 7, 'col': index % 7})

    # Everything off the wall keeps its place. The stove shelf is not ranked (four
    # things you reach for constantly do not need sorting, and moving the salt
    # would be actively annoying), and the pantry and freezer are not shelves with
    # slots at all. Checked as "not a wall rack" rather than "is the stove", so
    # adding a location cannot silently drop its contents from the layout.
    for key, place in layout.items():
        if place['rack'] not in wall:
            placements.append({'spice_key': key, **place})

    moves = []
    for placement in placements:
        current = layout[placement['spice_key']]
        if (current['rack'], current['row'], current['col']) != (
                placement['rack'], placement['row'], placement['col']):
            spice = rack.ALL_BY_KEY[placement['spice_key']]
            moves.append({
                'spice_key': placement['spice_key'],
                'name': spice.name,
                'uses': counts.get(placement['spice_key'], 0),
                'from': current,
                'to': {'rack': placement['rack'], 'row': placement['row'],
                       'col': placement['col']},
            })

    return {
        'mode': mode,
        'placements': placements,
        'moves': moves,
        'total_recipes': len(db.history(limit=1000)),
        'unused': sorted(
            (rack.SPICE_BY_KEY[k].name for k in rack_keys if not counts.get(k)),
            key=str.lower),
    }
