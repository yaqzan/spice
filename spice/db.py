"""SQLite connection, schema, and the settings/layout accessors.

SQLite because this is a single-cook database on a single machine — a few hundred
recipes at most — and a one-file store means the entire history is backed up by
copying it. WAL is on so a long OpenRouter call writing a recipe never blocks the
rack view from reading.

Three things live in here that deserve naming, because they are the difference
between this app and the chat project it replaces:

* `ratings` is the feedback loop. In the chat version, calibration lived in a
  hand-edited markdown block that nobody ever edited. Here every cooked dish
  writes a row and every future prompt reads them all.
* `layout` is mutable. The rack is physical furniture that gets rearranged, so
  where a jar sits is data, not a constant.
* `spice_state` is stock. A recipe that calls for a jar that ran out three weeks
  ago is worse than no recipe.
"""

from __future__ import annotations

import json
import sqlite3
import threading

from . import config, rack

SCHEMA_VERSION = 1

_local = threading.local()

SCHEMA = """
-- One row per generated recipe. `payload` is the validated model response
-- exactly as the frontend renders it, so a recipe opened six months from now
-- looks identical to the day it was cooked even if the schema has moved on.
CREATE TABLE IF NOT EXISTS recipes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    query         TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    protein       TEXT,
    cuisine       TEXT,
    heat_level    INTEGER,
    model         TEXT,
    payload       TEXT    NOT NULL,          -- json
    prompt_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd      REAL,
    archived      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_recipes_created ON recipes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recipes_cuisine ON recipes(cuisine);

-- The feedback loop. Salt and heat are rated on their OWN axes rather than
-- folded into the overall score, because the two failures on record were both
-- seasoning-level errors that got remembered as flavour lessons: the 2/10 steak
-- was over-salted, and "never use a blend on steak" is the wrong conclusion to
-- draw from that. Separate axes mean the model can be told "your salt runs 20%
-- hot" without also being told the recipe was bad.
CREATE TABLE IF NOT EXISTS ratings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id   INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    rated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    overall     REAL    NOT NULL,            -- 1-10, halves allowed: the two
                                            -- best dishes on record are 9.5
                                            -- and 8.5, and int() ate both
    salt_delta  INTEGER NOT NULL DEFAULT 0,  -- -2 way under .. +2 way over
    heat_delta  INTEGER NOT NULL DEFAULT 0,  -- -2 too mild .. +2 too hot
    would_repeat INTEGER,                    -- 1 yes / 0 no / null unsaid
    notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_ratings_recipe ON ratings(recipe_id);

-- Which jars a recipe actually called for. Denormalised on purpose: this is the
-- table the re-shelving proposal reads, and it wants to be a cheap GROUP BY.
CREATE TABLE IF NOT EXISTS spice_uses (
    recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    spice_key  TEXT    NOT NULL,
    used_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (recipe_id, spice_key)
);

CREATE INDEX IF NOT EXISTS idx_uses_spice ON spice_uses(spice_key);

-- Where every jar currently sits. Seeded from rack.DEFAULT_LAYOUT, then owned by
-- the user: the app proposes a frequency-sorted arrangement, the user accepts or
-- ignores it, and only an accepted proposal writes here.
CREATE TABLE IF NOT EXISTS layout (
    spice_key  TEXT PRIMARY KEY,
    rack       TEXT NOT NULL,
    row        INTEGER NOT NULL,
    col        INTEGER NOT NULL
);

-- Stock and age. `opened_on` matters more than people think: ground spice is
-- most of the way to sawdust a year after opening, and "why did that taste of
-- nothing" is usually this and not the recipe.
CREATE TABLE IF NOT EXISTS spice_state (
    spice_key  TEXT PRIMARY KEY,
    stock      TEXT NOT NULL DEFAULT 'ok',   -- ok | low | out
    opened_on  TEXT,
    note       TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- One row per BILLED OpenRouter completion, written before the call returns and
-- regardless of whether it succeeds.
--
-- The spend cap used to count rows in `recipes`, which are only written when the
-- whole pipeline succeeds. That made every failed ask free and uncounted -- and
-- a single failed ask fires up to three completions through the schema fallback
-- chain, so a client stuck in a retry loop could spend without bound while the
-- cap read zero. That is precisely the failure the cap exists to stop, so it now
-- counts what is actually billed.
CREATE TABLE IF NOT EXISTS api_calls (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    called_at TEXT NOT NULL DEFAULT (datetime('now')),
    model     TEXT
);

CREATE INDEX IF NOT EXISTS idx_api_calls_at ON api_calls(called_at);
"""

