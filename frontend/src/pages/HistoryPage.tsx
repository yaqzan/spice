import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAccess } from '../access'
import type { HistoryRow } from '../types'

const SALT_TAGS: Record<number, string> = {
  [-2]: 'way under', [-1]: 'under', 0: '', 1: 'salty', 2: 'too salty',
}
const HEAT_TAGS: Record<number, string> = {
  [-2]: 'no kick', [-1]: 'mild', 0: '', 1: 'hot', 2: 'too hot',
}

type Sort = 'new' | 'old' | 'top' | 'az'
type Show = 'all' | 'great' | 'rated' | 'unrated'

const SORTS: { value: Sort; label: string }[] = [
  { value: 'new', label: 'Newest' },
  { value: 'old', label: 'Oldest' },
  { value: 'top', label: 'Top rated' },
  { value: 'az', label: 'A to Z' },
]
const SHOWS: { value: Show; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'great', label: '8 and up' },
  { value: 'rated', label: 'Rated' },
  { value: 'unrated', label: 'Unrated' },
]

const SORTERS: Record<Sort, (a: HistoryRow, b: HistoryRow) => number> = {
  // Dates are ISO strings, so string order is date order. The API already sends
  // newest first; sorting anyway keeps this page correct if that ever changes.
  new: (a, b) => b.created_at.localeCompare(a.created_at),
  old: (a, b) => a.created_at.localeCompare(b.created_at),
  // Unrated sinks to the bottom rather than reading as a zero.
  top: (a, b) => (b.overall ?? -1) - (a.overall ?? -1)
    || b.created_at.localeCompare(a.created_at),
  az: (a, b) => a.title.localeCompare(b.title),
}

const matches = (row: HistoryRow, needle: string) =>
  [row.title, row.cuisine, row.protein, row.query, row.notes]
    .some((field) => field?.toLowerCase().includes(needle))

export function HistoryPage() {
  const { authed } = useAccess()
  const [rows, setRows] = useState<HistoryRow[] | null>(null)
  const [search, setSearch] = useState('')
  const [cuisine, setCuisine] = useState('')
  const [sort, setSort] = useState<Sort>('new')
  const [show, setShow] = useState<Show>('all')

  useEffect(() => {
    api.recipes(500).then((r) => setRows(r.recipes)).catch(() => setRows([]))
  }, [])

  const cuisines = useMemo(
    () => [...new Set((rows ?? []).map((r) => r.cuisine).filter(Boolean) as string[])]
      .sort((a, b) => a.localeCompare(b)),
    [rows],
  )

  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (rows ?? [])
      .filter((r) => !cuisine || r.cuisine === cuisine)
      .filter((r) => {
        if (show === 'great') return (r.overall ?? 0) >= 8
        if (show === 'rated') return r.overall !== null
        if (show === 'unrated') return r.overall === null
        return true
      })
      .filter((r) => !needle || matches(r, needle))
      .sort(SORTERS[sort])
  }, [rows, search, cuisine, show, sort])

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
  const filtering = !!(search || cuisine || show !== 'all')

  return (
    <div className="page history-page">
      <h1>Cooked</h1>
      {authed && unrated > 0 && (
        <p className="muted small">
          {unrated} waiting on a rating — those are the ones doing nothing for you.
        </p>
      )}

      <div className="history-controls">
        <input type="search" placeholder="Search dishes, cuisines, notes"
               aria-label="Search the cookbook" value={search}
               onChange={(e) => setSearch(e.target.value)} />
        <div className="history-selects">
          <select aria-label="Cuisine" value={cuisine}
                  onChange={(e) => setCuisine(e.target.value)}>
            <option value="">All cuisines</option>
            {cuisines.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select aria-label="Sort" value={sort}
                  onChange={(e) => setSort(e.target.value as Sort)}>
            {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div className="history-shows" role="group" aria-label="Show">
          {SHOWS.map((s) => (
            <button key={s.value} type="button"
                    className={show === s.value ? 'on' : ''}
                    aria-pressed={show === s.value}
                    onClick={() => setShow(s.value)}>
              {s.label}
            </button>
          ))}
        </div>
        <p className="muted small history-count">
          {filtering ? `${shown.length} of ${rows.length}` : `${rows.length}`} dishes
        </p>
      </div>

      {!shown.length && <p className="muted">Nothing matches that.</p>}
      <ul className="history">
        {shown.map((row) => (
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
