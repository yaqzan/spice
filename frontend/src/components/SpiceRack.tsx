import { useMemo } from 'react'
import { useIsWide } from '../useIsWide'
import type { Jar } from '../types'

// The rack visual. This is the reason the app exists: the answer to "where is
// the cumin" should be a picture of the shelf with one jar lit up, not a
// sentence describing a shelf.
//
// Drawn as SVG rather than a CSS grid for one specific reason — it scales to any
// phone width without reflowing. A grid would wrap 7 columns to 4 on a narrow
// screen and the picture would stop matching the furniture, which defeats the
// whole point.

const JAR_W = 38
const JAR_H = 50
const GAP_X = 7
const GAP_Y = 30          // room under each row for the highlighted jar's label
const PAD_X = 20          // room at the left for the row number
const PAD_TOP = 16

// An SVG stretches to its container, so a shelf holding fewer jars would draw
// BIGGER ones — a 5-wide stove rendering jars 35% larger than a 7-wide rack, and
// a one-jar freezer rendering a jar the size of a dinner plate. That silently
// implies the containers differ in size, which is exactly the kind of small lie
// the rack picture cannot afford.
//
// So each shelf is capped at its share of a REFERENCE width. Every SVG then
// scales by the same factor and a jar is a jar everywhere, in any container, at
// any screen width.
//
// The reference is "the widest shelf sharing this shelf's column", not a global
// constant — see FullRack. Those are the same thing on a phone, where every rack
// is stacked in one full-width column. They are NOT the same on a wide screen,
// and using the global figure there is what left a quarter of the third column
// permanently empty: the stove drew at 5/7 of a column sized for seven jars, and
// the leftover looked like a hole in the page rather than a short shelf.
//
// The smaller shelves (stove, fridge, freezer) do not carry row numbers, so they
// need only a little side padding. That is what lets a 3-wide and a 4-wide shelf
// sit side by side inside the width of one 7-wide wall rack, at the same jar size.
const PAD_SMALL = 11
const padOf = (wall: boolean) => (wall ? PAD_X : PAD_SMALL)
const shelfWidth = (cols: number, wall = true) =>
  padOf(wall) * 2 + cols * JAR_W + (cols - 1) * GAP_X

/** How many jars wide a given shelf is. One definition, used to draw it and to
 *  size the column it sits in. */
function shelfCols(jars: Jar[], rackName: string): number {
  const mine = jars.filter((j) => j.rack === rackName)
  return mine.length ? Math.max(...mine.map((j) => j.col)) + 1 : 0
}

export type Highlight = { order: number; amount: string }

type Props = {
  jars: Jar[]
  rackName: string
  label: string
  /** A wall rack: frequency rows, numbered, with room at the left for the numbers. */
  wall?: boolean
  highlights?: Record<string, Highlight>
  /** Kitchen-wide unique stacked abbreviations, keyed by spice_key. */
  codes: Record<string, string[]>
  /** Width of the widest shelf sharing this one's column, in viewBox units.
   *  This shelf draws at its own width as a fraction of that. */
  reference: number
  /** Where this shelf sits in the wide-screen grid. Set by FullRack, which is
   *  the only thing that knows how the shelves are arranged on the wall. */
  style?: React.CSSProperties
  onTap?: (jar: Jar) => void
  selected?: string | null
}

// ── the jar itself ───────────────────────────────────────────────────────────
// Four ideas, everything else is shading: a cap narrower than the glass, a
// shoulder curve, contents that stop short of the neck, and a paper label near
// the base. The first three are what make a 38px rectangle read as a jar; the
// label is what makes fifty-six of them read as a bought matching set.

/** The glass silhouette — shoulders curving up to the neck, gently rounded
 *  base. One path string shared by the colour fill, the hover scrim and the
 *  clip that keeps the shading inside the glass, so they can never disagree
 *  about where the jar ends. */
