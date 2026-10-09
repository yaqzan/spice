import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { useAccess } from '../access'
import { RecipeCard } from '../components/RecipeCard'
import { RatingSheet } from '../components/RatingSheet'
import type { RackView, Recipe } from '../types'
import { useDials } from '../useDials'

export function RecipePage() {
  const { id } = useParams()
  const { authed } = useAccess()
  const [recipe, setRecipe] = useState<Recipe | null>(null)
  const [rack, setRack] = useState<RackView | null>(null)
  const [rating, setRating] = useState(false)
  const [error, setError] = useState('')
  const [dials, setDials] = useDials()
  // Taps on + land faster than responses; only the latest one may paint.
  const latest = useRef(0)

  useEffect(() => {
    if (!id) return
    api.rack().then(setRack).catch(() => setRack(null))
  }, [id])

  useEffect(() => {
    if (!id) return
    const ticket = ++latest.current
    // The old card stays up while the new numbers are fetched, so the page
    // does not blank between taps; the amounts snap when they arrive.
    api.recipe(Number(id), dials)
      .then((r) => { if (ticket === latest.current) setRecipe(r) })
      .catch((e) => setError(String(e.message)))
  }, [id, dials])

  if (error) return <div className="page"><p className="error">{error}</p></div>
  if (!recipe) return <div className="page"><p className="muted">Loading…</p></div>

  return (
    <div className="page recipe-page">
      <RecipeCard payload={recipe.payload} rack={rack}
                  rated={!!recipe.rating} onDials={setDials}
                  onRate={authed ? () => setRating(true) : undefined} />

      {recipe.rating && (
        <p className="rated-note">
          {authed ? 'You gave this' : 'Rated'} {recipe.rating.overall}/10
          {recipe.rating.notes ? ` — “${recipe.rating.notes}”` : ''}
        </p>
      )}

      {rating && (
        <RatingSheet
          existing={recipe.rating}
          onClose={() => setRating(false)}
          onSubmit={async (body) => {
            // Only the rating: the response is the stored recipe, which would
            // throw away whatever the dials are set to.
            const rated = await api.rate(Number(id), body)
            setRecipe((r) => (r ? { ...r, rating: rated.rating } : rated))
          }}
        />
      )}
    </div>
  )
}
