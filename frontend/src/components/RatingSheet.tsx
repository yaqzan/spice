import { useState } from 'react'
import type { Rating } from '../types'

// The feedback loop, and the one screen that has to be effortless — it gets used
// standing over a plate with one hand. Three taps and a done button.
//
// Salt and heat are rated separately from the dish itself on purpose. The steak
// that scored 2/10 in the old chat project was over-salted, and the conclusion
// drawn from it — "never put a blend on steak" — is not what went wrong. Rating
// the axes apart means a seasoning miss teaches a seasoning lesson.

const SALT = [
  { value: -2, label: 'Way under' },
  { value: -1, label: 'A bit under' },
  { value: 0, label: 'Spot on' },
  { value: 1, label: 'A bit salty' },
  { value: 2, label: 'Way too salty' },
]

const HEAT = [
  { value: -2, label: 'No kick' },
  { value: -1, label: 'Mild' },
  { value: 0, label: 'Right' },
  { value: 1, label: 'Hot' },
  { value: 2, label: 'Too hot' },
]

type Props = {
  existing: Rating | null
  onSubmit: (body: Record<string, unknown>) => Promise<void>
  onClose: () => void
}

export function RatingSheet({ existing, onSubmit, onClose }: Props) {
  const [overall, setOverall] = useState(existing?.overall ?? 7)
  const [salt, setSalt] = useState(existing?.salt_delta ?? 0)
  const [heat, setHeat] = useState(existing?.heat_delta ?? 0)
  const [repeat, setRepeat] = useState<number | null>(existing?.would_repeat ?? null)
  const [notes, setNotes] = useState(existing?.notes ?? '')
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await onSubmit({ overall, salt_delta: salt, heat_delta: heat,
                       would_repeat: repeat, notes })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <h3>How was it?</h3>

        <label className="field">
          <span>Overall <b>{overall}/10</b></span>
          <input type="range" min={1} max={10} value={overall}
                 onChange={(e) => setOverall(Number(e.target.value))} />
        </label>

        <fieldset className="segmented">
          <legend>Salt</legend>
          {SALT.map((o) => (
            <button key={o.value} className={salt === o.value ? 'on' : ''}
                    onClick={() => setSalt(o.value)}>{o.label}</button>
          ))}
        </fieldset>

        <fieldset className="segmented">
          <legend>Heat</legend>
          {HEAT.map((o) => (
            <button key={o.value} className={heat === o.value ? 'on' : ''}
                    onClick={() => setHeat(o.value)}>{o.label}</button>
          ))}
        </fieldset>

        <fieldset className="segmented">
          <legend>Cook it again?</legend>
          <button className={repeat === 1 ? 'on' : ''} onClick={() => setRepeat(1)}>Yes</button>
          <button className={repeat === 0 ? 'on' : ''} onClick={() => setRepeat(0)}>No</button>
        </fieldset>

        <label className="field">
          <span>Anything worth remembering?</span>
          <textarea value={notes} rows={3} placeholder="Needed more garlic. Pan was too hot."
                    onChange={(e) => setNotes(e.target.value)} />
        </label>

        <div className="sheet-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
