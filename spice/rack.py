"""The spice registry: what we own, how each one behaves, and where it sits.

This module is the ONLY place a spice's canonical name, handling rule or default
shelf position is written down. The prompt builder reads it, the response
validator resolves model output against it, and the frontend renders the rack
from it — nothing re-declares a spice name in TypeScript or in a prompt string.

Two things live here and they are deliberately separate:

* `SPICES` — the inventory and its *behaviour*. Whether a jar is whole or ground,
  whether it scorches in a dry pan, when in the cook it should go in. This is
  physical fact about the contents and it does not change when jars get moved.
* `DEFAULT_LAYOUT` — where each jar sits *right now*. This is a seed only. The
  live layout lives in the database (see `db.py`) because the whole point of the
  app is that the rack gets re-shelved as we learn what actually gets used.

Ordering principle for the default layout: **row 1 is what you reach for without
looking**, and frequency drops as you go down. On top of that the left rack is
the savoury foundation (aromatics, blends, alliums) and the right rack is heat
and finishing — so a recipe that says "garlic powder then cayenne" is a left-hand
grab followed by a right-hand grab. Both racks are 4 rows of 7.
"""

from __future__ import annotations

from typing import NamedTuple

# ── how a spice behaves ──────────────────────────────────────────────────────
# `stage` is the default moment a spice should enter the pan. The model is
# allowed to override it with a reason, but this is what it is told to assume,
# and it is what stops the classic failures: garam masala boiled for 40 minutes
# until it tastes like dust, kasuri methi added early and turning bitter, urfa
# toasted until its oil goes acrid.
# CHRONOLOGICAL, and that is now load-bearing: schema.group_blend sorts the
# blend into bowls by this order, so a stage in the wrong place here puts a
# spice in the wrong bowl on the cook's counter. `temper` used to sit after
# `bloom` even though tempering is the first thing that happens in the pan.
STAGES = (
    'marinade',        # goes on the raw protein, hours ahead
    'dry_rub',         # goes on the surface before searing (salt-safe only)
    'temper',          # whole seeds popped in bare hot fat, before anything else
    'bloom',           # ground spice into fat for 30-60s to open up
    'early',           # in with the aromatics, tolerates long heat
    'mid',             # after the sear, once the pan has come down
    'last_five',       # final 5 minutes, volatile aromatics
    'off_heat',        # stirred in after the pan leaves the burner
    'garnish',         # sprinkled on the plate
)

FORMS = ('ground', 'whole', 'seed', 'flake', 'blend', 'herb', 'oil_cured',
         'ingredient', 'sauce', 'paste', 'oil')


class Spice(NamedTuple):
    key: str            # stable id, never shown to the user
    name: str           # canonical display name
    aka: tuple          # aliases the model (or a recipe) might use instead
    form: str
    stage: str          # default entry point in the cook
    burns: bool         # scorches in a hot dry pan — must go in after the sear
    heat: int           # 0-10 perceived heat; 0 for everything non-chile
    color: str          # jar contents colour, for the rack visual
    note: str           # the handling rule, verbatim into the prompt when used
    # Grams of salt a tablespoon of this carries, for anything that is seasoned
    # before it reaches the kitchen. The salt baseline is measured to a tenth of
    # a gram and then a tablespoon of soy sauce adds a third of a pound of meat's
    # entire budget without appearing anywhere in the salt figure. Written here
    # so the deduction is a number the prompt can print rather than a habit the
    # model has to remember. 0 means "adds no salt", which is most of the rack.
    salt_per_tbsp: float = 0.0

    @property
    def is_chile(self) -> bool:
        return self.heat > 0