# Cook profile + app settings. Defaults encode the taste profile the chat project
# established; every one of them is editable from the settings screen.
DEFAULT_SETTINGS = {
    'model': config.DEFAULT_MODEL,

    # THE most consequential setting in the app. Diamond Crystal is ~2.8g per
    # teaspoon, Morton kosher ~4.8g, fine table salt ~6.0g. A recipe written for
    # one and executed with another is off by up to 2x, which is exactly the size
    # of the error in the "way oversalted" steak on record.
    #
    # This kitchen uses fine iodized table salt. The old chat instructions
    # targeted "1 tsp Diamond Crystal per lb" and were executed with a teaspoon of
    # table salt, so the written target (0.62% of weight) and the actual practice
    # (1.32%) were never the same number.
    'salt_brand': 'table',

    # 1.65% of the protein's weight, and it is the amount MEASURED OUT -- what
    # he scoops, which is the only quantity a recipe can actually instruct.
    #
    # There is no net-of-loss figure here on purpose. An earlier version carried
    # one (~20% left on hands and bowls, so "really" 6.0 g/lb) and it was pure
    # inference: the bowl empties into the pan every time, so the loss is
    # transfer residue and cannot be weighed. It also invited exactly the wrong
    # correction -- reading 6.0 as the true number and writing it into this
    # gross field. The band below is measured end to end in scooped grams
    # against actual ratings, so the loss is already inside it, whatever it is.
    #
    # It is 1 1/4 TEAsp of this kitchen's own salt per pound: the rate every dish
    # rated 8.5 or above was actually seasoned at, including the 9.5 Jamaican.
    # The old 5.6 was reverse-engineered from the 7/10 Tex Mex -- the second
    # WORST dish on record -- whose shortfall the prompt's own doctrine already
    # blames on dilution across three cups of rice, and 5.6 gross lands at the
    # very 0.99% that had been judged "slightly under" to begin with.
    #
    # Three numbers get proposed as "corrections" to this and all three are
    # wrong: 3.5 (reading the memory's Diamond Crystal label, which was fiction
    # -- he has always used table salt), 5.6 (the retired value), and 6.0 (the
    # NET figure written into this GROSS field). Ratings move it from here.
    'salt_grams_per_lb': '7.5',

    'heat_tolerance': '4',             # 1-5; 4 = likes a real kick
    'acid_policy': 'background',       # none | background | free
    'default_protein_lb': '1.0',
    'servings': '2',

    # Backstop on spend. Counts BILLED OpenRouter calls per calendar day, not
    # finished recipes -- a recipe is normally one call, up to three when the
    # model fumbles the JSON shape and the fallback chain retries. 0 disables.
    # Guards against a retry loop as much as against a stranger.
    'daily_ask_limit': '60',
}

# Settings that existed once and must not linger. `access_salt` and `access_hash`
# held the shared passphrase before authorisation became "are you a tailnet peer"
# (see auth.py); removing them from DEFAULT_SETTINGS stops new databases growing
# them, but every database that already ran the old build still has the rows, and
# `settings()` reads whatever the table holds. So they are dropped on boot rather
# than filtered on the way out -- a secret nobody can use is still a secret worth
# not storing.
RETIRED_SETTINGS = ('access_salt', 'access_hash')

