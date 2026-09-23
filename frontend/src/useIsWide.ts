import { useEffect, useState } from 'react'

// One breakpoint, shared by anything that needs to make a LAYOUT decision in
// JavaScript rather than CSS. Kept in sync with the media query in styles.css by
// hand — there is one number and it is written down twice, which is cheaper than
// a build-time bridge for a single value.
export const WIDE = 900

export function useIsWide(): boolean {
  const [wide, setWide] = useState(
    () => typeof window !== 'undefined' && window.innerWidth >= WIDE,
  )
  useEffect(() => {
    const query = window.matchMedia(`(min-width: ${WIDE}px)`)
    const update = () => setWide(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return wide
}
