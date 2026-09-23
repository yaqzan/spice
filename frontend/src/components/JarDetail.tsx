import { useEffect } from 'react'
import { JarGlyph } from './SpiceRack'
import { STOCK_LABELS, form, stage } from '../labels'
import type { Jar, RackView } from '../types'

// What one jar is, once you have tapped it.
//
// The note is the reason this screen exists — fifty-six paragraphs of "bloom it
// or it stays dusty", "scorches above a gentle heat" — so it gets the room and
// the type size of the thing being read, not a caption squeezed under a header.
//
// Everything above the note is there to answer the question that made you tap:
// which jar is this, and where on the wall do I reach for it. The rest — form,
// stage, heat, whether it burns — is chips, because four labelled values in a
// grid is a spreadsheet and four chips is a glance.
//
// One component for both placements. On a phone it fills a sheet; on a desktop
// it sits in the aside beside the shelves. Rendering the same markup in both
// means the phone can never quietly fall behind the desktop.

/** 0-10 from rack.py, drawn rather than spelled out. */
function HeatMeter({ value }: { value: number }) {
  return (
    <span className="heat-meter" title={`heat ${value} of 10`}>
      <i style={{ width: `${value * 10}%` }} />
      <b>{value}/10</b>
    </span>
  )
}

function Chip({ children, tone }: { children: React.ReactNode; tone?: string }) {
  return <span className={`chip${tone ? ` chip-${tone}` : ''}`}>{children}</span>
}

export function JarDetail({ jar, view, authed, onStock, onClose }: {
  jar: Jar
  view: RackView
  authed: boolean
  onStock: (stock: string) => void
  onClose?: () => void
}) {
  const where = view.rack_labels[jar.rack] || jar.rack
  // Daily/Weekly/Regular/Rare belong to the two wall racks, which are the
  // shelves sorted by how often a hand goes to them. The stove and sauce
  // shelves group their rows by kind, so a frequency name there would be an
  // invention -- and which shelves those are comes over the wire, because this
  // file is not allowed to know one shelf from another.
  const wall = view.wall_racks ?? []
  const rowName = wall.includes(jar.rack) ? view.row_labels[jar.row] : ''

  return (
    <div className="jar-detail">
      <header className="jar-head">
        <JarGlyph colour={jar.color} />
        <div className="jar-title">
          <h2>{jar.name}</h2>
          {/* Where to reach, in the words the shelf labels use. This is the
              answer to the question the app was built for. */}
          <p className="jar-where">
            {where} <span>·</span> row {jar.row + 1} <span>·</span> position {jar.col + 1}
            {rowName && <em>{rowName}</em>}
          </p>
        </div>
        {onClose && (
          <button className="jar-close" onClick={onClose} aria-label="Close">×</button>
        )}
      </header>

      <div className="jar-chips">
        <Chip>{form(jar.form)}</Chip>
        <Chip tone="cuisine">{stage(jar.stage)}</Chip>
        {jar.heat > 0 && <Chip tone="heat"><HeatMeter value={jar.heat} /></Chip>}
        {jar.burns && <Chip tone="warn">burns easily</Chip>}
      </div>

      <p className="jar-note">{jar.note}</p>

      {authed && (
        <div className="jar-owner">
          <fieldset className="segmented">
            <legend>How much is left</legend>
            {Object.entries(STOCK_LABELS).map(([value, label]) => (
              <button key={value} className={jar.stock === value ? 'on' : ''}
                      onClick={() => onStock(value)}>{label}</button>
            ))}
          </fieldset>
          <p className="jar-uses">
            {jar.uses > 0
              ? `Called for in ${jar.uses} recipe${jar.uses === 1 ? '' : 's'}.`
              : 'Never called for yet.'}
            {jar.opened_on ? ` Opened ${jar.opened_on}.` : ''}
          </p>
        </div>
      )}
    </div>
  )
}

/**
 * The phone placement: a sheet over the rack.
 *
 * It has no confirm button. A big amber DONE across the bottom read as though
 * dismissing it committed something, when the stock buttons already save on tap
 * — and it ate the space the note wanted. Closing is the backdrop, the ×, or
 * Escape, which is what every other sheet on a phone does.
 */
export function JarSheet(props: Parameters<typeof JarDetail>[0] & { onClose: () => void }) {
  const { onClose } = props

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    // Without this the rack scrolls under the sheet whenever a drag starts on
    // the backdrop, and you lose your place on the shelf you were reading.
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [onClose])

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet jar-sheet" onClick={(e) => e.stopPropagation()}
           role="dialog" aria-label={props.jar.name}>
        <div className="sheet-grip" />
        <JarDetail {...props} />
      </div>
    </div>
  )
}
