# The system prompt

`spice/prompt.py` builds it fresh on every request. Nothing in it is
hand-maintained — the chat project this replaces kept inventory, rotation and
rating history in a hand-edited document, and two of three had gone stale.

Roughly 18 KB / ~4.5k tokens per request.

## What is computed vs. what is fixed

| Section | Source |
|---|---|
| Inventory, with stock flags | `db.layout()` + `db.spice_states()` + `rack.SPICES` |
| Cuisine rotation | `db.cuisine_recency()` — a `GROUP BY`, cannot go stale |
| Rated history table | `db.history(rated_only=True)` |
| Salt / heat correction | `db.salt_bias()`, `db.heat_bias()` |
| Salt brand and grams-per-tsp | `db.salt_brand()` from settings |
| Acid policy | settings |
| Taste profile, technique, protein rules | constants in `prompt.py` |

Inventory renders from the live layout, so the rack the model reasons about and
the rack on screen match even after a re-shelve.

Out-of-stock jars are listed and marked `OUT OF STOCK - do not use` rather than
hidden — hiding invites the model to invent a substitute for a gap it can sense
but not see.

## The rules, and why each is there

**Salt in grams, always — grams nowhere the cook can read them.** A tsp of
Diamond Crystal is 2.8g; a tsp of Morton is 4.8g — a recipe crossing that
boundary in volume is 71% out. So `salt.grams` / `salt.msg_grams` are the
model's answer, and `recipes.decorate()` (the last step before the screen)
converts them to spoons of the brand actually in the cupboard.

The card shows one unit for one thing. It used to print "9.5 g - 1 1/2 TEAsp
fine table salt" and the model would repeat grams in step prose too
("sprinkle 7.5g over the beef"). Fixed two ways: the prompt says grams belong
only in the two numeric fields, and `schema.spoonify()` converts any that slip
through into prose. `spoonify` is narrow by design — only a seasoning-sized
figure in a sentence about salt/MSG — because a gram figure elsewhere is a
weight of meat, and 454g of beef isn't three cups of salt.

Salt and MSG are stripped from `from_kitchen` (`schema.is_salt_row()`) — they
have their own panel; repeating them in grams on the shopping line is the same
seasoning twice, in two units.

**Salt the plate, not the protein.** The 7/10 Tex Mex was a rice bowl — salt
calibrated to a lb of beef gets diluted across three cups of rice, the likely
reason it read as slightly under.

**The salt band, from twelve cooked dishes** (arrived after the baseline was
set — turns it from inference into measurement):

| % of meat weight | outcome |
|---|---|
| 0.99% | underseasoned, twice independently (Tex-Mex rice bowl, stir-fry) |
| 1.32% | fine, scored 9 |
| **1.65%** | the target — 9, 9, 8.5, 8.5 across four cuisines |
| 1.85% | "a tad over-salted", still enjoyed |

7.5 g/lb is 1.65%, landing on the sweet spot by a different route. Floor ~1.3%,
ceiling ~1.8% — should not be pushed higher; the one dish that overshot is the
only one ever called over-salted.

**Deliberately no net-of-loss figure.** An earlier draft asserted ~1/5 of salt
is lost to hands/bowls, implying a "real" rate of 6.0 g/lb — inference dressed
as measurement, uncheckable (the mixing bowl empties into the pan every time;
nothing is left to weigh), and it invited writing 6.0 into a field that means
*scoop this much*. The band above is measured end-to-end (scooped grams against
actual ratings), so any loss is already inside it.

**Baseline is 7.5 g/lb (1.65%), measured from practice.** Every dish rated
8.5+ (9.5 Jamaican Curry Mince, two 9s, 8.5 Punjabi Bhuna) was seasoned at 1 1/4
tsp of *this kitchen's iodized table salt* per lb. The chat project's memory
called this "Diamond Crystal kosher" — never true (see audit.md).

The app's earlier baseline, 5.6 g/lb, was wrong three times over: reverse-
engineered from the 7/10 Tex Mex (the second-worst rated dish) while four
8.5+ dishes sat unused in the same log; treated that dish's shortfall as a rate
problem when it's dilution (see above); and 5.6g measured out lands at ~0.99%
after the usual loss — the exact number already judged "slightly under." The
app had quietly enshrined the under-salted dish.

1.65% is bold against the conventional 1-1.5% on purpose — profile is "bold,
salty, garlicky, spicy." Prompt says outright not to moderate back toward 1%.

**Salt early and alone; burnable spices after the sear.** Resolves the
contradiction in audit.md item 4: "build the salt in" means the recipe states
the exact amount, not premixed into a rub.

**Pre-salted blends are subtracted, arithmetic shown.** Cajun, NOLA Cajun, Tex
Mex, BBQ, Jerk, Umami Steak Seasoning all carry salt.

