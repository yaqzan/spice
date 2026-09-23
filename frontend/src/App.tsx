import { NavLink, Route, Routes } from 'react-router-dom'
import { AccessProvider, useAccess } from './access'
import { AskPage } from './pages/AskPage'
import { DemoPage } from './pages/DemoPage'
import { RecipePage } from './pages/RecipePage'
import { RackPage } from './pages/RackPage'
import { HistoryPage } from './pages/HistoryPage'
import { SettingsPage } from './pages/SettingsPage'

// Bottom tab bar rather than a top nav: this is held one-handed at a stove, and
// the bottom third of the screen is the only part a thumb reaches comfortably.
const TABS = [
  { to: '/', label: 'Ask', icon: '🍳' },
  { to: '/rack', label: 'Rack', icon: '🧂' },
  { to: '/cooked', label: 'Cooked', icon: '📖' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

function Shell() {
  const { ready, authed } = useAccess()

  // One frame of nothing rather than a flash of the public landing followed by
  // the real app — the check is a single local request and resolves instantly.
  if (!ready) return <div className="page"><p className="muted">…</p></div>

  return (
    <div className="app">
      <main>
        <Routes>
          {/* The front door changes depending on who is knocking: the owner gets
              the ask box, everyone else gets the shop window. */}
          <Route path="/" element={authed ? <AskPage /> : <DemoPage />} />
          <Route path="/recipe/:id" element={<RecipePage />} />
          <Route path="/rack" element={<RackPage />} />
          <Route path="/cooked" element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
      <nav className="tabs">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to} end={tab.to === '/'}
                   className={({ isActive }) => (isActive ? 'on' : '')}>
            <span aria-hidden>{tab.icon}</span>
            {tab.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

export default function App() {
  return (
    <AccessProvider>
      <Shell />
    </AccessProvider>
  )
}