# The inventory. `note` is written to be read by the model *and* by a human
# standing at the rack — it is the one-line reason this jar goes wrong.
SPICES: tuple = (
    # ── alliums & the daily foundation ───────────────────────────────────────
    Spice('garlic_powder', 'Garlic Powder', ('granulated garlic', 'garlic granules'),
          'ground', 'mid', True, 0, '#e8dcc0',
          'Burns fast and turns acrid. Never in the first sear — salt the protein, '
          'sear it, then add garlic powder once the pan has come down.'),
    Spice('onion_powder', 'Onion Powder', ('granulated onion',),
          'ground', 'mid', True, 0, '#e0d3b8',
          'Same burn risk as garlic powder, and it has sugar in it. After the sear.'),
    Spice('mushroom_powder', 'Mushroom Powder', ('porcini powder', 'shiitake powder',
                                                'dried mushroom powder',
                                                'mushroom seasoning'),
          'ground', 'early', False, 0, '#6b5847',
          'Pure glutamate depth with no heat, no acid and no flavour of its own '
          'that announces itself — it makes browned meat taste like it simmered '
          'for hours. Works in every cuisine on the rotation. A teaspoon per '
          'pound, in early with the aromatics. Ground here from dried shiitake: '
          'break the caps up first, then blitz — shiitake is woody rather than '
          'brittle, so a rolling pin will shard it but not powder it. Whole '
          'shiitake are often the better move anyway: soak them, slice them in, '
          'and use the soaking liquid, which is the most savoury thing in the '
          'kitchen. Never throw that water away.'),
    Spice('smoked_paprika', 'Smoked Paprika', ('pimenton', 'pimentón', 'smoked pimenton'),
          'ground', 'mid', True, 0, '#a83a1c',
          'Scorches and goes bitter above a gentle heat. Bloom in warm fat off the '
          'boil, or add after the sear. Carries smoke, so it dominates if overdone.'),
    Spice('paprika', 'Paprika', ('sweet paprika', 'hungarian paprika'),
          'ground', 'mid', True, 0, '#c14a20',
          'Mostly colour and body rather than flavour. Burns as easily as its '
          'smoked sibling — keep it off direct high heat.'),
    Spice('cumin', 'Cumin', ('ground cumin', 'jeera', 'cumin seeds', 'zeera'),
          'ground', 'bloom', False, 0, '#9c7a4a',
          'Wants fat and 30-45 seconds of heat to wake up. Whole seeds temper at '
          'the start; ground goes in with the aromatics.'),
    Spice('coriander', 'Coriander', ('ground coriander', 'dhania', 'coriander seed'),
          'ground', 'bloom', False, 0, '#b39a68',
          'The quiet partner to cumin — bloom them together. Toasting whole and '
          'grinding fresh is a real, noticeable upgrade here.'),
    # Deliberately NOT aliased to a bare "black pepper": the bulk jar owns that
    # name, because that is what an unqualified recipe means. This one has to be
    # asked for by name. The two used to collide and the winner was decided by
    # which tuple happened to be indexed first.
    Spice('zanzibar_black_pepper', 'Zanzibar Black Pepper', ('zanzibar pepper',
                                                             'zanzibar black pepper',
                                                             'cracked black pepper'),
          'ground', 'mid', False, 0, '#2e2622',
          'BEING USED UP — ground, like the bulk jar, which settles it: the thing '
          'that separates a good pepper from an ordinary one is being cracked to '
          'order, and neither of these is. Origin alone does not survive '
          'pre-grinding. Use THIS wherever a recipe calls for black pepper until '
          'it is gone; the big jar takes over afterwards, and this one is not '
          'being rebought.'),

    # ── warm workhorses ──────────────────────────────────────────────────────
    Spice('turmeric', 'Turmeric', ('haldi', 'ground turmeric'),
          'ground', 'bloom', True, 0, '#d4a017',
          'Raw it tastes like chalk and it stains everything it touches. Must see '
          'hot fat for a minute. Easy to overdo — it goes medicinal.'),
    Spice('ginger', 'Ginger', ('ground ginger', 'dried ginger', 'sonth'),
          'ground', 'bloom', False, 0, '#d9b47a',
          'Dried ginger is warm and dusty, not bright — it is not a substitute for '
          'fresh, it is a different spice. Good in rubs and Suya-style blends.'),
    Spice('garam_masala', 'Garam Masala', ('garam masala powder',),
          'blend', 'last_five', True, 0, '#7a4a28',
          'A finishing blend, not a base. Boil it and it goes flat and dusty — add '
          'in the last 5 minutes, off the boil, and let the residual heat do it.'),
    Spice('curry_powder', 'Curry Powder', ('madras curry powder', 'yellow curry powder'),
          'blend', 'bloom', True, 0, '#c8901f',
          'Needs fat and a minute of gentle heat or it stays raw and powdery. '
          'Contains turmeric, so the same burn and stain rules apply.'),
    Spice('fried_garlic', 'Fried Garlic', ('crispy garlic', 'fried garlic flakes'),
          'flake', 'garnish', True, 0, '#c9a35e',
          'Already cooked. It is a texture, not a seasoning — put it on the plate. '
          'Anything more than residual heat turns it black and bitter.'),
    Spice('sesame_seeds', 'Sesame Seeds', ('toasted sesame', 'white sesame', 'sesame'),
          'seed', 'garnish', False, 0, '#e5d5b0',
          'Toast dry until they smell nutty and start to skip, then off the heat '
          'immediately — they go from golden to burnt in about 20 seconds.'),
    # Two oreganos, and they are not the same plant. A bare "oregano" in a recipe
    # means the Mediterranean one, so THAT jar owns the plain name and this one
    # has to be asked for by country — the same call made for the two peppers.
    Spice('mexican_oregano', 'Mexican Oregano', ('mexican oregano',),
          'herb', 'early', False, 0, '#8a9068',
          'Citrusy and grassy where Mediterranean oregano is minty — a different '
          'plant, not a regional label. It belongs with cumin and chile; it will '
          'taste wrong in a tomato sauce. Crush between the palms as it goes in.'),
    Spice('oregano_leaves', 'Oregano Leaves', ('oregano', 'dried oregano',
                                               'mediterranean oregano', 'greek oregano'),
          'herb', 'early', False, 0, '#849464',
          'Whole-leaf Mediterranean oregano — minty and peppery, the oregano of '
          'tomato sauce, pizza and grilled lamb. Whole leaves need liquid and '
          'time; crush them between the palms so they actually release.'),
    Spice('sage', 'Sage Leaves', ('sage', 'dried sage', 'rubbed sage', 'sage leaves'),
          'herb', 'early', False, 0, '#8a9a86',
          'Whole leaves, so crush them between the palms on the way in. The pork, '
          'sausage and brown-butter herb — it can carry a fatty dish on its own. '
          'Leaves are far less dense than powder: if a recipe calls for ground '
          'sage, use TWO to THREE times the volume in crumbled leaves.'),

    # ── world blends & herbs ─────────────────────────────────────────────────
    Spice('five_spice', 'Chinese 5 Spice', ('chinese five spice', '5 spice', 'five spice'),
          'blend', 'marinade', True, 0, '#6b4423',
          'Star-anise-forward and very assertive — a quarter teaspoon per pound is '
          'plenty. Best in a marinade where it has time to mellow.'),
    Spice('berbere', 'Berbere', ('berbere spice',),
          'blend', 'bloom', True, 4, '#a02c1a',
          'Chile-heavy with fenugreek behind it. Wants fat and onion; used dry on a '
          'surface it tastes raw and harsh.'),
    Spice('zaatar', "Za'atar", ('zaatar', "za'atar", 'zatar'),
          'blend', 'garnish', True, 0, '#6f7a3a',
          'Contains sumac (sour) and sesame (burns). A finishing sprinkle on '
          'yoghurt, bread or cooked meat — never a cooking spice here.'),
    Spice('sumac', 'Sumac', ('sumaq', 'summaq', 'ground sumac'),
          'ground', 'garnish', False, 0, '#7d2b26',
          'THE sour one, and this kitchen does not want sour top notes — so it '
          'has one honest job: a light dust over something fatty and charred '
          '(grilled lamb, chicken skin, roast onions) where it cuts richness and '
          'reads as brightness rather than as lemon. Never in the pan, never as '
          'a lead flavour, and never more than a scant pinch per plate.'),
    Spice('italian_seasoning', 'Italian Seasoning', ('italian herbs', 'mixed herbs'),
          'herb', 'early', False, 0, '#7d8a55',
          'Dried herbs need liquid and time — good in a sauce, wasted as a dry '
          'sprinkle at the end.'),
    Spice('thyme', 'Thyme', ('dried thyme',),
          'herb', 'early', False, 0, '#77804b',
          'One of the few dried herbs that survives long cooking intact. Backbone '
          'of Jerk and Cajun; goes in early.'),
    Spice('kasuri_methi', 'Kasuri Methi', ('dried fenugreek leaves', 'fenugreek leaves', 'methi'),
          'herb', 'off_heat', False, 0, '#6e7346',
          'Crush hard between the palms to wake it, then in off the heat at the very '
          'end. Cooked, it turns bitter and loses the thing that makes it worth having.'),
    Spice('white_pepper', 'White Pepper', ('ground white pepper',),
          'ground', 'mid', False, 0, '#e8e0cc',
          'Funky and earthy, not just "pepper without the specks" — it is the '
          'signature of Chinese soups and hot-and-sour. A little goes far.'),

    # ── whole seeds & tempering ──────────────────────────────────────────────
    Spice('fenugreek_seeds', 'Fenugreek Seeds', ('methi seeds', 'fenugreek'),
          'seed', 'temper', True, 0, '#b08b3e',
          'Ferociously bitter if it browns past pale gold. Two or three seeds is '
          'often the whole dose — this is the most over-used jar on the rack.'),
    Spice('black_mustard_seeds', 'Black Mustard Seeds', ('mustard seeds', 'rai', 'brown mustard seeds'),
          'seed', 'temper', False, 0, '#3a2f22',
          'Into hot fat first, with a lid — they must pop. Unpopped they are just '
          'gritty; popped they turn nutty and sweet.'),
    Spice('fennel_seeds', 'Fennel Seeds', ('saunf', 'fennel'),
          'seed', 'temper', False, 0, '#a9a86a',
          'Sweet anise note. Crack them lightly first; whole they can read as a '
          'stray liquorice bomb in a mouthful.'),
    Spice('nigella_seeds', 'Nigella Seeds', ('kalonji', 'black seed', 'black cumin'),
          'seed', 'temper', False, 0, '#1f1b18',
          'Oniony and slightly bitter. Mostly for bread and pickles, or scattered '
          'over a finished curry.'),
    Spice('star_anise', 'Star Anise', ('star anise pods', 'badian'),
          'whole', 'early', False, 0, '#6b3f22',
          'A braising spice. One pod flavours a whole pot; two make it taste like '
          'liquorice. Fish it out before serving.'),
    Spice('wild_hing', 'Wild Hing (Asafoetida)', ('asafoetida', 'hing', 'asafetida'),
          'ground', 'temper', True, 0, '#c9a227',
          'A pinch — genuinely a pinch — and it MUST hit hot fat for a few seconds. '
          'Raw it smells like a gas leak; bloomed it tastes like garlic and onion '
          'had a better idea. Keep the lid shut.'),
    Spice('curry_leaves', 'Curry Leaves', ('curry leaf', 'kadi patta', 'meetha neem'),
          'herb', 'temper', False, 0, '#3f6b3a',
          'KEPT IN THE FREEZER, not on the rack — the aroma is volatile enough '
          'that dried leaves are close to inert, while frozen ones stay almost as '
          'good as fresh. Straight from frozen into hot oil at the start of a '
          'tempering; they spit hard, so use a lid. They are done when they go '
          'translucent and crackle, about 20 seconds. Nothing else in the kitchen '
          'substitutes for them.'),
    Spice('black_fungus', 'Black Fungus', ('wood ear', 'wood ear mushroom', 'cloud ear', 'mu er'),
          'ingredient', 'early', False, 0, '#3b2f2b',
          'NOT a spice — dried wood ear mushroom. Soak in warm water 20-30 minutes, '
          'trim the hard nub, slice. It contributes crunch, not flavour.'),

    # ── heat: the chile arsenal ──────────────────────────────────────────────
    Spice('cayenne', 'Cayenne', ('ground cayenne', 'cayenne pepper'),
          'ground', 'mid', True, 8, '#b02010',
          'Pure heat with almost no flavour of its own — the volume knob, not the '
          'song. Burns in a dry pan and the smoke will empty the kitchen.'),
    Spice('gochugaru', 'Gochugaru', ('korean chili flakes', 'korean red pepper flakes', 'gochu garu'),
          'flake', 'mid', True, 4, '#c5341c',
          'Fruity, smoky, surprisingly mild for how red it looks — you can use it by '
          'the tablespoon. Coarse flakes burn quickly on dry high heat.'),
    Spice('crushed_chili', 'Crushed Chili', ('chili flakes', 'red pepper flakes', 'crushed red pepper'),
          'flake', 'bloom', True, 6, '#a92c15',
          'Best bloomed in oil — that is what makes chili oil taste like chili oil '
          'rather than hot dust.'),
    Spice('celery_seed', 'Celery Seed', ('celery seeds', 'ground celery seed'),
          'seed', 'early', False, 0, '#8a7a4a',
          'The missing third of the Cajun trinity. Every Cajun, NOLA and BBQ rub '
          'on this rack has it and none of the loose spices do — it is the note '
          'that makes a home-built rub taste finished rather than nearly right. '
          'Ferociously strong: a quarter teaspoon per pound, and it goes bitter '
          'if you treat it like a seed to be toasted hard.'),
    Spice('chipotle', 'Chipotle', ('chipotle powder', 'ground chipotle'),
          'ground', 'mid', True, 6, '#7d3218',
          'Smoked jalapeño: smoke first, heat second. Stacking it with smoked '
          'paprika doubles the smoke and flattens everything else.'),
    Spice('kashmiri_chili', 'Kashmiri Chili', ('kashmiri mirch', 'kashmiri red chili', 'kashmiri chilli'),
          'ground', 'bloom', True, 2, '#c0261a',
          'The colour spice — deep red, barely hot. Use it by the tablespoon to get '
          'that restaurant red without setting anything on fire.'),
    Spice('cajun', 'Cajun', ('cajun seasoning', 'cajun spice'),
          'blend', 'mid', True, 5, '#8f3a1e',
          'Already salted — check before adding more salt. Paprika-heavy, so it '
          'burns; on for the second half of the cook.'),
    Spice('jerk', 'Jerk', ('jerk seasoning', 'jamaican jerk'),
          'blend', 'marinade', True, 7, '#4a3a22',
          'Allspice, thyme and scotch bonnet. Built for a long marinade and then '
          'char — 4 hours minimum, overnight is better.'),
    # 'ancho chili powder' is spelled out because the new Chili Powder jar's alias
    # would otherwise be the longest match inside it and steal the resolution.
    Spice('ancho_chili', 'Ancho Chili', ('ancho', 'ancho powder', 'ground ancho',
                                         'ancho chili', 'ancho chili powder'),
          'ground', 'bloom', True, 3, '#6b2c18',
          'Dried poblano — raisiny and mild, the body of a chili paste rather than '
          'its heat. Bloom it; raw it is dusty.'),
    Spice('ground_mustard', 'Ground Mustard', ('mustard powder', 'dry mustard',
                                              'english mustard powder', 'mustard flour'),
          'ground', 'mid', False, 3, '#d9c46a',
          'Heat on a different axis from every chile here — volatile mustard oil '
          'hits the nose and clears the sinuses rather than burning the tongue. '
          'That pungency only forms when the powder meets COLD liquid, and takes '
          'about 10 minutes; hot liquid kills the reaction and leaves it merely '
          'bitter. So slurry it cold first if you want the bite, or add it dry to '
          'a rub for gentle background sharpness. The missing sharp note in every '
          'BBQ and Cajun rub on this rack.'),
    # Sold under half a dozen names because the growing region moved: true Aleppo
    # is scarce, so the same chile ships as Armenian, Turkish or Maras red pepper.
    # All of them resolve here rather than failing to place.
    Spice('silk_chili', 'Silk Chili (Aleppo)', ('aleppo pepper', 'aleppo', 'pul biber',
                                                'silk chili', 'armenian red pepper',
                                                'turkish red pepper', 'maras pepper',
                                                'halaby pepper', 'armenian pepper'),
          'flake', 'garnish', False, 3, '#a83820',
          'Oil-cured, slightly sweet, gentle — roughly half the heat of crushed '
          'chili. A finishing chile: its whole appeal is the soft fruity top note '
          'and heat destroys it. The traditional cure adds SALT as well as oil, but '
          'the jar in this kitchen (Cedar Phoenicia Armenian Red Pepper) is '
          'dry-packed and unsalted — checked. So no salt deduction is needed for '
          'it, unlike the pre-salted blends.'),
    Spice('black_urfa_chili', 'Black Urfa Chili', ('urfa biber', 'urfa', 'isot pepper'),
          'oil_cured', 'garnish', False, 4, '#3d2420',
          'Oil-cured, raisin-and-tobacco dark. NEVER toast it and never put it in '
          'the pan — it goes on the finished plate or it is wasted.'),
    Spice('shichimi_togarashi', 'Shichimi Togarashi', ('shichimi', 'togarashi',
                                                       'seven spice', 'japanese seven spice',
                                                       'nanami togarashi'),
          'blend', 'garnish', False, 3, '#c2452a',
          'A table condiment, not a cooking spice. Half of what makes it good — '
          'nori, sesame, dried citrus peel — is destroyed by a pan, and the citrus '
          'is the one sour note this kitchen actually likes, because it arrives as '
          'aroma rather than as sharpness. Over the finished bowl, never into it.'),
    Spice('tex_mex', 'Tex Mex', ('tex-mex seasoning', 'taco seasoning'),
          'blend', 'mid', True, 3, '#9c4a22',
          'Usually pre-salted and often contains starch as a thickener — taste '
          'before salting and expect it to tighten a sauce.'),
    Spice('bbq', 'BBQ', ('bbq rub', 'barbecue seasoning'),
          'blend', 'mid', True, 2, '#6f3520',
          'Contains sugar, which means it will burn and go black long before the '
          'meat is done. Low heat, or brush it on in the last few minutes.'),
    Spice('nola_cajun', 'NOLA Cajun', ('new orleans cajun', 'nola seasoning'),
          'blend', 'mid', True, 5, '#8a3a24',
          'The saltier, more garlic-forward of the two Cajun jars. Pick one — using '
          'both is how a dish ends up over-salted.'),

    # ── warm sweet aromatics ─────────────────────────────────────────────────
    Spice('cinnamon', 'Ground Cinnamon', ('cinnamon', 'ground cinnamon', 'dalchini'),
          'ground', 'early', True, 0, '#8b4a20',
          'In savoury food it works as background warmth, not a flavour you should '
          'be able to name. A quarter teaspoon per pound is the ceiling.'),
    Spice('allspice', 'Allspice', ('pimento', 'ground allspice', 'jamaica pepper'),
          'ground', 'marinade', False, 0, '#5e3a22',
          'The engine of Jerk and of Middle Eastern meat. Reads as clove plus '
          'nutmeg plus pepper, and it takes over if you let it.'),
    # This kitchen has cardamom WHOLE and cloves GROUND — one jar each, not two.
    # That combination is lucky: whole pods are the durable form of the spice
    # that fades fastest, and ground cloves are the one ground spice that keeps.
    Spice('cardamom', 'Cardamom (pods)', ('green cardamom', 'elaichi',
                                          'cardamom pods', 'whole cardamom',
                                          'ground cardamom', 'cardamom powder'),
          'whole', 'early', False, 0, '#8e9a55',
          'Green cardamom, whole. Floral and sweet — crack the pods and use the '
          'seeds; the husk is filler. Whole pods hold for years, which matters '
          'because GROUND cardamom is the fastest-fading spice there is. If a '
          'recipe asks for ground, crush the seeds from about 3 pods per '
          'half-teaspoon rather than buying a ground jar.'),
    # Aliased to plain "cloves" and to "whole cloves" on purpose: this is the
    # only clove jar in the house, so a recipe calling for whole buds has to land
    # here and be told about the substitution rather than silently miss.
    Spice('ground_cloves', 'Ground Cloves', ('cloves', 'clove powder', 'laung',
                                             'powdered cloves', 'whole cloves',
                                             'clove buds'),
          'ground', 'early', False, 0, '#6b4028',
          'The bully of the rack, and there is no whole jar to fall back on. '
          'About 1/8 tsp stands in for 3-4 whole buds — and unlike buds you '
          'cannot fish it out, so a braise keeps getting more clove the longer '
          'it sits. Start lower than feels right. Keeps well over a year: '
          'cloves are heavy in eugenol, which does not flash off the way most '
          'ground aromatics do.'),
    Spice('sichuan_peppercorn', 'Sichuan Peppercorn', ('szechuan peppercorn', 'sichuan pepper', 'hua jiao'),
          'whole', 'temper', False, 0, '#7a3b3b',
          'Numbing, not hot — the "ma" in mala. Toast dry until fragrant, then '
          'grind. Sift out the black seeds, they are just grit.'),
    Spice('jamaican_hot_curry', 'Jamaican Hot Curry', ('jamaican curry', 'jamaican curry powder'),
          'blend', 'bloom', True, 5, '#c98a14',
          'Turmeric-heavy and genuinely hot. Traditionally burned into hot oil for '
          '30 seconds before anything else goes in — that step is the flavour.'),
    Spice('sun_dried_tomato_powder', 'Sun-Dried Tomato Powder', ('tomato powder', 'sundried tomato powder'),
          'ground', 'mid', True, 0, '#8c2f1c',
          'Concentrated savoury-sweet depth with a little acidity, which is exactly '
          'the kind of brightness that reads as "more flavour" rather than sour.'),

    # ── being used up ────────────────────────────────────────────────────────
    # Retired from the rack but not from the kitchen. They keep their entries so
    # recipes can spend them where they genuinely substitute for something the
    # dish already wanted. Each note carries the conversion, because a swap that
    # changes the salt or doubles the cumin is worse than wasting the jar.
    Spice('onion_salt', 'Onion Salt', ('onion salt',),
          'blend', 'mid', True, 0, '#ece3d2',
          'BEING USED UP — roughly 3 parts salt to 1 part onion powder, about '
          '4.5g of salt per teaspoon. Use it ONLY where a recipe already wants '
          'onion powder AND salt: 1 tsp of this replaces about 3/4 tsp of onion '
          'powder, and 4.5g must then come OFF the salt figure. If a dish does '
          'not want onion powder, do not reach for it.'),
    Spice('chili_powder', 'Chili Powder', ('chilli powder', 'chile powder',
                                           'american chili powder'),
          'blend', 'mid', True, 3, '#a83c1e',
          'BEING USED UP — an American-style BLEND: mild chile plus cumin, '
          'oregano and garlic. Use it where a Mexican or Tex-Mex dish already '
          'wants a mild chile AND cumin, and then CUT the separate cumin by '
          'about half, or the dish doubles up. Far milder than cayenne, so it '
          'is not a heat substitute for anything.'),
    Spice('parsley', 'Parsley', ('dried parsley', 'flat leaf parsley'),
          'herb', 'garnish', False, 0, '#6b8f4e',
          'BEING USED UP — dried parsley is colour, not flavour. Free to scatter '
          'over a finished brown dish that wants to look alive. It never changes '
          'how anything tastes, so it can never make a recipe worse; it just '
          'empties the jar.'),

    # ── specialty & rare ─────────────────────────────────────────────────────
    Spice('nutmeg', 'Nutmeg', ('ground nutmeg', 'jaiphal'),
          'whole', 'off_heat', False, 0, '#7a5333',
          'Grate to order — pre-ground nutmeg is a different, sadder spice. A few '
          'rasps into cream sauces and lamb.'),
    Spice('mace', 'Mace', ('javitri', 'ground mace'),
          'ground', 'early', False, 0, '#c98a3c',
          'The nutmeg husk — lighter and more floral than the seed. Classic in '
          'white sauces and Mughal braises where nutmeg would be too dark.'),
    Spice('black_cardamom', 'Black Cardamom', ('badi elaichi', 'brown cardamom'),
          'whole', 'early', False, 0, '#33281f',
          'Smoke-dried, camphorous, nothing like green cardamom. One pod, whole, '
          'into a braise, removed before serving.'),
    Spice('grains_of_paradise', 'Grains of Paradise', ('melegueta pepper', 'alligator pepper'),
          'whole', 'dry_rub', False, 2, '#6b5638',
          'Peppery with a citrus-cardamom lift. The signature of West African Suya '
          'alongside ginger and chile. Crack coarsely.'),
    Spice('annatto_seeds', 'Annatto Seeds', ('achiote', 'achiote seeds', 'annatto'),
          'seed', 'temper', False, 0, '#b5451c',
          'Whole seeds, and they are rock hard — infuse in warm oil for a few '
          'minutes and strain, do not try to eat them or grind them.'),
    Spice('purple_shallot_powder', 'Purple Shallot Powder', ('shallot powder', 'fried shallot powder'),
          'ground', 'mid', True, 0, '#8a6a7a',
          'BEING USED UP — dried and ground, a shallot is most of the way to an '
          'onion: what makes fresh shallot worth having is its texture and '
          'delicate sweetness, and neither survives the grinder. Substitute it '
          '1:1 wherever a recipe wants onion powder, until the jar is empty. '
          'Slightly sweeter and higher in sugar, so it burns even faster — keep '
          'it off the sear like the rest of the allium powders.'),
    Spice('umami_steak_seasoning', 'Umami Steak Seasoning', ('umami bomb', 'umami seasoning'),
          'blend', 'dry_rub', True, 0, '#4a3b2c',
          'PROVEN FAILURE ON STEAK (rated 2/10, badly over-salted and muddled). '
          'Heavily pre-salted. If it is used at all it belongs in ground meat or a '
          'gravy, and the recipe must add zero extra salt.'),
)