**Steak is an ingredient-count rule, not a prohibition.** See audit.md item 2
— the failure was a pre-salted commercial blend, not complexity as such.

**Burn discipline is generalised, not enumerated.** Replaces three hand-written
exceptions (Urfa, Garam Masala, Kasuri Methi) with a `burns` flag + default
`stage` per jar; `schema.normalise()` warns if a burner is scheduled into the
sear.

**A stage is a moment; bowls are built from it.** The cook measures everything
before turning on the heat, so `schema.group_blend()` sorts the blend into
numbered bowls by stage — same stage, same bowl, same instant in the pan. A
spice given the wrong stage gets physically premixed into the wrong bowl and
can't be un-mixed at the stove. Consequences the prompt states: a step adds a
whole bowl by number ("add BOWL 2") instead of re-listing contents; a step
needing spices from two different stages means the *stages* are wrong. (First
generation after this landed put bowls 2 and 3 into one step — exactly this.)

**Every amount in a step gets the same chip.** `StepText.tsx` marks up
durations (bold), bowl references, and measurements. A measurement merges with
its adjacent ingredient into one stamp (dot, name, number) only when adjacent
*and* the same kind of unit — "Heat 1 TBsp oil" merges; "remaining 1/4 TEAsp
rice salt" does not (rice is measured in cups; that spoon belongs to salt
further along). A measurement with no ingredient to join keeps its own chip.

The dot is the jar's colour (same swatch as rack + bowl); any step naming a jar
can stamp it. Its measurement stays with the step it belongs to. Fridge items
have no jar, so no dot — an empty ring reads as a failed-to-load swatch.

The card also prints each named bowl's contents under the step (names + jar
colours, never amounts). Two rules follow: the prompt forbids reciting bowl
contents inside a step (the Berbere generation once spent all of step 1 on
"BOWL 1 is Mushroom Powder; BOWL 2 is..."); and the card distrusts the model's
own bowl numbering — `rack.STAGES` order is authoritative, and where a step's
resolved jars name exactly one bowl and its text names exactly one,
`bowlsForStep()` in `RecipeCard.tsx` corrects the text to the jars.

**`rack.STAGES` is chronological; order sorts the bowls.** `temper` used to sit
after `bloom` — backwards, since whole seeds hit bare hot fat before ground
spice is bloomed. Harmless as a mere enum; wrong once bowls were numbered from
it.

**Teaspoons are `TEAsp`, tablespoons `TBsp`.** `tsp`/`tbsp` differ by one
character — a 3x error in a kitchen that weighs salt to a tenth of a gram.
Capitalising the distinguishing syllable changes shape/length, not just one
letter. `schema.canonical_units()` rewrites whatever the model wrote, in blend
amounts, kitchen amounts and step bodies. On screen, tablespoon gets a filled
chip rather than a second colour (every accent here is a shade of orange — two
hues would read as one).

**Only fractions that exist on a spoon, quarters ahead of thirds.** The table
used to allow 3/8 — not a real spoon, and a live recipe once printed `1 3/8
TEAsp`. Allowed: 1/8, 1/4, 1/3, 1/2, 2/3, 3/4. Thirds carry a small rounding
penalty so quarter wins unless the third is clearly closer; exact 0.333 still
rounds to 1/3.

Enforced in two places (two sources): `format_tsp()` governs anything the app
computes (the salt line); blend amounts are free text from the model, so the
prompt carries the same fraction list explicitly.

**The validator catches what the prompt only asks for.** Four guards in
`schema.py`:

- *A jar listed twice.* `_dedupe_blend()` sums `tsp` and now restates `amount`
  too — it used to sum the number and leave the string, so two 1-tsp rows
  displayed "1 TEAsp" and meant two.
- *A finishing spice scheduled into the heat.* `burns` can't catch this: Urfa,
  Silk Chili, sumac, kasuri methi don't scorch — heat just erases them — so
  they carry a finishing `stage` with no `burns` flag. Now `group_blend()`
  makes a stage a physical premix bowl, so a wrong stage tips a jar into the
  wrong dish before the stove is lit (Urfa's own note says never put it in the
  pan).
- *Tablespoons had their own unmeasurable fractions.* `format_tsp` reused the
  teaspoon ladder on `tsp/3`, so 3.5 tsp printed `1 1/8 TBsp` (an eighth of a
  tbsp = 0.375 tsp — the exact figure the 3/8 fix was meant to abolish).
  Tablespoons now go whole-or-half with remainder said in teaspoons; the test
  reads the rendered string back and checks it still means the input number,
  not just that its fraction token is in the allowed set.
- *Zero grams of salt.* Shape check tested `in (None, '')`, which zero walks
  past; `salt_display(0, ...)` returns `''`, so the largest element on the card
  rendered blank. Now fails validation and retries.

