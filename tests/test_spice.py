"""Tests for the parts that break silently.

The bugs this app can actually afford are cosmetic. The ones it cannot are: a jar
missing from the layout (the visual points at an empty slot), a spice name the
validator cannot resolve (the visual points at nothing), and a salt conversion
that is off by a brand (the food is inedible). Those get pinned here.
"""

from __future__ import annotations

import re

import pytest

from spice import db, prompt, rack, recipes, schema


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """A fresh database per test, so ordering never matters."""
    monkeypatch.setattr(db.config, 'DB_PATH', tmp_path / 'test.db')
    monkeypatch.setattr(db.config, 'DATA_DIR', tmp_path)
    # Third guard on the vault. vault._enabled() already refuses to run under
    # pytest, but the suite drives generation to a 200 at eleven call sites
    # against fresh databases where ids restart at 1 -- so if that guard is ever
    # weakened, this keeps a dozen fake dinners out of the real Obsidian vault.
    monkeypatch.setattr(db.config, 'TODO_FILE', tmp_path / 'Recipes.md')
    if hasattr(db._local, 'conn'):
        del db._local.conn
    db.ensure_schema()
    yield
    if hasattr(db._local, 'conn'):
        db._local.conn.close()
        del db._local.conn


# ── the rack ─────────────────────────────────────────────────────────────────

def test_every_spice_has_exactly_one_slot():
    rack.validate_default_layout()


def test_wall_racks_are_four_rows_of_at_most_seven():
    # Any gap belongs at the BOTTOM, among the rarely-used jars -- never in the
    # row you reach into without looking.
    for side in rack.wall_racks():
        rows = rack.DEFAULT_LAYOUT[side]
        assert len(rows) == 4
        assert all(0 < len(row) <= 7 for row in rows)
        assert len(rows[-1]) <= len(rows[0]), 'the gap should sit in the bottom row'


def test_the_wall_racks_never_overflow():
    # 28 slots a side, hard. They were exactly full until Black Fungus left for
    # the pantry; a free slot is fine, an overfull rack is a layout that cannot
    # physically exist.
    for side in rack.wall_racks():
        assert sum(len(r) for r in rack.DEFAULT_LAYOUT[side]) <= 28


def test_free_slots_are_reported_honestly():
    # Not asserting an exact number -- that changes every time a jar moves. What
    # matters is that free space is real space: capacity minus what is placed,
    # counted the same way the sorting guide counts it.
    free = {side: 28 - sum(len(r) for r in rack.DEFAULT_LAYOUT[side])
            for side in rack.wall_racks()}
    assert all(0 <= n <= 28 for n in free.values())
    # And any gap sits at the bottom, never in the row you reach into blind.
    for side, n in free.items():
        if n:
            rows = rack.DEFAULT_LAYOUT[side]
            assert len(rows[-1]) < 7, f'{side} has a gap but its bottom row is full'


def test_the_two_oreganos_are_neighbours():
    # The opposite rule: these are confusable but interchangeable-looking, and
    # keeping them adjacent makes picking the wrong plant a deliberate act.
    layout = db.layout()
    a, b = layout['mexican_oregano'], layout['oregano_leaves']
    assert a['rack'] == b['rack'] and a['row'] == b['row']
    assert abs(a['col'] - b['col']) == 1


def test_the_used_up_jars_are_reachable_again():
    # Retired from the rack but not from the kitchen -- a recipe has to be able
    # to name them, or they can never be spent.
    assert rack.resolve('onion salt').key == 'onion_salt'
    assert rack.resolve('chili powder').key == 'chili_powder'
    assert rack.resolve('parsley').key == 'parsley'


@pytest.mark.parametrize('written, expected', [
    ('oregano', 'oregano_leaves'),          # the unqualified name is the Med one
    ('dried oregano', 'oregano_leaves'),
    ('mexican oregano', 'mexican_oregano'),
    ('onion powder', 'onion_powder'),
    ('ancho chili powder', 'ancho_chili'),
    ('kashmiri chili powder', 'kashmiri_chili'),
    ('sumac', 'sumac'),
    ('sage', 'sage'),
    ('rubbed sage', 'sage'),
    ('mustard powder', 'ground_mustard'),
    ('dry mustard', 'ground_mustard'),
    ('porcini powder', 'mushroom_powder'),
    ('mushroom powder', 'mushroom_powder'),
    ('celery seed', 'celery_seed'),
    ('celery seeds', 'celery_seed'),
])
def test_the_new_jars_resolve_without_stealing_from_the_old(written, expected):
    assert rack.resolve(written).key == expected


@pytest.mark.parametrize('written', ['red pepper powder', 'red chili powder',
                                     'ground red pepper', 'chili', 'chilli'])
def test_genuinely_ambiguous_chile_names_never_auto_resolve(written):
    # These name different chiles to different cooks. 'red chili powder' is
    # Cayenne (heat 8) in one kitchen and Kashmiri (heat 2) in another -- a
    # four-fold error -- and plain containment would hand it to the American
    # "Chili Powder" BLEND, quietly adding cumin and oregano to an Indian dish.
    # They must surface as unresolved so the recipe names a chile.
    assert rack.resolve(written) is None


def test_ground_mustard_does_not_collide_with_the_mustard_seeds():
    # Whole black mustard seeds pop in hot fat; ground mustard is a cold-slurry
    # pungency that heat destroys. Same plant, opposite handling.
    assert rack.resolve('mustard powder').key == 'ground_mustard'
    assert rack.resolve('black mustard seeds').key == 'black_mustard_seeds'
    assert rack.resolve('mustard seeds').key == 'black_mustard_seeds'


def test_the_shopping_list_is_reserved_but_unusable():
    for key in ('kasuri_methi', 'mushroom_powder'):
        db.set_spice_state(key, 'out')
        assert key in db.layout(), f'{key} has no slot waiting for it'
    assert {'kasuri_methi', 'mushroom_powder'} <= db.out_of_stock()


def test_every_jar_we_own_is_placed_exactly_once():
    placed = [k for shelf in rack.RACKS
              for row in rack.DEFAULT_LAYOUT[shelf] for k in row]
    assert len(placed) == len(set(placed))
    assert set(placed) == set(rack.ALL_BY_KEY)


def test_a_jar_may_live_off_the_rack_it_is_declared_in():
    # Position is data; the tuple a spice is declared in is only source
    # organisation. Zanzibar pepper is declared among the rack spices and lives
    # above the stove, and that has to be legal rather than a validation error.
    assert 'zanzibar_black_pepper' in rack.SPICE_BY_KEY
    assert db.layout()['zanzibar_black_pepper']['rack'] == 'stove'
    assert db.layout()['umami_steak_seasoning']['rack'] == 'stove'


def test_reshelving_never_drags_a_stove_jar_onto_a_wall():
    # Selected by where it sits, not by what it is. The big jars physically do
    # not fit a rack slot, so no amount of usage should promote them.
    for mode in ('balanced', 'strict'):
        placed = {p['spice_key']: p
                  for p in recipes.reshelve_proposal(mode)['placements']}
        assert placed['zanzibar_black_pepper']['rack'] == 'stove'
        assert placed['umami_steak_seasoning']['rack'] == 'stove'


def test_layout_seeds_every_jar():
    layout = db.layout()
    for key in rack.SPICE_BY_KEY:
        assert key in layout, f'{key} never got a shelf position'


def test_no_two_jars_share_a_slot():
    slots = [(p['rack'], p['row'], p['col']) for p in db.layout().values()]
    assert len(slots) == len(set(slots))


# ── name resolution ──────────────────────────────────────────────────────────

@pytest.mark.parametrize('written, expected', [
    ('Cumin', 'cumin'),
    ('ground cumin', 'cumin'),
    ('JEERA', 'cumin'),
    ('Kashmiri chilli', 'kashmiri_chili'),
    ('kashmiri mirch', 'kashmiri_chili'),
    ('red pepper flakes', 'crushed_chili'),
    ('Korean chili flakes', 'gochugaru'),
    ('Silk Chili (Aleppo)', 'silk_chili'),
    ('aleppo pepper', 'silk_chili'),
    ('urfa biber', 'black_urfa_chili'),
    ('asafoetida', 'wild_hing'),
    ('dried fenugreek leaves', 'kasuri_methi'),
    ('wood ear mushroom', 'black_fungus'),
    ('five spice', 'five_spice'),
    ("za'atar", 'zaatar'),
    ('zaatar', 'zaatar'),
    ('monosodium glutamate', 'msg'),
])
def test_resolve_aliases(written, expected):
    spice = rack.resolve(written)
    assert spice is not None, f'{written!r} did not resolve'
    assert spice.key == expected


def test_resolve_rejects_things_we_do_not_own():
    assert rack.resolve('truffle salt') is None
    assert rack.resolve('') is None


@pytest.mark.parametrize('written', [
    # 'onion salt' used to belong here. We own it now, so it resolves -- which is
    # exactly the point of the list: it names things NOT in the kitchen.
    'truffle salt', 'garlic salt', 'celery salt', 'chili oil',
    'jerk chicken', 'fresh ginger root', 'lemon zest',
])
def test_a_longer_phrase_never_collapses_onto_a_shorter_jar(written):
    # The containment fallback used to resolve anything ending in "salt" to the
    # kosher salt on the stove shelf — which both lit the wrong jar and silently
    # dropped a real shopping-list item. These must stay unresolved so they land
    # in `from_kitchen` with a warning.
    assert rack.resolve(written) is None


def test_containment_still_catches_a_reasonable_rephrasing():
    assert rack.resolve('kashmiri chili powder').key == 'kashmiri_chili'
    assert rack.resolve('sichuan peppercorns').key == 'sichuan_peppercorn'


