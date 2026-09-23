# CLAUDE.md

## What this is

**Spice** answers "what do I do with pork belly" with a picture of the real rack, the right jars
lit up and numbered in pan order. Phone-first.

- Live at **https://spice.yaqzan.dev**, public on purpose. Anyone gets the rack and a frozen demo
  recipe; the rest needs a **tailnet peer** (URL printed by `serve`). No access code (removed).
- **Public repo (github.com/yaqzan/spice), plug and play.** Owner state is gitignored: `data/`
  (DB + key), `.env` (`SPICE_PUBLIC_ORIGIN`, `SPICE_TODO_FILE`), `ops/cloudflared-config.yml`,
  `ops/Caddyfile` (`.example` copies tracked). No machine path, domain, tailnet name/IP or tunnel
  UUID in tracked files. Pre-2026-09-23 history: private `yaqzan/spice-archive`.

## Commands

```powershell
python -m spice serve            # API + built SPA on :5003 (loopback + tailnet)
python -m spice ask "pork belly" --lb 1.5 [--model X]
python -m spice prompt           # print the exact system prompt
python -m spice rate 12 8 --salt -1
python -m spice log "Title" --cuisine X [--rating N]   # record a dish cooked outside the app
python -m spice rack | stats | reshelve [--apply] | stock <spice> <state>
pytest                           # no network or API key needed

npm --prefix frontend run build  # tsc --noEmit && vite build
py -3.11 tools/make_icons.py     # favicon + home-screen icons -> frontend/public/
C:\Development\server.ps1 -Action start -Service spice    # api + tunnel (this machine)
ops\windows\install-tasks.ps1 -Controller C:\Development\server.ps1   # watchdog task; ELEVATED shell
```

**`SPICE_OPEN=1` treats every caller as the owner. Development only:** the public tunnel lands on
loopback, so it opens the spend to the internet.

## Invariants

- **`rack.py` is the only place a spice name, alias or handling rule exists.** No spice name in
  TypeScript (a second list drifts). The sauce shelf is in the registry; each bottle's
  `salt_per_tbsp` is subtracted by the prompt.
- **Salt is stored in grams; the screen shows only spoons.** `recipes.decorate()` converts to
  spoons of the configured brand, prose included (`schema.spoonify`). Baseline **7.5 g/lb
  (1.65%)**, measured from every dish rated 8.5+; don't moderate it toward 1%. Table salt 6.0 g/tsp
  vs Diamond Crystal 2.8 g/tsp: mixing them up by volume is a 2x error. The salt jar label reads
  the same setting.
- **The card speaks to the cook in second person.**
- **A tailnet peer address is the only credential, judged on the TCP socket, never a header**
  (`X-Forwarded-For` is forgeable via the public tunnel). Bind loopback + tailnet address, never
  `0.0.0.0`. Don't bring back a shared code.
- **The spend cap counts billed API calls, not saved recipes.** One failure can bill three calls.
- **`rack.STAGES` is chronological; `schema.group_blend()` numbers the bowls from it.** A stage is
  a physical premix bowl, so reordering the tuple reorders the counter. Steps name a bowl instead
  of re-listing spices.
- **Every jar is placed exactly once**, checked at boot. Layout writes are all-or-nothing.
- **A jar is the same size on every shelf.** Each SVG caps width by jar count.
- **Never write a relative date without the absolute one beside it.** The prompt states today's
  date first; every entry carries its real date.
- **`127.0.0.1`, never `localhost`** (IPv6-first resolution doubles timeouts).
- **Bulk mutations dry-run by default**, `--apply` to commit.
- **`server.ps1` python services use `py -3.11`**, not bare `python`.

## Layout

`rack.py` registry -> `prompt.py` (built per request) -> OpenRouter -> `schema.normalise()` ->
SQLite -> `api.py` -> SVG rack + recipe card.

| Module | Owns |
|---|---|
| `rack.py` | Registry: names, aliases, handling rules, default shelf |
| `schema.py` | JSON contract, name resolution, units |
| `prompt.py` | System prompt, built from live state |
| `db.py` | Layout, stock, recipes, ratings, spend ledger |
| `auth.py` | Tailnet check, daily spend cap |
| `recipes.py` | Request pipeline, rack view, re-shelve |
| `vault.py` | Rating reminder line |

## Detail

- [rack.md](.claude/docs/rack.md): shelves, jar drawing, name resolution
- [prompt.md](.claude/docs/prompt.md): every prompt rule and its evidence
- [audit.md](.claude/docs/audit.md): review of the chat project this replaced
- [vault.md](.claude/docs/vault.md): the Obsidian rating reminder
- [ops/README.md](ops/README.md): hosting, what's public, tunnel, tailnet-only variant
