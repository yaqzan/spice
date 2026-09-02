import { useEffect, useState } from 'react'
import { api } from '../api'
import { PrivateNotice, useAccess } from '../access'
import type { Health, SettingsResponse } from '../types'

const ACID = [
  { value: 'none', label: 'None at all' },
  { value: 'background', label: 'Background only' },
  { value: 'free', label: 'Use it normally' },
]

export function SettingsPage() {
  const { authed } = useAccess()
  const [data, setData] = useState<SettingsResponse | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [saved, setSaved] = useState('')

  useEffect(() => {
    if (!authed) return
    api.settings().then(setData).catch(() => setData(null))
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [authed])

  if (!authed) {
    return (
      <div className="page">
        <h1>Settings</h1>
        <PrivateNotice what="The cook's own calibration" />
      </div>
    )
  }

  async function save(patch: Record<string, string>) {
    const result = await api.saveSettings(patch)
    setData((d) => (d ? { ...d, settings: result.settings } : d))
    setSaved(Object.keys(patch)[0])
    setTimeout(() => setSaved(''), 1200)
  }

  if (!data) return <div className="page"><p className="muted">Loading…</p></div>
  const s = data.settings

  return (
    <div className="page settings-page">
      <h1>Settings</h1>

      <section className="panel">
        <h3>Which salt is on the shelf?</h3>
        {/* The highest-leverage control in the app. Recipes are written in grams;
            this is what turns grams into the right number of spoons. Get it wrong
            and every dish is off by up to 2x. */}
        <fieldset className="segmented stacked">
          {Object.entries(data.salt_brands).map(([key, brand]) => (
            <button key={key} className={s.salt_brand === key ? 'on' : ''}
                    onClick={() => save({ salt_brand: key })}>
              {brand.label} <em>{brand.grams_per_tsp}g / tsp</em>
            </button>
          ))}
        </fieldset>
        {saved === 'salt_brand' && <p className="hint">Saved.</p>}
      </section>

      <section className="panel">
        <h3>Heat tolerance</h3>
        <input type="range" min={1} max={5} value={Number(s.heat_tolerance)}
               onChange={(e) => save({ heat_tolerance: e.target.value })} />
        <p className="muted small">{s.heat_tolerance}/5</p>
      </section>

      <section className="panel">
        <h3>Acid</h3>
        <fieldset className="segmented stacked">
          {ACID.map((o) => (
            <button key={o.value} className={s.acid_policy === o.value ? 'on' : ''}
                    onClick={() => save({ acid_policy: o.value })}>{o.label}</button>
          ))}
        </fieldset>
        <p className="muted small">
          “Background only” keeps sour off the top note but still lets a tomato,
          yoghurt or soy-sauce style acid stop a rich dish going flat.
        </p>
      </section>

      <section className="panel">
        <h3>Salt baseline</h3>
        <input type="number" step="0.2" value={s.salt_grams_per_lb}
               onChange={(e) => save({ salt_grams_per_lb: e.target.value })} />
        <p className="muted small">
          Grams per pound of protein, measured out, before any correction from
          your ratings. 7.5&thinsp;g is 1.65% of the meat&rsquo;s weight &mdash;
          which is 1&thinsp;&frac14;&nbsp;TEAsp of this salt, the rate every dish
          you rated 8.5 or above was actually seasoned at. It is bolder than the
          usual 1&ndash;1.5%, on purpose.
        </p>
      </section>

      <section className="panel">
        <h3>Model</h3>
        <input type="text" value={s.model} onChange={(e) => save({ model: e.target.value })} />
        <p className="muted small">
          Any OpenRouter model id. It needs to hold a JSON schema — the whole
          screen is built from structured output.
        </p>
      </section>

      <section className="panel">
        <h3>Daily API call limit</h3>
        {/* A backstop on spend, not a quota. It counts BILLED calls rather than
            finished recipes: a failed ask still costs money, and counting only
            successes made failures free and therefore unlimited. */}
        <input type="number" min={0} step="5" value={s.daily_ask_limit}
               onChange={(e) => save({ daily_ask_limit: e.target.value })} />
        <p className="muted small">
          OpenRouter calls per day before the app stops asking. A recipe is
          normally one call &mdash; up to three if the model fumbles the JSON and
          the fallback chain retries.
          {health?.daily_limit
            ? ` Used ${health.asks_today ?? 0} of ${health.daily_limit} today.`
            : ''}
          {' '}0 removes the cap.
        </p>
      </section>

      {health && (
        <section className="panel">
          <h3>Status</h3>
          <ul className="status">
            <li><span>OpenRouter key</span><b>{health.openrouter ? 'configured' : 'missing'}</b></li>
            <li>
              <span>You got in</span>
              <b>{health.via_tailnet ? 'from the tailnet' : 'via SPICE_OPEN'}</b>
            </li>
            <li><span>Jars on the rack</span><b>{health.jars}</b></li>
            <li><span>Recipes</span><b>{health.recipes}</b></li>
            <li><span>Rated</span><b>{health.rated}</b></li>
            <li><span>Model</span><b>{health.model}</b></li>
            <li><span>Version</span><b>{health.version}</b></li>
          </ul>
          {!health.openrouter && (
            <p className="error">
              No API key. Put one in <code>data/openrouter.key</code> and restart.
            </p>
          )}
          {/* The one state where the app is open to more than a tailnet peer.
              SPICE_OPEN is a development flag, and loopback is also where the
              public tunnel arrives -- so left on, it hands the internet the
              spend, the history and every mutation. */}
          {health.via_tailnet === false && (
            <p className="error">
              <code>SPICE_OPEN=1</code> is set, so every caller is treated as the
              owner &mdash; including anyone arriving through the public tunnel.
              Development only.
            </p>
          )}
        </section>
      )}
    </div>
  )
}