def test_garam_masala_and_garlic_powder_do_not_collide():
    # Both abbreviate to "GA" and both start with "gar" — the substring fallback
    # must not confuse them.
    assert rack.resolve('garam masala').key == 'garam_masala'
    assert rack.resolve('garlic powder').key == 'garlic_powder'


# ── measurements ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize('tsp, expected', [
    (1, '1 TEAsp'),
    (0.5, '1/2 TEAsp'),
    (1.5, '1 1/2 TEAsp'),
    (2.25, '2 1/4 TEAsp'),
    (3, '1 TBsp'),
    (4.5, '1 1/2 TBsp'),
    (0.0625, 'a pinch'),
    # Quarters beat thirds unless a third is genuinely closer. 0.30 is nearer to
    # 1/3 in raw distance, and still renders as 1/4: the quarter is the spoon
    # that comes to hand, and no dish has ever turned on 0.03 of a teaspoon.
    (0.30, '1/4 TEAsp'),
    (0.3333, '1/3 TEAsp'),
    (0.70, '3/4 TEAsp'),
    (0.6667, '2/3 TEAsp'),
])
def test_format_tsp(tsp, expected):
    assert schema.format_tsp(tsp) == expected


_FRACTION_VALUES = {'1/8': 0.125, '1/4': 0.25, '1/3': 1 / 3, '1/2': 0.5,
                    '2/3': 2 / 3, '3/4': 0.75}


def _read_back(text: str) -> float:
    """Read a rendered amount the way the cook does, and total it in teaspoons."""
    total = 0.0
    for part in text.split('+'):
        part = part.strip()
        multiplier = 3 if schema.TBSP in part else 1
        value = 0.0
        for token in part.replace(schema.TBSP, '').replace(schema.TSP, '').split():
            value += _FRACTION_VALUES.get(token, 0) or float(token)
        total += value * multiplier
    return total


@pytest.mark.parametrize('tsp', [x / 8 for x in range(1, 97)])
def test_every_printed_amount_is_measurable_and_means_what_it_says(tsp):
    """Two things at once, because the first test of this only checked one.

    The original swept the range collecting fraction TOKENS and compared them to
    an allowed set. `1/8` is in that set, so `format_tsp(3.5)` returning
    "1 1/8 TBsp" sailed through -- and an eighth of a TABLESPOON is 0.375 tsp,
    the exact unmeasurable amount that deleting 3/8 was supposed to abolish. A
    token is only measurable with respect to its unit.

    So this also reads the rendered string back and checks it still means the
    number that went in. A label nobody can measure and a label that lies are the
    same failure from the cook's side of the counter.
    """
    text = schema.format_tsp(tsp)
    for token in text.split():
        if '/' in token:
            assert token in _FRACTION_VALUES, f'{text!r}: no spoon measures {token}'
    assert abs(_read_back(text) - tsp) <= 0.13, f'{text!r} does not read back as {tsp}'


def test_a_jar_listed_twice_states_its_combined_total():
    # The model's commonest formatting habit is listing one jar at two moments.
    # _dedupe_blend summed `tsp` and left `amount` alone, and `amount` is what
    # the card prints -- so the cook measured half of what the recipe meant.
    merged = schema._dedupe_blend([
        {'spice_key': 'cumin', 'name': 'Cumin', 'amount': '1 TEAsp, cracked',
         'tsp': 1, 'stage': 'bloom'},
        {'spice_key': 'cumin', 'name': 'Cumin', 'amount': '1 TEAsp',
         'tsp': 1, 'stage': 'mid'},
    ])
    assert len(merged) == 1
    assert merged[0]['tsp'] == 2
    assert merged[0]['amount'] == '2 TEAsp, cracked'   # qualifier survives


def test_a_finishing_spice_scheduled_into_the_heat_is_flagged():
    # `burns` cannot catch these. Urfa, kasuri methi and garam masala do not
    # scorch -- heat just erases them -- so they carry a finishing stage instead
    # of a burns flag, and nothing was checking the model respected it. Since
    # group_blend() turns a stage into a physical premix bowl, an ignored
    # finishing stage is now a jar tipped into the wrong dish before the stove
    # is even on.
    payload = schema.normalise({
        'salt': {'grams': 7.5, 'msg_grams': 0},
        'blend': [{'spice': 'Black Urfa Chili', 'amount': '1 TEAsp', 'tsp': 1,
                   'stage': 'bloom', 'why': 'x'}],
        'steps': [],
    })
    assert any('Urfa' in w and 'finishing' in w for w in payload['warnings'])


def test_a_finishing_spice_at_its_own_default_says_nothing():
    payload = schema.normalise({
        'salt': {'grams': 7.5, 'msg_grams': 0},
        'blend': [{'spice': 'Black Urfa Chili', 'amount': '1 TEAsp', 'tsp': 1,
                   'stage': 'garnish', 'why': 'x'}],
        'steps': [],
    })
    # Not "no warnings at all" -- a deliberately minimal payload also earns a
    # missing-fields warning. The point is that the jar at its own default
    # earns nothing, the same exemption the burns guard already makes for hing.
    assert not any('finishing' in w for w in payload['warnings'])


def test_zero_grams_of_salt_is_a_failed_recipe_not_a_valid_one():
    # It rendered as an empty string into the largest element on the card. The
    # old guard tested `in (None, '')`, which zero walks straight past.
    errors = schema.shape_errors({
        'dish': 'D', 'cuisine': 'C', 'why': 'w', 'confidence': 'proven',
        'portion_lb': 1, 'salt': {'grams': 0, 'msg_grams': 0, 'rationale': 'r'},
        'blend': [{'spice': 'Cumin', 'amount': '1 TEAsp', 'tsp': 1,
                   'stage': 'bloom', 'why': 'w'}],
        'from_kitchen': [], 'steps': [{'title': 't', 'body': 'b', 'heat': 'none'}],
    })
    assert any('salt.grams' in e for e in errors)


@pytest.mark.parametrize('written, expected', [
    ('2 tbsp', '2 TBsp'),
    ('1 Tablespoon', '1 TBsp'),
    ('3 tablespoons', '3 TBsp'),
    ('1 tbs oil', '1 TBsp oil'),
    ('1 TBSP', '1 TBsp'),
    ('1/2 teaspoon', '1/2 TEAsp'),
    ('2 tsp, crushed', '2 TEAsp, crushed'),
    ('2 Tsp', '2 TEAsp'),
    ('a pinch', 'a pinch'),
])
def test_every_spelling_lands_on_the_house_units(written, expected):
    # The model writes `amount` as free text and will say tbsp, Tbsp and
    # tablespoon on different days. Left alone the screen shows the two units in
    # a dozen shapes, and the distinction that stops a threefold error only holds
    # some of the time.
    assert schema.canonical_units(written) == expected


@pytest.mark.parametrize('written', ['tbspoonful-ish', 'contsp', 'a tspish amount'])
def test_unit_rewriting_does_not_maul_ordinary_words(written):
    assert schema.canonical_units(written) == written


def test_the_two_units_do_not_look_alike():
    # The whole point. 'tsp' and 'tbsp' differ by one character; mistaking them
    # is a THREEFOLD error, the largest available in a kitchen that measures salt
    # to the gram. The distinguishing syllable is capitalised in each so they
    # differ in shape, not in one easily-missed letter.
    assert schema.TSP == 'TEAsp' and schema.TBSP == 'TBsp'
    assert schema.TSP.lower() != schema.TBSP.lower()
    assert not schema.TBSP.lower().startswith(schema.TSP.lower()[:2])


def test_salt_display_converts_by_brand():
    # The whole reason salt is stored in grams: 8g is nearly 3 tsp of Diamond
    # Crystal but only about 1 2/3 tsp of Morton. Following a Diamond Crystal
    # recipe with Morton in the box is a 70% overdose.
    diamond = schema.salt_display(8, 2.8, 'Diamond Crystal kosher')
    morton = schema.salt_display(8, 4.8, 'Morton kosher')
    assert diamond != morton
    assert schema.TSP in diamond
    # And the gram figure it was converted FROM never reaches the card. Two
    # units for one thing, on one line, is a choice offered to a cook holding a
    # hot pan; the app makes that choice for him instead.
    assert '8 g' not in diamond and '8g' not in morton


def test_spoonify_converts_the_grams_the_model_repeats_in_prose():
    # The model is told to answer in grams and then talk in spoons. It does the
    # first reliably and the second only mostly, and a step body that says
    # "sprinkle 7.5g" beside a panel that says "1 1/4 TEAsp" is the two-unit
    # confusion arriving through the back door.
    assert schema.spoonify('Sprinkle 7.5g of salt over the beef.', 6.0) == \
        'Sprinkle 1 1/4 TEAsp of salt over the beef.'
    # The setup sentence carries the subject into the next one.
    assert 'g ' not in schema.spoonify(
        'Measure out the salt. Sprinkle 7.5g evenly over the beef.', 6.0)
    # MSG is a different density, and is converted as itself.
    assert schema.spoonify('MSG is 1.5g.', 6.0) == 'MSG is 1/4 TEAsp.'
    # The smallest spoon is a phrase, not a number, and needs the preposition.
    assert schema.spoonify('Add 0.5g salt at a time.', 6.0) == \
        'Add a pinch of salt at a time.'


def test_spoonify_leaves_alone_the_grams_that_are_not_salt():
    # A weight of meat is not a quantity of seasoning, and converting it would
    # print a recipe calling for three cups of salt. Two guards: the sentence has
    # to be about salt, and the figure has to be seasoning-sized.
    assert schema.spoonify('Add 250g of tomatoes and season.', 6.0) == \
        'Add 250g of tomatoes and season.'
    assert schema.spoonify('Sear the beef for 6 minutes. Add 15g butter.', 6.0) == \
        'Sear the beef for 6 minutes. Add 15g butter.'
    assert '454g' in schema.spoonify('Beef: 454g at 1.65% needs 7.5g salt.', 6.0)


