"""Command line, mostly for the things a phone screen is bad at.

`serve` is the only command the app itself needs. The rest exist because a prompt
you cannot read is a prompt you cannot debug — `spice prompt` prints exactly what
gets sent, and `spice ask` runs the whole pipeline without a browser.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import api, db, openrouter, prompt, rack, recipes


def cmd_serve(_args) -> int:
    api.serve()
    return 0


def cmd_prompt(_args) -> int:
    db.ensure_schema()
    sys.stdout.write(prompt.build_system_prompt())
    return 0


def cmd_ask(args) -> int:
    db.ensure_schema()
    try:
        result = recipes.generate(args.query, args.lb, args.servings, args.extra or '',
                                  model=args.model or None)
    except openrouter.OpenRouterError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    payload = result['payload']
    print(f"\n{payload['title']}  [{payload.get('cuisine')}]  #{result['id']}")
    print(f"  {payload.get('why_this', '')}\n")
    print(f"  SALT  {payload['salt'].get('display')}  — {payload['salt'].get('when')}")
    layout = db.layout()
    for group in payload.get('blend_groups') or []:
        headline = 'mix these together' if group['premix'] else 'on its own'
        print()
        print(f"  BOWL {group['bowl']} - {headline}: {group['when']}")
        for item in group['items']:
            place = layout.get(item['spice_key'], {})
            where = (f"{place.get('rack', '?')} r{place.get('row', 0) + 1}"
                     f"c{place.get('col', 0) + 1}")
            print(f"      {item['name']:<26} {item['amount']:<16} {where}")
        if group['keep_apart']:
            print(f"      ! {group['keep_apart']}")
    for warning in payload.get('warnings', []):
        print(f'  ! {warning}')
    print()
    for step in payload['steps']:
        print(f"  {step['n']}. {step['title']} ({step['heat']})")
        print(f"     {step['body']}")
        if step.get('watch_for'):
            print(f"     watch: {step['watch_for']}")
    return 0


def cmd_rate(args) -> int:
    db.ensure_schema()
    if not db.recipe(args.id):
        print(f'no recipe {args.id}', file=sys.stderr)
        return 1
    recipes.rate(args.id, args.score, args.salt, args.heat, notes=args.notes or '')
    print(f'rated #{args.id} {args.score}/10 '
          f'(salt {args.salt:+d}, heat {args.heat:+d})')
    return 0


def cmd_log(args) -> int:
    """Enter a dish cooked before the app existed, with its rating."""
    db.ensure_schema()
    recipe_id = db.log_historical(args.title, args.cuisine, args.protein,
                                  args.notes or '', args.when)
    if args.rating is not None:
        db.rate(recipe_id, args.rating, args.salt, args.heat,
                notes=args.notes or '')
        if args.when:
            db.execute('UPDATE ratings SET rated_at = ? WHERE recipe_id = ?',
                       (args.when, recipe_id))
        print(f'logged #{recipe_id} {args.title} [{args.cuisine}] '
              f'- {args.rating}/10 (salt {args.salt:+d}, heat {args.heat:+d})')
    else:
        print(f'logged #{recipe_id} {args.title} [{args.cuisine}] - unrated')
    return 0


def cmd_rack(args) -> int:
    db.ensure_schema()
    view = recipes.rack_view()
    if args.json:
        print(json.dumps(view, indent=2))
        return 0
    for rack_name in view['racks']:
        print(f"\n{view['rack_labels'][rack_name]}")
        rows = {}
        for jar in view['jars']:
            if jar['rack'] == rack_name:
                rows.setdefault(jar['row'], []).append(jar)
        for row_index in sorted(rows):
            jars = sorted(rows[row_index], key=lambda j: j['col'])
            # Frequency names only where they mean something — the wall racks.
            label = (view['row_labels'][row_index]
                     if rack_name in view.get('wall_racks', ())
                     and row_index < len(view['row_labels']) else '')
            print(f'  {row_index + 1}' + (f' ({label}):' if label else ':'))
            for jar in jars:
                flag = '' if jar['stock'] == 'ok' else f"  [{jar['stock'].upper()}]"
                print(f"     {jar['col'] + 1}. {jar['name']:<30} "
                      f"{jar['uses']} use(s){flag}")
    return 0


def cmd_reshelve(args) -> int:
    db.ensure_schema()
    proposal = recipes.reshelve_proposal(args.mode)
    print(f"mode={proposal['mode']}  recipes={proposal['total_recipes']}  "
          f"moves={len(proposal['moves'])}")
    for move in proposal['moves']:
        print(f"  {move['name']:<30} {move['from']['rack']} r{move['from']['row'] + 1}"
              f" -> {move['to']['rack']} r{move['to']['row'] + 1}"
              f"c{move['to']['col'] + 1}   ({move['uses']} uses)")
    if not args.apply:
        print('\ndry run — pass --apply to commit')
        return 0
    db.set_layout(proposal['placements'])
    print(f"applied: {len(proposal['moves'])} jars moved")
    return 0


def cmd_stock(args) -> int:
    db.ensure_schema()
    spice = rack.resolve(args.spice)
    if not spice:
        print(f'no such spice: {args.spice}', file=sys.stderr)
        return 1
    db.set_spice_state(spice.key, args.state)
    print(f'{spice.name}: {args.state}')
    return 0


def cmd_stats(_args) -> int:
    db.ensure_schema()
    rows = db.history(limit=1000)
    rated = [r for r in rows if r['overall'] is not None]
    print(f'recipes: {len(rows)}   rated: {len(rated)}')
    if rated:
        print(f"mean score: {sum(r['overall'] for r in rated) / len(rated):.1f}/10")
        print(f'salt bias:  {db.salt_bias():+.2f}   heat bias: {db.heat_bias():+.2f}')
    counts = sorted(db.usage_counts().items(), key=lambda kv: -kv[1])
    if counts:
        print('\nmost used:')
        for key, count in counts[:15]:
            spice = rack.ALL_BY_KEY.get(key)
            print(f'  {count:>3}x  {spice.name if spice else key}')
    print('\ncuisine rotation:')
    for name, days, count, date in db.cuisine_recency():
        print(f'  {name:<18} {date}  {days}d ago   ({count}x)')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='spice', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('serve', help='run the API + built SPA').set_defaults(func=cmd_serve)
    sub.add_parser('prompt', help='print the system prompt that would be sent'
                   ).set_defaults(func=cmd_prompt)

    ask = sub.add_parser('ask', help='generate a recipe')
    ask.add_argument('query')
    ask.add_argument('--lb', type=float, default=1.0)
    ask.add_argument('--servings', type=int, default=2)
    ask.add_argument('--extra', default='')
    ask.add_argument('--model', default='', help='override the configured model once')
    ask.set_defaults(func=cmd_ask)

    rate = sub.add_parser('rate', help='rate a cooked recipe')
    rate.add_argument('id', type=int)
    rate.add_argument('score', type=int)
    rate.add_argument('--salt', type=int, default=0, help='-2 way under .. +2 way over')
    rate.add_argument('--heat', type=int, default=0, help='-2 too mild .. +2 too hot')
    rate.add_argument('--notes', default='')
    rate.set_defaults(func=cmd_rate)

    log = sub.add_parser('log', help='record a dish cooked before this app, '
                                     'so it can carry a rating')
    log.add_argument('title')
    log.add_argument('--cuisine', required=True)
    log.add_argument('--protein', default='')
    log.add_argument('--rating', type=float, default=None, help='1-10, halves ok')
    log.add_argument('--salt', type=int, default=0,
                     help='-2 way under .. +2 way over')
    log.add_argument('--heat', type=int, default=0,
                     help='-2 too mild .. +2 too hot')
    log.add_argument('--when', default='',
                     help='YYYY-MM-DD it was cooked; without it the cuisine '
                          'rotation thinks it was today')
    log.add_argument('--notes', default='')
    log.set_defaults(func=cmd_log)

    rack_cmd = sub.add_parser('rack', help='print the current rack')
    rack_cmd.add_argument('--json', action='store_true')
    rack_cmd.set_defaults(func=cmd_rack)

    reshelve = sub.add_parser('reshelve', help='propose a frequency-sorted rack')
    reshelve.add_argument('--mode', choices=('balanced', 'strict'), default='balanced')
    reshelve.add_argument('--apply', action='store_true', help='commit the new layout')
    reshelve.set_defaults(func=cmd_reshelve)

    stock = sub.add_parser('stock', help='mark a jar ok / low / out')
    stock.add_argument('spice')
    stock.add_argument('state', choices=db.STOCK_STATES)
    stock.set_defaults(func=cmd_stock)

    sub.add_parser('stats', help='what has been cooked and what gets used'
                   ).set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    return args.func(args)