SPICE_BY_KEY = {s.key: s for s in SPICES}

# Every string that should resolve to a spice, lowercased. Built once so
# validating a model response is a dict lookup rather than a fuzzy search.
_ALIAS_INDEX = {}
for _s in SPICES:
    _ALIAS_INDEX[_s.name.lower()] = _s.key
    _ALIAS_INDEX[_s.key.replace('_', ' ')] = _s.key
    for _alias in _s.aka:
        _ALIAS_INDEX[_alias.lower()] = _s.key


# ── the stove shelf ──────────────────────────────────────────────────────────
# Above the stove, immediately right of the racks. Not a rack row: these are the
# things reached for on every single dish, in bigger containers. Salt lives here
# and salt is the most important seasoning decision in the app, so it gets to be
# a first-class object rather than an afterthought in the pantry list.
STOVE: tuple = (
    # Display name is OVERRIDDEN at render time from the salt_brand setting (see
    # recipes.rack_view). The jar and the recipes must never be able to disagree
    # about which salt is in the house -- that mismatch is precisely the error
    # that produced the 2/10 steak.
    Spice('salt', 'Table Salt', ('salt', 'kosher salt', 'table salt',
                                 'iodized salt', 'fine salt',
                                 'diamond crystal', 'morton kosher'),
          'ingredient', 'dry_rub', False, 0, '#f2f0ea',
          'The one measurement that must never be guessed. Recipes give salt in '
          'GRAMS and the app converts to spoons of whatever is actually on this '
          'shelf, because a teaspoon of table salt is more than double a '
          'teaspoon of Diamond Crystal.'),
    Spice('msg', 'MSG', ('monosodium glutamate', 'accent', 'aji no moto', 'ajinomoto'),
          'ingredient', 'mid', False, 0, '#fbfaf6',
          'About a third of a teaspoon per pound on ground meat and savoury '
          'braises - standing equipment, and already accounted for in the salt '
          'baseline, so do not deduct salt for it. Amplifies perceived '
          'saltiness. Only if you go well above that dose, cut the salt by about '
          '20% or the dish lands over-seasoned.'),
    Spice('bulk_black_pepper', 'Black Pepper (big jar)', ('black pepper', 'ground black pepper'),
          'ground', 'mid', False, 0, '#33302c',
          'The everyday pepper, and the primary one going forward. Pre-ground, so '
          'its aroma fades within months of opening — buy small and often rather '
          'than a drum that goes dusty. Where pepper is genuinely the headline '
          '(steak, cacio e pepe), whole peppercorns cracked to order are a real '
          'upgrade over any pre-ground jar, whatever the origin on the label.'),
    Spice('saffron', 'Saffron', ('kesar', 'saffron threads'),
          'whole', 'early', False, 0, '#d8500f',
          'Bloom the threads in a splash of warm water or milk for 10 minutes '
          'first. Dropped in dry it just sits there being expensive.'),
    Spice('bay_leaves', 'Bay Leaves', ('bay leaf', 'bay', 'laurel', 'tej patta'),
          'whole', 'early', False, 0, '#6f7a4e',
          'In whole at the start of anything wet, out before serving. Its job is '
          'a background note you only notice when it is missing, and nothing else '
          'in this kitchen does that job. Two leaves for a pot; more turns soapy.'),
)


