# The rack: registry, layout, and the traps in both

## One list, no second list

`spice/rack.py` is the only place a spice name, alias, handling rule or default
shelf position exists. The frontend receives jars over the wire and renders
what it's given — no spice name anywhere in `frontend/src`. **Do not add one.**
A second inventory drifts within a week, and the failure is silent (the visual
points at a jar that isn't there).

`validate_default_layout()` runs on every boot and refuses to start if a spice
is placed twice, missing, or unknown.

## Why the jars sit where they do

Brief: "top rows for most used, across both racks." Implemented as:

- **Row 1 is what you reach for without looking**, frequency drops going down.
  Labels: Daily / Weekly / Regular / Rare.
- **Left rack is savoury foundation** (alliums, earth spices, world blends,
  whole seeds). **Right rack is heat and finishing** (chile arsenal,
  American/Caribbean blends, warm aromatics, specialties).

The left/right split isn't in the brief but is kept — most recipes here grab
from each side (garlic powder, then cayenne), turning search into reflex. It
also lets the re-shelve proposal re-sort rows without ever changing which wall
a jar lives on.

Initial ordering is **inference, not measurement** — derived from cuisine
rotation and the "salty, garlicky, savoury, spicy" profile, not counted usage.
A starting position the app is built to correct.

## How a jar is drawn, and why the label looks the way it does

A jar is four ideas in a 38x50 box (`JarShape` in SpiceRack.tsx): a uniform
near-black cap narrower than the glass, a shoulder curve (`JAR_PATH`, one path
string shared by fill/hover-scrim/shading-clip), contents stopping short of the
neck, and a cream paper label near the base. Caps are deliberately NOT tinted
per jar — matching caps make 56 jars read as one bought set, identity living in
the colour band between cap and label. `JarDetail` renders the same `JarGlyph`
so a tapped jar never looks like a different jar.

The label went through four designs; the surviving constraint is **one label
system whose legibility owes nothing to jar colour**:

1. Fixed near-black ink on glass — invisible on nigella, urfa, cloves.
2. Per-jar WCAG ink (`readableInk()`) — legible, but ink flipped black/white
   jar to jar and the shelf read as mismatched stickers.
3. Solid black chip, light ink — uniform, but 56 black tapes over the widest
   part of the glass read as a barcode sheet, colours read as margins.
4. Now: cream paper, dark ink, anchored near the base, sized to line count. The
   colour stays the loudest thing on the jar — the point of colour-coding at
   all.

Abbreviations are 8 characters/word (`LABEL_CHARS`), so most of the rack is
complete words. Lines of 7+ characters condense via SVG `textLength` (like
print) — do not shrink the font rack-wide or re-truncate; a word that still
doesn't fit cuts at 7 letters + a period (CORIAND.). Codes stay kitchen-unique
via `assignLabels`.

Two highlighted jars side by side condense their name captions to the cell
(`hitCells` + `textLength`) instead of overlapping mid-air.

## The sauce shelf, and the salt that used to be invisible

Bottles and tubs — soy, dark soy, oyster sauce, sesame oil, mirin, salted
cooking sake, instant dashi, doubanjiang, gochujang, LKK garlic soybean paste —
are registry entries and a drawn shelf like any other: a seasoning the app
can't see is one the model won't use, and one it can't weigh quietly wrecks the
salt.

A tbsp of light soy carries ~2.4g salt — a third of a lb of meat's whole
budget — and that salt used to appear nowhere in `salt.grams`.
`Spice.salt_per_tbsp` records it, the prompt prints it as a flag, and
`SALT_DOCTRINE` tells the model to subtract the total and show the subtraction.
Toasted sesame oil carries **0** deliberately — an invented figure would
subtract from a real dish.

Three placement notes:

- **A drawn shelf is not the retired pantry.** `pantry`/`cupboard` names stay
  retired — they were lists beside a picture. Everything that can hold a jar is
  drawn, sauce shelf included.
- **Unqualified "soy sauce" resolves to the light one** — dark soy must be
  asked for by name (same rule keeps bulk pepper from losing "black pepper" to
  the Zanzibar jar). Dark soy is used by the tsp for colour; defaulting to it
  would be a fivefold error.
- **`black bean garlic sauce` resolves to the garlic soybean paste**, bought
  instead of it.

Rows here group by kind, not frequency — Daily/Weekly/Regular/Rare would be a
lie about this shelf. `rack.wall_racks()` answers "does this shelf have
frequency rows" and travels over the wire (`wall_racks` in the rack view)
instead of every screen hardcoding `!== 'stove'`.

## Always in the house

`rack.STAPLES` — fresh garlic, fresh ginger, the two rices. Not jars, and
deliberately not resolvable as jars: `resolve()` refuses anything called
*fresh* (dried ginger in the jar is a different spice, not a weaker one). But
silence read as absence — the model was writing them onto the shopping list as
if a trip out were needed. Prompt now names them as always available; they
still go in `from_kitchen` with an amount.

## Re-shelving

`recipes.reshelve_proposal()` ranks jars by how many recipes called for them
and proposes a new arrangement. Two modes:

- **`balanced`** (default) — keeps every jar on its current rack, re-sorts rows
  within it. Preserves the left/right split.
- **`strict`** — ranks all 56 globally, fills left row 1, right row 1, left row
  2... Literal reading of the brief, at the cost of the split.

Ties break on current position, so unused jars never shuffle for no reason.

The stove shelf is never re-sorted — four constant-reach jars don't need
ranking, and moving the salt would be actively annoying.

**The proposal only ever changes the picture.** Committing writes the new
layout to the database; physical jars are the owner's problem. The UI says so.

## Name resolution — the part that bites

`rack.resolve()` maps whatever a model calls a spice onto a jar. Forgiving by
design ("ground cumin", "Kashmiri chilli", "chili flakes" all land correctly);
three specific behaviours are load-bearing, all covered by tests.

**1. Short single-word aliases can't swallow a longer phrase.** The containment
fallback used to resolve `"truffle salt"` to the kosher salt on the stove shelf
(substring match on `"salt"`) — wrong jar, and silently drops a real shopping
item. Aliases shorter than 6 characters with no space only match exactly.
`garlic salt`, `celery salt`, `onion salt` all depend on this.

**2. Anything called "fresh" is refused outright.** `"fresh ginger root"` used
to resolve to the dried jar. Now any probe containing the standalone word
`fresh` returns `None` and lands in `from_kitchen`. `"freshly ground black
pepper"` still resolves — different word.

**3. Longest alias wins, rather than requiring a unique hit.** `"sichuan
peppercorns"` matches both `sichuan peppercorn` and the bare `peppercorns`
alias on the black pepper jar. Demanding uniqueness returned nothing; longest
overlap wins. A genuine tie at the same length returns `None`.

An unresolvable name is never an error — it moves to `from_kitchen` with an
on-screen warning. A recipe with a caveat beats a 500.

## Jars that need a human, not code

- **"Red Pepper"** — genuinely ambiguous, one shelf from both Cayenne and
  Crushed Chili. Registry flags it and tells the model to prefer a named chile;
  real fix is a label.
- **"Black Fungus"** — dried wood ear mushroom, not a spice. Registry marks it
  `form='ingredient'` with soaking instructions so it never lands in a
  teaspoon-measured blend.
- **"Umami Steak Seasoning"** — carries its 2/10 in its handling note, or the
  model reaches for it exactly where it failed.
