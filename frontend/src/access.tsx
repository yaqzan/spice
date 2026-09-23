import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

// Whether this browser is talking to the app from the owner's tailnet.
//
// One boolean, decided by the server from the TCP peer address and never by
// anything this code can set. There is nothing to unlock, nothing to type, and
// nothing to remember between visits — you are either on that network or you are
// looking at the exhibit. See spice/auth.py.

type AccessState = {
  ready: boolean
  authed: boolean
}

const AccessContext = createContext<AccessState>({ ready: false, authed: false })

export const useAccess = () => useContext(AccessContext)

export function AccessProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AccessState>({ ready: false, authed: false })

  useEffect(() => {
    // /api/health is public and answers `authed` either way, so this is one
    // request rather than a probe followed by a real call.
    api.health()
      .then((h) => setState({ ready: true, authed: !!h.authed }))
      // A server we cannot reach is not someone else's server. Let the pages
      // render and show their own errors.
      .catch(() => setState({ ready: true, authed: false }))
  }, [])

  return <AccessContext.Provider value={state}>{children}</AccessContext.Provider>
}

/** Stands in for a tab that holds nothing but the owner's own data. */
export function PrivateNotice({ what }: { what: string }) {
  return <p className="muted">{what} is the owner&rsquo;s, and stays on his tailnet.</p>
}
