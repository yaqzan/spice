# Audit of the original Spice Rack instructions

The chat-project instructions and its "memory" were byte-identical — no separate
accumulated state existed. The only state that ever changed was two lines in a
rated-recipes table.

Items marked **[built]** are fixed in the app. **[your call]** need a decision.

---

## 1. The feedback loop never ran **[built]**

Symptom: instructions asked the user to hand-edit the system prompt after every
dinner ("ask him to update the rated recipes section above"). Happened twice,
ever. Rated recipes stayed frozen at two entries (one from a bad dish); cuisine
rotation stayed frozen at the literal string `Last used: Tex Mex`.

Fix: every rating writes a DB row; rotation is a `GROUP BY` over what was
actually cooked; the prompt rebuilds from scratch per request. No hand-maintained
state left in the system prompt.

---

## 2. One bad steak became a law that is too broad **[built]**

Symptom: Umami Bomb steak scored 2/10 (oversalted, too complex, no identity) and
the instructions generalised to "never use complex blends on steak."

Root cause: the blend was a **pre-salted commercial product** — salt error and
"no identity" both trace to that one jar, not to ingredient count.

Fix: prompt states the real rule — steak is eaten in slices where you taste the
crust directly, so 3-4 assertive ingredients is the ceiling and salt must be
exact; pre-salted commercial blends are out because you can't know the salt
load. Names the Umami Bomb specifically rather than banning a category.

---

## 3. Salt was specified in a unit that cannot survive contact with a kitchen **[built]**

Symptom: instructions targeted "~1 tsp Diamond Crystal kosher salt per lb" —
meaningless unless Diamond Crystal is the actual box on the counter.

| Salt | g per level tsp | vs. Diamond Crystal |
|---|---|---|
| Diamond Crystal kosher | 2.8 g | baseline |
| Morton kosher | 4.8 g | +71% |
| Fine sea / table | 6.0 g | +114% |

Root cause: the kitchen actually uses **fine iodized table salt** (Windsor), not
Diamond Crystal. Written target (2.8g = 0.62%/lb) and actual practice (6.0g =
1.32%/lb) were never the same number — every calibration note in the original
doc was fiction.

