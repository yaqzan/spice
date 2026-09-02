# The rating reminder in Obsidian

One line, in one file: `C:\Obsidian\Mycelium\To Do\Recipes.md`.

A generated recipe costs real money and is worth nothing to the app until
rated — ratings move the salt correction, heat correction, and cuisine
rotation. The case: **not one app-generated recipe had ever been rated, while
twelve of fourteen hand-entered dishes carried a score.** The app was never
short a rating screen — it was short of anything that asked.

```
---
cssclasses:
  - todo-data
source: spice
---

## To rate

- [ ] 2026-08-24 — Ancho Chipotle Thighs #24 — [rate](http://bookmaker.tailf242a1.ts.net:5003/recipe/24)

## Rated

- [x] 2026-08-22 — Suya Peanut Chicken #7 — [rate](…/recipe/7) ✅ 2026-08-24
```

Generating adds the line; rating ticks it and moves it down. That's the whole
feature.

## What most of these lines will do, honestly

Get ticked "never made it" — the owner generates recipes he doesn't cook (four
in one testing morning). **That's the feature working, not failing:** the
missing signal was never "I forgot to rate it," it was "I cooked this one." A
two-tap dismissal is a fine outcome for a line that cost one keystroke.

## Why one file, not a note per recipe

The vault was rebuilt specifically to undo note-per-task. Spore's
`config/rules.toml` records the receipt: 231 imported pages whose entire
content was three frontmatter keys, costing *"231 entries in the quick
switcher, the graph and every search result."* A rating nudge is a name, a
date, a link — one line.

## Where it must never go

- **Not the Spice engineering board.** `Projects.base` selects tickets
  vault-wide on `file.hasProperty("project")` — that property *is* board
  membership, no folder to hide in. Never write a `project:` key here.
- **Not under `Food/`.** Spore recognises a restaurant by folder shape
  (`root.glob("*/*.md")` where the note's stem matches its parent) — a recipes
  folder there becomes restaurant #121 and gets rewritten.
- **Not appended to `To Do\Tasks.md`.** `source: spore`; a full Spore
  `transform` rebuilds it from source rows and drops anything appended.
  Unprioritised lines also fall into the `now` bucket, next to a prescription
  pickup.
- **Not a new top-level folder.** `home.py` auto-appends any unclaimed
  top-level folder to the Home launcher's tiles.

`To Do/` is right for another reason: pinned first in `Home.md`, and already
thumb-sized on his phone — where a nudge has to land.

## The rules baked into the line

- **`#<id>` is the identity.** Lines are found by word-boundaried id, never by
  title (models write those, and repeat them) or position. `#8` must never
  match inside `#80`.
- **ISO date first**, so the To Do app's alphabetical sort is also
  chronological (without it `#10` sorts above `#8`).
- **The link is the tailnet address**, from `config.tailnet_url()`, route
  `/recipe/<id>`. Never `https://spice.yaqzan.dev/...` — cloudflared connects
  over loopback, so even a phone on the tailnet arrives looking like a
  stranger and 403s. With Tailscale down there's no honest link, so it
  degrades to naming the CLI command instead.
- **Only ` ` and `x` as checkbox marks**; `⏫ ⏬ 🔺 🔼 🔽`, `📅 <date>` and
  `✅ <date>` are stripped from titles — the Spore To Do tooling parses those
  as metadata, and a line it can't parse is simply gone from the rebuilt tab.
- **The title never goes in frontmatter.** Spore's `check.py` parses every
  note's frontmatter vault-wide; a model title containing a colon would redden
  a check in an unrelated repo.

## The three things that must not break

1. **pytest must never write to the vault.** The suite drives generation to a
   200 at eleven call sites against fresh DBs where ids restart at 1 — an
   unguarded hook would append fake dinners every run and collide with real
   recipe #1. Three guards: `_enabled()` short-circuits on
   `PYTEST_CURRENT_TEST`; the path is read through `config.TODO_FILE` at call
   time so a test can move it; the autouse `temp_db` fixture repoints it at
   `tmp_path` regardless. Tests that need the vault to run override
   `_enabled` rather than clearing the env var — **pytest re-sets
   `PYTEST_CURRENT_TEST` at the start of every phase**, so a `delenv` in a
   fixture is gone by the time the test body runs.
2. **Generation must never fail on a vault error.** By the time the hook runs,
   the model has been paid. Every call is wrapped; a locked file or unmounted
   drive costs one printed sentence.
3. **The note is rebuilt from the FILE, never the database.** Makes a deleted
   line a durable "stop asking me" — nothing here knows what used to be there.
   Rebuilding from the database would resurrect every ticked line.

## Where the hook sits

`recipes.generate()` immediately after `db.save_recipe()`, and `recipes.rate()`
— both CLI and API route through these so a reminder can't be ticked in one
place and left standing in the other.

Deliberately **not** `db.save_recipe()` itself: `db.log_historical()` calls it,
so `spice log` would open a reminder for a dish cooked months ago and close it
one line later. `cli.py`'s `cmd_log` calls `db.rate()` directly instead — a
logged dish never opened a reminder, nothing to close.

## Not built, on purpose

**No `.base`, no board.** A checklist line has no frontmatter, invisible to
every base in the vault — cheapest possible isolation, no way to fail by
rendering an empty board.

**No read-back from Obsidian.** A checkbox carries one bit; a rating carries a
score, a salt delta, a heat delta and notes — and the salt delta is what moves
the 7.5 g/lb baseline. Ticking a box means "stop asking," nothing more.

## Phase 2, not done

`Recipes.md` is a valid tickable checklist today but not registered as a To Do
*tab* — needs a `[[todo.list]]` block in `C:\Development\Spore\config\rules.toml`
and a `py pipeline.py todo` run **from the Spore repo**. That run rewrites
other tab notes per Spore's own `[todo.drop]` config, and registering the tab
makes unrated recipes count toward the Home page's To Do badge.
