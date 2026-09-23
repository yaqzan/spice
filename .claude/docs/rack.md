# The rack: registry, layout, and traps

## One list only

- **`spice/rack.py` is the only place a spice name, alias, handling rule or default shelf position
  exists.** The frontend renders the jars it's sent; no spice name anywhere in `frontend/src`.
  Don't add one: a second list drifts silently and the visual points at a missing jar.
- `validate_default_layout()` runs on every boot and refuses to start if a spice is placed twice,
  missing, or unknown.

## Where the jars sit

Brief: "top rows for most used, across both racks."

- **Row 1 is what you grab without looking**; frequency drops going down. Labels: Daily / Weekly /
  Regular / Rare.
- **Left rack: savoury base** (alliums, earth spices, world blends, whole seeds). **Right rack:
  heat and finishing** (chiles, American/Caribbean blends, warm aromatics, specialties).
- The left/right split isn't in the brief but stays: most recipes grab from both sides, and
  re-shelving can re-sort rows without moving a jar to the other wall.
- The starting order is **a guess**, from cuisine rotation and the "salty, garlicky, savoury,
  spicy" profile. The app is built to correct it.

## How a jar is drawn

- A 38x50 box (`JarShape` in SpiceRack.tsx): near-black cap narrower than the glass, shoulder curve
  (`JAR_PATH`, one path shared by fill, hover scrim and shading clip), contents stopping below the
  neck, cream paper label near the base.
- Caps are **not** tinted per jar (owner decision): matching caps make 56 jars read as one set;
  identity is the colour band between cap and label.
- `JarDetail` renders the same `JarGlyph`, so a tapped jar looks the same.

**The label must stay legible regardless of jar colour.** Rejected designs, don't bring back:

1. Fixed dark ink on glass: invisible on nigella, urfa, cloves.
2. Per-jar WCAG ink (`readableInk()`): ink flipped black/white jar to jar, looked like mismatched
   stickers.
3. Solid black chip, light ink: 56 black tapes read as a barcode sheet.
4. Current: cream paper, dark ink, near the base, sized to line count. Colour stays the loudest
   thing on the jar.

Label text:

- Abbreviations allow 8 characters per word (`LABEL_CHARS`), so most labels are full words.
- Lines of 7+ characters condense via SVG `textLength`. Don't shrink the font rack-wide or
  re-truncate. A word that still doesn't fit cuts at 7 letters + a period (CORIAND.).
- Codes stay unique across the kitchen via `assignLabels`.
- Two highlighted jars side by side condense their captions to the cell (`hitCells` +
  `textLength`) so they don't overlap.

## The sauce shelf

- Soy, dark soy, oyster sauce, sesame oil, mirin, salted cooking sake, instant dashi, doubanjiang,
  gochujang and LKK garlic soybean paste are registry entries on a drawn shelf. A seasoning the app
  can't see, the model won't use; one it can't weigh wrecks the salt.
- **A tbsp of light soy carries ~2.4 g salt**, a third of a lb of meat's budget. `Spice.salt_per_tbsp`
  records it, the prompt flags it, and `SALT_DOCTRINE` tells the model to subtract it and show the
  subtraction.
- Toasted sesame oil carries **0** on purpose: an invented figure would subtract from a real dish.
- **A drawn shelf is not the retired pantry.** `pantry`/`cupboard` stay retired (they were lists
  beside a picture). Everything that holds a jar is drawn.
- **Plain "soy sauce" resolves to light soy.** Dark soy must be named (it's used by the tsp for
  colour; defaulting to it is a fivefold error). Same rule keeps bulk pepper from losing "black
  pepper" to the Zanzibar jar.
- **`black bean garlic sauce` resolves to the garlic soybean paste** (bought instead of it).
- Rows here group by kind, not frequency. `rack.wall_racks()` says which shelves have frequency
  rows and is sent as `wall_racks` in the rack view. Don't hardcode `!== 'stove'` in screens.

## Always in the house

- `rack.STAPLES`: fresh garlic, fresh ginger, the two rices. Not jars and not resolvable as jars
  (`resolve()` refuses anything called *fresh*; dried ginger is a different spice).
- The prompt names them as always available, or the model puts them on the shopping list. They
  still go in `from_kitchen` with an amount.

## Re-shelving

`recipes.reshelve_proposal()` ranks jars by how many recipes used them.

- **`balanced`** (default): every jar stays on its rack; rows re-sort within it.
- **`strict`**: ranks all 56 globally, fills left row 1, right row 1, left row 2, and so on. Loses
  the left/right split.
- Ties break on current position, so unused jars don't shuffle.
- The stove shelf is never re-sorted (four always-reached jars; moving the salt is annoying).
- **The proposal only changes the picture.** Committing writes the layout to the DB; moving the
  physical jars is the owner's job, and the UI says so.

## Name resolution traps

`rack.resolve()` maps whatever the model calls a spice onto a jar ("ground cumin", "Kashmiri
chilli", "chili flakes" all land). Three behaviours matter, all tested:

1. **Short single-word aliases only match exactly.** Aliases under 6 characters with no space
   can't match inside a longer phrase, or `"truffle salt"` lands on the kosher salt. `garlic salt`,
   `celery salt`, `onion salt` depend on this.
2. **Anything with the standalone word `fresh` returns `None`** and goes to `from_kitchen`
   (`"fresh ginger root"` used to hit the dried jar). `"freshly ground black pepper"` still
   resolves.
3. **Longest alias wins.** `"sichuan peppercorns"` matches both `sichuan peppercorn` and the black
   pepper jar's `peppercorns`; the longer wins. A tie at the same length returns `None`.

An unresolvable name is never an error: it moves to `from_kitchen` with an on-screen warning.

## Jars that need a human

- **"Red Pepper"**: ambiguous, one shelf from Cayenne and Crushed Chili. The registry tells the
  model to prefer a named chile; the real fix is a new label.
- **"Black Fungus"**: dried wood ear mushroom. `form='ingredient'` with soaking instructions, so it
  never lands in a teaspoon blend.
- **"Umami Steak Seasoning"**: its handling note carries its 2/10, or the model reaches for it
  exactly where it failed.