const JAR_PATH = [
  'M 2 19.5', 'C 2 13.2 6.5 10.5 12 10.5', 'L 26 10.5',
  'C 31.5 10.5 36 13.2 36 19.5', 'L 36 45.5',
  'Q 36 49.5 32 49.5', 'L 6 49.5', 'Q 2 49.5 2 45.5', 'Z',
].join(' ')

/** Cylindrical shading, light from the upper left: a bright band a third of the
 *  way in, falling to dark at both edges. Colour-agnostic, so one gradient
 *  serves every jar in an SVG — the id is suffixed because several rack SVGs
 *  share the page and SVG ids are document-global. */
function Sheen({ id }: { id: string }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stopColor="#000" stopOpacity="0.28" />
      <stop offset="0.13" stopColor="#000" stopOpacity="0.02" />
      <stop offset="0.21" stopColor="#fff" stopOpacity="0.17" />
      <stop offset="0.36" stopColor="#fff" stopOpacity="0.03" />
      <stop offset="0.75" stopColor="#000" stopOpacity="0.06" />
      <stop offset="1" stopColor="#000" stopOpacity="0.32" />
    </linearGradient>
  )
}

/** Glass, contents, headspace, sheen, cap. The clip id must be unique in the
 *  document — spice keys are, and the one detail glyph brings its own. */
function JarShape({ colour, clipId, sheenId }: {
  colour: string
  clipId: string
  sheenId: string
}) {
  return (
    <g className="jar-visual">
      <clipPath id={clipId}><path d={JAR_PATH} /></clipPath>
      <path d={JAR_PATH} fill={colour} className="jar-glass" />
      <g clipPath={`url(#${clipId})`}>
        {/* The contents stop short of the neck. This one dark band is most of
            what turns "coloured shape" into "jar of stuff". */}
        <rect x={2} y={10.5} width={34} height={5.5} className="jar-headspace" />
        <rect x={2} y={10.5} width={34} height={39} fill={`url(#${sheenId})`} />
      </g>
      <g className="jar-cap">
        <rect x={0} width={38} height={20} rx={3} className="jar-cap-base" />
        <rect x={2} y={1.4} width={34} height={1.6} rx={0.8} className="jar-cap-shine" />
      </g>
    </g>
  )
}

/** The tapped jar, held up beside its name in JarDetail. Same drawing as the
 *  shelf — a glyph shaded by different rules there would look like a different
 *  jar — minus the label, which would just repeat the heading beside it. */
export function JarGlyph({ colour }: { colour: string }) {
  return (
    <svg className="jar-glyph" viewBox="0 0 38 50" aria-hidden>
      <defs><Sheen id="jar-sheen-glyph" /></defs>
      <JarShape colour={colour} clipId="jar-clip-glyph" sheenId="jar-sheen-glyph" />
    </svg>
  )
}

function words(name: string): string[] {
  return name.replace(/\(.*?\)/g, '').trim().split(/\s+/).filter(Boolean)
}

// One word per line, stacked, whole wherever possible — TURMERIC, not TURMER.
//
// A three-letter mash was the wrong compromise: nobody can read "SPE" as
// Sichuan Peppercorn. Six characters kept the shape of every word but cut most
// of them mid-syllable, and a shelf of TURMER / CORIAN / CHIPOT reads as a
// column overflow, not a label. At eight characters nearly the whole rack is
// complete words — long lines condense to the label width like real print
// (textLength, in the renderer) instead of overflowing. A word that still has
// to give gets cut at seven letters and a period, the way a printed label
// abbreviates on purpose: CORIAND., not CORIANDE.
const LABEL_LINES = 3
const LABEL_CHARS = 8
// Below this a word renders full-size; at or above it the label condenses the
// line to fit (textLength, in the renderer). Splitting a word across two
// shorter lines — when the label has a spare line to give it — reads better
// than a squeezed one, so this is also the threshold that decides when a
// word is worth breaking in two.
const SQUEEZE_CHARS = 7

