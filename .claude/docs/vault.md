# The rating reminder in Obsidian

**One line per recipe, in one file:** `SPICE_TODO_FILE` from the gitignored `.env` (the owner's is
`C:\Obsidian\Mycelium\To Do\Recipes.md`). Unset = feature off.

Why: ratings drive the salt correction, heat correction and cuisine rotation, but **no
app-generated recipe had ever been rated, while 12 of 14 hand-entered dishes had a score.** The
app had a rating screen; nothing asked.

```
---
cssclasses:
  - todo-data
source: spice
---

## To rate

- [ ] 2026-08-24 — Ancho Chipotle Thighs #24 — [rate](http://<machine>.<tailnet>.ts.net:5003/recipe/24)

## Rated

- [x] 2026-08-22 — Suya Peanut Chicken #7 — [rate](…/recipe/7) ✅ 2026-08-24
```

Generating adds the line; rating ticks it and moves it down.

**Most lines will get ticked "never made it"**, since the owner generates recipes he doesn't cook.
That's fine: the missing signal was "I cooked this one".

## Why one file, not a note per recipe

The vault was rebuilt to undo note-per-task (Spore's `config/rules.toml`: 231 imported pages of
nothing but frontmatter cluttered the quick switcher, graph and search). A nudge is one line.

## Where it must never go

- **Not the Spice engineering board.** `Projects.base` selects vault-wide on
  `file.hasProperty("project")`, so that property is board membership. Never write a `project:`
  key.
- **Not under `Food/`.** Spore treats `*/*.md` whose stem matches its folder as a restaurant; a
  recipes folder there gets rewritten.
- **Not appended to `To Do\Tasks.md`.** It's `source: spore`; a Spore `transform` rebuilds it and
  drops appended lines. Unprioritised lines also land in the `now` bucket.
- **Not a new top-level folder.** `home.py` adds any unclaimed top-level folder to the Home tiles.

`To Do/` is pinned first in `Home.md` and already works on his phone, where the nudge has to land.

## Rules for the line

- **`#<id>` is the identity.** Lines are found by word-boundaried id, never by title (models repeat
  titles) or position. `#8` must never match inside `#80`.
- **ISO date first**, so alphabetical sort is chronological.
- **The link is the tailnet address** from `config.tailnet_url()`, route `/recipe/<id>`. Never
  `https://spice.yaqzan.dev/...`: cloudflared connects over loopback, so even a tailnet phone
  arrives as a stranger and gets refused. With Tailscale down, the line names the CLI command
  instead (`spice rate <id>`).
- **Only ` ` and `x` as checkbox marks.** `⏫ ⏬ 🔺 🔼 🔽`, `📅 <date>` and `✅ <date>` are stripped
  from titles: Spore's To Do tooling reads them as metadata and drops lines it can't parse.
- **The title never goes in frontmatter.** Spore's `check.py` parses frontmatter vault-wide; a
  colon in a model title would fail a check in another repo.

## Three things that must not break

1. **pytest never writes to the vault.** The suite generates recipes against fresh DBs (ids restart
   at 1), so an unguarded hook would add fake dinners and collide with real #1. Three guards:
   `_enabled()` short-circuits on `PYTEST_CURRENT_TEST`; the path is read through
   `config.TODO_FILE` at call time; the autouse `temp_db` fixture points it at `tmp_path`. Tests
   that need the vault override `_enabled` instead of clearing the env var: **pytest re-sets
   `PYTEST_CURRENT_TEST` every phase**, so a fixture's `delenv` is gone by the test body.
2. **Generation never fails on a vault error.** The model is already paid for. Every call is
   wrapped; a locked file or missing drive prints one sentence.
3. **The note is rebuilt from the FILE, never the database.** A deleted line then means "stop
   asking"; rebuilding from the DB would bring back every ticked line.

## Where the hook sits

- In `recipes.generate()` right after `db.save_recipe()`, and in `recipes.rate()`. CLI and API
  both go through these, so a reminder can't be ticked in one and left in the other.
- **Not in `db.save_recipe()` itself:** `db.log_historical()` calls it, so `spice log` would open
  and close a reminder for an old dish. `cli.py`'s `cmd_log` calls `db.rate()` directly.

## Not built, on purpose

- **No `.base`, no board.** A checklist line has no frontmatter, so no base in the vault sees it.
- **No read-back from Obsidian.** A checkbox is one bit; a rating is score, salt delta, heat delta
  and notes (the salt delta moves the 7.5 g/lb baseline). Ticking means "stop asking", nothing
  more.

## Phase 2, not done

`Recipes.md` works as a checklist but isn't a registered To Do *tab*. That needs a `[[todo.list]]`
block in `C:\Development\Spore\config\rules.toml` and `py pipeline.py todo` run **from the Spore
repo**. That run also rewrites other tab notes per Spore's `[todo.drop]` config, and unrated
recipes would then count toward the Home page's To Do badge.
