# CLAUDE.md

## What this is

**Spice** answers "what do I do with pork belly" with a picture of the real rack,
the right jars lit up and numbered in pan order. Phone-first, desktop-capable.

Live at **https://spice.yaqzan.dev** — deliberately public (doubles as a
portfolio piece). The rack visual and a frozen demo recipe are open to anyone;
everything else needs the request to arrive **from a tailnet peer**, via
`http://bookmaker.tailf242a1.ts.net:5003`. No access code, no unlock screen —
removed on purpose (see ops/README.md).

## Commands

```powershell
python -m spice serve            # API + built SPA on :5003 (loopback + tailnet)
python -m spice ask "pork belly" --lb 1.5 [--model X]
python -m spice prompt           # print the exact system prompt
python -m spice rate 12 8 --salt -1
python -m spice rack | stats | reshelve [--apply] | stock <spice> <state>
pytest                           # no network or API key needed

npm --prefix frontend run build  # tsc --noEmit && vite build
py -3.11 tools/make_icons.py     # favicon + home-screen icons -> frontend/public/
.\server.ps1 -Action start -Service spice     # api + cloudflared tunnel
```

`SPICE_OPEN=1` treats every caller as the owner. **Development only** — loopback
is where the public tunnel lands, so it opens the spend to the internet.

## Invariants

Cost real money, real food, or real trust.

- **`rack.py` is the only place a spice name, alias or handling rule exists.**
  No spice name in TypeScript — a second list drifts within a week. The sauce
  shelf is part of the registry; each bottle carries `salt_per_tbsp` (a tbsp of
  soy is a third of a pound of meat's salt budget) and the prompt subtracts it.
- **Salt lives in grams; the screen speaks only spoons.** Grams are the storage
  unit (brand-independent); `recipes.decorate()` converts to spoons of the
  configured brand on the way out, prose included (`schema.spoonify`). No two
  units for one thing on the card. Baseline: **7.5 g/lb (1.65%), measured out**
  — the rate every dish rated 8.5+ actually used; do not moderate it toward a
  textbook 1%. Table salt is 6.0 g/tsp vs. Diamond Crystal's 2.8 g/tsp — crossing
  that boundary in volume is a 2x error, and caused the one 2/10 dish. The rack's
  salt jar label reads from the same setting.
- **The card addresses the cook, second person.** He reads it about himself;
  third person reads like someone else's notes.
- **A tailnet peer address is the only credential, judged on the TCP socket,
  never a header.** The app is also on a public tunnel; trusting
  `X-Forwarded-For` would let anyone forge a peer. Bind loopback + the tailnet
  address, never `0.0.0.0`. Do not reintroduce a shared code.
- **The spend cap counts billed API calls, not saved recipes.** Counting
  successes made failures free, and one failure can bill three completions.
- **`rack.STAGES` is chronological and `schema.group_blend()` numbers the bowls
  from it.** The cook premixes before lighting the stove — a stage is a
  physical bowl, not a hint. Reordering the tuple reorders his counter. Steps
  name a bowl instead of re-listing spices, so the two cannot disagree.
- **Every jar is placed exactly once**, checked at boot. Layout writes are
  all-or-nothing — a half-applied layout points the picture at the wrong shelf.
- **A jar is the same size on every shelf.** Each SVG caps width in proportion
  to jar count, or a short shelf draws big jars and implies bigger containers.
- **Never write a relative date without an absolute one beside it.** "3d ago"
  goes stale in a saved payload, doc, or vault note. Prompt states today's date
  up front; every entry carries its real date.
- **`127.0.0.1`, never `localhost`** (IPv6-first resolution doubles timeouts;
  see global rules).
- **Bulk mutations dry-run by default**, `--apply` to commit.
- **`server.ps1` python services must use `py -3.11`**, not bare `python`.

## Layout

`rack.py` registry -> `prompt.py` (built fresh per request) -> OpenRouter ->
`schema.normalise()` -> SQLite -> `api.py` -> SVG rack + recipe card.

| Module | Owns |
|---|---|
| `rack.py` | The registry: names, aliases, handling rules, default shelf |
| `schema.py` | The JSON contract, name resolution, measurement formatting |
| `prompt.py` | System prompt, assembled from live state — nothing hand-kept |
| `db.py` | Layout, stock, recipes, ratings, spend ledger |
| `auth.py` | Tailnet check, daily spend cap |
| `recipes.py` | Request pipeline, rack view, re-shelve proposal |
| `vault.py` | One rating reminder line in the owner's Obsidian To Do |

## Detail

- [.claude/docs/rack.md](.claude/docs/rack.md) — shelf logic, name-resolution traps
- [.claude/docs/prompt.md](.claude/docs/prompt.md) — every prompt rule and its evidence
- [.claude/docs/audit.md](.claude/docs/audit.md) — review of the chat project this replaced
- [.claude/docs/vault.md](.claude/docs/vault.md) — the Obsidian rating reminder
- [ops/README.md](ops/README.md) — hosting, the tunnel, why the code is gone
