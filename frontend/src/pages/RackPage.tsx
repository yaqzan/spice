import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAccess } from '../access'
import { FullRack } from '../components/SpiceRack'
import { RackList } from '../components/RackList'
import { JarDetail, JarSheet } from '../components/JarDetail'
import { useIsWide } from '../useIsWide'
import type { Jar, Proposal, RackView } from '../types'

export function RackPage() {
  // The rack itself is public — it is the exhibit. Stock, usage counts and
  // re-shelving are the owner's, and the API refuses them anyway; hiding the
  // controls just avoids offering a button that can only 401.
  const { authed } = useAccess()
  const wide = useIsWide()
  const [rack, setRack] = useState<RackView | null>(null)
  const [tapped, setTapped] = useState<Jar | null>(null)
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [mode, setMode] = useState<'balanced' | 'strict'>('balanced')
  const [busy, setBusy] = useState(false)
  // Picture for finding a jar mid-cook, names for physically sorting the shelf.
  const [view, setView] = useState<'picture' | 'names'>('picture')

  useEffect(() => { api.rack().then(setRack) }, [])

  async function setStock(stock: string) {
    if (!tapped) return
    await api.setStock(tapped.spice_key, stock)
    setRack(await api.rack())
    setTapped({ ...tapped, stock: stock as Jar['stock'] })
  }

  async function loadProposal(next: 'balanced' | 'strict') {
    setMode(next)
    setProposal(await api.proposal(next))
  }

  async function applyProposal() {
    if (!proposal) return
    setBusy(true)
    try {
      setRack(await api.applyLayout(proposal.placements))
      setProposal(null)
    } finally { setBusy(false) }
  }

  if (!rack) return <div className="page"><p className="muted">Loading…</p></div>

  return (
    <div className="page rack-page">
      <h1>The rack</h1>

      {/* The drawing spans the page. Nothing sits beside it: a fixed column on
          the right left a visible hole whenever it had nothing in it, and one
          that appeared on click would narrow the shelves and shrink every jar
          in the picture. The panels go underneath instead. */}
      <div className="rack-controls">
        {!wide && (
          <div className="segmented inline">
            <button className={view === 'picture' ? 'on' : ''}
                    onClick={() => setView('picture')}>Picture</button>
            <button className={view === 'names' ? 'on' : ''}
                    onClick={() => setView('names')}>Full names</button>
          </div>
        )}
      </div>

      {(wide || view === 'picture') ? (
        <FullRack jars={rack.jars} racks={rack.racks}
                  rackLabels={rack.rack_labels}
                  onTap={setTapped} selected={tapped?.spice_key ?? null} />
      ) : (
        <RackList jars={rack.jars} racks={rack.racks}
                  rackLabels={rack.rack_labels} rowLabels={rack.row_labels} />
      )}

      {/* Not rendered at all when it would be empty: an empty grid still carries
          its own top margin, which is a gap under the shelves that nothing
          explains. */}
      {((wide && tapped) || authed) && (
      <div className="rack-panels">
        {/* On desktop the jar detail is a panel rather than a modal, so you can
            click along a row reading notes without dismissing a sheet between
            every jar. It is absent until a jar is selected — the panel used to
            hold a line of instructions telling you to click a jar, which is a
            caption on an empty box explaining that the box is empty. */}
        {wide && tapped && (
          <section className="panel jar-panel">
            <JarDetail jar={tapped} view={rack} authed={authed}
                       onStock={setStock} onClose={() => setTapped(null)} />
          </section>
        )}

        {authed && (
          <section className="panel">
            <h3>Re-shelve</h3>
            <p className="muted small">
              Sorts the jars you actually reach for onto the top rows, from what
              has been called for across every recipe so far.
            </p>
            <div className="segmented inline">
              <button className={mode === 'balanced' ? 'on' : ''}
                      onClick={() => loadProposal('balanced')}>Keep left/right split</button>
              <button className={mode === 'strict' ? 'on' : ''}
                      onClick={() => loadProposal('strict')}>Pure frequency</button>
            </div>

            {proposal && (
              <>
                <p className="muted small">
                  Based on {proposal.total_recipes} recipe{proposal.total_recipes === 1 ? '' : 's'}.
                  {proposal.total_recipes < 15 &&
                    ' Thin evidence so far — worth waiting until you have cooked more.'}
                </p>
                {proposal.moves.length === 0 ? (
                  <p className="muted">Nothing to move. The rack is already sorted.</p>
                ) : (
                  <>
                    <ul className="moves">
                      {proposal.moves.slice(0, 30).map((m) => (
                        <li key={m.spice_key}>
                          <b>{m.name}</b>
                          <span>
                            {rack.rack_labels[m.from.rack]} r{m.from.row + 1}
                            {' → '}
                            {rack.rack_labels[m.to.rack]} r{m.to.row + 1}·{m.to.col + 1}
                          </span>
                          <em>{m.uses} use{m.uses === 1 ? '' : 's'}</em>
                        </li>
                      ))}
                    </ul>
                    {proposal.moves.length > 30 &&
                      <p className="muted small">+{proposal.moves.length - 30} more.</p>}
                    <button className="primary" onClick={applyProposal} disabled={busy}>
                      {busy ? 'Saving…' : `Move ${proposal.moves.length} jars`}
                    </button>
                    <p className="hint">
                      This only changes the picture. Move the real jars to match.
                    </p>
                  </>
                )}
                {proposal.unused.length > 0 && (
                  <p className="muted small">
                    Never used yet: {proposal.unused.join(', ')}
                  </p>
                )}
              </>
            )}
          </section>
        )}
      </div>
      )}

      {/* On a wide screen the picture/names toggle is a false choice — there is
          room for the drawing AND the names, and sorting the shelf wants both. */}
      {wide && (
        <div className="rack-names-wide">
          <RackList jars={rack.jars} racks={rack.racks}
                    rackLabels={rack.rack_labels} rowLabels={rack.row_labels} />
        </div>
      )}

      {/* Phones keep the sheet: there is no room for a panel, and a tap should
          fill the screen rather than nudge one off it. */}
      {tapped && !wide && (
        <JarSheet jar={tapped} view={rack} authed={authed}
                  onStock={setStock} onClose={() => setTapped(null)} />
      )}
    </div>
  )
}
