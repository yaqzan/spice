# Scaling: the people dial and the heat dial

The card's header has two dials: **people** (1-24) and **heat** (🫑 Mild / 🌶️ Medium / 🔥 Hot).
Both live in the URL (`?serves=4&heat=mild`, `useDials.ts`), so reload and shared links keep them.

## Where the maths lives

- **Server only.** `GET /api/recipes/<id>` and `/api/demo` take `serves` and `heat`;
  `recipes.view()` -> `schema.adjust()` -> `decorate()`. The spoon rounding is in `schema.py`;
  a TypeScript copy would drift. The frontend only says which notch.
- **Always from the stored numbers**, never from the last view, so a dial turned up and back lands
  exactly where it began (test: `test_a_dial_turned_and_returned_lands_where_it_started`).
- `payload.scaling` always comes back (`serves`, `base_serves`, `heat`, `base_heat`, `heat_dial`,
  `changed`), so the controls render from the server.
- `servings` is written into the payload at generation. Recipes saved before that start the dial at
  the `servings` setting (2).
- Junk params fall back silently: unknown heat = as written, non-number serves = as written,
  out-of-range serves clamps to 1-24. The old `?scale=<factor>` still works.

## What scales

- **Blend jars:** from the exact `tsp`, not the rounded label (scaling the label scales its rounding
  error). A note after the spoons ("cracked") rides along.
- **`blend_groups` and each step's `spices` chips are rebuilt from the scaled blend.** The old
  `scale()` only touched `blend`, which the card doesn't render, so it looked like it did nothing.
- **Shopping list:** leading counts round to halves (never below 1/2), cloves to whole, cups to
  quarters/thirds (under 1/4 cup is said in spoons), lb to quarters, grams <= 30 keep a decimal so
  `spoonify()` converts them accurately.
- **Prose** (step body, watch-for, salt when/rationale, salt check, serve with): every
  number+unit quantity. **Not** times, temperatures, lengths ("2-inch"), rates ("7.5 g per lb") or
  can sizes ("14 oz can").
- **Salt and MSG** scale with the food. `portion_lb` scales. **Times don't**; the hint says a bigger
  batch may need another round in the pan.

## Rounding: scant and heaped

A spoon set has quarters, thirds and halves only. After scaling, `measure_tsp()` says **scant**
when the true amount is >12% under the nearest spoon and **heaped** when >12% over (0.19 tsp ->
"scant 1/4 TEAsp"). Within 12% it says nothing. Applied to scaled amounts and to the salt panel when
`scaling.changed`; the recipe as written reads exactly as the model wrote it.

## The heat dial

- **Only `rack.HEAT_DIAL` jars move** (cayenne, crushed chili, chipotle, gochugaru, Aleppo, Urfa,
  chili crisp, chili garlic sauce), plus fresh chiles in the shopping list (`rack.FRESH_CHILE`) and a
  quantity in prose sitting right before a dial jar's name. Blends (Cajun, jerk, berbere), colour
  chiles (Kashmiri, ancho), mustard, and salted bases (doubanjiang, gochujang) stay put: moving them
  changes the dish, not the heat. Reasons are in the `HEAT_DIAL` comment.
- **Base level** comes from the model's `heat_level`: 1-2 mild, 3 medium, 4-5 hot. With
  `heat_tolerance` 4 most recipes are written hot.
- **Dose per notch:** mild 1, medium 2, hot 3.5 (perceived heat climbs slower than dose).
- Turning a **salted** dial jar (chili crisp, chili garlic) hands the extra salt back:
  `salt.grams` drops by the extra tbsp x `salt_per_tbsp`, floored at a quarter of the dish's salt.
- **No dial jar and no fresh chile = dial greyed out** with "No chile in this one". The dial never
  adds a chile the model didn't pick.
- The header heat dots follow the dial (mild 2, medium 3, hot 4).
