"""Flask API + static host for the built SPA.

One port serves both, so whatever fronts this needs exactly one hostname. Every
route the frontend uses lives under `/api`; anything else falls through to the
SPA's `index.html` so client-side routes deep-link and a bookmarked recipe opens
straight to that recipe.
"""

from __future__ import annotations

import threading

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.serving import make_server

from . import auth, config, db, openrouter, rack, recipes, schema

VERSION = '1.0.0'

# Readable by anyone, GET only. Everything not on this list is private, so adding
# a route defaults to closed and a mistake here is a deliberate act rather than an
# oversight.
#
# The app doubles as a portfolio piece, so the rack visual and a worked example
# are meant to be seen. Everything else -- the spend (`/api/ask`), the owner's
# cooking history and ratings, his settings, and every mutation -- needs a tailnet
# peer address, and there is no second way to get one.
#
# `/api/health` is on the list by necessity too -- server.ps1's watchdog polls it
# through the public hostname -- and it is written to leak nothing beyond "there
# is a service here" to a caller off the tailnet.
PUBLIC_ENDPOINTS = frozenset({
    '/api/health',
    '/api/rack',            # the showpiece; redacted for anonymous callers
    '/api/demo',            # a frozen example recipe, costs nothing to serve
})


def create_app():
    db.ensure_schema()
    app = Flask(__name__, static_folder=None)

    def authed() -> bool:
        """True only for a tailnet peer (or an explicitly opened dev server).

        `request.remote_addr` is the real TCP peer. It is NOT read from
        `X-Forwarded-For`, and it must never be: this app is simultaneously
        reachable through a public Cloudflare tunnel, so a forwarded header
        would let anyone on the internet claim to be a tailnet peer. Through the
        tunnel, cloudflared connects over loopback, so those requests present as
        127.0.0.1 and are treated as the strangers they are.
        """
        return auth.authorised(request.remote_addr)

    @app.before_request
    def require_tailnet():
        """Default-deny on /api: public routes are whitelisted, GET only.

        Static assets stay open on purpose -- the HTML and JS are not secret, and
        the public face of the app is built out of them.
        """
        # Lowercased and stripped of a trailing slash before comparing. Flask's
        # own routing is case-sensitive and would 404 `/API/rack` anyway, but the
        # guard should not be the thing relying on that: normalising here means a
        # near-miss path is refused rather than waved through to the router.
        path = request.path.lower().rstrip('/') or '/'
        if not path.startswith('/api/'):
            return None
        if request.method == 'GET' and path in PUBLIC_ENDPOINTS:
            return None
        if authed():
            return None
        # No `gated` flag and nothing to retry with: there is no code to supply,
        # so the client has nothing to do about this except stop asking.
        return jsonify({'error': 'This is the owner\'s, and only reachable '
                                 'from his tailnet.'}), 401

    # ── health ───────────────────────────────────────────────────────────────

    @app.get('/api/health')
    def health():
        try:
            count = db.one('SELECT COUNT(*) c FROM recipes')['c']
            rated = db.one('SELECT COUNT(*) c FROM ratings')['c']
            ok = True
        except Exception:
            count = rated = 0
            ok = False

        # This route is unauthenticated by necessity (the watchdog polls it over
        # the public hostname), so to a stranger it says only that a service is
        # alive. Which model is configured and how much has been cooked here are
        # nobody else's business.
        #
        # `authed` is here rather than on a route of its own: it is the one bit
        # the frontend needs on boot to decide whether to draw the owner's app or
        # the public exhibit, and health was already the call it made.
        if not authed():
            return jsonify({'status': 'ok' if ok else 'error',
                            'authed': False, 'jars': len(rack.SPICES),
                            'version': VERSION})

        return jsonify({
            'status': 'ok' if ok else 'error',
            'authed': True,
            'recipes': count,
            'rated': rated,
            'jars': len(rack.SPICES),
            # Whether a key is present, never the key itself.
            'openrouter': bool(config.openrouter_key()),
            'model': db.setting('model'),
            'asks_today': auth.asks_today(),
            'daily_limit': auth.daily_limit(),
            # How this caller got in. False here means the dev override is on --
            # worth being able to see from the settings screen, because it is the
            # one state where the app is open to more than a peer.
            'via_tailnet': auth.from_tailnet(request.remote_addr),
            'version': VERSION,
        })

    # ── the rack ─────────────────────────────────────────────────────────────

    @app.get('/api/rack')
    def get_rack():
        return jsonify(recipes.rack_view(include_private=authed()))

    @app.get('/api/demo')
    def demo():
        """A frozen, real recipe so an anonymous visitor sees the thing working.

        Served from a file rather than generated: it must cost nothing, look the
        same every time, and keep working when the API key is absent or the
        OpenRouter account is empty.
        """
        payload = recipes.demo_recipe()
        if payload is None:
            return jsonify({'error': 'no demo recipe available'}), 404
        return jsonify({'payload': payload})

    @app.post('/api/rack/state')
    def set_rack_state():
        body = request.get_json(silent=True) or {}
        key = body.get('spice_key')
        if key not in rack.ALL_BY_KEY:
            return jsonify({'error': f'unknown spice: {key}'}), 400
        stock = body.get('stock', 'ok')
        if stock not in db.STOCK_STATES:
            return jsonify({'error': f'stock must be one of {db.STOCK_STATES}'}), 400
        db.set_spice_state(key, stock, body.get('opened_on'), body.get('note'))
        return jsonify({'ok': True, 'spice_key': key, 'stock': stock})

    @app.get('/api/rack/proposal')
    def rack_proposal():
        mode = request.args.get('mode', 'balanced')
        if mode not in ('balanced', 'strict'):
            return jsonify({'error': 'mode must be balanced or strict'}), 400
        return jsonify(recipes.reshelve_proposal(mode))

    @app.post('/api/rack/layout')
    def apply_layout():
        """Commit a new arrangement — only ever called after the user says yes.

        Validated hard: a placement list that is missing a jar or double-books a
        slot would leave the visual pointing at the wrong shelf, which is the one
        failure that makes the whole app untrustworthy.
        """
        body = request.get_json(silent=True) or {}
        placements = body.get('placements') or []
        keys = [p.get('spice_key') for p in placements]
        if len(keys) != len(set(keys)):
            return jsonify({'error': 'a spice appears twice in the layout'}), 400
        unknown = [k for k in keys if k not in rack.ALL_BY_KEY]
        if unknown:
            return jsonify({'error': f'unknown spices: {unknown}'}), 400
        # Every jar the app knows about, not just the 56 on the walls — dropping
        # a stove-shelf item would quietly take the salt off the visual, and
        # set_layout() replaces the whole table rather than merging.
        missing = set(rack.ALL_BY_KEY) - set(keys)
        if missing:
            return jsonify({'error': f'{len(missing)} jars missing from the layout: '
                                     f'{sorted(missing)[:5]}'}), 400
        slots = [(p.get('rack'), p.get('row'), p.get('col')) for p in placements]
        if len(slots) != len(set(slots)):
            return jsonify({'error': 'two jars share a slot'}), 400
        db.set_layout(placements)
        return jsonify(recipes.rack_view())

    # ── asking for a recipe ──────────────────────────────────────────────────

    @app.post('/api/ask')
    def ask():
        body = request.get_json(silent=True) or {}
        query = (body.get('query') or '').strip()
        if not query:
            return jsonify({'error': 'Say what you are cooking.'}), 400
        try:
            portion_lb = float(body.get('portion_lb') or db.setting('default_protein_lb'))
            servings = int(body.get('servings') or db.setting('servings'))
        except (TypeError, ValueError):
            return jsonify({'error': 'portion_lb and servings must be numbers'}), 400

        # Checked before the call, not after: the point is to not spend the money.
        if auth.over_daily_limit():
            return jsonify({'error': f'Daily limit of {auth.daily_limit()} recipes '
                                     f'reached. Raise it in Settings if that is wrong.'}), 429

        try:
            result = recipes.generate(query, portion_lb, servings,
                                      extra=body.get('extra') or '',
                                      model=body.get('model'))
        except openrouter.OpenRouterError as exc:
            # A model failure is an expected outcome, not a server fault — 502 so
            # the frontend can show the message rather than a generic crash.
            return jsonify({'error': str(exc)}), 502
        return jsonify(result)

    # ── history ──────────────────────────────────────────────────────────────

    @app.get('/api/recipes')
    def list_recipes():
        try:
            limit = min(max(1, int(request.args.get('limit') or 50)), 500)
        except (TypeError, ValueError):
            return jsonify({'error': 'limit must be a number'}), 400
        rated_only = request.args.get('rated') == '1'
        return jsonify({'recipes': db.history(limit=limit, rated_only=rated_only)})

    @app.get('/api/recipes/<int:recipe_id>')
    def get_recipe(recipe_id):
        row = db.recipe(recipe_id)
        if not row:
            return jsonify({'error': 'no such recipe'}), 404
        factor = request.args.get('scale')
        if factor:
            try:
                value = float(factor)
            except (TypeError, ValueError):
                return jsonify({'error': 'scale must be a number'}), 400
            # Infinity and negatives are numbers too, and a negative one produces
            # a recipe calling for minus four grams of salt.
            if not (0 < value <= 20) or value != value:
                return jsonify({'error': 'scale must be between 0 and 20'}), 400
            row['payload'] = recipes.decorate(schema.scale(row['payload'], value))
        else:
            # Decorated on the way out, never trusted from storage: the salt line
            # then quotes whichever salt is in the cupboard today, and a recipe
            # saved before the card stopped printing grams reads like the rest.
            row['payload'] = recipes.decorate(row['payload'])
        return jsonify(row)

    @app.post('/api/recipes/<int:recipe_id>/rate')
    def rate_recipe(recipe_id):
        if not db.recipe(recipe_id):
            return jsonify({'error': 'no such recipe'}), 404
        body = request.get_json(silent=True) or {}
        try:
            overall = int(body.get('overall'))
        except (TypeError, ValueError):
            return jsonify({'error': 'overall is required, 1-10'}), 400
        if not 1 <= overall <= 10:
            return jsonify({'error': 'overall must be 1-10'}), 400

        def clamp(value):
            try:
                return max(-2, min(2, int(value or 0)))
            except (TypeError, ValueError):
                return 0

        recipes.rate(recipe_id, overall,
                     salt_delta=clamp(body.get('salt_delta')),
                     heat_delta=clamp(body.get('heat_delta')),
                     would_repeat=body.get('would_repeat'),
                     notes=body.get('notes') or '')
        return jsonify(db.recipe(recipe_id))

    @app.post('/api/recipes/<int:recipe_id>/archive')
    def archive_recipe(recipe_id):
        db.execute('UPDATE recipes SET archived = 1 WHERE id = ?', (recipe_id,))
        return jsonify({'ok': True})

    # ── settings ─────────────────────────────────────────────────────────────

    @app.get('/api/settings')
    def get_settings():
        return jsonify({
            'settings': db.settings(),
            'salt_brands': {k: {'label': v[0], 'grams_per_tsp': v[1]}
                            for k, v in db.SALT_BRANDS.items()},
            'has_key': bool(config.openrouter_key()),
        })

    @app.post('/api/settings')
    def post_settings():
        body = request.get_json(silent=True) or {}
        # Whitelisted against the defaults, so an unknown key is a 400 rather
        # than a new row nothing reads.
        allowed = set(db.DEFAULT_SETTINGS)
        for key, value in body.items():
            if key not in allowed:
                return jsonify({'error': f'unknown setting: {key}'}), 400
            if key == 'daily_ask_limit':
                # Coerce and store the INT, not whatever JSON arrived. A JSON
                # number 60.0 passed int(60.0) here and was then stored as the
                # string '60.0', which int() could not read back -- and the cap
                # treated the unreadable value as "no cap". Validation that does
                # not persist what it validated is not validation.
                try:
                    value = int(float(value))
                    if value < 0:
                        raise ValueError
                except (TypeError, ValueError):
                    return jsonify({'error': 'daily_ask_limit must be 0 or more'}), 400
            if key == 'salt_brand' and value not in db.SALT_BRANDS:
                return jsonify({'error': f'unknown salt brand: {value}'}), 400
            if key == 'acid_policy' and value not in ('none', 'background', 'free'):
                return jsonify({'error': f'unknown acid policy: {value}'}), 400
            db.set_setting(key, value)
        return jsonify({'settings': db.settings()})

    @app.get('/api/models')
    def models():
        try:
            return jsonify({'models': openrouter.list_models()})
        except openrouter.OpenRouterError as exc:
            return jsonify({'error': str(exc)}), 502

    # ── the built SPA ────────────────────────────────────────────────────────

    @app.get('/')
    def index():
        return _spa()

    @app.get('/<path:path>')
    def static_or_spa(path):
        target = config.FRONTEND_DIST / path
        if target.is_file():
            return send_from_directory(config.FRONTEND_DIST, path)
        return _spa()

    def _spa():
        index_file = config.FRONTEND_DIST / 'index.html'
        if not index_file.is_file():
            return ('Frontend not built. Run: npm --prefix frontend install && '
                    'npm --prefix frontend run build', 503)
        return send_from_directory(config.FRONTEND_DIST, 'index.html')

    return app


