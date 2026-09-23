import { useMemo, useState } from 'react'
import { Amount } from './Amount'
import { FullRack } from './SpiceRack'
import { mentioned, StepText } from './StepText'
import type { Stamp } from './StepText'
import type { BlendGroup, BlendItem, Jar, RackView, RecipePayload, Step } from '../types'

// Burner settings on a 1-10 dial, because "medium-high" is the instruction that
// burns spice crusts. The dial numbers are the kitchen's own calibration note.
const HEAT_LABELS: Record<string, string> = {
  none: 'no heat',
  low: 'low · dial 2',
  medium_low: 'med-low · dial 3',
  medium: 'medium · dial 4-5',
  medium_high: 'med-high · dial 6-7',
  high: 'high · dial 8-9',
}

const CONFIDENCE_LABELS: Record<string, string> = {
  proven: 'Close to something you rated well',
  well_trodden: 'A classic combination',
  adaptation: 'A classic, bent to fit the rack',
  experiment: 'Genuinely untested',
}

function Chip({ children, tone }: { children: React.ReactNode; tone?: string }) {
  return <span className={`chip${tone ? ` chip-${tone}` : ''}`}>{children}</span>
}

function HeatDots({ level }: { level: number }) {
  return (
    <span className="heat-dots" aria-label={`heat ${level} of 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <i key={n} className={n <= level ? 'on' : ''} />
      ))}
    </span>
  )
}

function Times({ times }: { times: RecipePayload['times'] }) {
  const parts: string[] = []
  if (times.marinate_min) parts.push(`${fmt(times.marinate_min)} marinating`)
  if (times.prep_min) parts.push(`${fmt(times.prep_min)} prep`)
  if (times.cook_min) parts.push(`${fmt(times.cook_min)} cooking`)
  return <p className="times">{parts.join(' · ')}{times.total_min ? ` — ${fmt(times.total_min)} all in` : ''}</p>
}

function fmt(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}

function BlendRow({ item }: { item: BlendItem }) {
  const [open, setOpen] = useState(false)
  return (
    <li className={`blend-row${item.out_of_stock ? ' blend-out' : ''}`}
        onClick={() => setOpen((v) => !v)}>
      <span className="blend-swatch" style={{ background: item.color }} />
      {/* No stage on the row any more. The bowl it is sitting in already says
          when it goes in -- that is what the bowl IS -- and repeating it on
          every line made the group heading look like decoration. */}
      <span className="blend-main">
        <strong>{item.name}</strong>
      </span>
      <span className="blend-amount"><Amount>{item.amount}</Amount></span>
      {open && (
        <span className="blend-detail">
          {item.why && <span className="blend-why">{item.why}</span>}
          <span className="blend-note">{item.note}</span>
          {item.out_of_stock && <span className="blend-warn">Marked out of stock.</span>}
        </span>
      )}
    </li>
  )
}

/** Which bowls this step touches, and whether the sentence numbered them right.
 *
 *  Two sources disagree here, and only one of them is checked. The bowls are
 *  numbered by the app, from each jar's stage; the "BOWL 2" inside a step body
 *  is the model counting for itself, and it counts in the order it happens to
 *  write the steps. When a recipe blooms its bowl after adding an early-stage
 *  jar, the two numberings cross over — the sentence says BOWL 1 and means the
 *  bowl the card calls 2.
 *
 *  So the jars attached to the step win, because they were resolved against the
 *  registry, and a lone number in the prose is corrected to match. Where a step
 *  genuinely uses several bowls there is nothing safe to correct, and the text
 *  is left exactly as written. */
function bowlsForStep(step: Step, groups: BlendGroup[]) {
  const bowlOf = new Map<string, number>()
  groups.forEach((g) => g.items.forEach((i) => bowlOf.set(i.spice_key, g.bowl)))

  const fromJars = new Set<number>()
  step.spices.forEach((s) => {
    const bowl = bowlOf.get(s.spice_key)
    if (bowl) fromJars.add(bowl)
  })
  const spoken = new Set<number>()
  for (const match of (step.body || '').matchAll(/BOWL\s*(\d+)/gi)) {
    spoken.add(Number(match[1]))
  }

  const renumber = new Map<number, number>()
  if (fromJars.size === 1 && spoken.size === 1) {
    const [right] = [...fromJars]
    const [written] = [...spoken]
    if (written !== right) renumber.set(written, right)
  }
  const wanted = new Set(fromJars)
  spoken.forEach((n) => wanted.add(renumber.get(n) ?? n))
  return { bowls: groups.filter((g) => wanted.has(g.bowl)), renumber }
}

/** What each step's sentence may name, and where each measurement belongs.
 *
 *  An ingredient is stamped in the step that first mentions it and nowhere else.
 *  The beef is put in the pan once; "push the beef to one side" three steps
 *  later is talking about it, not adding it, and hanging "1 lb" off every
 *  mention turns the method into a receipt. */
function stampPlan(payload: RecipePayload) {
  // "Yellow onion, finely diced" is a name with a knife instruction stapled to
  // it; the step says "onion". Match on the name and leave the rest to the
  // shopping list, which is where a prep note belongs anyway.
  const kitchen: Stamp[] = (payload.from_kitchen || []).map((k) => ({
    label: (k.item || '').split(',')[0].trim() || k.item,
    amount: k.amount,
  }))
  // A jar's colour is its identity, and it is the same colour wherever the name
  // appears — on the rack, in its bowl, in a sentence. So every jar in the blend
  // can be stamped by any step that names it. Its measurement is a different
  // thing: that belongs to the step the jar actually goes into, so a jar named
  // somewhere else gets the dot and the name with no number attached.
  const jars: Stamp[] = (payload.blend || [])
    .map((item) => ({ label: item.name, amount: '', color: item.color }))
  const claimed = new Set<string>()
  return (payload.steps || []).map((step) => {
    const mine = step.spices.map((s) => ({ label: s.name, amount: s.amount, color: s.color }))
    const named = new Set(mine.map((s) => s.label))
    const stamps: Stamp[] = [
      ...mine,
      ...jars.filter((j) => !named.has(j.label)),
      ...kitchen,
    ]
    const allow = new Set<number>()
    for (const index of mentioned(step.body || '', stamps)) {
      // A colour-only stamp is an identification, not an instruction, so it
      // neither needs nor spends the one measurement each ingredient gets.
      if (!stamps[index].amount) {
        allow.add(index)
        continue
      }
      const key = stamps[index].label.trim().toLowerCase()
      if (claimed.has(key)) continue
      claimed.add(key)
      allow.add(index)
    }
    return { stamps, allow }
  })
}

function StepRow({ step, groups, stamps, allow }: {
  step: Step
  groups: BlendGroup[]
  stamps: Stamp[]
  allow: Set<number>
}) {
  const { bowls, renumber } = useMemo(() => bowlsForStep(step, groups), [step, groups])
  const numbers = useMemo(() => new Set(bowls.map((b) => b.bowl)), [bowls])

  return (
    <li className="step">
      <div className="step-head">
        <span className="step-n">{step.n}</span>
        <h4>{step.title}</h4>
        <span className="step-meta">
          {step.heat !== 'none' && <Chip tone="heat">{HEAT_LABELS[step.heat] || step.heat}</Chip>}
          {step.minutes > 0 && <Chip>{fmt(step.minutes)}</Chip>}
        </span>
      </div>
      <p className="step-body">
        <StepText text={step.body} stamps={stamps} allow={allow}
                  bowls={numbers} renumber={renumber} />
      </p>
      {bowls.length > 0 && (
        // What is in the bowls this step names — and only what, never how much.
        // The measurements live in the blend section, where they were measured
        // out before the stove was lit; repeating them here would invite a
        // second pour mid-cook. This is a reminder, not an instruction, so it
        // sits with the other small print rather than in the step's own voice.
        <ul className="step-bowls">
          {bowls.map((bowl) => (
            <li key={bowl.bowl}>
              <span className="bowl-n">{bowl.bowl}</span>
              <span className="step-bowl-items">
                {bowl.items.map((item) => (
                  <span key={item.spice_key} className="step-bowl-item">
                    <i style={{ background: item.color }} />{item.name}
                  </span>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
      {step.watch_for && <p className="step-watch"><span>Watch for</span> {step.watch_for}</p>}
    </li>
  )
}

type Props = {
  payload: RecipePayload
  rack: RackView | null
  onRate?: () => void
  rated?: boolean
}

export function RecipeCard({ payload, rack, onRate, rated }: Props) {
  // Jars light up in the order they enter the pan, so the badge numbers on the
  // rack match the reading order of the blend list.
  const highlights = useMemo(() => {
    const out: Record<string, { order: number; amount: string }> = {}
    payload.blend.forEach((item, index) => {
      out[item.spice_key] = { order: index + 1, amount: item.amount }
    })
    // Spoons alone under the jar: the jar itself is already labelled with the
    // brand, so the panel's fuller line would just be the label said twice.
    if (payload.salt?.grams) {
      out['salt'] = { order: 0, amount: payload.salt.spoons || payload.salt.display }
    }
    if (payload.salt?.msg_grams) {
      out['msg'] = { order: 0, amount: payload.salt.msg_spoons || payload.salt.msg_display || '' }
    }
    return out
  }, [payload])

  // Worked out for the method as a whole, not per step: which step gets to
  // carry each ingredient's measurement depends on every step before it.
  const plan = useMemo(() => stampPlan(payload), [payload])

  const [tapped, setTapped] = useState<Jar | null>(null)

  return (
    <article className="recipe">
      <header className="recipe-head">
        <h2>{payload.title}</h2>
        <div className="recipe-chips">
          {payload.cuisine && <Chip tone="cuisine">{payload.cuisine}</Chip>}
          <Chip><HeatDots level={payload.heat_level} /></Chip>
          <Chip tone={payload.confidence === 'experiment' ? 'warn' : 'calm'}>
            {CONFIDENCE_LABELS[payload.confidence] || payload.confidence}
          </Chip>
        </div>
        <Times times={payload.times} />
        {payload.why_this && <p className="why">{payload.why_this}</p>}
      </header>

      {payload.warnings?.length > 0 && (
        <ul className="warnings">
          {payload.warnings.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      )}

      <section className="panel panel-rack">
        <h3>Grab these</h3>
        {rack ? (
          <>
            <FullRack jars={rack.jars} racks={rack.racks}
                      rackLabels={rack.rack_labels} highlights={highlights}
                      onTap={setTapped} selected={tapped?.spice_key ?? null} />
            {tapped && (
              <p className="jar-tip">
                <strong>{tapped.name}</strong> — {tapped.note}
              </p>
            )}
          </>
        ) : <p className="muted">Loading the rack…</p>}
      </section>

      <section className="panel salt-panel">
        <h3>Salt</h3>
        {/* Salt gets its own panel and the biggest number on the page. Both
            recorded failures in this kitchen were seasoning-level, not
            flavour-level. */}
        <p className="salt-big"><Amount>{payload.salt.display}</Amount></p>
        {payload.salt.msg_display &&
          <p className="salt-msg">+ <Amount>{payload.salt.msg_display}</Amount></p>}
        <p className="salt-when">{payload.salt.when}</p>
        <p className="salt-why">{payload.salt.rationale}</p>
      </section>

      <section className="panel">
        <h3>The blend <span className="muted">for {payload.portion_lb} lb {payload.protein}</span></h3>
        {/* Grouped by the moment each jar enters the pan, never as one flat
            list. Measuring everything out before starting is the right habit and
            is also how a dish gets ruined — garam masala tipped in with the cumin
            spends forty minutes boiling instead of five. Same bowl means same
            moment. */}
        {(payload.blend_groups ?? []).map((group) => (
          <div key={group.stage} className="bowl">
            <div className="bowl-head">
              <span className="bowl-n">{group.bowl}</span>
              <span className="bowl-when">
                <strong>{group.premix ? 'Mix these together' : 'On its own'}</strong>
                <em>{group.when}</em>
              </span>
            </div>
            <ul className="blend">
              {group.items.map((item) => <BlendRow key={item.spice_key} item={item} />)}
            </ul>
            {group.keep_apart && (
              <p className="bowl-apart">{group.keep_apart}</p>
            )}
          </div>
        ))}
        <p className="hint">
          Separate bowls, not one. Tap a row for what it is doing and how it
          misbehaves.
        </p>
      </section>

      {payload.from_kitchen?.length > 0 && (
        <section className="panel">
          <h3>Not on the rack</h3>
          <ul className="kitchen">
            {payload.from_kitchen.map((k, i) => (
              <li key={i} className={k.off_rack ? 'off-rack' : ''}>
                <span>{k.item}</span><b><Amount>{k.amount}</Amount></b>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel">
        <h3>Method</h3>
        {payload.pan && <p className="pan">{payload.pan}</p>}
        <ol className="steps">
          {payload.steps.map((step, index) => (
            <StepRow key={step.n} step={step} groups={payload.blend_groups ?? []}
                     stamps={plan[index]?.stamps ?? []}
                     allow={plan[index]?.allow ?? new Set()} />
          ))}
        </ol>
      </section>

      <section className="panel">
        <h3>Salt check</h3>
        <p>{payload.salt_check}</p>
      </section>

      {(payload.serve_with || payload.leftovers) && (
        <section className="panel">
          {payload.serve_with && <><h3>Serve with</h3><p>{payload.serve_with}</p></>}
          {payload.leftovers && <><h3>Leftovers</h3><p>{payload.leftovers}</p></>}
        </section>
      )}

      {onRate && (
        <button className="primary rate-cta" onClick={onRate}>
          {rated ? 'Update your rating' : 'Rate it once you have eaten'}
        </button>
      )}
    </article>
  )
}