# ── the sauce shelf ──────────────────────────────────────────────────────────
# Bottles and tubs rather than jars, and the reason they are here rather than in
# a list somewhere is the reason everything else is here: a seasoning the app
# cannot see is a seasoning the model will not use, and one it cannot weigh is a
# seasoning that quietly wrecks the salt.
#
# Nearly every one of these is salt in solution. A tablespoon of soy sauce is
# about a third of the entire salt budget for a pound of meat, and it has never
# appeared in `salt.grams` in this app's life. `salt_per_tbsp` is what fixes
# that: the prompt prints the figure beside the jar and the model subtracts it,
# the same way it already subtracts the salt inside a Cajun blend.
#
# Not re-sorted by usage. These are grouped by what they are, because that is how
# a hand finds a bottle it has picked up a hundred times.
SAUCES: tuple = (
    # An unqualified "soy sauce" means this one -- that is what a recipe writer
    # means by the words, and dark soy has to be asked for by name. Same rule
    # that keeps the bulk pepper from losing "black pepper" to the Zanzibar jar.
    Spice('light_soy_sauce', 'Light Soy Sauce', ('soy sauce', 'soya sauce', 'shoyu',
                                                 'light soy', 'usukuchi', 'regular soy sauce'),
          'sauce', 'mid', False, 0, '#4a2a18',
          'The seasoning soy, and the biggest hidden salt in the kitchen: about '
          '2.4g of salt a tablespoon, which is a third of what a pound of meat is '
          'allowed. Count it against the salt and take that much off the measured '
          'figure. Goes in with the liquid — poured onto a screaming dry pan it '
          'scorches into something acrid before it seasons anything. Keeps at room '
          'temperature but fades there — the fridge holds its aroma for months '
          'longer.',
          2.4),
    Spice('dark_soy_sauce', 'Dark Soy Sauce', ('dark soy', 'lao chou', 'thick soy sauce',
                                               'dark soya sauce', 'black soy sauce'),
          'sauce', 'mid', False, 0, '#1c1410',
          'Colour and molasses depth, not seasoning — used by the TEASPOON where '
          'light soy is used by the tablespoon, and it stains a whole pan '
          'mahogany. A tablespoon where a teaspoon was meant makes the dish look '
          'burnt and taste faintly bitter. Still carries about 2g of salt a '
          'tablespoon. Never a one-for-one swap for light soy. Fridge after opening, '
          'same as its lighter sibling.',
          2.0),
    Spice('oyster_sauce', 'Oyster Sauce', ('oyster flavoured sauce', 'oyster flavored sauce',
                                           'stir fry sauce'),
          'sauce', 'mid', False, 0, '#3d2410',
          'The fastest route to a stir-fry that tastes like a restaurant, and the '
          'fastest route to over-salting one: about 1.4g of salt a tablespoon, on '
          'top of sugar and starch that tighten a sauce as it reduces. In near the '
          'end, off a high flame, and expect the sauce to thicken after it. '
          'REFRIGERATE once opened — this one genuinely spoils.',
          1.4),
    Spice('toasted_sesame_oil', 'Toasted Sesame Oil', ('sesame oil', 'roasted sesame oil',
                                                       'dark sesame oil'),
          'oil', 'off_heat', True, 0, '#b4761c',
          'A seasoning that happens to be a liquid, never the cooking fat. It '
          'smokes low and turns bitter, and the aroma that is the entire point of '
          'it is the first thing heat removes. Off the burner, at the end, a '
          'teaspoon at a time. A recipe that says "fry in sesame oil" means a '
          'neutral oil with this stirred in afterwards. A delicate oil that goes '
          'rancid faster than it runs out: keep it in the fridge and it stays '
          'nutty rather than turning flat and waxy.'),
    Spice('mirin', 'Mirin', ('aji-mirin', 'ajimirin', 'sweet rice wine', 'hon-mirin',
                             'mirin style seasoning'),
          'sauce', 'mid', True, 0, '#e0c079',
          'The bottle here is Kikkoman Aji-Mirin, a mirin-STYLE seasoning: corn '
          'syrup and a little salt rather than brewed hon-mirin. So it is sweeter '
          'than the real thing, it browns and can catch, and it brings a trace of '
          'salt with it. A tablespoon per pound gives gloss and roundness; much '
          'more and the glaze goes candied. REFRIGERATE after opening — the '
          'sugar and the low alcohol are the reason the bottle says so, and it '
          'is where the aji-mirin bottles differ from true hon-mirin, which '
          'keeps in a cupboard on its own alcohol.',
          0.15),
    Spice('cooking_sake', 'Cooking Sake', ('ryorishu', 'ryōrishu', 'japanese cooking sake',
                                           'sake', 'cooking rice wine'),
          'sauce', 'mid', False, 0, '#e8e4c8',
          'Salted ryōrishu — roughly 2% salt, which makes it a seasoning as well '
          'as an alcohol and means it is NOT interchangeable with drinking sake. '
          'Its job is to strip the raw smell off meat and add depth; give it a '
          'moment at a simmer or the dish tastes of raw alcohol. Fridge after '
          'opening; it is closer to a seasoning than to a wine.',
          0.35),
    # GRANULES, not a bottled concentrate, and the salt figure is per tablespoon
    # of the powder — which is an enormous dose nobody would ever use. That is the
    # point: a rounded teaspoon eyeballed into half a cup of water is four times
    # the stock it should be and a gram and a half of unaccounted salt.
    Spice('dashi', 'Hondashi', ('dashi', 'bonito dashi', 'bonito soup stock',
                                'katsuo dashi', 'japanese soup stock', 'dashi granules',
                                'instant dashi'),
          'ingredient', 'early', False, 0, '#c2a066',
          'Instant bonito stock in granule form. Make it up first — about 1 TEAsp '
          'to 2 cups of hot water for drinking-strength stock, so half a cup takes '
          'a scant 1/4 TEAsp — and MEASURE it rather than shaking the jar over the '
          'pan, because the powder is roughly a third salt and it is the easiest '
          'thing here to quadruple by accident. It already contains MSG and sugar, '
          'so a dish using it does not want MSG on top. Use it wherever a recipe '
          'would otherwise get plain water. The one thing on this shelf that must '
          'NOT go in the fridge: it is a powder, and condensation turns it to a '
          'brick. Sealed, cool, dry.',
          3.4),
    Spice('doubanjiang', 'Doubanjiang', ('pixian doubanjiang', 'broad bean paste',
                                         'fermented broad bean paste', 'chili bean paste',
                                         'toban djan', 'doubanjang', 'pixian bean paste'),
          'paste', 'bloom', True, 3, '#8f2a16',
          'Pixian, and the backbone of everything Sichuan — also the saltiest '
          'thing in the cupboard at roughly 1.8g of salt a tablespoon. Fry it in '
          'oil over a MEDIUM flame for 30 seconds until the oil goes red; skip '
          'that and it tastes raw and harsh. Chop the beans first if they are '
          'whole. On a high flame it burns, and burnt doubanjiang is bitter for '
          'the whole dish. Fridge once opened, and smooth the surface flat so the '
          'oil sits over it.',
          1.8),
    Spice('gochujang', 'Gochujang', ('korean chili paste', 'gochoojang', 'kochujang',
                                     'korean red pepper paste'),
          'paste', 'mid', True, 2, '#b4261a',
          'Sweet, deeply savoury and only moderately hot — the sugar in it browns '
          'and then burns, so it goes into liquid rather than onto a dry hot pan. '
          'One of the few acid sources this kitchen actually likes, because it '
          'reads savoury rather than sour. About 0.8g of salt a tablespoon. Fridge '
          'once opened, where it will happily keep for a year and slowly darken.',
          0.8),
    # The KEY still says soybean paste because the tub was described that way when
    # it was first written down, and a key is a stable id that the layout and the
    # usage counts are already keyed on. The display name follows the label on the
    # jar, the same way the salt jar does. Both sets of words resolve here.
    Spice('garlic_soybean_paste', 'Black Bean Garlic Sauce', ('black bean garlic sauce',
                                                              'black bean sauce',
                                                              'lkk black bean garlic sauce',
                                                              'fermented black beans',
                                                              'douchi',
                                                              'garlic soybean paste',
                                                              'lkk garlic soybean paste',
                                                              'soybean paste with garlic'),
          'paste', 'bloom', True, 0, '#3f3128',
          'Lee Kum Kee, and the black specks are douchi — fermented black soybeans, '
          'which are cured in salt and taste like it: about 1.6g of salt a '
          'tablespoon. Already heavily garlicked, so no garlic powder goes on top '
          'of it. Fry it briefly in oil to wake the beans up, then get liquid in '
          'before it catches. Mash the beans against the pan if you want it to '
          'disappear into a sauce rather than sit in it as specks. Fridge once '
          'opened.',
          1.6),
)


