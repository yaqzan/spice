# Spice

![The rack view, jars lit up for a recipe](docs/screenshot.webp)

What do I need for pork belly, and where is it on the rack. That's the only question
Spice answers, and it answers it by drawing my actual shelf.

Mine runs at https://spice.yaqzan.dev.

I own too many spices to hold the shelf in my head, and every recipe app assumes a rack
that isn't mine. Ask a generic chat window for a recipe and you get a list of names;
you're still the one translating "smoked paprika" into "second shelf, third jar, next
to the cumin." Spice keeps one registry of every jar I own, its aliases, and its shelf
position, and every recipe it writes gets checked against that registry before it's
allowed on screen. The picture you see is generated from the same layout data the app
uses to place the jar.

Salt is the one place a recipe app can quietly be wrong. Diamond Crystal and Morton
kosher salt differ by 71% per teaspoon by volume, so a recipe that says "a spoon" is
really only correct for one specific salt brand. Spice stores salt in grams, a
brand-independent unit, and only converts to spoons at the moment it renders a card, for
whichever brand I've told it I actually keep on the counter. Getting this wrong once
cost a dish that scored 2 out of 10.

The recipe card groups spices into numbered bowls in the order they go in the pan. That ordering comes from one tuple in the rack registry, so
the bowl numbers on the card and the physical premix order in the kitchen can never
drift apart. A rating I leave after cooking, plus whether the salt or heat landed,
feeds straight back into the system prompt for the next recipe, and the prompt itself is
rebuilt from live database state on every single request. The predecessor project this
replaced kept its system prompt as static text, and it froze, never updating as I
changed my mind about the rack.

There's no login screen. The app decides who I am from the raw TCP connection, not a
header, so a public tunnel sitting in front of it can't be tricked into impersonating me
by forging `X-Forwarded-For`. Off the tailnet, the site is a read-only public exhibit;
on it, it's mine.

`.claude/` holds the guidance I give Claude Code when it works in this repo. I develop
with agents heavily, and the docs there are the project's memory.

## Running it

You need Python 3.11+ and Node 18+.

```bash
git clone https://github.com/yaqzan/spice
cd spice
pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
SPICE_OPEN=1 python -m spice serve   # http://127.0.0.1:5003, API and UI on one port
pytest                               # no network or API key needed
```

An OpenRouter key goes in `data/openrouter.key` or `OPENROUTER_API_KEY`. Nothing
else is needed to boot. Without a key the rack, history and settings all still
work, and asking for a recipe says so plainly.

Anything private needs the request to arrive from a tailnet peer, so a browser
pointed at `127.0.0.1:5003` sees only the public face. `SPICE_OPEN=1` treats every
caller as the owner, for trying it out and for development. Never leave it on for
a server the internet can reach: see [ops/README.md](ops/README.md) for why that is
a flag and not a setting.

## Your data

Everything that's yours stays out of git:

| file | what it's for |
|---|---|
| `data/spice.db` | shelf layout, stock, recipes, ratings, the spend ledger. Created on first run |
| `data/openrouter.key` | your OpenRouter key |
| `.env` | optional settings: your public URL, a Markdown file for rating reminders. Copy `.env.example` |
| `ops/cloudflared-config.yml`, `ops/Caddyfile` | your hosting, copied from the `.example` files |

The jars themselves are in `spice/rack.py`: every spice, its aliases, how it
behaves in a pan, and a starting layout. That's my rack. To match yours, edit
`SPICES`, `SAUCES` and `DEFAULT_LAYOUT` there; the app checks at boot that every
jar is placed exactly once. After that, re-shelving happens in the app and lives in
the database.

Full command list and architecture: [CLAUDE.md](CLAUDE.md).
Hosting: [ops/README.md](ops/README.md).

## First five minutes

1. **Settings → which salt is on the shelf.** Nothing else matters as much.
2. **Rack**: mark anything you've run out of.
3. Ask for something.
4. Cook it, then **rate it**. An unrated recipe teaches the app nothing.

## Layout

```
spice/
  rack.py       the registry: names, aliases, handling rules, default shelf
  schema.py     the JSON contract, name resolution, measurement formatting
  prompt.py     system prompt, assembled fresh from live state every request
  db.py         layout, stock, recipes, ratings, spend ledger
  auth.py       tailnet check, daily spend cap
  recipes.py    request pipeline, rack view, re-shelve proposal
  vault.py      optional rating reminder, one line in a Markdown to-do
frontend/       Vite + React + TypeScript
ops/            tunnel and Caddy examples, Windows watchdog
tests/          no network or API key needed to run
```

## License

MIT
