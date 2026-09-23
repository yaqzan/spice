import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

// The proteins that actually come out of this freezer, as one-tap starters.
// Typing on a phone with cold hands is the friction this removes.
const QUICK = ['Chicken thighs', 'Ground beef', 'Pork belly', 'Steak',
               'Lamb mince', 'Shrimp', 'Salmon', 'Paneer', 'Chicken wings', 'Beef chuck']

export function AskPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [portion, setPortion] = useState(1)
  const [extra, setExtra] = useState('')
  const [showExtra, setShowExtra] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function ask(text?: string) {
    const value = (text ?? query).trim()
    if (!value || busy) return
    setBusy(true)
    setError('')
    try {
      const recipe = await api.ask({ query: value, portion_lb: portion, extra })
      navigate(`/recipe/${recipe.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page ask-page">
      <h1>What are we cooking?</h1>

      <form onSubmit={(e) => { e.preventDefault(); ask() }}>
        <input className="ask-input" value={query} autoFocus
               placeholder="pork belly, something Korean"
               onChange={(e) => setQuery(e.target.value)} />

        <div className="portion">
          <span>Protein</span>
          <button type="button" onClick={() => setPortion((p) => Math.max(0.25, +(p - 0.25).toFixed(2)))}>−</button>
          <b>{portion} lb</b>
          <button type="button" onClick={() => setPortion((p) => +(p + 0.25).toFixed(2))}>+</button>
        </div>

        {showExtra ? (
          <textarea className="ask-extra" rows={2} value={extra}
                    placeholder="what else is in the fridge, who is eating, how long you have"
                    onChange={(e) => setExtra(e.target.value)} />
        ) : (
          <button type="button" className="link" onClick={() => setShowExtra(true)}>
            + add constraints
          </button>
        )}

        <button className="primary big" disabled={busy || !query.trim()}>
          {busy ? 'Working out the blend…' : 'Give me a recipe'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <div className="quick">
        {QUICK.map((item) => (
          <button key={item} disabled={busy} onClick={() => { setQuery(item); ask(item) }}>
            {item}
          </button>
        ))}
      </div>

      {busy && (
        <p className="muted centred">
          Reading the rack, checking what you have already eaten lately…
        </p>
      )}
    </div>
  )
}