// A handful of names split cleaner by hand than any generic rule finds:
// MUSHROOM breaks mid-word into two real words, not two arbitrary halves.
// New jars fall back to a plain middle split — fine for most words, but a
// bad one is worth a line here rather than living with it.
const WORD_BREAKS: Record<string, [string, string]> = {
  mushroom: ['Mush', 'Room'],
  allspice: ['All', 'Spice'],
  cardamom: ['Carda', 'Mom'],
}

// Descriptors that cost a line without earning it: "Sun-Dried" is worth
// knowing on the jar's full name, but on a three-line label it only pushes
// TOMATO and POWDER — the words that actually identify the jar — into a
// squeeze. Scoped by the exact word text, which is safe only because the
// rack is a short, known list; a future collision would need its own entry.
const DROP_WORDS = new Set(['sundried'])

function splitWord(word: string): [string, string] {
  const hint = WORD_BREAKS[word.toLowerCase()]
  if (hint) return hint
  const mid = Math.round(word.length / 2)
  return [word.slice(0, mid), word.slice(mid)]
}

function clip(word: string, chars: number): string {
  if (word.length <= chars) return word.toUpperCase()
  return `${word.slice(0, chars - 1).toUpperCase()}.`
}

function abbreviate(name: string, chars = LABEL_CHARS): string[] {
  // Hyphens join a compound that should stay on one line: "Sun-Dried Tomato
  // Powder" reads its two halves as one word, SUNDRIED, so it can be dropped
  // as a whole rather than half-surviving as SUN.
  const w = words(name.replace(/-/g, '')).filter((x) => !DROP_WORDS.has(x.toLowerCase()))
  if (!w.length) return ['?']

  const lines: string[] = []
  for (let i = 0; i < w.length && lines.length < LABEL_LINES; i++) {
    const word = w[i]
    const remaining = w.length - i - 1
    const spare = LABEL_LINES - lines.length - 1 - remaining
    if (spare > 0 && word.length >= SQUEEZE_CHARS) {
      const [head, tail] = splitWord(word)
      lines.push(clip(head, chars), clip(tail, chars))
    } else {
      lines.push(clip(word, chars))
    }
  }
  return lines.slice(0, LABEL_LINES)
}

// SVG has no text wrapping, so the FULL name — shown on hover and by the Labels
// toggle — is broken into lines by hand. Ten characters is about a jar's width
// at that smaller size, so "Zanzibar Black Pepper" lands on three tidy lines.
const WRAP_CHARS = 10
const WRAP_LINES = 4

function wrap(name: string): string[] {
  const w = words(name)
  const lines: string[] = []
  for (const word of w) {
    const last = lines[lines.length - 1]
    if (last && last.length + 1 + word.length <= WRAP_CHARS) {
      lines[lines.length - 1] = `${last} ${word}`
    } else {
      lines.push(word)
    }
  }
  if (lines.length <= WRAP_LINES) return lines
  return [...lines.slice(0, WRAP_LINES - 1), `${lines[WRAP_LINES - 1].slice(0, 8)}…`]
}

/**
 * Abbreviations that are unique ACROSS THE WHOLE KITCHEN.
 *
 * Per-name codes collided silently: Fennel and Fenugreek Seeds both became FS,
 * Ground Cinnamon and Ground Cloves both GC. A label that cannot tell two jars
 * apart is worse than no label, because it reads as certainty.
 *
 * At six characters a word the inventory separates itself — FENNEL/SEEDS beside
 * FENUGR/SEEDS needs no tie-breaking. The widening loop is a backstop for a
 * future jar that genuinely clashes, not the mechanism.
 *
 * Sorted by ROW so a top-row daily jar gets the tightest label if anything ever
 * does have to give; key breaks ties so rendering stays stable.
 */
function assignLabels(jars: Jar[]): Record<string, string[]> {
  const taken = new Set<string>()
  const out: Record<string, string[]> = {}
  const order = [...jars].sort(
    (a, b) => a.row - b.row || a.spice_key.localeCompare(b.spice_key))
  for (const jar of order) {
    let lines = abbreviate(jar.name)
    for (let chars = LABEL_CHARS; taken.has(lines.join('.')) && chars < 10; chars += 1) {
      lines = abbreviate(jar.name, chars + 1)
    }
    taken.add(lines.join('.'))
    out[jar.spice_key] = lines
  }
  return out
}

