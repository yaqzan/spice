import { useEffect } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
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
  { to: '/cookbook', label: 'Cookbook', icon: '📖' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

// iOS home-screen apps cold-start with a layout viewport ~47pt short of the screen,
// so the fixed tab bar floats above the home indicator until something (a route
// change, a scroll) makes WebKit re-measure. Do that on purpose after first paint
// and whenever the app returns to the foreground.
function useViewportNudge() {
  useEffect(() => {
    const nudge = () => {
      window.scrollTo(0, 1)
      window.scrollTo(0, 0)
      window.dispatchEvent(new Event('resize'))
    }
    const timers = [50, 300, 1000].map((ms) => window.setTimeout(nudge, ms))
    const onVisible = () => { if (document.visibilityState === 'visible') nudge() }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('pageshow', nudge)
    return () => {
      timers.forEach(window.clearTimeout)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('pageshow', nudge)
    }
  }, [])
}

function Shell() {
  const { ready, authed } = useAccess()
  useViewportNudge()

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
          <Route path="/cookbook" element={<HistoryPage />} />
          <Route path="/cooked" element={<Navigate to="/cookbook" replace />} />
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
