import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { PrivateNotice, useAccess } from '../access'
import type { HistoryRow } from '../types'

const SALT_TAGS: Record<number, string> = {
  [-2]: 'way under', [-1]: 'under', 0: '', 1: 'salty', 2: 'too salty',
}
const HEAT_TAGS: Record<number, string> = {
  [-2]: 'no kick', [-1]: 'mild', 0: '', 1: 'hot', 2: 'too hot',
}

export function HistoryPage() {
  const { authed } = useAccess()
  const [rows, setRows] = useState<HistoryRow[] | null>(null)

  useEffect(() => {
    if (!authed) return
    api.recipes(100).then((r) => setRows(r.recipes)).catch(() => setRows([]))
  }, [authed])

  // What has been cooked here, and what it scored, is personal. The rack is the
  // public exhibit; this is not.
  if (!authed) {
    return (
      <div className="page">
        <h1>Cooked</h1>
        <PrivateNotice what="What has been cooked here" />
      </div>
    )
  }
  if (!rows) return <div className="page"><p className="muted">Loading…</p></div>
  if (!rows.length) {
    return (
      <div className="page">
        <h1>Cooked</h1>
        <p className="muted">Nothing yet. Every recipe you rate sharpens the next one.</p>
      </div>
    )
  }

  const unrated = rows.filter((r) => r.overall === null).length

  return (
    <div className="page history-page">
      <h1>Cooked</h1>
      {unrated > 0 && (
        <p className="muted small">
          {unrated} waiting on a rating — those are the ones doing nothing for you.
        </p>
      )}
      <ul className="history">
        {rows.map((row) => (
          <li key={row.id}>
            <Link to={`/recipe/${row.id}`}>
              <span className="history-main">
                <strong>{row.title}</strong>
                <em>{[row.cuisine, row.protein].filter(Boolean).join(' · ')}</em>
              </span>
              <span className="history-side">
                {row.overall !== null
                  ? <b className={`score s${Math.round(row.overall / 2)}`}>{row.overall}</b>
                  : <b className="score unrated">–</b>}
                <em>
                  {[SALT_TAGS[row.salt_delta ?? 0], HEAT_TAGS[row.heat_delta ?? 0]]
                    .filter(Boolean).join(', ')}
                </em>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