**A correction needs something to correct from.** `calibration_block()` takes
the rating COUNT — mean 0.0 over an empty table and mean 0.0 over twelve
dinners are opposite claims, and it used to print both as "landing on target.
Hold the line." Floor is derived from the live baseline (0.75x), not a
hard-coded "about 1%" — at 1.65% that old wording let one `salt_delta=+2`
rating cut 30% and land below the retired 5.6 value. `salt_bias()`/
`heat_bias()` average the last 15 ratings — unbounded averaging would let a
dish from six months ago pull on tonight's seasoning forever.

**Generating is not cooking; the rotation only counts the latter.**
`cuisine_recency()` joins `ratings`, so an unrated recipe steers nothing (four
recipes generated in one morning of testing once had the prompt announcing
Korean/Indian/West African/Middle Eastern all "cooked that day"). A rating is
the only evidence a dish reached a plate.

**Dishes cooked before the app existed can still be entered.**
`spice log "<title>" --cuisine X --rating 9.5 --when 2026-07-24` writes a recipe
row and its rating together. Two details: the row carries **no blend**
(`save_recipe()` counts `spice_uses` from blend rows, and inventing a spice
list would feed fictional numbers into a proposal that physically moves jars);
and `--when` matters — without it every logged dish lands on today and skews
the rotation.

**A cuisine is folded onto its lane on write.** `canonicalise_cuisine()` in
`db.py` strips hedges ("-inspired", "-style", "-ish") and maps regional names
onto the tracked lane (Punjabi -> Indian, Sichuan -> Chinese, Jamaican ->
Caribbean). Happened for real: pork belly stored as `Korean-inspired` left
`Korean` reading as never cooked, so the rotation re-offered a dish just made.
Applied on write so rotation/history/future additions agree without each
remembering to normalise. An unknown lane keeps its own name.

**Chicken breast is cue-based, never temperature-based.** The rule earning the
8.5: sear briefly for colour, finish in the sauce — a simmer is far harder to
overshoot than a pan. No internal temperature target: the owner doesn't probe,
these breasts are thin, and a probe in a thin cutlet reads the pan as much as
the meat. Cue: opaque, springy, juices clear.

**MSG buys no salt reduction — settled by a dish, not by taste.** The Jul 4
stir-fry had salt cut from 1 to 3/4 tsp/lb specifically because MSG was in it,
landed at 0.99%, came out underseasoned; every dish after it went to the full
rate and scored 8.5+. The old rule ("cut salt ~20% with MSG") was also the
prompt's only mention of the jar, so every generated recipe but one answered
`msg_grams` as 0 — a required field described purely as a penalty reads as a
discouragement. Owner had no independent preference here; he was following the
chat project's own bad advice.

**Steak gets a temperature; chicken breast gets a cue.** Not inconsistent: a
near-disaster on record was a wagyu flat iron given "90 seconds a side" —
timing for a half-inch steak applied to one over an inch thick, served raw to a
guest. A time is a guess about an unstated thickness. Steak is thick enough to
probe honestly, so it's anchored to internal temperature (minutes as
approximation); over an inch gets steered to a low oven plus short hard sear.
Breast here is thin and unprobed, so it gets the sensory cue instead. The cut
decides which instrument is honest.

**Absolute dates, with the gap alongside.** The rotation block used to say
"West African (3d ago)" with no date column and no stated "today" for the model
to count from. A relative date expires — correct for a day, quietly wrong
after, including a future session reading back a saved payload or a vault
note. Now the prompt opens with today's date, rotation reads "last cooked
2026-08-21, 3d ago", and every rated dish shows the day it was eaten.

**Heat as a dial number.** "Medium-high" kills spice crusts. Steps render as
`med-low - dial 3` against the kitchen's own 1-10 calibration.

**`confidence`, not a predicted score.** A model asked to predict its own
rating says 8 or 9 every time. `proven` / `well_trodden` / `adaptation` /
`experiment` carries actual information; prompt says `experiment` is a good
answer.

## Structured output

`schema.RECIPE_SCHEMA` is sent as a strict JSON schema. `openrouter.py` tries
three approaches in order — `json_schema` strict, then `json_object`, then the
schema pasted into the prompt — and only a schema-shaped failure falls through.
Auth and billing errors raise immediately instead of burning two more calls.

The response still goes through a lenient parser (bare object, fenced block, or
object embedded in prose) — a model that wraps perfect JSON in a markdown fence
shouldn't cost a recipe.

**The model must support structured output.** Picking one that doesn't is the
fastest route to a blank screen; `/api/models` flags which ones do.

## Debugging

`python -m spice prompt` prints exactly what gets sent. If a recipe comes back
wrong, read that first — nine times out of ten the answer is visible in the
rendered prompt.