def serve():
    """Listen on loopback and, if Tailscale is up, on the tailnet address too.

    Two named binds rather than 0.0.0.0. Binding everything would also expose the
    port to the LAN, and the guarantee this whole feature rests on is that the
    SOCKET proves where a request came from — a LAN client must not be able to
    connect at all, let alone arrive with an address that could be mistaken for a
    peer. Loopback carries the cloudflared tunnel; the tailnet address carries
    the phone.
    """
    config.ensure_dirs()
    app = create_app()

    hosts = [config.API_HOST]
    tailnet = config.tailscale_ip() if config.TRUST_TAILNET else ''
    if tailnet and tailnet != config.API_HOST:
        hosts.append(tailnet)

    servers = [make_server(host, config.API_PORT, app, threaded=True)
               for host in hosts]
    for host in hosts:
        print(f'Spice on http://{host}:{config.API_PORT}'
              + ('   <- the way in' if host == tailnet else '   (public face only)'))
    if tailnet:
        url = config.tailnet_url()
        if url:
            print(f'Tailnet peers: {url}')
    else:
        print('Tailscale not detected - nobody can reach anything private, '
              'including you. Everyone gets the rack and the demo.')
    if config.OPEN_ACCESS:
        print('!! SPICE_OPEN=1 - EVERY caller is treated as the owner, including '
              'anyone arriving through the public tunnel. Development only.')

    threads = [threading.Thread(target=s.serve_forever, daemon=True)
               for s in servers[1:]]
    for thread in threads:
        thread.start()
    servers[0].serve_forever()