export function SpiceRack({
  jars, rackName, label, wall = true, highlights, onTap, selected, codes, reference,
  style,
}: Props) {
  const mine = useMemo(
    () => jars.filter((j) => j.rack === rackName).sort((a, b) => a.row - b.row || a.col - b.col),
    [jars, rackName],
  )
  if (!mine.length) return null

  const cols = shelfCols(jars, rackName)
  const rows = Math.max(...mine.map((j) => j.row)) + 1
  // Which cells hold a highlighted jar. A caption is wider than its jar, so
  // two hits side by side used to run their names into each other mid-air;
  // when a jar knows its neighbour is also captioned, a long name condenses
  // to the cell instead of colliding.
  const hitCells = new Set(
    mine.filter((j) => highlights?.[j.spice_key]).map((j) => `${j.row}:${j.col}`))
  const rowHeight = JAR_H + GAP_Y
  const pad = padOf(wall)
  const width = shelfWidth(cols, wall)
  const dimming = !!highlights && Object.keys(highlights).length > 0
  // Room under the final row only when something down there needs a caption.
  const tail = dimming ? GAP_Y : 10
  // A one-row shelf is a footnote, not a wall of jars: it does not need the
  // headroom the multi-row racks use for their row numbers. Trimming it is what
  // lets the freezer sit in the slack under the stove instead of hanging below
  // the bottom of every other shelf.
  const compact = rows === 1
  const padTop = compact ? 4 : PAD_TOP
  const height = padTop + (rows - 1) * rowHeight + JAR_H + (compact ? 6 : tail)

  return (
    <figure className={`rack${compact ? ' rack-compact' : ''}${wall ? '' : ' rack-small'}`}
            style={style}>
      <figcaption className="rack-label">{label}</figcaption>
      <svg viewBox={`0 0 ${width} ${height}`}
           className="rack-svg"
           style={{ maxWidth: `${(width / reference) * 100}%` }}
           role="img" aria-label={`${label}, ${mine.length} jars`}>
        <defs><Sheen id={`jar-sheen-${rackName}`} /></defs>
        {Array.from({ length: rows }, (_, row) => {
          const y = padTop + row * rowHeight
          return (
            <g key={`shelf-${row}`}>
              {/* The plank the jars stand on — it is what makes the picture read
                  as a shelf at a glance rather than as a grid of swatches. Two
                  tones: a lit top surface and a shadowed front edge. */}
              <rect x={pad - 6} y={y + JAR_H} width={width - pad * 2 + 12} height={2}
                    rx={1} className="rack-shelf-top" />
              <rect x={pad - 6} y={y + JAR_H + 2} width={width - pad * 2 + 12} height={3}
                    rx={1} className="rack-shelf-face" />
              {wall && (
                <text x={pad - 10} y={y + JAR_H / 2 + 4} className="rack-row-number"
                      textAnchor="end">{row + 1}</text>
              )}
              {/* No frequency letter. "Regular" and "Rare" both rendered as R,
                  so the tag column said D / W / R / R — two rows labelled
                  identically, which is worse than leaving it to the numbers. */}
            </g>
          )
        })}

        {mine.map((jar) => {
          const hit = highlights?.[jar.spice_key]
          const dim = dimming && !hit
          const x = pad + jar.col * (JAR_W + GAP_X)
          const y = padTop + jar.row * rowHeight
          const isSelected = selected === jar.spice_key
          return (
            <g key={jar.spice_key} transform={`translate(${x} ${y})`}
               className={`jar${dim ? ' jar-dim' : ''}${hit ? ' jar-hit' : ''}`}
               onClick={() => onTap?.(jar)} role={onTap ? 'button' : undefined}>
              {hit && (
                <rect x={-4} y={-4} width={JAR_W + 8} height={JAR_H + 8} rx={9}
                      className="jar-ring" />
              )}
              {isSelected && (
                <rect x={-4} y={-4} width={JAR_W + 8} height={JAR_H + 8} rx={9}
                      className="jar-selected" />
              )}
              {/* Contact shadow on the plank, so the jar stands rather than
                  floats. */}
              <ellipse cx={JAR_W / 2} cy={JAR_H + 0.8} rx={14.5} ry={1.7}
                       className="jar-shadow" />
              <JarShape colour={jar.color} clipId={`jar-clip-${jar.spice_key}`}
                        sheenId={`jar-sheen-${rackName}`} />
              {(() => {
                const lines = codes[jar.spice_key] ?? []
                const step = 7.5
                // A cream paper label with dark ink, anchored just under the
                // cap, growing downward line by line. It replaced a black
                // tape chip: same job — one label system whose legibility
                // owes nothing to the jar colour behind it — but the tape sat
                // dead centre over the widest part of the glass, so the shelf
                // read as 56 stickers and the colours read as margins. Up
                // here the band of colour below the label stays the loudest
                // thing on the jar, which is the point of colour-coding a
                // rack at all.
                const labelH = lines.length * step + 2.4
                const top = 21
                return (
                  <g className="jar-code">
                    <rect x={4.5} y={top} width={JAR_W - 9} height={labelH}
                          rx={1.6} className="jar-label-bg" />
                    {lines.map((line, i) => (
                      // Long words condense to the label width, the way print
                      // does, rather than overflowing the paper or forcing the
                      // whole rack down to the longest word's type size.
                      <text key={i} x={JAR_W / 2} y={top + 1.2 + step / 2 + i * step}
                            textAnchor="middle" dominantBaseline="central"
                            {...(line.length >= 7
                              ? { textLength: 26.5, lengthAdjust: 'spacingAndGlyphs' as const }
                              : {})}>{line}</text>
                    ))}
                  </g>
                )
              })()}

              {/* Full name, revealed on hover. Both states are rendered always
                  and swapped in CSS — no React state per jar, so hovering 56
                  of them costs nothing. The scrim is what makes white text
                  readable on Kosher Salt as well as on Nigella Seeds. */}
              <g className="jar-full">
                <path d={JAR_PATH} className="jar-full-scrim" />
                {(() => {
                  const lines = wrap(jar.name)
                  const lineHeight = 7
                  const top = 8 + (JAR_H - 8) / 2 - ((lines.length - 1) * lineHeight) / 2 + 2
                  return lines.map((line, index) => (
                    <text key={index} x={JAR_W / 2} y={top + index * lineHeight}
                          textAnchor="middle" className="jar-full-text">{line}</text>
                  ))
                })()}
              </g>

              {jar.stock === 'out' && (
                <line x1={4} y1={JAR_H - 4} x2={JAR_W - 4} y2={13} className="jar-out" />
              )}
              {/* Low sits up on the glass, clear of the label — a warning
                  sticker, not a fourth line of text. */}
              {jar.stock === 'low' && (
                <circle cx={JAR_W - 7} cy={16} r={2.6} className="jar-low" />
              )}

              {hit && (
                <>
                  <circle cx={JAR_W - 2} cy={2} r={10} className="jar-badge-bg" />
                  <text x={JAR_W - 2} y={6} textAnchor="middle" className="jar-badge">
                    {hit.order}
                  </text>
                  {(() => {
                    const name = jar.name.replace(/\(.*?\)/g, '').trim()
                    const crowded = (hitCells.has(`${jar.row}:${jar.col - 1}`) ||
                                     hitCells.has(`${jar.row}:${jar.col + 1}`)) &&
                                    name.length >= 10
                    return (
                      <text x={JAR_W / 2} y={JAR_H + 13} textAnchor="middle"
                            className="jar-name"
                            {...(crowded
                              ? { textLength: JAR_W + GAP_X - 3,
                                  lengthAdjust: 'spacingAndGlyphs' as const }
                              : {})}>{name}</text>
                    )
                  })()}
                  <text x={JAR_W / 2} y={JAR_H + 24} textAnchor="middle" className="jar-amount">
                    {hit.amount}
                  </text>
                </>
              )}
            </g>
          )
        })}
      </svg>
    </figure>
  )
}