def test_salt_is_not_listed_twice_in_two_units():
    # The salt panel carries the converted number. A shopping-list line for the
    # same salt can only be in grams, so the card would show one seasoning in
    # both units -- exactly what the gram pipeline exists to prevent.
    payload = schema.normalise({
        'from_kitchen': [{'item': 'fine table salt', 'amount': '9.5g total'},
                         {'item': 'MSG', 'amount': '1.5g'},
                         {'item': 'onion salt', 'amount': '1 tsp'},
                         {'item': 'unsalted butter', 'amount': '1 tbsp'}],
    })
    items = [k['item'] for k in payload['from_kitchen']]
    assert items == ['onion salt', 'unsalted butter']


def test_scale_moves_spices_and_salt_together():
    payload = {
        'portion_lb': 1,
        'blend': [{'spice_key': 'cumin', 'tsp': 1, 'amount': '1 tsp'}],
        'salt': {'grams': 5.6, 'msg_grams': 1},
    }
    schema.scale(payload, 2)
    assert payload['blend'][0]['tsp'] == 2
    assert payload['salt']['grams'] == 11.2
    assert payload['portion_lb'] == 2


# ── validating what the model returns ────────────────────────────────────────

def _payload(**overrides):
    base = {
        'title': 'Test dish', 'cuisine': 'Korean', 'protein': 'chicken thighs',
        'portion_lb': 1, 'confidence': 'well_trodden', 'why_this': 'because',
        'heat_level': 4, 'pan': 'cast iron',
        'times': {'prep_min': 10, 'marinate_min': 0, 'cook_min': 15, 'total_min': 25},
        'blend': [], 'salt': {'grams': 6, 'msg_grams': 0, 'when': 'ahead',
                              'rationale': '1 lb x 5.6g'},
        'from_kitchen': [], 'steps': [], 'salt_check': 'taste it',
        'serve_with': 'rice', 'leftovers': 'fridge',
    }
    base.update(overrides)
    return base


def test_unknown_spice_moves_to_the_shopping_list():
    payload = _payload(blend=[
        {'spice': 'Cumin', 'amount': '1 tsp', 'tsp': 1, 'stage': 'bloom',
         'step': 1, 'why': 'base'},
        {'spice': 'Truffle Salt', 'amount': '1 tsp', 'tsp': 1, 'stage': 'mid',
         'step': 1, 'why': 'nope'},
    ])
    out = schema.normalise(payload)
    assert [i['spice_key'] for i in out['blend']] == ['cumin']
    assert any('Truffle Salt' in w for w in out['warnings'])
    assert out['from_kitchen'][0]['item'] == 'Truffle Salt'


def test_burnable_spice_in_the_sear_raises_a_warning():
    payload = _payload(blend=[
        {'spice': 'Garlic Powder', 'amount': '1 tsp', 'tsp': 1, 'stage': 'dry_rub',
         'step': 1, 'why': 'garlic'},
    ])
    out = schema.normalise(payload)
    assert any('scorches' in w for w in out['warnings'])


def test_out_of_stock_spice_is_flagged():
    payload = _payload(blend=[
        {'spice': 'Gochugaru', 'amount': '1 tbsp', 'tsp': 3, 'stage': 'mid',
         'step': 1, 'why': 'heat'},
    ])
    out = schema.normalise(payload, out_of_stock={'gochugaru'})
    assert out['blend'][0]['out_of_stock'] is True
    assert any('out of stock' in w for w in out['warnings'])


def test_repeated_spice_is_folded_into_one_jar():
    # The rack can only light a jar once, so two mentions have to become one row
    # or the badge numbers stop matching the list.
    payload = _payload(blend=[
        {'spice': 'Cumin', 'amount': '1 tsp', 'tsp': 1, 'stage': 'bloom',
         'step': 1, 'why': 'base'},
        {'spice': 'ground cumin', 'amount': '1/2 tsp', 'tsp': 0.5, 'stage': 'last_five',
         'step': 3, 'why': 'lift'},
    ])
    out = schema.normalise(payload)
    assert len(out['blend']) == 1
    assert out['blend'][0]['tsp'] == 1.5
    assert 'last_five' in out['blend'][0]['stages']


def test_spices_attach_to_their_step():
    payload = _payload(
        blend=[{'spice': 'Cumin', 'amount': '1 tsp', 'tsp': 1, 'stage': 'bloom',
                'step': 2, 'why': 'base'}],
        steps=[{'n': 1, 'title': 'Salt', 'body': '...', 'minutes': 0,
                'heat': 'none', 'watch_for': ''},
               {'n': 2, 'title': 'Bloom', 'body': '...', 'minutes': 1,
                'heat': 'medium_low', 'watch_for': 'fragrant'}])
    out = schema.normalise(payload)
    assert out['steps'][0]['spices'] == []
    assert out['steps'][1]['spices'][0]['name'] == 'Cumin'


def test_normalise_survives_junk():
    out = schema.normalise({'blend': [{'spice': None}], 'steps': None})
    assert out['blend'] == []
    assert out['steps'] == []


# ── the feedback loop ────────────────────────────────────────────────────────

def test_ratings_drive_the_salt_correction():
    payload = schema.normalise(_payload())
    for _ in range(3):
        recipe_id = db.save_recipe(payload, {'query': 'x', 'model': 'test'})
        db.rate(recipe_id, 6, salt_delta=2)
    assert db.salt_bias() == pytest.approx(2.0)

    from spice import prompt
    text = prompt.calibration_block(db.salt_bias(), db.heat_bias())
    assert 'too salty' in text
    assert 'Cut your salt target' in text


def test_cuisine_recency_replaces_the_hand_edited_tracker():
    payload = schema.normalise(_payload(cuisine='Korean'))
    recipe_id = db.save_recipe(payload, {'query': 'x', 'model': 'test'})

    # Generating is not cooking. Four recipes generated in one testing session
    # had the prompt reporting four cuisines as cooked that day and steering
    # away from all of them.
    assert db.cuisine_recency() == []

    db.rate(recipe_id, 8)
    names = [name for name, _, _, _ in db.cuisine_recency()]
    assert names == ['Korean']


def test_a_logged_dish_counts_as_cooked_even_without_a_score():
    # The other evidence a dish reached a plate. `spice log` exists only to
    # record something he cooked, so the act of logging IS the claim -- and
    # requiring a rating as well lost the Korean beef he remembered eating but
    # never scored, leaving Korean reading as a lane never touched.
    db.log_historical('Gochugaru Beef', 'Korean', 'ground beef', when='2026-07-29')
    assert 'Korean' in [name for name, _, _, _ in db.cuisine_recency()]

    from spice import prompt
    assert 'Korean' in prompt.rotation_block(db.cuisine_recency())


@pytest.mark.parametrize('written, lane', [
    ('Korean-inspired', 'Korean'),      # the one that actually happened
    ('korean style', 'Korean'),
    ('Tex Mex', 'Tex-Mex'),
    ('Punjabi', 'Indian'),
    ('Sichuan', 'Chinese'),
    ('Jamaican', 'Caribbean'),
    ('Levantine', 'Middle Eastern'),
    ('Cajun/Southern', 'Cajun'),
    ('West African', 'West African'),
    ('Georgian', 'Georgian'),           # unknown lanes keep their own name
])
def test_a_cuisine_folds_onto_its_lane(written, lane):
    # The rotation buckets on the stored string. "Korean-inspired" read as a
    # lane never cooked while Korean sat beside it going cold, so the model was
    # invited to repeat the dish it had just made.
    assert db.canonicalise_cuisine(written) == lane


def test_the_lane_is_folded_on_write_not_on_read():
    payload = schema.normalise(_payload(cuisine='Korean-inspired'))
    recipe_id = db.save_recipe(payload, {'query': 'x', 'model': 'test'})
    assert db.recipe(recipe_id)['cuisine'] == 'Korean'


def test_usage_counts_track_jars_not_recipes():
    payload = schema.normalise(_payload(blend=[
        {'spice': 'Cumin', 'amount': '1 tsp', 'tsp': 1, 'stage': 'bloom',
         'step': 1, 'why': ''},
        {'spice': 'Gochugaru', 'amount': '1 tsp', 'tsp': 1, 'stage': 'mid',
         'step': 1, 'why': ''},
    ]))
    db.save_recipe(payload, {'query': 'x', 'model': 'test'})
    counts = db.usage_counts()
    assert counts['cumin'] == 1 and counts['gochugaru'] == 1


# ── re-shelving ──────────────────────────────────────────────────────────────

def test_proposal_keeps_every_jar_and_never_double_books():
    payload = schema.normalise(_payload(blend=[
        {'spice': 'Kasuri Methi', 'amount': '1 tsp', 'tsp': 1, 'stage': 'off_heat',
         'step': 1, 'why': ''},
    ]))
    for _ in range(5):
        db.save_recipe(payload, {'query': 'x', 'model': 'test'})

    for mode in ('balanced', 'strict'):
        proposal = recipes.reshelve_proposal(mode)
        keys = [p['spice_key'] for p in proposal['placements']]
        assert len(keys) == len(set(keys))
        assert set(rack.SPICE_BY_KEY) <= set(keys)
        slots = [(p['rack'], p['row'], p['col']) for p in proposal['placements']]
        assert len(slots) == len(set(slots))


def test_balanced_mode_keeps_a_jar_on_its_own_rack():
    proposal = recipes.reshelve_proposal('balanced')
    layout = db.layout()
    for placement in proposal['placements']:
        assert placement['rack'] == layout[placement['spice_key']]['rack']


