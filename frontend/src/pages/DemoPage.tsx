import { useEffect, useState } from 'react'
import { api } from '../api'
import { RecipeCard } from '../components/RecipeCard'
import type { RackView, RecipePayload } from '../types'

// What a visitor off the tailnet lands on: one recipe, with the rack drawn to
// scale and the jars it needs lit up and numbered in the order they hit the pan.
//
// Served from a frozen fixture, so it costs nothing and looks the same whether
// or not there is credit on the API account. The page says so once, in four
// words, and then gets out of the way — it used to open with a paragraph
// explaining what the app was for, which is a thing you write when you do not
// trust the screen to speak for itself.

export function DemoPage() {
  const [payload, setPayload] = useState<RecipePayload | null>(null)
  const [rack, setRack] = useState<RackView | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.demo().then((d) => setPayload(d.payload))
      .catch(() => setError('The example recipe is not available right now.'))
    api.rack().then(setRack).catch(() => setRack(null))
  }, [])

  return (
    <div className="page demo-page">
      <header className="demo-hero">
        <h1>Spice</h1>
        <p className="muted small">A saved example.</p>
      </header>

      {error && <p className="error">{error}</p>}
      {payload
        ? <RecipeCard payload={payload} rack={rack} />
        : !error && <p className="muted">Loading…</p>}
    </div>
  )
}