# ── always in the house ──────────────────────────────────────────────────────
# Not jars, and deliberately not resolvable as jars: fresh garlic is not the
# garlic powder on the rack, and `resolve()` refuses anything called fresh for
# exactly that reason. But the model still needs to know they are here, or it
# writes them onto the shopping list as though tonight depends on a trip out.
# Name and one line each, straight into the prompt.
STAPLES = (
    ('Fresh garlic', 'Always in. Not the same ingredient as garlic powder and '
                     'never a substitute for it in either direction.'),
    ('Fresh ginger', 'Always in. Bright and hot where the dried jar is warm and '
                     'dusty — again, a different spice, not a stronger one.'),
    ('Short-grain rice', 'Sticky, for anything Japanese or Korean and anything '
                         'eaten with a spoon or chopsticks.'),
    ('Long-grain rice', 'Separate grains — basmati and the like, for everything '
                        'else. Salt its water; it is a third of the plate and it '
                        'dilutes a blend calibrated to the meat.'),
)


# ── owned, but deliberately not in play ──────────────────────────────────────
# Things in the pantry that were considered for the stove shelf and left in the
# cupboard. Recorded with the reason so the decision does not get re-litigated
# every time someone opens that cupboard. NOT part of the inventory the model
# sees: a jar that should not be reached for is worse than a jar that is absent,
# because the model will find a use for anything you show it.
IN_STORAGE = (
    ('Parsley — using up, not rebuying',
     'Dried parsley is colour, not flavour -- the herb that loses the most in '
     'drying, and the one where fresh is genuinely a different ingredient. It was '
     'occupying a slot to make brown dishes look alive.'),
    ('Red Pepper (jar reused)',
     'Nobody could say which chile was in it. Between Cayenne, Kashmiri, Ancho, '
     'Chipotle, Gochugaru and Crushed Chili there was no heat it uniquely gave, '
     'and an unlabelable jar cannot be reasoned about.'),
    ('Onion Salt — using up, not rebuying',
     'Roughly three parts salt to one part onion powder, so a teaspoon smuggles '
     'about 4.5g of salt past a recipe calibrated in grams. Onion powder plus '
     'measured salt is the same seasoning with a number you control, and both '
     'are already on the rack.'),
    ('Chili Powder — using up, not rebuying',
     'American chili powder is a BLEND -- mild chile plus cumin, oregano and '
     'garlic -- so it double-doses the cumin in anything Mexican while being far '
     'milder than cayenne. Between Cayenne, Kashmiri, Ancho, Chipotle, Gochugaru, '
     'Crushed Chili and Red Pepper there is no heat it uniquely provides.'),
    ('Lemon Pepper',
     'Citrus-forward, and a sour top note is the one flavour direction this '
     'kitchen actively dislikes. Zanzibar pepper plus garlic powder gets the '
     'pepper without the lemon.'),
    ('Salt & Pepper Seasoning',
     'A pre-mixed salt of unknown ratio, which is exactly what the gram-level '
     'salt calibration exists to avoid. Salt and pepper are both already here '
     'and both already measured.'),
    ('Blackened Seasoning',
     'Overlaps Cajun and NOLA Cajun, which are both already on the rack -- and '
     'the standing rule is to pick ONE of those two, because stacking them is '
     'how a dish ends up over-salted. A third is a worse version of that '
     'problem. Cajun plus extra smoked paprika and thyme is the same thing.'),
    ('Ground Star Anise',
     'The whole pods stay on the rack and the ground jar does not, for three '
     'reasons. Ground anise goes flat in months because the anethole that makes '
     'it smell of anything is volatile, while whole pods hold for years. Chinese '
     '5 Spice is already star-anise-dominant, so that jar IS the ground version '
     'in a more useful form. And whole pods are self-limiting -- you count them, '
     'and one is usually the whole dose -- whereas a teaspoon of ground is an '
     'enormous amount of a spice that bullies everything near it. If a recipe '
     'genuinely wants it ground, crack one pod.'),
    ('Chicken Spice',
     'A pre-salted all-purpose poultry rub. The one dish that scored 2/10 here '
     'was a pre-salted commercial blend, and chicken thighs are the most '
     'versatile canvas on the list -- a generic chicken rub is the least '
     'interesting thing to do with them. Garlic powder, onion powder, paprika '
     'and measured salt is the same blend with a salt number you control.'),
)

