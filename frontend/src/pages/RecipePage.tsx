import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { RecipeCard } from '../components/RecipeCard'
import { RatingSheet } from '../components/RatingSheet'
import type { RackView, Recipe } from '../types'

export function RecipePage() {
  const { id } = useParams()
  const [recipe, setRecipe] = useState<Recipe | null>(null)
  const [rack, setRack] = useState<RackView | null>(null)
  const [rating, setRating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api.recipe(Number(id)).then(setRecipe).catch((e) => setError(String(e.message)))
    api.rack().then(setRack).catch(() => setRack(null))
  }, [id])

  if (error) return <div className="page"><p className="error">{error}</p></div>
  if (!recipe) return <div className="page"><p className="muted">Loading…</p></div>

  return (
    <div className="page recipe-page">
      <RecipeCard payload={recipe.payload} rack={rack}
                  rated={!!recipe.rating} onRate={() => setRating(true)} />

      {recipe.rating && (
        <p className="rated-note">
          You gave this {recipe.rating.overall}/10
          {recipe.rating.notes ? ` — “${recipe.rating.notes}”` : ''}
        </p>
      )}

      {rating && (
        <RatingSheet
          existing={recipe.rating}
          onClose={() => setRating(false)}
          onSubmit={async (body) => { setRecipe(await api.rate(Number(id), body)) }}
        />
      )}
    </div>
  )
}
