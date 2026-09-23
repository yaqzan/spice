# Audit of the original Spice Rack instructions

The original chat-project instructions and its "memory" were identical; the only state that ever
changed was two lines in a rated-recipes table.

**This records the ORIGINAL instructions and what was decided. It is not the live spec:** where a
number here disagrees with `CLAUDE.md`, `prompt.md` or the tests, those win.

**[built]** = fixed in the app. **[your call]** = needs a decision.

## 1. The feedback loop never ran [built]

- Problem: the user had to hand-edit the system prompt after every dinner. Happened twice.
  Cuisine rotation stayed stuck at `Last used: Tex Mex`.
- Fix: every rating is a DB row; rotation is a `GROUP BY` over what was cooked; the prompt is
  rebuilt per request. No hand-kept state in the prompt.

## 2. One bad steak became a rule that was too broad [built]

- Problem: Umami Bomb steak scored 2/10, and the instructions banned complex blends on steak.
- Cause: the blend was **pre-salted**. The salt and the "no identity" both came from that jar.
- Fix: steak is tasted crust-first in slices, so 3-4 assertive ingredients max and exact salt.
  Pre-salted commercial blends are out (unknown salt load). Umami Bomb is named, not a category.

## 3. Salt was given in a unit that doesn't survive a real kitchen [built]

| Salt | g per level tsp | vs Diamond Crystal |
|---|---|---|
| Diamond Crystal kosher | 2.8 g | baseline |
| Morton kosher | 4.8 g | +71% |
| Fine sea / table | 6.0 g | +114% |

- Problem: target was "~1 tsp Diamond Crystal per lb", but the kitchen uses **fine iodized table
  salt** (Windsor). Written target (0.62%) and practice (1.32%) never matched.
- Re-read: Tex Mex (7/10, "slightly under") was ~0.99%; the 2/10 steak was a pre-salted blend plus
  table salt, over 2%. Salt did most of the damage.
- Fix: model answers in **grams**; app converts to spoons of table salt. Baseline **7.5 g/lb
  (1.65%)**, measured from every dish rated 8.5+. Tests pin both brand and percentage band.
- Second bug: the target is per lb of protein, but the Tex Mex was a rice bowl (0.99% beef diluted
  by three cups of unsalted rice). The prompt now says to salt the finished plate and give the
  starch its own salt.

## 4. Two rules contradicted each other [built]

- Problem: "build salt into the spice recipe" vs "salt first, sear, then add burnable spices".
- Fix: "build the salt in" means the recipe states the exact amount. Salt goes on early and alone
  (dry brine); burnable spices go on after the sear. Every registry spice has a `burns` flag and a
  default `stage`; the validator warns if a burner is scheduled into the sear.

## 5. The inventory had errors [built]

- **"Jamaican Hot Curry" was listed twice** (Left Rack row 4 and pantry). Now on the rack only.
- **"Black Fungus" is not a spice** (dried wood ear mushroom). Flagged as an ingredient with
  soaking instructions.
- **"Red Pepper" is ambiguous** (cayenne or chili flakes, one shelf from both). Flagged;
  **relabel the physical jar.**
- **Cardamom and Black Cardamom are different spices** (black is smoke-dried, camphorous). Noted so
  a model won't swap them.
- **Annatto** is whole hard seed: needs an oil infusion and straining.
- Fix: every jar has `form`, a default `stage`, a `burns` flag and a one-line handling note. This
  replaced the hand-written Urfa / Garam Masala / Kasuri Methi exceptions.

## 6. "No sour" was too absolute [your call]

- Problem: no citrus/vinegar/sumac, yet Za'atar (sumac) and Sun-Dried Tomato Powder stayed. Read
  literally it also bans tomato, tamarind, yoghurt marinades, gochujang, kimchi, most braises.
- Distinction: **sour as a top note** (lemon, tasting vinegar) is a real preference and stays out.
  **Acid as structure** is different: zero acid reads as "needs something".
- Fix: a setting, default **"background only"** (acid where it reads savoury: tomato paste, yoghurt,
  gochujang, soy, fish sauce; never headline). Also **None at all** and **Use it normally**.

## 7. "Predicted rating: X/10" was theatre [built]

- Problem: a model scoring itself says 8-9 every time.
- Fix: `confidence` instead: `proven` (close to something rated 7+), `well_trodden`,
  `adaptation`, `experiment`. The prompt says `experiment` is a good answer.

## 8. One number hid three kinds of failure [built]

- Problem: the 2/10 steak couldn't say whether the idea was bad or just oversalted.
- Fix: overall score, **salt** (way under to way over) and **heat** (no kick to too hot) as three
  taps. Salt/heat averages feed the prompt as corrections ("recent recipes ran salty, cut ~15%"),
  so a seasoning miss can't poison a flavour rule.

## 9. The rack had no state [built]

- Problem: 56 jars, no idea what had run out or gone stale.
- Fix: tap a jar to mark **low**/**out**; `out` is left out of the prompt. `opened_on` exists in
  the schema, **not yet in the UI**.

## 10. "Only spices from the rack" banned mentioning an onion [built]

- Fix: a separate `from_kitchen` list, required by the prompt. Any name that isn't a real jar
  lands there with a warning.

## 11. Missing entirely, now added [built]

- **Scaling**: the app does the arithmetic (e.g. 1.4 lb).
- **Times**: prep/cook/total.
- **Leftover blend**: what to do with the extra mix.
- **Which pan**: cast iron vs carbon steel, per recipe.

## 12. The best section was buried at the bottom [built]

- Problem: the batch-searing notes were prose at the end.
- Fix: every step carries a **burner dial number** (1-10) and a `watch_for` checkpoint, shown
  inline (e.g. "wipe the black residue, fresh oil between batches" on the searing step).

## Still open

1. ~~Which salt is in the box?~~ **Answered: fine iodized table salt** (item 3).
2. **Acid policy** (item 6): defaults to "background only"; owner's palate.
3. **Real usage data**: the rack layout is a guess; real counts feed the **Re-shelve** screen.
4. **`opened_on` / jar age warnings**: schema yes, UI no. Worth it?
5. **Relabel the "Red Pepper" jar.** Not a software fix.
