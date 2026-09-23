# Hosting Spice

**Live at `https://spice.yaqzan.dev`, public, through its own cloudflared tunnel.**

Public on purpose: it's a portfolio piece and the rack visual is the thing to show. The spend and
the owner's data are not public.

## What a stranger can and cannot reach

| Open to anyone (GET only) | Needs a tailnet peer address |
|---|---|
| `/api/health`, minimal for a stranger | `/api/ask`, **the one that spends money** |
| `/api/rack`, redacted | `/api/settings` (read and write) |
| `/api/demo`, one frozen real recipe | `/api/recipes`, `/api/recipes/<id>` |
| the SPA's HTML/JS/CSS and icons | `/api/models` |
| | every mutation: stock, layout, ratings |

- **The guard is default-deny** (`PUBLIC_ENDPOINTS` in `spice/api.py`). A new route is private
  unless added to that list, so forgetting gives a 401, not a leak.
- **Anonymous `/api/rack`** returns every jar, but each `uses` is 0 and each `stock` is `ok`
  (usage and stock describe the owner's habits).
- **Anonymous `/api/health`** returns only `status`, `authed: false`, `jars` and `version`.

## The network is the only credential

> A request from `100.64.0.0/10` is the owner. Everything else is a visitor.

- A hostname isn't secret: **Certificate Transparency logs publish every certificate name within
  minutes**, and bots probe them. `/api/ask` spends a metered OpenRouter key.
- The shared passphrase (PBKDF2, remembered in `localStorage`) **is gone** on purpose: it needed a
  lock screen and explanatory copy that crowded the public page.
- Judged on the **TCP peer address, never a header** (see `CLAUDE.md`). cloudflared runs on this
  machine, so tunnel traffic arrives on loopback as a stranger. Whatever loopback can reach, the
  internet can reach.
- Trade-off, accepted: **no way into the private side without Tailscale**, owner included.

### The one exception: `SPICE_OPEN`

`npm run dev` talks to a loopback API, which can never authenticate, so the owner side can't be
built without this:

```powershell
$env:SPICE_OPEN = '1'; py -3.11 -m spice serve   # development ONLY
```

Every caller is then the owner. **Never set this in `server.ps1`: loopback is where the public
tunnel lands, so it hands the internet the spend.** It's an env var, not a stored setting, so it
can't be left on by a click. `serve()` prints a warning and Settings shows a red banner while it's
on.

Second backstop: `daily_ask_limit` (default 60) caps billed calls per calendar day, checked
**before** the API call. It also stops a stuck client looping.

## The tunnel

Copy `ops/cloudflared-config.example.yml` to `ops/cloudflared-config.yml` (gitignored) and fill in
your tunnel. On my machine a shared controller runs it:

```powershell
C:\Development\server.ps1 -Action start  -Service spice     # api + tunnel
C:\Development\server.ps1 -Action status -Service spice
C:\Development\server.ps1 -Action logs   -Service spice-api
```

- Spice has its own tunnel (`spice`), not an ingress rule on `trading-api`: that one is
  dashboard-managed and can't be extended from a config file, and a separate tunnel means a Spice
  restart never touches trading or fantasy. Same pattern as Curator and Scribe.
- **DNS routing trap:** `~/.cloudflared/config.yml` names the `trading-api` tunnel, and
  `cloudflared tunnel route dns <name>` ignores its name argument when that file names a tunnel.
  Always pass `--config` and the UUID:

```bash
cloudflared --config ops/cloudflared-config.yml tunnel route dns <tunnel-uuid> <hostname>
```

- `--overwrite-dns` repairs a bad record. About 30 s of edge 502s after a connector restart is
  normal.

## Later: the tailnet-only variant

**Ready but not active.** `server.ps1` has a `spice-proxy` service for it, left out of
`$ServiceOrder` so `-Service all` doesn't start it.

- Idea: point the **public** DNS record at this machine's **private** Tailscale address
  (`tailscale ip -4`, CGNAT space). The name resolves for everyone; only the tailnet can connect.
- The certificate then needs a DNS-01 challenge. `C:\Development\_ops\caddy\caddy.exe` is a
  Caddy 2.11.4 build with `caddy-dns/cloudflare`. Don't replace the winget Caddy on PATH with it:
  `winget upgrade` would silently swap it back.

To switch:

1. Cloudflare -> API Tokens -> *Edit zone DNS*, scoped to `yaqzan.dev` only.
   `setx /M CLOUDFLARE_API_TOKEN "<token>"`
2. Copy `ops/Caddyfile.example` to `ops/Caddyfile` (gitignored), fill in your hostname and tailnet
   IP, then check: `C:\Development\_ops\caddy\caddy.exe validate --config ops\Caddyfile` (fails
   only on the empty token until step 1 is done).
3. Replace the `spice` CNAME with an `A` record to your tailnet IP, **grey cloud**.
4. Stop `spice-tunnel`, start `spice-proxy`.

Only one of the two can own the hostname; switching means swapping the DNS record.

Afterwards:

- *Name resolves, connection hangs*: the device is off the tailnet.
- *Tailnet `bind` fails at startup*: Tailscale isn't up yet.
- The tailnet IP lives in two places, the Caddyfile `bind` and the DNS record; `tailscale ip -4`
  gives the current one.

## Not done, on purpose

- **No Cloudflare Access.** A second identity system for an audience of one owner plus anonymous
  visitors who are meant to see the demo.
- **No `tailscale funnel`.** Same public exposure, none of the tunnel's benefits.