STOVE_BY_KEY = {s.key: s for s in STOVE}
SAUCE_BY_KEY = {s.key: s for s in SAUCES}
for _s in STOVE + SAUCES:
    _ALIAS_INDEX.setdefault(_s.name.lower(), _s.key)
    _ALIAS_INDEX.setdefault(_s.key.replace('_', ' '), _s.key)
    for _alias in _s.aka:
        _ALIAS_INDEX.setdefault(_alias.lower(), _s.key)

ALL_BY_KEY = {**SPICE_BY_KEY, **STOVE_BY_KEY, **SAUCE_BY_KEY}

# Everything that arrives already salted, with how much. Read by the prompt so
# the deduction is printed rather than remembered.
PRE_SALTED = tuple(s for s in ALL_BY_KEY.values() if s.salt_per_tbsp)


# ── where the jars sit ───────────────────────────────────────────────────────
# Seed layout only — the live one is in the database. Row 1 is eye level and
# arm's reach; row 4 is the stretch. Left rack = savoury foundation, right rack =
# heat and finishing, so most recipes are one grab from each side.
#
# 4 rows x 7 columns per rack, both racks full: 56 jars, every one of them
# exactly once.
DEFAULT_LAYOUT = {
    # Both wall racks are now exactly full: 28 slots, 28 jars, no gaps. Anything
    # new from here displaces something rather than slotting in.
    'left': (
        # row 1 — reach for these without looking
        ('garlic_powder', 'onion_powder', 'smoked_paprika', 'paprika',
         'cumin', 'coriander', 'turmeric'),
        # row 2 — weekly. Onion Salt sits two along from Onion Powder rather than
        # beside it: they look alike and one of them is 75% salt.
        ('ginger', 'garam_masala', 'curry_powder', 'fried_garlic',
         'sesame_seeds', 'mushroom_powder', 'white_pepper'),
        # row 3 — the herb row. The two oreganos are adjacent so that grabbing the
        # wrong plant takes a deliberate mistake rather than a glance.
        ('mexican_oregano', 'oregano_leaves', 'italian_seasoning', 'thyme',
         'five_spice', 'berbere', 'sun_dried_tomato_powder'),
        # row 4 — the stretch: whole seeds and specialists. Kasuri Methi holds its
        # slot while it is out of stock, so nothing has to move twice when the jar
        # arrives. Annatto came across from the right rack's finishing row when
        # Shichimi Togarashi arrived: annatto is a hard whole seed infused in warm
        # oil, which is this row's whole subject, and it was the only thing on that
        # finishing row that never touches a finished plate.
        ('kasuri_methi', 'sage', 'fenugreek_seeds', 'black_mustard_seeds',
         'fennel_seeds', 'nigella_seeds', 'annatto_seeds'),
    ),
    'right': (
        # row 1 — the heat you actually use
        ('cayenne', 'gochugaru', 'crushed_chili', 'chipotle',
         'kashmiri_chili', 'cajun', 'jerk'),
        # row 2 — weekly heat and the American/Caribbean blends. Celery Seed sits
        # here rather than with the other seeds: it is what those rubs are made
        # of, so it belongs where you reach when building one.
        ('ancho_chili', 'ground_mustard', 'tex_mex', 'bbq',
         'nola_cajun', 'jamaican_hot_curry', 'celery_seed'),
        # row 3 — warm aromatics. Star anise moved across from the left rack: it
        # belongs with the braising spices, not with the tempering seeds.
        ('cinnamon', 'allspice', 'cardamom', 'ground_cloves',
         'star_anise', 'sichuan_peppercorn', 'nutmeg'),
        # row 4 — the finishing four first (they go on the plate, never in the
        # pan), then the genuine rarities, then Shichimi Togarashi, which is a
        # finishing condiment and belongs at the front of this row by kind. It
        # sits at the end because that is the slot Annatto vacated, and a jar
        # arriving should cost one physical move, not five.
        ('silk_chili', 'black_urfa_chili', 'zaatar', 'sumac',
         'mace', 'black_cardamom', 'shichimi_togarashi'),
    ),
    # Above the stove, immediately right of the racks. These are here because of
    # their CONTAINERS as much as their use -- the big jars do not fit a rack
    # slot. Two rows of five rather than one row of ten: ten jars across is
    # unreadable on a phone. Not frequency-sorted; moving the salt would just be
    # annoying.
    # Fourteen, in three rows that each mean something rather than a count that
    # happens to wrap. Narrower rows also suit a shelf that is not as wide as the
    # wall racks.
    'stove': (
        # Reached for on nearly every dish.
        ('salt', 'msg', 'bulk_black_pepper', 'bay_leaves'),
        # Occasional, and here because of the jar rather than the frequency.
        ('wild_hing', 'saffron', 'grains_of_paradise', 'black_fungus',
         'umami_steak_seasoning'),
        # Being used up. Kept together on purpose: this row shortens and then
        # disappears, instead of leaving gaps scattered through the shelf.
        ('zanzibar_black_pepper', 'purple_shallot_powder', 'onion_salt',
         'chili_powder', 'parsley'),
    ),
    # Bottles and tubs, beside the stove. Grouped by what they are rather than by
    # frequency: a hand that has picked up the soy a hundred times finds it by
    # where its neighbours are, and the pastes are the ones you have to read.
    'sauces': (
        # The stir-fry four, reached for together.
        ('light_soy_sauce', 'dark_soy_sauce', 'oyster_sauce', 'toasted_sesame_oil'),
        # The Japanese liquids.
        ('mirin', 'cooking_sake', 'dashi'),
        # The fermented pastes — the salty, spoonable end of the shelf.
        ('doubanjiang', 'gochujang', 'garlic_soybean_paste'),
    ),
    # Not a shelf with slots. Row and column are recorded only to keep one
    # storage model for everything; they mean nothing here.
    'freezer': (
        ('curry_leaves',),
    ),
}