def test_a_used_jar_is_promoted_to_the_top_row():
    # Kasuri Methi starts on the bottom row of the left rack. Use it enough and
    # it should climb — that is the entire premise of the re-shelve feature.
    # (Asserted as "not the top row" rather than a fixed number, so re-arranging
    # the shelf does not break a test about promotion.)
    assert db.layout()['kasuri_methi']['row'] > 0
    payload = schema.normalise(_payload(blend=[
        {'spice': 'Kasuri Methi', 'amount': '1 tsp', 'tsp': 1, 'stage': 'off_heat',
         'step': 1, 'why': ''},
    ]))
    for _ in range(4):
        db.save_recipe(payload, {'query': 'x', 'model': 'test'})
    proposal = recipes.reshelve_proposal('balanced')
    placed = {p['spice_key']: p for p in proposal['placements']}
    assert placed['kasuri_methi']['row'] == 0


def test_stove_shelf_is_never_reshuffled():
    proposal = recipes.reshelve_proposal('strict')
    layout = db.layout()
    for placement in proposal['placements']:
        if layout[placement['spice_key']]['rack'] == 'stove':
            assert placement['rack'] == 'stove'


# ── prompt assembly ──────────────────────────────────────────────────────────

def test_prompt_lists_every_jar_and_its_trap():
    from spice import prompt
    text = prompt.build_system_prompt()
    for spice in rack.SPICES:
        assert spice.name in text, f'{spice.name} missing from the prompt'
    assert 'GRAMS' in text
    assert 'Diamond Crystal' in text


def test_out_of_stock_jars_are_marked_unusable_in_the_prompt():
    from spice import prompt
    db.set_spice_state('gochugaru', 'out')
    text = prompt.build_system_prompt()
    assert 'OUT OF STOCK' in text


def test_prompt_carries_rated_history():
    from spice import prompt
    payload = schema.normalise(_payload(title='Gochujang Thighs', cuisine='Korean'))
    recipe_id = db.save_recipe(payload, {'query': 'x', 'model': 'test'})
    db.rate(recipe_id, 8, salt_delta=-1, notes='needed more garlic')
    text = prompt.build_system_prompt()
    assert 'Gochujang Thighs' in text
    assert '8/10' in text
    assert 'needed more garlic' in text


# ── the whole path, through HTTP, with the model stubbed ─────────────────────

MODEL_REPLY = {
    'title': 'Gochujang Thighs', 'cuisine': 'Korean', 'protein': 'chicken thighs',
    'portion_lb': 1.5, 'confidence': 'well_trodden',
    'why_this': 'Korean has not come up yet.', 'heat_level': 4,
    'pan': 'cast iron, holds heat through three batches',
    'times': {'prep_min': 15, 'marinate_min': 60, 'cook_min': 20, 'total_min': 95},
    'blend': [
        {'spice': 'Gochugaru', 'amount': '1 tbsp', 'tsp': 3, 'stage': 'mid',
         'step': 3, 'why': 'fruity heat'},
        {'spice': 'garlic powder', 'amount': '2 tsp', 'tsp': 2, 'stage': 'mid',
         'step': 3, 'why': 'the whole point'},
        {'spice': 'toasted sesame', 'amount': '1 tsp', 'tsp': 1, 'stage': 'garnish',
         'step': 4, 'why': 'texture'},
        # Not a jar -- must land in from_kitchen rather than on the rack.
        {'spice': 'fresh ginger', 'amount': '1 thumb', 'tsp': 0, 'stage': 'early',
         'step': 2, 'why': 'brightness'},
    ],
    'salt': {'grams': 8.4, 'msg_grams': 1.5, 'when': '45 min ahead, dry',
             'rationale': '1.5 lb x 5.6 g/lb, minus 20% for the MSG'},
    'from_kitchen': [{'item': 'gochujang', 'amount': '2 tbsp'}],
    'steps': [
        {'n': 1, 'title': 'Salt', 'body': 'Salt the bare thighs.', 'minutes': 45,
         'heat': 'none', 'watch_for': 'Surface should look dry and tacky.'},
        {'n': 2, 'title': 'Marinate', 'body': 'Gochujang and ginger.', 'minutes': 60,
         'heat': 'none', 'watch_for': ''},
        {'n': 3, 'title': 'Sear', 'body': 'Batches. Spices after the sear.',
         'minutes': 12, 'heat': 'medium_low', 'watch_for': 'Steady sizzle, no smoke.'},
        {'n': 4, 'title': 'Finish', 'body': 'Sesame on the plate.', 'minutes': 1,
         'heat': 'none', 'watch_for': ''},
    ],
    'salt_check': 'Taste one piece before the last batch.',
    'serve_with': 'Short-grain rice.', 'leftovers': 'Three days, fridge.',
}


# A tailnet address, and the only credential the app has (see spice/auth.py).
# Anything driving the owner's own screens must arrive from one -- there is no
# header, code or cookie that can stand in for it.
PEER_ADDR = '100.80.250.61'
PEER = {'REMOTE_ADDR': PEER_ADDR}


@pytest.fixture
def client(monkeypatch):
    """The owner, on his own network. Every request carries a peer address."""
    from spice import api as api_module, openrouter
    monkeypatch.setattr(openrouter, 'generate',
                        lambda *a, **k: (dict(MODEL_REPLY), {'model': 'stub'}))
    app = api_module.create_app()
    app.config['TESTING'] = True
    test_client = app.test_client()
    test_client.environ_base['REMOTE_ADDR'] = PEER_ADDR
    return test_client


def test_ask_renders_a_complete_recipe(client):
    response = client.post('/api/ask', json={'query': 'chicken thighs', 'portion_lb': 1.5})
    assert response.status_code == 200
    payload = response.get_json()['payload']

    # Three real jars resolved; the fresh ginger did not.
    assert [i['spice_key'] for i in payload['blend']] == \
        ['gochugaru', 'garlic_powder', 'sesame_seeds']
    assert any(k['item'] == 'fresh ginger' for k in payload['from_kitchen'])
    assert any('fresh ginger' in w for w in payload['warnings'])

    # Salt arrived in grams and left in spoons of the configured brand, with the
    # grams left behind: they are how the app stores salt, not how it says it.
    assert '8.4 g' not in payload['salt']['display']
    assert schema.TSP in payload['salt']['display']
    assert 'fine table salt' in payload['salt']['display']
    assert payload['salt']['spoons'] and 'fine table salt' not in payload['salt']['spoons']
    assert payload['salt']['msg_display']

    # Spices are attached to the step that uses them.
    sear = next(s for s in payload['steps'] if s['n'] == 3)
    assert {s['name'] for s in sear['spices']} == {'Gochugaru', 'Garlic Powder'}


def test_ask_then_rate_feeds_the_next_prompt(client):
    recipe_id = client.post('/api/ask', json={'query': 'chicken thighs'}).get_json()['id']
    rated = client.post(f'/api/recipes/{recipe_id}/rate',
                        json={'overall': 9, 'salt_delta': 1, 'notes': 'a touch salty'})
    assert rated.status_code == 200
    assert rated.get_json()['rating']['overall'] == 9

    from spice import prompt
    text = prompt.build_system_prompt()
    assert 'Gochujang Thighs' in text and '9/10' in text
    assert 'Korean' in text                    # rotation now knows
    assert 'Cut your salt target' in text      # calibration reacted


def test_used_jars_are_counted_for_reshelving(client):
    client.post('/api/ask', json={'query': 'chicken thighs'})
    counts = db.usage_counts()
    assert counts['gochugaru'] == 1
    assert 'fresh ginger' not in counts


def test_rating_validates_its_input(client):
    recipe_id = client.post('/api/ask', json={'query': 'x'}).get_json()['id']
    assert client.post(f'/api/recipes/{recipe_id}/rate', json={'overall': 47}).status_code == 400
    assert client.post(f'/api/recipes/{recipe_id}/rate', json={}).status_code == 400


def test_layout_endpoint_refuses_a_broken_arrangement(client):
    good = [{'spice_key': k, **v} for k, v in db.layout().items()]
    assert client.post('/api/rack/layout', json={'placements': good}).status_code == 200

    dropped = good[:-1]
    assert client.post('/api/rack/layout', json={'placements': dropped}).status_code == 400

    collided = [dict(p) for p in good]
    collided[1].update(rack=collided[0]['rack'], row=collided[0]['row'],
                       col=collided[0]['col'])
    assert client.post('/api/rack/layout', json={'placements': collided}).status_code == 400


def test_ask_without_a_key_explains_itself():
    from spice import api as api_module, openrouter
    app = api_module.create_app()
    app.config['TESTING'] = True

    def boom(*_a, **_k):
        raise openrouter.OpenRouterError('No OpenRouter API key configured.')

    original = openrouter.generate
    openrouter.generate = boom
    try:
        response = app.test_client().post('/api/ask', json={'query': 'steak'},
                                          environ_base=PEER)
        assert response.status_code == 502
        assert 'API key' in response.get_json()['error']
    finally:
        openrouter.generate = original


def test_the_salt_jar_is_labelled_from_the_setting_not_the_registry():
    # The rack said "Kosher Salt" while every recipe said fine table salt. A
    # disagreement about WHICH salt is exactly the error behind the 2/10 steak,
    # so the jar label and the measurement now read from one place.
    label = db.salt_brand()[0]
    jar = next(j for j in recipes.rack_view()['jars'] if j['spice_key'] == 'salt')
    assert jar['name'].lower() == label.lower()
    assert 'kosher' not in jar['name'].lower()

    db.set_setting('salt_brand', 'morton_kosher')
    jar = next(j for j in recipes.rack_view()['jars'] if j['spice_key'] == 'salt')
    assert 'morton' in jar['name'].lower(), 'the jar did not follow the setting'


@pytest.mark.parametrize('written', ['salt', 'table salt', 'iodized salt',
                                     'kosher salt', 'fine salt'])
def test_every_name_for_salt_finds_the_one_jar(written):
    assert rack.resolve(written).key == 'salt'