Re-reading the two data points through the real salt: Tex Mex (7/10, "slightly
under") was ~0.99%; the 2/10 steak was a pre-salted blend *plus* a teaspoon-scale
scoop of table salt, comfortably north of 2%. Salt did most of the damage; the
blend took the blame.

Fix: model answers in **grams**; app converts to spoons of table salt. Baseline
**7.5 g/lb (1.65%), measured out** — the rate every dish rated 8.5+ was actually
seasoned at. Tests pin both brand and percentage band.

> This file records the ORIGINAL chat instructions and what was decided. It is
> not the live spec — where a number here disagrees with `CLAUDE.md` /
> `prompt.md` / the tests, those win.

Second bug, same direction: the target is *per lb of protein*, but the 7/10 Tex
Mex was a rice bowl — beef seasoned to 0.99% then diluted across three cups of
unsalted rice, so the mouthful was under 1%. Prompt now says to salt the
finished plate and give the starch its own salt.

---

## 4. Two rules in the document directly contradict each other **[built]**

Symptom: "always build salt into the spice recipe itself, not as a separate
step" vs. "salt first, sear, then add [burnable] spices later" — for any seared
spice-coated protein (most of this kitchen's cooking) these can't both be
followed.

Fix: "build the salt in" now means *the recipe states the exact salt amount*,
not physical premixing. Salt goes on early and alone (dry brine); burnable
spices go on after the sear. Every registry spice carries a `burns` flag and
default `stage`; the validator raises a visible warning if a burner is
scheduled into the sear.

---

## 5. The inventory had real errors **[built]**

- **"Jamaican Hot Curry" listed twice** (Left Rack row 4 and the pantry) —
  deduplicated, now lives on the rack.
- **"Black Fungus" is not a spice** — dried wood ear mushroom, rehydrated for
  crunch. Flagged in the registry as an ingredient with soaking instructions.
- **"Red Pepper" is ambiguous** — ground red pepper = cayenne in US usage,
  crushed red pepper = chili flakes, and it sits one shelf from both. Flagged
  ambiguous; **worth relabelling the physical jar.**
- **"Cardamom" vs "Black Cardamom"** are not variants — black is smoke-dried and
  camphorous. Noted so a model won't substitute.
- **Annatto** is whole, rock-hard seed — needs an oil infusion and straining,
  not a sprinkle. Was the same class of error the hand-written Urfa/Garam
  Masala/Kasuri Methi exceptions were each patching one at a time.

Fix: every jar carries `form`, a default `stage`, a `burns` flag, and a one-line
handling note. Three hand-written exceptions became one general mechanism.

---

## 6. "No sour" is stated more absolutely than it should be **[your call]**

Instructions said no citrus/vinegar/sumac, then separately kept Za'atar
(contains sumac) and Sun-Dried Tomato Powder (acidic) on the rack. Read
absolutely, the rule also excludes tomato, tamarind, yoghurt marinades,
gochujang, kimchi and most braises — much of the cuisine rotation.

Distinction: **sour as a top note** (a squeeze of lemon, a vinegar you can
taste) is a real preference, honoured as written. **Acid as a structural
element** is different — zero acid anywhere in a salty/garlicky/fatty/spicy
profile reads as "needs something," not "needs lemon."

Fix: built as a setting, default **"background only"** — acid allowed where it
reads savoury (tomato paste, yoghurt marinade, gochujang, soy, fish sauce),
never as headline. Settings also offers **None at all** and **Use it
normally**.

---

## 7. "Predicted rating: X/10" is theatre **[built]**

Symptom: a model asked to predict its own score outputs 8-9 essentially always
— no calibration, every incentive to flatter, and it makes real ratings harder
to read.

Fix: replaced with `confidence`: `proven` (close to something rated 7+),
`well_trodden`, `adaptation`, `experiment` — prompt explicitly says
`experiment` is a good answer.

---

## 8. Ratings collapsed three different failures into one number **[built]**

Symptom: the steak scored 2/10 with no way to tell whether the idea was bad or
a good idea was oversalted (see item 2 — wrong lesson got learned).

Fix: overall score, **salt** (way under -> way over) and **heat** (no kick ->
too hot) as three separate taps. Salt/heat averages feed back into the prompt
as explicit corrections ("recent recipes have run salty, cut the target ~15%"),
so a seasoning miss can't poison a flavour rule.

---

## 9. The rack had no state at all **[built]**

Symptom: 56 jars, no notion of what's run out or aged. A recipe built around
gochugaru finished three weeks ago is worse than no recipe; ground spice is
mostly sawdust a year after opening.

Fix: tap any jar to mark **low**/**out**; `out` is excluded from the prompt.
Schema has an `opened_on` field, **not yet surfaced in the UI**.

---

## 10. "List only spices from the rack" forbade mentioning an onion **[built]**

Symptom: taken literally, the model couldn't tell you a recipe needs garlic,
yoghurt, soy sauce or oil — so it either broke the rule or left things implied.

Fix: separate `from_kitchen` list; prompt insists on it explicitly. Anything
named that isn't a real jar lands there automatically with a warning.

---

## 11. Missing entirely, now added **[built]**

- **Scaling** — everything was "per lb"; app does the arithmetic for e.g. 1.4 lb.
- **Times** — no prep/cook/total time anywhere.
- **Leftover blend** — no note on what to do with 3 tbsp of leftover mix.
- **Which pan** — batch-searing covered cast iron vs. carbon steel, but no
  recipe ever said which to use.

---

## 12. The best-written section was buried at the bottom **[built]**

The batch-searing notes were the strongest part of the document but sat as
prose at the end, most likely to be skimmed.

Fix: every step carries a heat level as a **burner dial number** (1-10) and a
`watch_for` sensory checkpoint, rendered inline with the step — e.g. "wipe the
black residue, add fresh oil between batches" attached to the searing step
where it's needed.

---

## Still open

1. ~~Which salt is in the box?~~ **Answered: fine iodized table salt** (item 3).
2. **Acid policy** (item 6) — defaulted to "background only"; your palate.
3. **Real usage data** — rack layout is a best guess from cuisine rotation and
   taste profile. Real numbers feed the **Re-shelve** screen.
4. **`opened_on` / jar age warnings** — schema exists, UI doesn't. Worth it?
5. **Relabel the "Red Pepper" jar.** Nothing software can fix that one.
