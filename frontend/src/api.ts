import type {
  Health, HistoryRow, Proposal, RackView, Recipe, RecipePayload, SettingsResponse,
  Placement,
} from './types'

// No credential rides on these requests, and there is nowhere to put one. The
// server decides what this caller may see from the TCP address the request
// arrived on: a tailnet peer gets the whole app, everyone else gets the rack and
// the frozen demo. See spice/auth.py.
//
// That is why there is no token here, no localStorage, and no retry-with-a-code
// path — a 401 is a fact about which network you are on, not a prompt.

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`,
                              { headers: { 'Content-Type': 'application/json' }, ...init })
  const text = await response.text()
  let body: any = null
  try { body = text ? JSON.parse(text) : null } catch { body = null }

  if (!response.ok) {
    // The backend deliberately answers model failures with a human sentence;
    // surface that rather than a status code.
    throw new Error(body?.error || `Request failed (${response.status})`)
  }
  return body as T
}

const post = <T,>(path: string, body: unknown) =>
  call<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  health: () => call<Health>('/health'),

  /** The frozen example. Public, and costs nothing to serve. */
  demo: () => call<{ payload: RecipePayload }>('/demo'),

  rack: () => call<RackView>('/rack'),
  setStock: (spice_key: string, stock: string) =>
    post<{ ok: boolean }>('/rack/state', { spice_key, stock }),
  proposal: (mode: string) => call<Proposal>(`/rack/proposal?mode=${mode}`),
  applyLayout: (placements: Placement[]) => post<RackView>('/rack/layout', { placements }),

  ask: (body: { query: string; portion_lb?: number; servings?: number; extra?: string }) =>
    post<Recipe>('/ask', body),

  recipes: (limit = 50) => call<{ recipes: HistoryRow[] }>(`/recipes?limit=${limit}`),
  recipe: (id: number, scale?: number) =>
    call<Recipe>(`/recipes/${id}${scale && scale !== 1 ? `?scale=${scale}` : ''}`),
  rate: (id: number, body: Record<string, unknown>) =>
    post<Recipe>(`/recipes/${id}/rate`, body),

  settings: () => call<SettingsResponse>('/settings'),
  saveSettings: (patch: Record<string, string>) =>
    post<{ settings: Record<string, string> }>('/settings', patch),
}
