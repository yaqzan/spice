// Human phrasing for the enums in spice/rack.py.
//
// The KEYS are the contract and come over the wire; only the wording lives here.
// This is not a second registry — no spice name, alias or handling rule appears
// in TypeScript (see CLAUDE.md). It is one file rather than a copy in every
// component that needs to say "bloom" out loud.

/** rack.py STAGES — when a jar goes into the pan. */
export const STAGE_LABELS: Record<string, string> = {
  marinade: 'in the marinade',
  dry_rub: 'dry rub, before the sear',
  bloom: 'bloom in hot fat',
  temper: 'temper in oil first',
  early: 'early, with the aromatics',
  mid: 'after the sear, heat down',
  last_five: 'last 5 minutes',
  off_heat: 'off the heat',
  garnish: 'on the plate',
}

/** rack.py FORMS — what is physically in the jar. */
export const FORM_LABELS: Record<string, string> = {
  ground: 'ground',
  whole: 'whole',
  seed: 'whole seeds',
  flake: 'flakes',
  blend: 'blend',
  herb: 'dried herb',
  oil_cured: 'oil-cured',
  ingredient: 'ingredient',
  sauce: 'bottled sauce',
  paste: 'fermented paste',
  oil: 'finishing oil',
}

/** db.py STOCK_STATES — how much is left in it. */
export const STOCK_LABELS: Record<string, string> = {
  ok: 'Have it',
  low: 'Running low',
  using_up: 'Using up',
  out: 'Out',
}

export const stage = (key: string) => STAGE_LABELS[key] || key.replace(/_/g, ' ')
export const form = (key: string) => FORM_LABELS[key] || key.replace(/_/g, ' ')