def test_the_default_salt_is_the_one_actually_in_the_kitchen():
    # Not a cosmetic default. This kitchen uses fine iodized table salt, while
    # the instructions this app replaced were written for Diamond Crystal -- so
    # the stated target (1 tsp/lb = 0.62% of weight) and the actual practice
    # (1 tsp/lb of table salt = 1.32%) were never the same number. Flipping this
    # back to Diamond Crystal would halve every recipe's salt.
    label, grams_per_tsp = db.salt_brand()
    assert label == 'fine table salt'
    assert grams_per_tsp == 6.0


def test_a_bad_rating_cannot_drag_salt_below_the_proven_rate():
    # The floor used to be the literal words "about 1% of the dish weight",
    # written when the baseline was 1.23%. Against 1.65% that let a single
    # salt_delta=+2 rating cut 30% -- landing at 1.16%, BELOW the retired 5.6
    # value that prompt.md spends five paragraphs repudiating, and inside the
    # conventional band the same prompt forbids sixteen lines later. One
    # disappointing dinner should not overturn four good ones.
    rate = float(db.setting('salt_grams_per_lb'))
    block = prompt.calibration_block(2.0, 0.0, rated=6, salt_rate=rate)
    floor = float(re.search(r'never below ([\d.]+)g', block).group(1))
    assert floor >= 5.6, f'floor {floor}g is under the retired baseline'
    assert floor / 453.6 * 100 > 1.2


def test_calibration_does_not_pass_a_verdict_on_an_empty_table():
    # A mean of 0.0 over no ratings used to print "landing on target. Hold the
    # line." directly above a history section saying nothing had been rated.
    empty = prompt.calibration_block(0.0, 0.0, rated=0)
    assert 'on target' not in empty and 'Nothing has been rated' in empty
    assert 'on target' in prompt.calibration_block(0.0, 0.0, rated=6)


def test_the_salt_baseline_matches_what_the_good_dishes_actually_used():
    # 1 1/4 tsp of THIS kitchen's salt per pound -- 7.5g, 1.65% of the meat's
    # weight, measured out. That is what the 9.5, the two 9s and the 8.5 were
    # all seasoned at.
    #
    # The old baseline was 5.6g, reverse-engineered from the 7/10 Tex Mex, and
    # was wrong twice over: it calibrated to a dish that was rated UNDER-salted,
    # and it ignored that the same dish was a rice bowl, so the shortfall was
    # dilution rather than rate. Worse, 5.6g measured lands at about 0.99% once
    # the usual fifth is left on hands and bowls -- which is precisely the
    # number that had been judged slightly under in the first place.
    grams_per_lb = float(db.setting('salt_grams_per_lb'))
    percent = grams_per_lb / 453.6 * 100
    assert 1.5 < percent < 1.8, f'{percent:.2f}% is outside the calibrated band'



# ── the rating reminder in the vault ─────────────────────────────────────────

