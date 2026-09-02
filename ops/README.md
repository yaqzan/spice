# Hosting Spice

**Live now: `https://spice.yaqzan.dev`, public, via its own cloudflared tunnel.**

Public is deliberate — the app doubles as a portfolio piece, and the rack visual
is the thing worth showing. What is *not* public is the spend or the owner's
data. That split is the whole design of the exposure, so it is worth stating
plainly before the mechanics.

## What a stranger can and cannot reach

| Open to anyone (GET only) | Needs a tailnet peer address |
|---|---|
| `/api/health` — minimal for a stranger | `/api/ask` — **the one that spends money** |
| `/api/rack` — redacted | `/api/settings` (read and write) |
| `/api/demo` — one frozen real recipe | `/api/recipes`, `/api/recipes/<id>` |
| the SPA's HTML/JS/CSS and icons | `/api/models` |
| | every mutation: stock, layout, ratings |

The guard is **default-deny** (`PUBLIC_ENDPOINTS` in `spice/api.py`): a new route
is private unless it is explicitly added to that list, so the failure mode of
forgetting is a 401 rather than a leak.

Redaction matters as much as the list. An anonymous `/api/rack` returns every
jar — the drawing is intact — but each `uses` count is 0 and each `stock` is
`ok`. Which jars are running low and which get reached for constantly is a
picture of somebody's kitchen habits, and it is not interesting to a stranger.
Likewise anonymous `/api/health` reports only `status`, `authed: false`, `jars`
and `version`; not the model, not how much has been cooked.

## Why the network is the only credential

A hostname is not a secret. **Certificate Transparency logs publish every name a
public certificate is issued for, within minutes**, and there are bots that do
nothing but read those logs and probe what they find. "Nobody knows the URL" was
never true. With a metered OpenRouter key behind `/api/ask`, the realistic cost of
an open door is a stranger's recipes on someone else's bill.

There used to be a shared passphrase for exactly that reason — PBKDF2-hashed,
typed once per device, remembered in `localStorage`. **It is gone.** Not because
it failed, but because of what it cost around itself: a door needs a lock, a lock
needs a screen, the screen needs copy explaining why you are being asked, and the
public landing page ends up two-thirds apology. Deleting the door deleted all
four, and the remaining rule fits in a sentence:

> A request from `100.64.0.0/10` is the owner. Everything else is a visitor.

Judged on the **TCP peer address**, never a header — see the invariant in
`CLAUDE.md`. cloudflared runs on this machine, so tunnel traffic arrives on
loopback and is a stranger like anyone else. Whatever a loopback caller can
reach, the internet can reach; that is the entire public attack surface.

The trade is real and was made deliberately: there is now **no way into the
private side from a device without Tailscale**, including for the owner. The
answer to "I am on my mother's laptop" is "you are not cooking from it".

### The one exception: `SPICE_OPEN`

A laptop running `npm run dev` talks to a loopback API and can therefore never
authenticate, which makes the whole owner-side of the app unbuildable. So:

```powershell
$env:SPICE_OPEN = '1'; py -3.11 -m spice serve   # development ONLY
```

Every caller is then the owner. **Never set this in `server.ps1`** — loopback is
where the public tunnel lands, so it hands the internet the spend. It is an
environment variable rather than a stored setting precisely so it cannot be left
on by a click; `serve()` prints a warning while it is on and Settings shows a red
banner.

Second, independent backstop: `daily_ask_limit` (default 60) caps billed calls per
calendar day and is checked **before** the API call, so the money is not spent
first. It guards against a stuck client looping as much as against a stranger.

## The tunnel

```powershell
C:\Development\server.ps1 -Action start  -Service spice     # api + tunnel
C:\Development\server.ps1 -Action status -Service spice
C:\Development\server.ps1 -Action logs   -Service spice-api
```

Its own tunnel (`spice`, UUID `535c7f15-…`), not an ingress rule on the shared
`trading-api` one: that tunnel is dashboard-managed and cannot be extended from a
config file, and keeping Spice separate means a Spice restart never touches the
trading or fantasy ingress. Same pattern as Curator and Scribe.

**Routing DNS on this machine has a trap.** `~/.cloudflared/config.yml` names the
`trading-api` tunnel, and `cloudflared tunnel route dns <name>` silently ignores
its name argument when that file names a tunnel — the record ends up on the wrong
tunnel. Always pass `--config` *and* the UUID:

```bash
cloudflared --config C:/Development/Spice/ops/cloudflared-config.yml tunnel route dns 535c7f15-0a7e-45e0-80b1-896eaaae84e4 spice.yaqzan.dev
```

Add `--overwrite-dns` to repair a bad record. Roughly 30 seconds of edge 502s
after a connector restart is normal.

---

## Later: the tailnet-only variant

Kept ready but **not active**, because testing came first. The files are written
and `server.ps1` has a `spice-proxy` service for it; it is deliberately left out
of `$ServiceOrder` so `-Service all` does not try to start it.

The idea: point the **public** DNS record at this machine's **private** Tailscale
address (`100.80.250.61`). That is CGNAT space — routable inside the tailnet and
nowhere else. The name resolves for everyone; the connection completes only from
the tailnet.

Because nothing public can then reach the host, the certificate has to come from a
DNS-01 challenge. `C:\Development\_ops\caddy\caddy.exe` is a Caddy 2.11.4 build
carrying `caddy-dns/cloudflare` for exactly that. It is deliberately **not** the
winget Caddy on PATH — that one is the vanilla build with no DNS provider, and
overwriting it would put a custom binary somewhere `winget upgrade` can silently
swap back.

To switch over:

1. Cloudflare → API Tokens → *Edit zone DNS*, scoped to `yaqzan.dev` only.
   `setx /M CLOUDFLARE_API_TOKEN "<token>"`
2. Verify: `C:\Development\_ops\caddy\caddy.exe validate --config C:\Development\Spice\ops\Caddyfile`
   (it currently fails only on the empty token, which is the expected state)
3. Replace the `spice` CNAME with an `A` record → `100.80.250.61`, **grey cloud**.
4. Stop `spice-tunnel`, start `spice-proxy`.

The two cannot both own the hostname — switching means swapping the DNS record.

Failure modes worth recognising afterwards: *name resolves, connection hangs* is
a device off the tailnet, not a bug. *`bind 100.80.250.61` fails at startup* means
Tailscale is not up yet. The tailnet IP appears in two places — the Caddyfile
`bind` and the DNS record — and `tailscale ip -4` gives the current one.

## Not done, on purpose

**No Cloudflare Access.** It would work, but it is a second identity system to
maintain for an app whose whole audience is one person plus anonymous readers who
are *supposed* to get as far as the exhibit.

**No `tailscale funnel`.** Same public-exposure decision wearing a different hat,
with none of the tunnel's benefits.
