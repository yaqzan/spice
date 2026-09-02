// Amounts, with the two spoons pulled apart.
//
// "1 tsp" and "1 tbsp" differ by one character. Read at a glance, at small
// size, over a hot pan, that is a threefold error waiting to happen — the
// largest mistake available in a kitchen that otherwise measures salt to the
// gram. So the backend writes them as TEAsp and TBsp (schema.canonical_units),
// which already differ in length, in shape and in where the capitals fall, and
// this adds a third axis: colour. Distinguishable without reading carefully,
// which is the only kind of reading that happens mid-cook.
//
// Both tokens are spelled out here rather than built from a shared constant on
// purpose — if the backend's spelling ever changes, this file simply stops
// matching and renders plain text, instead of silently colouring the wrong word.
const UNITS = /(TEAsp|TBsp)/

export function Amount({ children }: { children: string }) {
  const parts = (children || '').split(UNITS)
  return (
    <>
      {parts.map((part, i) => {
        if (part === 'TBsp') return <b key={i} className="unit-tbsp">TBsp</b>
        if (part === 'TEAsp') return <b key={i} className="unit-tsp">TEAsp</b>
        return <span key={i}>{part}</span>
      })}
    </>
  )
}
