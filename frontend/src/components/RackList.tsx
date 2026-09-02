import type { Jar } from '../types'

// The rack as words rather than a picture.
//
// The SVG is the right thing when you are standing at the shelf mid-cook and
// need to see WHERE a jar is. It is the wrong thing when you are physically
// sorting fifty-six jars, because a 38-pixel-wide jar can only carry a
// three-letter code and "GAR" is both Garlic Powder and Garam Masala. This view
// exists for the sorting job: full names, in position order, nothing abbreviated.

export function RackList({ jars, rackLabels, racks, rowLabels }: {
  jars: Jar[]
  racks: string[]
  rackLabels: Record<string, string>
  rowLabels: string[]
}) {
  return (
    <div className="rack-list">
      {racks.map((rackName) => {
        const mine = jars.filter((j) => j.rack === rackName)
        if (!mine.length) return null
        const rows = Array.from(new Set(mine.map((j) => j.row))).sort((a, b) => a - b)
        return (
          <section key={rackName} className="rack-list-rack">
            <h3>{rackLabels[rackName] || rackName}</h3>
            {rows.map((row) => (
              <div key={row} className="rack-list-row">
                <h4>
                  Row {row + 1}
                  {rackName !== 'stove' && rowLabels[row] &&
                    <em> · {rowLabels[row]}</em>}
                </h4>
                <ol>
                  {mine.filter((j) => j.row === row).sort((a, b) => a.col - b.col)
                    .map((jar) => (
                      <li key={jar.spice_key}>
                        <span className="pos">{jar.col + 1}</span>
                        <i style={{ background: jar.color }} />
                        <span className="nm">{jar.name}</span>
                        {jar.stock !== 'ok' &&
                          <b className={`stock-${jar.stock}`}>{jar.stock}</b>}
                      </li>
                    ))}
                </ol>
              </div>
            ))}
          </section>
        )
      })}
    </div>
  )
}
