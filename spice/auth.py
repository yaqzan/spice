"""Who gets to spend money and read the cook's own data.

There is exactly one answer: a request that arrived from a tailnet peer. No
passphrase, no session, no token — the TCP peer address is the whole of it.

That is a deliberate narrowing. There used to be a shared code as well, typed
into an unlock sheet on first visit. But a code means the public hostname has a
door in it, and a door needs a lock, and a lock needs a screen, and the screen
needs copy explaining why it is there. Deleting the door deleted all four. What
remains on the public tunnel is a read-only exhibit — the rack drawing and one
frozen example recipe — and there is nothing on it to guess your way past.

`X-Forwarded-For` is never consulted and must never be. This app is reachable
through a public Cloudflare tunnel at the same moment it is reachable on the
tailnet, so a header claiming a 100.x address would hand every stranger on the
internet a peer's privileges.
"""

from __future__ import annotations

import ipaddress

from . import config, db

# Tailscale hands every node an address in this range (RFC 6598 shared address
# space). It is the tailnet's own block, and nothing routes into it from the
# public internet.
TAILNET = ipaddress.ip_network('100.64.0.0/10')


def from_tailnet(remote_addr: str) -> bool:
    """Did this request arrive from a tailnet peer?

    Judged on the TCP peer address only. Requests through the public tunnel
    reach the app over loopback — cloudflared runs on this machine — so they
    present as 127.0.0.1 and are strangers, exactly like anyone else out there.
    """
    if not config.TRUST_TAILNET or not remote_addr:
        return False
    try:
        return ipaddress.ip_address(remote_addr) in TAILNET
    except ValueError:
        return False


def is_open() -> bool:
    """The development escape hatch, off unless `SPICE_OPEN=1`.

    Since a tailnet peer address is the only credential, a laptop running the
    Vite dev server against a loopback API can never authenticate — the API
    would 401 every private route and the whole owner-side of the app would be
    unreachable while building it.

    This is the one thing that can open the app without a peer address, so it is
    an explicit environment variable rather than a stored setting, it defaults
    off, and `serve()` prints a warning whenever it is on.
    """
    return config.OPEN_ACCESS


def authorised(remote_addr: str) -> bool:
    """The single gate the API asks. Everything else is a stranger."""
    return is_open() or from_tailnet(remote_addr)


# ── the spend backstop ───────────────────────────────────────────────────────
# Independent of who is asking, because the failure it guards against is not a
# stranger at all: a retry loop or a stuck client can burn a lot of tokens
# quickly, and this app deliberately has no other rate limiting.

def asks_today() -> int:
    """Billed completions today — NOT finished recipes.

    Counting saved recipes made every failed ask free: the row is only written
    when the whole pipeline succeeds, while a failure still bills up to three
    completions through the schema fallback chain. The cap was blind to exactly
    the runaway it was written to stop.
    """
    return db.api_calls_today()


def daily_limit() -> int:
    """The cap, failing CLOSED on a value it cannot read.

    0 legitimately means "no cap", so returning 0 on a parse error silently
    disabled the only spend guard in the app. A stored value like '60.0' — which
    a JSON number produces — used to do exactly that. Falling back to the default
    keeps a broken setting safe rather than open.
    """
    raw = db.setting('daily_ask_limit')
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError):
        return int(db.DEFAULT_SETTINGS['daily_ask_limit'])


def over_daily_limit() -> bool:
    limit = daily_limit()
    return bool(limit) and asks_today() >= limit