# Grams per level teaspoon. The reason salt is stored in grams everywhere else.
SALT_BRANDS = {
    'diamond_crystal': ('Diamond Crystal kosher', 2.8),
    'morton_kosher': ('Morton kosher', 4.8),
    'table': ('fine table salt', 6.0),
}


def connect() -> sqlite3.Connection:
    """One connection per thread. Flask serves requests on several."""
    conn = getattr(_local, 'conn', None)
    if conn is None:
        config.ensure_dirs()
        conn = sqlite3.connect(config.DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        _local.conn = conn
    return conn


def query(sql: str, params: tuple = ()) -> list:
    return connect().execute(sql, params).fetchall()


def one(sql: str, params: tuple = ()):
    return connect().execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()):
    conn = connect()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur


def ensure_schema() -> None:
    rack.validate_default_layout()
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    _seed_layout()
    _seed_settings()
    _drop_retired_settings()


def _seed_layout() -> None:
    """Fill in any jar that has no position yet.

    Written as a fill rather than a reset so it is safe on every boot: a rack the
    user has rearranged is never stomped, and a spice newly added to the registry
    lands in its default slot instead of vanishing from the visual.
    """
    known = {r['spice_key'] for r in query('SELECT spice_key FROM layout')}
    rows = []
    for rack_name in rack.RACKS:
        for row_index, row in enumerate(rack.DEFAULT_LAYOUT[rack_name]):
            for col_index, key in enumerate(row):
                if key not in known:
                    rows.append((key, rack_name, row_index, col_index))
    if rows:
        conn = connect()
        conn.executemany(
            'INSERT OR IGNORE INTO layout (spice_key, rack, row, col) VALUES (?,?,?,?)', rows)
        conn.commit()


def _seed_settings() -> None:
    conn = connect()
    conn.executemany('INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)',
                     list(DEFAULT_SETTINGS.items()))
    conn.commit()


def _drop_retired_settings() -> None:
    """Delete settings the app no longer has any code to read.

    Runs after the seed, not before -- otherwise seeding would put back what this
    just removed. Safe to run on every boot; after the first one it deletes
    nothing.
    """
    conn = connect()
    conn.executemany('DELETE FROM settings WHERE key = ?',
                     [(key,) for key in RETIRED_SETTINGS])
    conn.commit()


# ── settings ─────────────────────────────────────────────────────────────────

def settings() -> dict:
    out = dict(DEFAULT_SETTINGS)
    for row in query('SELECT key, value FROM settings'):
        out[row['key']] = row['value']
    return out


def setting(key: str, default=None):
    row = one('SELECT value FROM settings WHERE key = ?', (key,))
    if row:
        return row['value']
    return DEFAULT_SETTINGS.get(key, default)


def set_setting(key: str, value) -> None:
    execute('INSERT INTO settings (key, value) VALUES (?,?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value', (key, str(value)))


def salt_brand() -> tuple:
    """(label, grams per teaspoon) for whichever salt is actually on the shelf."""
    return SALT_BRANDS.get(setting('salt_brand'), SALT_BRANDS['diamond_crystal'])


# ── layout ───────────────────────────────────────────────────────────────────

def layout() -> dict:
    """`{spice_key: {'rack','row','col'}}` for every placed jar."""
    return {r['spice_key']: {'rack': r['rack'], 'row': r['row'], 'col': r['col']}
            for r in query('SELECT spice_key, rack, row, col FROM layout')}


def set_layout(placements: list) -> None:
    """Replace the whole arrangement in one transaction.

    All-or-nothing because a half-applied layout would leave two jars claiming
    one slot and the visual pointing at the wrong shelf.
    """
    conn = connect()
    with conn:
        conn.execute('DELETE FROM layout')
        conn.executemany(
            'INSERT INTO layout (spice_key, rack, row, col) VALUES (?,?,?,?)',
            [(p['spice_key'], p['rack'], int(p['row']), int(p['col'])) for p in placements])


# ── stock ────────────────────────────────────────────────────────────────────