# Every shelf is drawn. The freezer holds one bag, so it renders as a single jar
# in a corner rather than as a separate kind of thing — a list beside a picture
# was more machinery than one item deserved, and it made the freezer look like a
# different category of storage instead of just a smaller shelf.
RACKS = ('left', 'right', 'stove', 'sauces', 'freezer')

RACK_LABELS = {'left': 'Left Rack', 'right': 'Right Rack',
               'stove': 'Above the Stove', 'sauces': 'Sauces & Pastes',
               'freezer': 'Freezer'}
# Frequency rows, and they only mean anything on the two wall racks — those are
# the shelves sorted by how often a hand goes to them. Everywhere else the rows
# group by kind, so numbering them Daily/Weekly would be a lie about the shelf.
ROW_LABELS = ('Daily', 'Weekly', 'Regular', 'Rare')


# Phrases that must NEVER auto-resolve, because they name different chiles to
# different cooks and the app cannot tell which was meant. "Red chili powder" is
# ground cayenne in one kitchen (heat 8) and Kashmiri in another (heat 2) -- a
# four-fold error -- and containment would otherwise hand it to the American
# "Chili Powder" BLEND, quietly adding cumin and oregano to an Indian dish.
# Better to surface it and make the recipe name a chile.
AMBIGUOUS = frozenset({
    'red chili powder', 'red chilli powder', 'red pepper', 'red pepper powder',
    'ground red pepper', 'chile', 'chili', 'chilli',
})