@pytest.fixture
def live_vault(tmp_path, monkeypatch):
    """Let vault.py actually run, pointed somewhere harmless.

    It refuses to do anything while PYTEST_CURRENT_TEST is set, which is the
    guard that keeps the suite out of the real Obsidian vault -- so testing it
    at all means lifting that guard and replacing it with a temp path.

    The guard is overridden by replacing `_enabled` rather than by deleting the
    environment variable: pytest re-sets PYTEST_CURRENT_TEST at the start of
    every phase, so a delenv in a fixture is gone again by the time the test
    body runs. That the guard itself works is proved separately, below.
    """
    from spice import vault
    monkeypatch.setattr(vault, '_enabled', lambda: True)
    monkeypatch.setattr(db.config, 'TODO_FILE', tmp_path / 'Recipes.md')
    monkeypatch.setattr(db.config, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(db.config, 'tailnet_url', lambda: 'http://box.ts.net:5003')
    return vault


def test_a_generated_recipe_becomes_one_unticked_line(live_vault):
    live_vault.add_recipe(8, 'Gochujang Beef Bowl')
    text = db.config.TODO_FILE.read_text(encoding='utf-8')
    assert text.count('- [ ]') == 1
    assert '#8' in text and 'Gochujang Beef Bowl' in text
    assert '/recipe/8' in text          # singular route; /recipes/8 is not one
    assert live_vault.OPEN_HEADING in text


def test_the_same_recipe_is_never_listed_twice(live_vault):
    live_vault.add_recipe(8, 'Gochujang Beef Bowl')
    live_vault.add_recipe(8, 'Gochujang Beef Bowl')
    assert db.config.TODO_FILE.read_text(encoding='utf-8').count('- [ ]') == 1


def test_an_id_is_matched_whole(live_vault):
    # "#8" must not match inside "#80", or rating one dish ticks another.
    live_vault.add_recipe(80, 'Eighty')
    live_vault.mark_rated(8)
    assert '- [ ]' in db.config.TODO_FILE.read_text(encoding='utf-8')


def test_rating_ticks_the_line_and_moves_it(live_vault):
    live_vault.add_recipe(8, 'Gochujang Beef Bowl')
    live_vault.mark_rated(8)
    text = db.config.TODO_FILE.read_text(encoding='utf-8')
    assert '- [ ]' not in text
    assert text.index(live_vault.DONE_HEADING) < text.index('- [x]')
    assert '#8' in text


def test_a_deleted_line_stays_deleted(live_vault):
    # Removing a line in Obsidian is a durable "stop asking me". Rating the
    # recipe afterwards must not resurrect it.
    live_vault.add_recipe(8, 'Gochujang Beef Bowl')
    db.config.TODO_FILE.write_text(live_vault._FRONTMATTER, encoding='utf-8')
    live_vault.mark_rated(8)
    assert '#8' not in db.config.TODO_FILE.read_text(encoding='utf-8')


def test_a_vault_write_failure_never_breaks_a_recipe(live_vault, monkeypatch):
    # By the time this runs the model has been paid for. A locked file, an
    # unmounted drive or a read-only vault must cost a log line and nothing
    # else -- losing the recipe over a failed reminder would be an absurd trade.
    def boom(_text):
        raise OSError('the vault is on a drive that is not there')

    monkeypatch.setattr(live_vault, '_write', boom)
    live_vault.add_recipe(1, 'Anything')
    live_vault.mark_rated(1)


def test_the_vault_is_untouched_while_running_under_pytest(tmp_path, monkeypatch):
    # The guard every other test in this file relies on. tmp_path EXISTS, so the
    # only thing standing between this suite and the owner's real Obsidian vault
    # is the pytest check inside _enabled() -- which is what this pins. Note the
    # other vault tests override _enabled rather than clearing the environment
    # variable, because pytest re-sets it at the start of every phase.
    monkeypatch.setattr(db.config, 'TODO_FILE', tmp_path / 'Recipes.md')
    from spice import vault
    assert vault._enabled() is False
    vault.add_recipe(1, 'Anything')
    assert not (tmp_path / 'Recipes.md').exists()


def test_reserved_todo_markers_are_stripped_from_a_title(live_vault):
    # The To Do tooling in the Spore repo parses these as priority and dates.
    live_vault.add_recipe(9, 'Beef ⏫ with a date 📅 2026-01-01')
    line = db.config.TODO_FILE.read_text(encoding='utf-8')
    assert '⏫' not in line and '2026-01-01' not in line


def test_no_link_is_better_than_a_dead_one(live_vault, monkeypatch):
    # The public origin can never authenticate: cloudflared connects over
    # loopback, so a tailnet phone still arrives looking like a stranger.
    monkeypatch.setattr(db.config, 'tailnet_url', lambda: '')
    live_vault.add_recipe(11, 'Offline Dish')
    text = db.config.TODO_FILE.read_text(encoding='utf-8')
    assert 'http' not in text and 'spice rate 11' in text


# ── the pantry decisions ─────────────────────────────────────────────────────

def test_bay_leaves_are_on_the_stove_shelf():
    # The one pantry item promoted: nothing else in this kitchen does the
    # background-aromatic job in a wet, long-cooked dish.
    assert 'bay_leaves' in rack.STOVE_BY_KEY
    assert 'bay_leaves' in rack.DEFAULT_LAYOUT['stove'][0]
    assert db.layout()['bay_leaves']['rack'] == 'stove'
    assert rack.resolve('bay leaf').key == 'bay_leaves'


@pytest.mark.parametrize('name', [
    'lemon pepper', 'blackened seasoning', 'chicken spice',
    'salt and pepper seasoning',
])
def test_items_left_in_storage_never_resolve_to_a_jar(name):
    # They are owned but deliberately out of play. Resolving one would put a jar
    # on the rack diagram that is not on the rack, and would quietly reintroduce
    # a pre-salted blend into a kitchen calibrated in grams.
    assert rack.resolve(name) is None


def test_storage_decisions_are_documented_with_reasons():
    # No count assertion: the list grows every time something is considered and
    # rejected, and a test that breaks on that is testing arithmetic, not intent.
    # What matters is that nothing lands here without a reason attached.
    assert rack.IN_STORAGE
    for name, reason in rack.IN_STORAGE:
        assert name and len(reason) > 40, f'{name} has no real reason recorded'


def test_ground_star_anise_stays_in_the_cupboard():
    # Whole pods keep for years and are self-limiting (you count them); ground
    # anise fades in months, and Chinese 5 Spice already covers that flavour.
    assert any('Star Anise' in name for name, _ in rack.IN_STORAGE)
    assert rack.SPICE_BY_KEY['star_anise'].form == 'whole'
    # It sits with the warm braising aromatics on the right, not with the
    # tempering seeds it used to be filed beside.
    assert db.layout()['star_anise']['rack'] == 'right'


# ── the public boundary ──────────────────────────────────────────────────────
# The app is deliberately on the open internet, with a metered API key behind it.
# These are the tests that say what a stranger may and may not reach.

from spice import auth  # noqa: E402


@pytest.fixture
def public(monkeypatch):
    """An app reached the way a stranger reaches it: not from the tailnet.

    Flask's test client presents no REMOTE_ADDR unless one is given, which is
    exactly the stranger case. Pass `environ_base=PEER` to make a request AS the
    owner -- there is no header, token or code that can do it, which is the whole
    point of the design under test.
    """
    from spice import api as api_module, openrouter
    monkeypatch.setattr(openrouter, 'generate',
                        lambda *a, **k: (dict(MODEL_REPLY), {'model': 'stub'}))
    # The development override would make every assertion below vacuously pass,
    # so it is forced off rather than assumed off.
    monkeypatch.setattr(auth.config, 'OPEN_ACCESS', False)
    app = api_module.create_app()
    app.config['TESTING'] = True
    return app.test_client()


@pytest.mark.parametrize('path', ['/api/health', '/api/rack', '/api/demo'])
def test_the_shop_window_is_open(public, path):
    assert public.get(path).status_code == 200


def test_health_tells_the_frontend_which_app_to_draw(public):
    """The one bit of self-knowledge the public API hands out.

    There is no /api/access/check any more -- with no code to try, an endpoint
    whose job was "is this code right?" had nothing left to answer. The frontend
    needs exactly one boolean on boot to choose between the owner's app and the
    exhibit, and health was already the call it made.
    """
    assert public.get('/api/health').get_json()['authed'] is False
    assert public.get('/api/health', environ_base=PEER).get_json()['authed'] is True


def test_the_tailnet_address_is_never_handed_out(public):
    """It used to be public, and deliberately so -- that reasoning has expired.

    While a code existed, the tailnet address was just a shortcut past typing
    one, and useless to anyone not already on the network. It is now the ONLY
    route to anything private, so it stays off the public surface entirely.
    """
    for path in ('/api/health', '/api/rack', '/api/demo'):
        assert 'tailnet' not in public.get(path).get_data(as_text=True).lower()


@pytest.mark.parametrize('method, path', [
    ('post', '/api/ask'),                 # the one that spends money
    ('get', '/api/settings'),
    ('post', '/api/settings'),
    ('get', '/api/recipes'),
    ('get', '/api/recipes/1'),
    ('get', '/api/models'),
    ('get', '/api/rack/proposal'),
    ('post', '/api/rack/state'),
    ('post', '/api/rack/layout'),
])
def test_everything_else_is_shut(public, method, path):
    assert getattr(public, method)(path, json={}).status_code == 401


@pytest.mark.parametrize('path', [
    '/api/recipes/', '/API/recipes', '/api/RECIPES', '/api/settings/',
])
def test_near_miss_paths_do_not_slip_past_the_guard(public, path):
    # Flask's router is case-sensitive and would 404 most of these, but the guard
    # must not be the thing depending on that. Anything but 200 is acceptable;
    # a 200 would mean private data escaped.
    assert public.get(path).status_code != 200


@pytest.mark.parametrize('method', ['head', 'options'])
def test_non_get_verbs_cannot_read_private_routes(public, method):
    assert getattr(public, method)('/api/recipes').status_code != 200


def test_anonymous_health_says_nothing_useful(public):
    body = public.get('/api/health').get_json()
    assert body['authed'] is False
    for leaky in ('model', 'recipes', 'rated', 'openrouter', 'asks_today'):
        assert leaky not in body, f'/api/health leaked {leaky} to an anonymous caller'


def test_anonymous_rack_is_redacted_but_still_complete(public):
    jars = public.get('/api/rack').get_json()['jars']
    assert len(jars) == len(rack.ALL_BY_KEY)          # the drawing is intact
    assert all(j['uses'] == 0 for j in jars)          # habits are not
    assert all(j['stock'] == 'ok' for j in jars)


def test_the_owner_sees_the_private_fields(public):
    db.set_spice_state('gochugaru', 'out')
    jars = public.get('/api/rack', environ_base=PEER).get_json()['jars']
    assert any(j['stock'] == 'out' for j in jars)
    body = public.get('/api/health', environ_base=PEER).get_json()
    assert 'model' in body


def test_the_retired_passphrase_is_gone_from_the_database(public):
    """A database that ran the old build still holds the salt and hash.

    Dropping them from DEFAULT_SETTINGS only stops NEW databases growing them;
    `settings()` returns whatever the table holds, so an upgraded install would
    have gone on serving a dead secret through /api/settings forever.
    """
    for key in db.RETIRED_SETTINGS:
        db.set_setting(key, 'left-over-from-the-old-build')
    db.ensure_schema()                       # the boot path that cleans them out

    assert db.one('SELECT COUNT(*) c FROM settings WHERE key IN '
                  f'({",".join("?" * len(db.RETIRED_SETTINGS))})',
                  db.RETIRED_SETTINGS)['c'] == 0
    served = public.get('/api/settings', environ_base=PEER).get_json()['settings']
    for key in db.RETIRED_SETTINGS:
        assert key not in served
    # ...and they cannot be written back, because they are not settings any more.
    assert public.post('/api/settings', json={'access_hash': 'x'},
                       environ_base=PEER).status_code == 400


def test_no_header_can_buy_a_way_in(public):
    """There is no credential to present, so presenting one changes nothing.

    The old build accepted X-Spice-Code. Anything still sending it -- an old
    phone with the code in localStorage, a bot that scraped the header name --
    gets the same 401 as a caller sending nothing at all.
    """
    for header in ('X-Spice-Code', 'Authorization', 'Cookie'):
        response = public.get('/api/settings', headers={header: 'test-code-123'})
        assert response.status_code == 401, f'{header} was honoured'
    body = public.get('/api/settings').get_json()
    # No `gated` flag: there is nothing the client could do about this.
    assert 'gated' not in body


def test_the_daily_cap_stops_the_spending_before_the_call(public, monkeypatch):
    from spice import openrouter
    calls = []

    def stub(system, user, model, on_attempt=None):
        # Behave like the real client: log the billed completion first.
        if on_attempt:
            on_attempt(model)
        calls.append(model)
        return dict(MODEL_REPLY), {'model': model}

    monkeypatch.setattr(openrouter, 'generate', stub)
    db.set_setting('daily_ask_limit', '2')
    for _ in range(2):
        assert public.post('/api/ask', json={'query': 'x'},
                           environ_base=PEER).status_code == 200
    blocked = public.post('/api/ask', json={'query': 'x'}, environ_base=PEER)
    assert blocked.status_code == 429
    assert len(calls) == 2, 'the third request still called OpenRouter'


def test_a_failing_ask_still_counts_against_the_cap(public, monkeypatch):
    """The critical one: failures used to be free and therefore unlimited.

    A recipe row is only written when the whole pipeline succeeds, so counting
    recipes made every failed ask invisible — while a single failure still fires
    up to three billed completions through the schema fallback chain. A client
    stuck in a retry loop could spend without bound while the cap read zero.
    """
    from spice import openrouter
    billed = []

    def always_fails(system, user, model, on_attempt=None):
        for _ in range(3):                       # the fallback chain, all billed
            if on_attempt:
                on_attempt(model)
            billed.append(model)
        raise openrouter.OpenRouterError('model returned prose')

    monkeypatch.setattr(openrouter, 'generate', always_fails)
    db.set_setting('daily_ask_limit', '6')

    for _ in range(2):
        assert public.post('/api/ask', json={'query': 'x'},
                           environ_base=PEER).status_code == 502
    assert len(billed) == 6
    assert db.one('SELECT COUNT(*) c FROM recipes')['c'] == 0, 'no recipe was saved'
    assert auth.asks_today() == 6, 'billed calls were not counted'

    stopped = public.post('/api/ask', json={'query': 'x'}, environ_base=PEER)
    assert stopped.status_code == 429
    assert len(billed) == 6, 'the cap did not stop the third attempt'


@pytest.mark.parametrize('sent, expected', [
    (60.0, 60),      # a JSON number: used to store '60.0' and disable the cap
    (60, 60),
    ('60', 60),
    (0, 0),          # 0 genuinely means "no cap"
])
def test_the_limit_is_stored_as_something_readable(public, sent, expected):
    assert public.post('/api/settings', json={'daily_ask_limit': sent},
                       environ_base=PEER).status_code == 200
    assert auth.daily_limit() == expected


def test_an_unreadable_limit_fails_closed_not_open():
    # 0 legitimately means "no cap", so returning 0 on a parse error silently
    # removed the only spend guard in the app. Fall back to the default instead.
    db.set_setting('daily_ask_limit', 'not-a-number')
    assert auth.daily_limit() == int(db.DEFAULT_SETTINGS['daily_ask_limit'])
    assert auth.daily_limit() > 0


@pytest.mark.parametrize('bad', ['-1', 'abc', None])
def test_a_bad_limit_is_refused_at_the_door(public, bad):
    assert public.post('/api/settings', json={'daily_ask_limit': bad},
                       environ_base=PEER).status_code == 400


def test_the_dev_override_opens_everything_and_is_off_by_default(public, monkeypatch):
    """SPICE_OPEN exists so the Vite dev server can reach the owner's screens.

    It is the only thing besides a peer address that opens the app, and loopback
    is also where the public tunnel lands -- so left on in production it hands
    the internet the spend. Hence: environment variable, default off, and the
    settings screen shows it in red.
    """
    assert public.get('/api/settings').status_code == 401       # default

    monkeypatch.setattr(auth.config, 'OPEN_ACCESS', True)
    assert public.get('/api/settings').status_code == 200
    body = public.get('/api/health').get_json()
    assert body['authed'] is True
    # Distinguishable from a real peer, which is what the warning hangs off.
    assert body['via_tailnet'] is False


# ── the frozen demo ──────────────────────────────────────────────────────────

def test_the_demo_recipe_is_render_ready_as_returned():
    """Test what the endpoint actually hands back, not a copy we fixed up first.

    The earlier version of this test normalised the payload itself and then
    asserted on the result, which passed happily while the real endpoint served
    an unnormalised payload — nameless blend rows and a rack with nothing lit.
    """
    from spice import recipes as recipes_module
    payload = recipes_module.demo_recipe()
    assert payload is not None, 'spice/demo.json is missing'
    assert not payload.get('warnings'), payload.get('warnings')

    # Everything RecipeCard and SpiceRack read must already be present.
    assert payload['blend'], 'demo has no blend'
    for item in payload['blend']:
        assert item['spice_key'] in rack.ALL_BY_KEY
        assert item['name'] and item['amount'] and item['color']
    for step in payload['steps']:
        assert 'spices' in step, 'steps were never linked to their jars'
    assert any(step['spices'] for step in payload['steps']), \
        'no step references a jar, so the walkthrough shows nothing'

    # Re-run per request, so it always quotes the configured salt.
    assert 'fine table salt' in payload['salt']['display']


def test_the_demo_endpoint_serves_what_the_frontend_needs(public):
    payload = public.get('/api/demo').get_json()['payload']
    assert all(item.get('name') and item.get('spice_key')
               for item in payload['blend'])


# ── whole vs ground, and reserved slots ──────────────────────────────────────

@pytest.mark.parametrize('written, expected', [
    ('cardamom', 'cardamom'),
    ('green cardamom', 'cardamom'),
    ('cardamom pods', 'cardamom'),
    # No ground cardamom jar exists, so a recipe asking for it must still land on
    # the pods -- with the note telling the cook to crush seeds from about three.
    ('ground cardamom', 'cardamom'),
    ('cardamom powder', 'cardamom'),
    # ...and mirror-image for cloves: only a ground jar exists, so a recipe
    # calling for whole buds lands there and gets told the conversion.
    ('cloves', 'ground_cloves'),
    ('whole cloves', 'ground_cloves'),
    ('ground cloves', 'ground_cloves'),
    ('clove powder', 'ground_cloves'),
])
def test_the_form_we_actually_own_is_what_resolves(written, expected):
    assert rack.resolve(written).key == expected


def test_we_do_not_pretend_to_own_the_other_form():
    # The kitchen has cardamom whole and cloves ground -- one jar each. Carrying
    # registry entries for jars that are not in the house would put them on the
    # rack diagram and let a recipe call for them.
    assert 'ground_cardamom' not in rack.ALL_BY_KEY
    assert 'cloves' not in rack.ALL_BY_KEY
    assert rack.SPICE_BY_KEY['cardamom'].form == 'whole'
    assert rack.SPICE_BY_KEY['ground_cloves'].form == 'ground'


def test_the_clove_note_carries_the_conversion():
    # There is no whole jar to fall back on, so the substitution ratio and the
    # "cannot fish it out" warning have to travel with the jar.
    note = rack.SPICE_BY_KEY['ground_cloves'].note
    assert '1/8 tsp' in note and 'fish it out' in note


def test_an_unowned_jar_keeps_its_slot_but_never_reaches_a_recipe():
    # Kasuri Methi is on the shopping list. Its slot stays reserved so nothing
    # has to move twice when it arrives, and stock='out' keeps it out of prompts.
    db.set_spice_state('kasuri_methi', 'out')
    assert db.layout()['kasuri_methi']['rack'] == 'left'
    assert 'kasuri_methi' in db.out_of_stock()

    from spice import prompt
    text = prompt.build_system_prompt()
    assert 'Kasuri Methi' in text
    assert 'OUT OF STOCK' in text


def test_wild_hing_lives_above_the_stove():
    assert db.layout()['wild_hing']['rack'] == 'stove'
    # Still a rack-declared spice; only its shelf changed.
    assert 'wild_hing' in rack.SPICE_BY_KEY


def test_hing_keeps_its_tempering_default_without_a_burn_warning():
    # It burns AND it must hit hot fat first -- the registry's own default must
    # not trip the burn warning.
    payload = _payload(blend=[
        {'spice': 'Wild Hing', 'amount': 'a pinch', 'tsp': 0.06, 'stage': 'temper',
         'step': 1, 'why': 'bloom in fat'},
    ])
    out = schema.normalise(payload)
    assert not any('scorches' in w for w in out['warnings'])


# ── the pantry and the freezer ───────────────────────────────────────────────

def test_every_shelf_is_drawn():
    # There is no second kind of storage: every place a jar can be is a shelf in
    # the picture, and nothing is a list beside one. The freezer holds a single
    # bag and is still drawn; the sauce shelf holds bottles and is still drawn.
    # The two names that were retired were retired for being LISTS, and adding a
    # drawn shelf is not the same thing as bringing one of those back.
    assert set(rack.RACKS) == {'left', 'right', 'stove', 'sauces', 'freezer'}
    assert not hasattr(rack, 'LISTED_RACKS')
    for name in ('pantry', 'cupboard'):
        assert name not in rack.RACKS


def test_the_wet_seasonings_carry_their_salt():
    # A tablespoon of light soy is about a third of the salt a pound of meat is
    # allowed, and until these landed on the shelf that salt appeared nowhere in
    # the app. The figure is registry data so the prompt can print it and the
    # model can subtract it, rather than it living in somebody's memory.
    assert rack.ALL_BY_KEY['light_soy_sauce'].salt_per_tbsp > 2
    assert {s.key for s in rack.PRE_SALTED} >= {
        'light_soy_sauce', 'dark_soy_sauce', 'oyster_sauce', 'doubanjiang',
        'gochujang', 'garlic_soybean_paste', 'dashi', 'cooking_sake'}
    # Toasted sesame oil is a seasoning too, and carries no salt at all. A figure
    # invented for it would be subtracted from a real dish.
    assert rack.ALL_BY_KEY['toasted_sesame_oil'].salt_per_tbsp == 0
    # And the figures reach the model, or none of the above is worth anything.
    text = prompt.build_system_prompt()
    assert 'salt per TBsp' in text


def test_an_unqualified_soy_sauce_is_the_light_one():
    # What a recipe writer means by "soy sauce". Dark soy is used by the teaspoon
    # for colour, so a recipe that got it by default would be a fivefold error in
    # the wrong direction -- the same trap the bulk pepper jar exists to avoid.
    assert rack.resolve('soy sauce').key == 'light_soy_sauce'
    assert rack.resolve('dark soy').key == 'dark_soy_sauce'
    # Bought instead of black bean garlic sauce, so a recipe asking for that has
    # to find the tub that is actually in the cupboard.
    assert rack.resolve('black bean garlic sauce').key == 'garlic_soybean_paste'


def test_the_staples_are_known_without_becoming_jars():
    # Fresh garlic must never resolve onto the garlic powder -- they are
    # different ingredients and the registry says so. But the model still has to
    # know the kitchen has them, or it writes them up as a shopping trip.
    assert rack.resolve('fresh garlic') is None
    assert rack.resolve('fresh ginger') is None
    text = prompt.build_system_prompt()
    assert 'Always in the house' in text
    assert 'Fresh garlic' in text


def test_the_soaking_mushroom_is_off_the_spice_rack():
    # Black Fungus is dried wood ear -- a 30-minute soak, not a teaspoon. It went
    # to the stove shelf when the pantry was retired.
    assert db.layout()['black_fungus']['rack'] == 'stove'


def test_curry_leaves_live_in_the_freezer():
    assert db.layout()['curry_leaves']['rack'] == 'freezer'
    assert rack.resolve('curry leaf').key == 'curry_leaves'
    note = rack.SPICE_BY_KEY['curry_leaves'].note
    assert 'FREEZER' in note and 'dried' in note


def test_reshelving_leaves_the_off_rack_places_alone():
    # Checked as "not a wall rack" rather than "is the stove", so adding a
    # location cannot silently drop its contents out of the layout.
    layout = db.layout()
    for mode in ('balanced', 'strict'):
        placed = {p['spice_key']: p for p in recipes.reshelve_proposal(mode)['placements']}
        assert set(placed) == set(layout), 'a location vanished from the proposal'
        for key, place in layout.items():
            if place['rack'] not in rack.wall_racks():
                assert placed[key]['rack'] == place['rack']


def test_the_rack_view_covers_every_shelf():
    view = recipes.rack_view()
    assert view['racks'] == list(rack.RACKS)
    assert {j['rack'] for j in view['jars']} == set(rack.RACKS)
    assert all(name in view['rack_labels'] for name in view['racks'])


def test_the_prompt_lists_off_rack_places_without_inventing_rows():
    from spice import prompt
    text = prompt.build_system_prompt()
    assert 'Curry Leaves' in text and 'Black Fungus' in text
    freezer = text.split('### Freezer')[1].split('###')[0]
    assert 'Row' not in freezer, 'a one-row shelf was given a row number'
    # ...while the shelves that DO have slots keep their row headings.
    assert '### Above the Stove' in text
    stove = text.split('### Above the Stove')[1].split('###')[0]
    assert 'Row 1' in stove and 'Row 2' in stove


# ── jars being used up ───────────────────────────────────────────────────────

def test_using_up_is_available_not_absent():
    # The whole point: it is still usable. Treating it like 'out' would defeat
    # the feature, and treating it like 'ok' would never spend the jar.
    for key in ('onion_salt', 'chili_powder', 'parsley'):
        db.set_spice_state(key, 'using_up')
    assert db.using_up() == {'onion_salt', 'chili_powder', 'parsley'}
    assert not (db.using_up() & db.out_of_stock())


def test_the_prompt_asks_for_them_and_forbids_forcing_them():
    from spice import prompt
    for key in ('onion_salt', 'chili_powder', 'parsley'):
        db.set_spice_state(key, 'using_up')
    text = prompt.build_system_prompt()
    assert '## Jars to use up' in text
    # Both halves must be present. "Use these up" alone invites the model to bend
    # dishes around them, which costs a dinner to save a teaspoon.
    assert 'Spend them where you can' in text
    assert 'Never bend a dish to consume one' in text


def test_each_using_up_jar_carries_its_conversion():
    # A swap that silently doubles the cumin or the salt is worse than wasting
    # the jar, so the arithmetic travels with the spice.
    assert '4.5g' in rack.SPICE_BY_KEY['onion_salt'].note
    assert 'OFF the salt figure' in rack.SPICE_BY_KEY['onion_salt'].note
    assert 'CUT the separate cumin' in rack.SPICE_BY_KEY['chili_powder'].note


def test_using_up_jars_are_not_on_the_wall_racks():
    # They came off the rack; they did not leave the kitchen. All of them sit
    # above the stove with everything else that has no rack slot.
    layout = db.layout()
    for key in ('onion_salt', 'chili_powder', 'parsley'):
        assert layout[key]['rack'] == 'stove'
        assert layout[key]['rack'] not in rack.wall_racks()


def test_finishing_a_jar_takes_it_out_of_play():
    for key in ('onion_salt', 'chili_powder', 'parsley'):
        db.set_spice_state(key, 'out')
    assert {'onion_salt', 'chili_powder', 'parsley'} <= db.out_of_stock()
    assert db.using_up() == set()


@pytest.mark.parametrize('state', ['ok', 'low', 'using_up', 'out'])
def test_every_stock_state_is_accepted_by_the_api(public, state):
    response = public.post('/api/rack/state',
                           json={'spice_key': 'parsley', 'stock': state},
                           environ_base=PEER)
    assert response.status_code == 200


def test_a_nonsense_stock_state_is_refused(public):
    assert public.post('/api/rack/state',
                       json={'spice_key': 'parsley', 'stock': 'maybe'},
                       environ_base=PEER).status_code == 400


def test_using_up_is_a_state_not_a_location():
    """A jar on its way out still lives somewhere real.

    Every using-up jar sits above the stove, alongside things that are staying.
    The state says "spend this"; the shelf says where to reach. Conflating them
    would invent a location the kitchen does not have — which is exactly what a
    short-lived `cupboard` did before it was removed.
    """
    for key in ('zanzibar_black_pepper', 'purple_shallot_powder',
                'onion_salt', 'chili_powder', 'parsley'):
        db.set_spice_state(key, 'using_up')
        assert db.layout()[key]['rack'] == 'stove', f'{key} has no real shelf'
    # ...and the stove also holds jars that are staying, so the shelf carries no
    # implication about state.
    assert db.layout()['salt']['rack'] == 'stove'
    assert 'salt' not in db.using_up()

    from spice import prompt
    text = prompt.build_system_prompt()
    section = text.split('## Jars to use up')[1]
    assert 'Zanzibar Black Pepper' in section
    assert 'Purple Shallot Powder' in section


def test_the_replacements_are_named_in_the_notes():
    # A "use it up" instruction is useless without saying what it stands in for.
    assert 'wherever a recipe calls for black pepper' in \
        rack.ALL_BY_KEY['zanzibar_black_pepper'].note
    assert '1:1 wherever a recipe wants onion powder' in \
        rack.ALL_BY_KEY['purple_shallot_powder'].note


# ── tailnet auto-auth ────────────────────────────────────────────────────────

@pytest.mark.parametrize('addr, expected', [
    ('100.64.0.1', True),          # first address in the tailnet block
    (PEER_ADDR, True),             # this machine
    ('100.127.255.254', True),     # last address in the block
    ('127.0.0.1', False),          # the cloudflared tunnel arrives here
    ('192.168.1.50', False),       # LAN
    ('100.128.0.1', False),        # just outside 100.64.0.0/10
    ('100.63.255.255', False),     # just below it
    ('', False),
    ('not-an-ip', False),
])
def test_only_the_tailnet_block_counts(addr, expected):
    assert auth.from_tailnet(addr) is expected


def test_a_tailnet_peer_gets_the_whole_app(public):
    assert public.get('/api/settings', environ_base=PEER).status_code == 200
    assert public.get('/api/recipes', environ_base=PEER).status_code == 200
    body = public.get('/api/health', environ_base=PEER).get_json()
    assert body['via_tailnet'] is True


def test_the_tunnel_gets_nothing_private(public):
    # cloudflared connects over loopback, so public traffic presents as
    # 127.0.0.1 -- which must NOT be mistaken for a local privilege. With the
    # access code gone this is the entire public attack surface: whatever a
    # loopback caller can reach, the internet can reach.
    loopback = {'REMOTE_ADDR': '127.0.0.1'}
    assert public.get('/api/settings', environ_base=loopback).status_code == 401
    assert public.post('/api/ask', json={'query': 'x'},
                       environ_base=loopback).status_code == 401
    assert public.get('/api/health', environ_base=loopback).get_json().get('via_tailnet') is None


def test_a_forwarded_header_cannot_forge_a_tailnet_address(public):
    """The bypass this design exists to prevent.

    X-Forwarded-For is set by the caller. If the guard read it, anyone on the
    public internet could claim a tailnet address and walk straight in. Only the
    real TCP peer counts -- and since the peer address is now the ONLY
    credential, this is the single assertion holding the whole door shut.
    """
    for header in ('X-Forwarded-For', 'X-Real-IP', 'X-Client-IP',
                   'Forwarded', 'True-Client-IP'):
        response = public.get('/api/settings', headers={header: '100.80.250.61'},
                              environ_base={'REMOTE_ADDR': '203.0.113.9'})
        assert response.status_code == 401, f'{header} forged a tailnet address'


def test_the_tailnet_check_can_be_switched_off(public, monkeypatch):
    # SPICE_TRUST_TAILNET=0 shuts the last door: nobody is the owner, anywhere.
    monkeypatch.setattr(auth.config, 'TRUST_TAILNET', False)
    assert public.get('/api/settings',
                      environ_base={'REMOTE_ADDR': '100.80.250.61'}).status_code == 401


# ── bowls: what gets mixed now, and what waits ───────────────────────────────

def test_the_blend_is_grouped_by_when_it_goes_in():
    """The cook measures everything out before starting.

    That is the right habit and also how a dish gets ruined: tip garam masala
    into the bowl with the cumin and it boils for forty minutes instead of five.
    So the blend is never one flat list — same bowl means same moment.
    """
    payload = schema.normalise(_payload(blend=[
        {'spice': 'Cumin', 'amount': '1 tsp', 'tsp': 1, 'stage': 'bloom',
         'step': 1, 'why': ''},
        {'spice': 'Garlic Powder', 'amount': '2 tsp', 'tsp': 2, 'stage': 'mid',
         'step': 2, 'why': ''},
        {'spice': 'Smoked Paprika', 'amount': '1 tsp', 'tsp': 1, 'stage': 'mid',
         'step': 2, 'why': ''},
        {'spice': 'Garam Masala', 'amount': '1/2 tsp', 'tsp': 0.5,
         'stage': 'last_five', 'step': 3, 'why': ''},
    ]))
    groups = payload['blend_groups']
    assert [g['stage'] for g in groups] == ['bloom', 'mid', 'last_five']

    by_stage = {g['stage']: g for g in groups}
    assert by_stage['mid']['premix'] is True          # two jars, one bowl
    assert by_stage['bloom']['premix'] is False       # one jar, no bowl needed
    # The finishing spice is in its own bowl AND carries the reason.
    assert by_stage['last_five']['premix'] is False
    assert 'flat and dusty' in by_stage['last_five']['keep_apart']


def test_bowls_run_in_the_order_they_enter_the_pan():
    payload = schema.normalise(_payload(blend=[
        {'spice': 'Fried Garlic', 'amount': '1 tsp', 'tsp': 1, 'stage': 'garnish',
         'step': 4, 'why': ''},
        {'spice': 'Black Mustard Seeds', 'amount': '1 tsp', 'tsp': 1,
         'stage': 'temper', 'step': 1, 'why': ''},
        {'spice': 'Turmeric', 'amount': '1 tsp', 'tsp': 1, 'stage': 'bloom',
         'step': 2, 'why': ''},
    ]))
    order = [g['stage'] for g in payload['blend_groups']]
    assert order == ['temper', 'bloom', 'garnish'], 'bowls out of chronological order'
    assert [g['bowl'] for g in payload['blend_groups']] == [1, 2, 3]


def test_every_jar_lands_in_exactly_one_bowl():
    payload = schema.normalise(_payload(blend=[
        {'spice': n, 'amount': '1 tsp', 'tsp': 1, 'stage': s, 'step': 1, 'why': ''}
        for n, s in (('Cumin', 'bloom'), ('Coriander', 'bloom'),
                     ('Cayenne', 'mid'), ('Kasuri Methi', 'off_heat'))
    ]))
    grouped = [i['spice_key'] for g in payload['blend_groups'] for i in g['items']]
    assert sorted(grouped) == sorted(i['spice_key'] for i in payload['blend'])
    assert len(grouped) == len(set(grouped))


def test_the_stages_that_must_not_share_a_bowl_say_why():
    # A rule with no reason gets ignored the first time it is inconvenient.
    for stage in ('temper', 'last_five', 'off_heat', 'garnish'):
        assert schema.STAGE_KEEP_APART[stage], f'{stage} has no reason recorded'
    # ...and the ordinary cooking stages do not nag.
    for stage in ('bloom', 'early', 'mid'):
        assert stage not in schema.STAGE_KEEP_APART


def test_the_prompt_tells_the_model_stage_is_structural():
    from spice import prompt
    text = prompt.build_system_prompt()
    assert 'BOWLS' in text
    assert 'TEAsp' in text and 'TBsp' in text
