# Spice

Ask it what you're cooking. It answers with a picture of your actual spice rack, the
right jars lit up and numbered in the order they go in the pan.

Live: https://spice.yaqzan.dev

## Why I built it

I own too many spices to hold the shelf in my head, and every recipe app assumes a spice
rack that isn't mine. I wanted something that points at the specific jar, remembers
whether the last dish came out too salty, and gets the actual conversion right between
the salt I own and the salt a recipe writer probably meant. A generic chat window can
write a recipe. It can't render my shelf or remember what I told it about my food.

## How it works

- `rack.py` is the only place a spice name, alias, or handling rule is defined. There is
  no second spice list in the frontend to drift out of sync.
- `prompt.py` rebuilds the system prompt fresh from live database state on every
  request, so it can never carry stale "memory" text forward.
- A request goes rack registry to prompt to OpenRouter to `schema.normalise()` to
  SQLite to the API to an SVG rack render plus a recipe card.
- Recipes store salt in grams, a brand-independent unit, and convert to spoons of your
  configured salt brand only at render time (`schema.spoonify`). Diamond Crystal and
  Morton differ by 71% per teaspoon, and showing both units on a card just asks you to
  pick one with a pan already hot.
- Rate a dish and separately say whether the salt and heat landed. The averages feed
  straight back into future prompts.
- Access control is by TCP peer, not a password. On the tailnet the app knows who you
  are from the connection itself; off the tailnet it's a read-only public exhibit.

`.claude/` holds the guidance I give Claude Code when it works in this repo. I develop
with agents heavily, and the docs there are the project's memory.

## What I think is interesting

- Access control trusts only the raw socket's remote address, and explicitly refuses to
  trust `X-Forwarded-For`, which the same box's public tunnel would let anyone forge
  (`spice/auth.py`, locked in by `tests/test_spice.py::test_only_the_tailnet_block_counts`).
- Salt-unit correctness is a first-class design constraint, not a formatting detail. The
  71% volume difference between salt brands is called out as the direct cause of the one
  dish that scored 2/10 (`.claude/docs/audit.md`).
- `rack.STAGES` ordering is load-bearing. The tuple order in `rack.py` drives
  `schema.group_blend()`'s premix-bowl numbering, so the recipe card's bowl order always
  matches the physical order things go in the pan.
- Every jar is guaranteed placed exactly once on boot, and layout writes are
  all-or-nothing, so a half-applied layout can never point the rendered picture at the
  wrong shelf.
- The prompt is rebuilt from the database on every call instead of maintained as text.
  This was a direct fix for the chat-project predecessor it replaced, whose system
  prompt froze and never updated (`.claude/docs/audit.md`).

## Running it

This is a personal self-hosted tool that assumes my specific spice rack, my Tailscale
network, and my Windows machine. Here's what you'd need to run it yourself:

```powershell
python -m spice serve            # API + built SPA on :5003
python -m spice ask "pork belly" --lb 1.5
python -m spice rate 12 8 --salt -1
pytest                           # no network or API key needed
```

An OpenRouter API key goes in `data/openrouter.key` (gitignored) or the
`OPENROUTER_API_KEY` environment variable. Without a key the rack, history, and settings
still work; asking for a recipe just says a key is missing. `SPICE_OPEN=1` treats every
caller as the owner and is for local development only, since loopback is where the
public tunnel lands.

## Layout

```
spice/
  rack.py       the registry: names, aliases, handling rules, default shelf
  schema.py     the JSON contract, name resolution, measurement formatting
  prompt.py     system prompt, assembled fresh from live state every request
  db.py         layout, stock, recipes, ratings, spend ledger
  auth.py       tailnet check, daily spend cap
  recipes.py    request pipeline, rack view, re-shelve proposal
  vault.py      a rating reminder line in my Obsidian to-do
frontend/       Vite + React + TypeScript
ops/            cloudflared tunnel, Caddy config
tests/          no network or API key needed to run
```

## Status

Live and in daily use for actual cooking. This is a snapshot of a private working repo;
the commit history isn't published.

## License

MIT