def resolve(name: str):
    """Map whatever the model called a spice onto a registry entry, or None.

    Deliberately forgiving — the model will write "ground cumin" or "Kashmiri
    chilli" or "chili flakes" and every one of those has to land on a jar, because
    a spice that does not resolve is a spice the rack visual cannot point at.
    """
    if not name:
        return None
    probe = ' '.join(str(name).lower().replace('-', ' ').split())

    # "fresh ginger" is not the dried ginger in the jar, and "fresh garlic" is
    # not garlic powder — the registry says so in as many words. Anything called
    # fresh belongs on the shopping list, so refuse to place it on the rack.
    # ("freshly ground black pepper" survives: that is a different word.)
    if 'fresh' in probe.split():
        return None

    if probe in AMBIGUOUS:
        return None

    hit = _ALIAS_INDEX.get(probe)
    if hit:
        return ALL_BY_KEY[hit]

    # Try again without parenthetical qualifiers: "silk chili (aleppo)".
    if '(' in probe:
        stripped = probe.split('(')[0].strip()
        hit = _ALIAS_INDEX.get(stripped)
        if hit:
            return ALL_BY_KEY[hit]

    # Last resort: a unique containment match, so "kashmiri chili powder" still
    # finds the Kashmiri jar.
    #
    # Deliberately narrow. A naive substring match resolves "truffle salt" and
    # "garlic salt" to the kosher salt on the stove shelf, which would put the
    # wrong jar on screen AND quietly drop a real shopping-list item — so short
    # single-word aliases ("salt", "jerk", "bbq") are excluded from this pass.
    # They can still match exactly; they just cannot swallow a longer phrase.
    def specific(text: str) -> bool:
        return ' ' in text or len(text) >= 6

    # Two directions, and they are not symmetric:
    #
    #   forward  (alias inside probe)  -- "kashmiri chili powder" contains the
    #            alias "kashmiri chili". The extra words are noise; fine.
    #   reverse  (probe inside alias)  -- only when the probe is a PREFIX of the
    #            alias, so "urfa" reaches "urfa biber". Words added AFTER a name
    #            elaborate it; words added BEFORE it specialise it, and a generic
    #            request must never be silently specialised. Without the prefix
    #            rule, a bare "chili powder" resolved to Ancho Chili purely
    #            because "ancho chili powder" was the longest string containing
    #            it -- lighting a specific jar for a request that named none.
    matches = [(len(text), key) for text, key in _ALIAS_INDEX.items()
               if specific(text) and (text in probe
                                      or (len(probe) >= 5 and text.startswith(probe)))]
    if not matches:
        return None

    # Longest alias wins rather than demanding a unique hit: "sichuan
    # peppercorns" matches both "sichuan peppercorn" and the bare "peppercorns"
    # on the black pepper jar, and the longer overlap is the right answer every
    # time. A genuine tie between two different jars stays unresolved.
    best = max(length for length, _ in matches)
    winners = {key for length, key in matches if length == best}
    if len(winners) == 1:
        return ALL_BY_KEY[winners.pop()]
    return None


def validate_default_layout() -> None:
    """Everything we own placed exactly once, every slot holding a real jar.

    Checked across ALL shelves together rather than per-shelf, because where a
    jar lives is data and has nothing to do with which tuple above it happens to
    be declared in. Zanzibar pepper is the case that proved it: a rack spice by
    nature, but it ships in a jar too tall for a rack slot, so it lives above the
    stove. Tying position to declaration made that a validation error instead of
    a fact about the kitchen.

    Called by the schema bootstrap. A typo here would silently drop a jar off the
    visual, which is the one bug this app cannot afford.
    """
    placed = [key for shelf in RACKS for row in DEFAULT_LAYOUT[shelf] for key in row]
    duplicates = {k for k in placed if placed.count(k) > 1}
    if duplicates:
        raise ValueError(f'jar placed twice in the default layout: {sorted(duplicates)}')
    missing = set(ALL_BY_KEY) - set(placed)
    if missing:
        raise ValueError(f'jar missing from the default layout: {sorted(missing)}')
    unknown = set(placed) - set(ALL_BY_KEY)
    if unknown:
        raise ValueError(f'unknown jar in the default layout: {sorted(unknown)}')


def wall_racks() -> tuple:
    """The shelves that get re-sorted by frequency. The stove shelf does not."""
    return ('left', 'right')