/**
 * Every shelf in the kitchen.
 *
 * The wall racks keep a full-width row each. Everything smaller (stove, fridge,
 * freezer) is packed Tetris-style into one block beside or below them: two
 * columns, each new shelf dropped into whichever column is currently shorter, so
 * a 3-wide stove (5 rows) sits next to a 4-wide fridge (4 rows) with the one-jar
 * freezer filling the gap under it. The block is exactly one wall rack wide, and
 * every shelf in it is drawn at the same scale as the wall racks, so a jar is the
 * same size everywhere. On a wide screen the block is simply the third column.
 */
export function FullRack(props: Omit<Props, 'rackName' | 'label' | 'codes' | 'reference' | 'wall'> & {
  rackLabels: Record<string, string>
  racks: string[]
  /** Which shelves are the numbered wall racks. Everything else is packed. */
  wallRacks?: string[]
}) {
  const { racks, rackLabels, wallRacks, ...rest } = props
  const wide = useIsWide()
  // Computed once over every jar, so codes are unique across shelves rather than
  // only within one.
  const codes = useMemo(() => assignLabels(rest.jars), [rest.jars])

  const plan = useMemo(() => {
    const wallSet = new Set(wallRacks ?? ['left', 'right'])
    // An empty rack draws nothing, so it must not claim space either.
    const present = racks.filter((name) => shelfCols(rest.jars, name) > 0)
    const walls = present.filter((name) => wallSet.has(name))
    const smalls = present.filter((name) => !wallSet.has(name))

    const rowsOf = (name: string) =>
      Math.max(...rest.jars.filter((j) => j.rack === name).map((j) => j.row)) + 1
    const widthOf = (name: string) => shelfWidth(shelfCols(rest.jars, name), wallSet.has(name))

    // Greedy drop into the shorter column. A one-row shelf is a footnote and
    // weighs less than a row of a full shelf.
    const packed: string[][] = [[], []]
    const filled = [0, 0]
    for (const name of smalls) {
      const rows = rowsOf(name)
      const weight = rows === 1 ? 0.6 : rows
      const at = filled[1] < filled[0] ? 1 : 0
      packed[at].push(name)
      filled[at] += weight
    }
    const columns = packed.filter((column) => column.length > 0)
    const columnWidths = columns.map((column) => Math.max(...column.map(widthOf)))
    const blockWidth = columnWidths.reduce((sum, w) => sum + w, 0)

    const widest = Math.max(blockWidth, ...walls.map(widthOf), 1)
    const references: Record<string, number> = {}
    for (const name of walls) references[name] = wide ? widthOf(name) : widest
    columns.forEach((column, i) => column.forEach((name) => { references[name] = columnWidths[i] }))

    const template = [...walls.map(widthOf), ...(columns.length ? [blockWidth] : [])]
      .map((w) => `${w}fr`).join(' ')
    return { walls, columns, columnWidths, blockWidth, widest, references, template }
  }, [racks, wallRacks, rest.jars, wide])

  const { walls, columns, columnWidths, blockWidth, widest, references, template } = plan
  const draw = (name: string, wall: boolean) => (
    <SpiceRack key={name} rackName={name} label={rackLabels[name] || name} wall={wall}
               codes={codes} reference={references[name]} {...rest} />
  )

  return (
    <div className="rack-stack" style={wide ? { gridTemplateColumns: template } : undefined}>
      {walls.map((name) => draw(name, true))}
      {columns.length > 0 && (
        <div className="rack-pack"
             style={{
               gridTemplateColumns: columnWidths.map((w) => `${w}fr`).join(' '),
               maxWidth: wide ? undefined : `${(blockWidth / widest) * 100}%`,
             }}>
          {columns.map((column, i) => (
            <div key={i} className="rack-pack-col">
              {column.map((name) => draw(name, false))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
