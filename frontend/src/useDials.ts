import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Dials } from './api'
import type { HeatLevel } from './types'

const LEVELS: HeatLevel[] = ['mild', 'medium', 'hot']

/** The card's dials, kept in the URL (?serves=4&heat=mild) so a reload or a
 *  shared link opens the recipe the way it was being cooked. */
export function useDials(): [Dials, (next: Dials) => void] {
  const [params, setParams] = useSearchParams()
  const serves = Number(params.get('serves')) || undefined
  const raw = params.get('heat') as HeatLevel | null
  const heat = raw && LEVELS.includes(raw) ? raw : undefined
  const dials = useMemo(() => ({ serves, heat }), [serves, heat])

  const set = useCallback((next: Dials) => {
    const out = new URLSearchParams(params)
    for (const [key, value] of Object.entries(next)) {
      if (value) out.set(key, String(value))
      else out.delete(key)
    }
    setParams(out, { replace: true })
  }, [params, setParams])

  return [dials, set]
}