def spice_states() -> dict:
    return {r['spice_key']: dict(r) for r in query('SELECT * FROM spice_state')}


def set_spice_state(spice_key: str, stock: str, opened_on=None, note=None) -> None:
    execute("""INSERT INTO spice_state (spice_key, stock, opened_on, note, updated_at)
               VALUES (?,?,?,?, datetime('now'))
               ON CONFLICT(spice_key) DO UPDATE SET
                 stock = excluded.stock,
                 opened_on = COALESCE(excluded.opened_on, spice_state.opened_on),
                 note = COALESCE(excluded.note, spice_state.note),
                 updated_at = datetime('now')""",
            (spice_key, stock, opened_on, note))


# `using_up` is available like `ok`, but the prompt is told to SPEND it: a jar
# that is on its way out and will not be rebought. It exists so "use this up"
# is a state the app can reason about rather than a note somebody has to
# remember, and so the substitution rules travel with the jar.
STOCK_STATES = ('ok', 'low', 'using_up', 'out')


def using_up() -> set:
    return {r['spice_key'] for r in
            query("SELECT spice_key FROM spice_state WHERE stock = 'using_up'")}


def out_of_stock() -> set:
    return {r['spice_key'] for r in query("SELECT spice_key FROM spice_state WHERE stock = 'out'")}


# ── recipes ──────────────────────────────────────────────────────────────────

TRACKED_CUISINES = (
    'Indian', 'Korean', 'Mexican', 'Tex-Mex', 'Middle Eastern', 'Chinese',
    'West African', 'Cajun', 'Caribbean', 'Thai', 'Japanese', 'North African',
    'Ethiopian', 'Turkish', 'Italian', 'American BBQ', 'American', 'Cuban',
)

# Spellings that mean an existing lane. The rotation buckets on the stored
# string, so "Korean-inspired" read as a lane never cooked while Korean sat next
# to it looking cold -- and the model was invited to repeat what it just made.
_CUISINE_ALIASES = {
    'tex mex': 'Tex-Mex', 'texmex': 'Tex-Mex', 'mexican/tex-mex': 'Tex-Mex',
    'cajun/southern': 'Cajun', 'creole': 'Cajun', 'nola': 'Cajun',
    'south indian': 'Indian', 'north indian': 'Indian', 'punjabi': 'Indian',
    'sichuan': 'Chinese', 'szechuan': 'Chinese', 'cantonese': 'Chinese',
    'levantine': 'Middle Eastern', 'lebanese': 'Middle Eastern',
    'jamaican': 'Caribbean', 'nigerian': 'West African', 'suya': 'West African',
    'moroccan': 'North African', 'bbq': 'American BBQ',
    'american bbq': 'American BBQ', 'southern': 'American',
}

# Qualifiers a model reaches for when it does not want to claim authenticity.
# They describe its confidence, not a different cuisine.
_CUISINE_HEDGES = ('-inspired', ' inspired', '-style', ' style', '-ish',
                   ' fusion', '-leaning', ' leaning')


def canonicalise_cuisine(name: str) -> str:
    """Fold a written cuisine onto the lane it belongs to.

    Applied on WRITE, so the rotation, the history table and anything added
    later all agree without each having to remember to normalise.
    """
    text = (name or '').strip()
    if not text:
        return text
    for hedge in _CUISINE_HEDGES:
        if text.lower().endswith(hedge):
            text = text[:-len(hedge)].strip(' -')
            break
    lowered = text.lower()
    if lowered in _CUISINE_ALIASES:
        return _CUISINE_ALIASES[lowered]
    for known in TRACKED_CUISINES:
        if known.lower() == lowered:
            return known
    # An unknown lane keeps the model's own words, minus the hedge. Cooking
    # something new is legitimate, and snapping it to the nearest known name
    # would hide it from the rotation -- the one thing the rotation exists to
    # notice.
    return text


