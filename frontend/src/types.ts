// Mirrors the Python contract in spice/schema.py and spice/recipes.py.
// Nothing here is a second source of truth — no spice name, stage or rack label
// is written down in TypeScript. Anything that names a jar comes over the wire.

// 'using_up' is available like 'ok', but flagged so recipes prefer it: a jar
// on its way out that will not be rebought.
export type Stock = 'ok' | 'low' | 'using_up' | 'out'

export type Jar = {
  spice_key: string
  name: string
  form: string
  stage: string
  burns: boolean
  heat: number
  color: string
  note: string
  rack: string
  row: number
  col: number
  stock: Stock
  opened_on: string | null
  uses: number
}

export type RackView = {
  jars: Jar[]
  racks: string[]
  rack_labels: Record<string, string>
  row_labels: string[]
  /** The shelves those row labels actually describe. */
  wall_racks?: string[]
  stages: string[]
}

export type BlendItem = {
  spice: string
  spice_key: string
  name: string
  amount: string
  tsp: number
  stage: string
  stages?: string[]
  step: number
  why: string
  note: string
  burns: boolean
  is_pantry: boolean
  heat: number
  color: string
  out_of_stock?: boolean
}

/** One bowl: every jar that enters the pan at the same moment. */
export type BlendGroup = {
  stage: string
  when: string
  items: BlendItem[]
  premix: boolean
  keep_apart: string
  bowl: number
}

export type Step = {
  n: number
  title: string
  body: string
  minutes: number
  heat: string
  watch_for: string
  spices: { spice_key: string; name: string; amount: string; color: string }[]
}

export type Salt = {
  grams: number
  msg_grams: number
  when: string
  rationale: string
  /** Spoons of the configured brand, with the brand named. */
  display: string
  /** The same spoons without the brand - for under the jar, which is labelled. */
  spoons?: string
  msg_display?: string
  msg_spoons?: string
  brand: string
}

export type RecipePayload = {
  title: string
  cuisine: string
  protein: string
  portion_lb: number
  confidence: 'proven' | 'well_trodden' | 'adaptation' | 'experiment'
  why_this: string
  heat_level: number
  pan: string
  times: { prep_min: number; marinate_min: number; cook_min: number; total_min: number }
  blend: BlendItem[]
  blend_groups: BlendGroup[]
  salt: Salt
  from_kitchen: { item: string; amount: string; off_rack?: boolean }[]
  steps: Step[]
  salt_check: string
  serve_with: string
  leftovers: string
  warnings: string[]
}

export type Rating = {
  overall: number
  salt_delta: number
  heat_delta: number
  would_repeat: number | null
  notes: string
  rated_at: string
}

export type Recipe = {
  id: number
  created_at: string
  query: string
  title: string
  protein: string | null
  cuisine: string | null
  model: string | null
  payload: RecipePayload
  rating: Rating | null
}

export type HistoryRow = {
  id: number
  created_at: string
  query: string
  title: string
  protein: string | null
  cuisine: string | null
  heat_level: number | null
  overall: number | null
  salt_delta: number | null
  heat_delta: number | null
  notes: string | null
}

export type Placement = { spice_key: string; rack: string; row: number; col: number }

export type Proposal = {
  mode: 'balanced' | 'strict'
  placements: Placement[]
  moves: {
    spice_key: string
    name: string
    uses: number
    from: { rack: string; row: number; col: number }
    to: { rack: string; row: number; col: number }
  }[]
  total_recipes: number
  unused: string[]
}

export type Settings = Record<string, string>

export type SettingsResponse = {
  settings: Settings
  salt_brands: Record<string, { label: string; grams_per_tsp: number }>
  has_key: boolean
}

// /api/health is the app's only public statement about who is asking. To a
// caller off the tailnet it answers `status`, `authed: false`, `jars` and
// `version` and nothing else — the rest is deliberately absent rather than
// empty, so these are optional.
export type Health = {
  status: string
  authed: boolean
  version: string
  jars?: number
  recipes?: number
  rated?: number
  openrouter?: boolean
  model?: string
  asks_today?: number
  daily_limit?: number
  /** False while the SPICE_OPEN development override is what let you in. */
  via_tailnet?: boolean
}