def save_recipe(payload: dict, meta: dict) -> int:
    cur = execute("""INSERT INTO recipes
                     (query, title, protein, cuisine, heat_level, model, payload,
                      prompt_tokens, output_tokens, cost_usd)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (meta.get('query', ''), payload.get('title', 'Untitled'),
                   payload.get('protein'),
                   canonicalise_cuisine(payload.get('cuisine')),
                   payload.get('heat_level'), meta.get('model'),
                   json.dumps(payload, ensure_ascii=False),
                   meta.get('prompt_tokens'), meta.get('output_tokens'),
                   meta.get('cost_usd')))
    recipe_id = cur.lastrowid

    keys = {item['spice_key'] for item in payload.get('blend', []) if item.get('spice_key')}
    if keys:
        conn = connect()
        conn.executemany('INSERT OR IGNORE INTO spice_uses (recipe_id, spice_key) VALUES (?,?)',
                         [(recipe_id, key) for key in sorted(keys)])
        conn.commit()
    return recipe_id


HISTORICAL_MODEL = 'historical'


def log_historical(title: str, cuisine: str, protein: str, notes: str = '',
                   when: str = '') -> int:
    """Record a dish this app did not generate, so it can carry a rating.

    Everything the feedback loop knows came through the billed generate path,
    which means the thirteen dishes actually cooked before this app existed --
    including the 9.5 that the salt baseline is derived from -- could not be
    entered at all, and `rate` 404s without a parent row.

    The payload deliberately has no `blend`. `save_recipe` counts spice_uses
    from blend rows, and a remembered dish has no reliable spice list; inventing
    one would put fictional usage counts into the re-shelve proposal, which
    physically moves jars on a wall. Cuisine and the rating are what these rows
    are for: rotation and calibration.
    """
    payload = {'title': title, 'cuisine': cuisine, 'protein': protein,
               'why_this': notes or 'Cooked before this app existed.',
               'blend': [], 'steps': [], 'from_kitchen': []}
    recipe_id = save_recipe(payload, {'query': '<logged from memory>',
                                      'model': HISTORICAL_MODEL, 'cost_usd': 0})
    # Without a real date these all land on the day they were typed, and the
    # cuisine rotation -- which is pure recency -- concludes that the 2/10 steak
    # from months ago was cooked this afternoon and starts steering away from
    # the lane. An approximate date is far better than today's.
    if when:
        execute('UPDATE recipes SET created_at = ? WHERE id = ?', (when, recipe_id))
    return recipe_id


def recipe(recipe_id: int):
    row = one('SELECT * FROM recipes WHERE id = ?', (recipe_id,))
    if not row:
        return None
    out = dict(row)
    out['payload'] = json.loads(out['payload'])
    out['rating'] = rating_for(recipe_id)
    return out


def rating_for(recipe_id: int):
    row = one('SELECT * FROM ratings WHERE recipe_id = ? ORDER BY rated_at DESC LIMIT 1',
              (recipe_id,))
    return dict(row) if row else None


def rate(recipe_id: int, overall: int, salt_delta: int = 0, heat_delta: int = 0,
         would_repeat=None, notes: str = '') -> None:
    execute("""INSERT INTO ratings
               (recipe_id, overall, salt_delta, heat_delta, would_repeat, notes)
               VALUES (?,?,?,?,?,?)""",
            (recipe_id, float(overall), int(salt_delta), int(heat_delta),
             would_repeat, notes or ''))


def history(limit: int = 50, rated_only: bool = False) -> list:
    sql = """SELECT r.id, r.created_at, r.query, r.title, r.protein, r.cuisine,
                    r.heat_level, r.archived,
                    g.overall, g.salt_delta, g.heat_delta, g.notes, g.would_repeat
             FROM recipes r
             LEFT JOIN ratings g ON g.id = (
                 SELECT id FROM ratings WHERE recipe_id = r.id ORDER BY rated_at DESC LIMIT 1)
             WHERE r.archived = 0"""
    if rated_only:
        sql += ' AND g.overall IS NOT NULL'
    sql += ' ORDER BY r.created_at DESC LIMIT ?'
    return [dict(r) for r in query(sql, (limit,))]


def cuisine_recency() -> list:
    """`[(cuisine, days_since_last_cooked, times_cooked, last_date)]`, freshest first.

    The DATE is carried alongside the gap, and both go into the prompt, because a
    gap on its own is a fact with an expiry on it. "3 days ago" is true for one
    day; anything that stores or quotes it — a saved prompt, a doc, a note in the
    vault, a future session reading back this conversation — is then holding a
    number that quietly became wrong. The date never rots, and the gap is what
    the model actually reasons with, so it gets both.

    Replaces the chat project's hand-edited "Last used: Tex Mex" line — this is
    the same information, except it cannot go stale.

    The question is "what has he EATEN lately", not "what has the model written
    lately" — generating a recipe costs a keystroke, and four generated in one
    morning of testing had the prompt reporting Korean, Indian, West African and
    Middle Eastern as all cooked that day and steering away from every one.

    So a row counts if there is evidence a human put it on a plate, and there are
    two kinds. A RATING is the obvious one. The other is having been entered
    through `spice log`, which exists only to record a dish he cooked — the act
    of logging one IS the claim that he cooked it. Requiring a rating as well
    would lose the dishes he remembers eating but not scoring, which is exactly
    the Korean beef that left Korean reading as a lane never touched.
    """
    rows = query(f"""SELECT r.cuisine,
                           CAST(julianday('now') - julianday(MAX(r.created_at)) AS INTEGER) AS days,
                           COUNT(*) AS n,
                           MAX(r.created_at) AS last
                    FROM recipes r
                    LEFT JOIN ratings g ON g.recipe_id = r.id
                    WHERE r.cuisine IS NOT NULL AND r.cuisine != '' AND r.archived = 0
                      AND (g.id IS NOT NULL OR r.model = '{HISTORICAL_MODEL}')
                    GROUP BY r.cuisine ORDER BY MAX(r.created_at) DESC""")
    return [(r['cuisine'], r['days'], r['n'], (r['last'] or '')[:10]) for r in rows]


def usage_counts() -> dict:
    """`{spice_key: times called for}` — the input to the re-shelve proposal."""
    return {r['spice_key']: r['n'] for r in query(
        'SELECT spice_key, COUNT(*) n FROM spice_uses GROUP BY spice_key')}


def record_api_call(model: str) -> None:
    """Log a billed completion. Called before the request, so a crash still counts."""
    execute('INSERT INTO api_calls (model) VALUES (?)', (model,))


def api_calls_today() -> int:
    row = one("SELECT COUNT(*) c FROM api_calls WHERE called_at >= date('now')")
    return int(row['c']) if row else 0


def rated_count() -> int:
    """How many dinners the calibration is actually standing on.

    The prompt needs this separately from the bias itself, because a mean of 0.0
    over an empty table and a mean of 0.0 over twelve dinners are opposite
    claims, and the calibration block used to print both as "landing on target".
    """
    row = one('SELECT COUNT(*) c FROM ratings')
    return int(row['c']) if row else 0


# How many recent ratings the correction listens to. Unbounded averaging means a
# dish from six months ago pulls on tonight's seasoning forever, and it gets
# harder to move the number the more you cook — the opposite of a feedback loop.
BIAS_WINDOW = 15


def _recent_mean(column: str) -> float:
    row = one(f'SELECT AVG({column}) avg FROM '
              '(SELECT {0} FROM ratings ORDER BY rated_at DESC, id DESC LIMIT ?)'
              .format(column), (BIAS_WINDOW,))
    return float(row['avg']) if row and row['avg'] is not None else 0.0


def salt_bias() -> float:
    """Mean salt_delta across recent rated dishes: >0 means recipes run salty.

    Fed back into the prompt as an explicit correction so the calibration
    improves with evidence rather than with anecdote.
    """
    return _recent_mean('salt_delta')


def heat_bias() -> float:
    return _recent_mean('heat_delta')
