"""Side-by-side colour-scheme candidates, drawn with the app's real stylesheet.

Writes .work/palettes.html (gitignored): one mock phone per palette, each made
of the same class names the app uses, so what you see is what the theme does.
A palette is only the variable block at the top of frontend/src/styles.css;
pick one here, then copy its values there (and theme-color in index.html and
the manifest).

    py -3.11 tools/palette_preview.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / 'frontend' / 'src' / 'styles.css'
OUT = ROOT / '.work' / 'palettes.html'

# Wood stays wood and the caps stay near-black in every option: they are the
# physical rack, not the app chrome.
WOOD = {'shelf-top': '#5a4a37', 'shelf-face': '#2e261c'}

PALETTES = [
    ('A', 'Ember (current)', 'Warm char, orange accent. Today\'s look, for comparison.', {
        'bg': '#16130f', 'surface': '#1f1b16', 'surface-2': '#2a251e', 'line': '#3a3229',
        'text': '#f0e9df', 'muted': '#a1958a', 'accent': '#e08a2b', 'accent-dim': '#7a4a14',
        'on-accent': '#1a1208', 'hot': '#d94a2b', 'hot-dim': '#6b2a1a', 'good': '#6f9e4a',
        'warn': '#d9a13a', 'shelf-top': '#5d4a35', 'shelf-face': '#322718', 'cap': '#2b241c'}),
    ('B', 'Basil', 'Green-black ground, fresh basil accent. The straight "green for food" take.', {
        'bg': '#0f1411', 'surface': '#161d18', 'surface-2': '#1f2821', 'line': '#2c3830',
        'text': '#ecefe6', 'muted': '#93a096', 'accent': '#5fbf6b', 'accent-dim': '#24502c',
        'on-accent': '#07140a', 'hot': '#e0583a', 'hot-dim': '#5e2418', 'good': '#9bd46a',
        'warn': '#e2b043', 'cap': '#232a25', **WOOD}),
    ('C', 'Olive & Brass', 'Olive-tinted dark, chartreuse-olive accent. Earthier, more pantry than garden.', {
        'bg': '#13130e', 'surface': '#1b1c15', 'surface-2': '#25261c', 'line': '#36372a',
        'text': '#efeadb', 'muted': '#a29f8a', 'accent': '#b5c24a', 'accent-dim': '#4a5220',
        'on-accent': '#141605', 'hot': '#d9512e', 'hot-dim': '#622a18', 'good': '#7fb85a',
        'warn': '#e0a63a', 'cap': '#262619', **WOOD}),
    ('D', 'Sage & Copper', 'Green ground, copper accent. Green as the room, spice-orange as the action.', {
        'bg': '#111714', 'surface': '#18201c', 'surface-2': '#212b26', 'line': '#2f3b35',
        'text': '#eef0ea', 'muted': '#98a69e', 'accent': '#e0874a', 'accent-dim': '#6e3f1f',
        'on-accent': '#1a0f06', 'hot': '#e5533a', 'hot-dim': '#612519', 'good': '#7ec27a',
        'warn': '#e3b04b', 'cap': '#1f2723', **WOOD}),
    ('E', 'Mint', 'Deep teal-black, bright mint accent. The most modern and the most "app".', {
        'bg': '#0d1615', 'surface': '#132120', 'surface-2': '#1b2c2a', 'line': '#28403c',
        'text': '#eaf3ee', 'muted': '#8fa9a2', 'accent': '#4fd1a0', 'accent-dim': '#165244',
        'on-accent': '#04150f', 'hot': '#ef5b45', 'hot-dim': '#5c231b', 'good': '#8ad26b',
        'warn': '#f0b950', 'cap': '#1c2826', **WOOD}),
    ('F', 'Saffron Ink', 'Not green: blue-black ground, saffron accent. Jars pop hardest on cool dark.', {
        'bg': '#0f1218', 'surface': '#161a22', 'surface-2': '#1f2430', 'line': '#2d3342',
        'text': '#eceae4', 'muted': '#9499a6', 'accent': '#f2b134', 'accent-dim': '#5e4515',
        'on-accent': '#1a1204', 'hot': '#e5533d', 'hot-dim': '#5d2219', 'good': '#6fbf73',
        'warn': '#e8873a', 'cap': '#222733', **WOOD}),
]

# A slice of the real rack: three jars lit (one an olive herb, the hardest case
# for a green accent), the rest dimmed, one low.
JARS = [
    ('CHI', 'Chilli', '#b02010', 1, '1 tsp', None),
    ('CUM', 'Cumin', '#9c7a4a', 2, '2 tsp', None),
    ('ORE', 'Oregano', '#7d8a55', 3, '½ tsp', None),
    ('TUR', 'Turmeric', '#d4a017', 0, '', None),
    ('NIG', 'Nigella', '#1f1b18', 0, '', None),
    ('SAL', 'Salt', '#e8dcc0', 0, '', 'low'),
    ('GAR', 'Garam', '#7a4a28', 0, '', None),
]
JAR_PATH = ('M 2 19.5 C 2 13.2 6.5 10.5 12 10.5 L 26 10.5 C 31.5 10.5 36 13.2 36 19.5 '
            'L 36 45.5 Q 36 49.5 32 49.5 L 6 49.5 Q 2 49.5 2 45.5 Z')
SHEEN = ''.join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in [
    (0, '#000', .28), (.13, '#000', .02), (.21, '#fff', .17), (.36, '#fff', .03),
    (.75, '#000', .06), (1, '#000', .32)])


def luminance(hex_: str) -> float:
    rgb = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def rack(key: str) -> str:
    pad, w, h, gap = 14, 38, 50, 7
    width = pad * 2 + len(JARS) * w + (len(JARS) - 1) * gap
    out = [f'<svg viewBox="0 0 {width} 92" class="rack-svg"><defs>'
           f'<linearGradient id="sh-{key}" x1="0" y1="0" x2="1" y2="0">{SHEEN}</linearGradient></defs>',
           f'<rect x="{pad - 6}" y="{14 + h}" width="{width - pad * 2 + 12}" height="2" rx="1" class="rack-shelf-top"/>',
           f'<rect x="{pad - 6}" y="{16 + h}" width="{width - pad * 2 + 12}" height="3" rx="1" class="rack-shelf-face"/>']
    for i, (code, name, colour, order, amount, stock) in enumerate(JARS):
        x, cid = pad + i * (w + gap), f'c-{key}-{i}'
        out.append(f'<g transform="translate({x} 14)" class="jar{"" if order else " jar-dim"}">')
        if order:
            out.append(f'<rect x="-4" y="-4" width="{w + 8}" height="{h + 8}" rx="9" class="jar-ring"/>')
        out.append(
            f'<ellipse cx="{w / 2}" cy="{h + .8}" rx="14.5" ry="1.7" class="jar-shadow"/>'
            f'<g class="jar-visual"><clipPath id="{cid}"><path d="{JAR_PATH}"/></clipPath>'
            f'<path d="{JAR_PATH}" fill="{colour}" class="jar-glass"/>'
            f'<g clip-path="url(#{cid})"><rect x="2" y="10.5" width="34" height="5.5" class="jar-headspace"/>'
            f'<rect x="2" y="10.5" width="34" height="39" fill="url(#sh-{key})"/></g>'
            f'<rect x="0" width="38" height="20" rx="3" class="jar-cap-base"/>'
            f'<rect x="2" y="1.4" width="34" height="1.6" rx=".8" class="jar-cap-shine"/></g>'
            f'<g class="jar-code"><rect x="4.5" y="21" width="29" height="9.9" rx="1.6" class="jar-label-bg"/>'
            f'<text x="19" y="26.2" text-anchor="middle" dominant-baseline="central">{code}</text></g>')
        if stock == 'low':
            out.append(f'<circle cx="{w - 7}" cy="16" r="2.6" class="jar-low"/>')
        if order:
            out.append(f'<circle cx="{w - 2}" cy="2" r="10" class="jar-badge-bg"/>'
                       f'<text x="{w - 2}" y="6" text-anchor="middle" class="jar-badge">{order}</text>'
                       f'<text x="19" y="{h + 14}" text-anchor="middle" class="jar-name">{name}</text>'
                       f'<text x="19" y="{h + 24}" text-anchor="middle" class="jar-amount">{amount}</text>')
        out.append('</g>')
    return ''.join(out) + '</svg>'


def phone(letter: str, name: str, pitch: str, v: dict[str, str]) -> str:
    style = ';'.join(f'--{k}:{val}' for k, val in v.items())
    checks = [('text on bg', v['text'], v['bg']), ('muted on card', v['muted'], v['surface']),
              ('accent on card', v['accent'], v['surface']), ('ink on accent', v['on-accent'], v['accent'])]
    ratios = ' · '.join(f'{label} <b>{contrast(a, b):.1f}</b>' for label, a, b in checks)
    swatches = ''.join(f'<i title="--{k} {v[k]}" style="background:{v[k]}"></i>'
                       for k in ('bg', 'surface', 'surface-2', 'line', 'muted', 'text',
                                 'accent', 'accent-dim', 'good', 'warn', 'hot'))
    return f'''
<section class="option">
  <header><h2>{letter}. {name}</h2><p>{pitch}</p><div class="sw">{swatches}</div>
  <p class="ratios">{ratios}</p></header>
  <div class="phone" style="{style}">
    <div class="pad">
      <div class="recipe-head">
        <div class="recipe-chips">
          <span class="chip chip-cuisine">Sichuan</span><span class="chip chip-time">2 h 10</span>
          <span class="chip chip-heat"><span class="heat-dots"><i class="on"></i><i class="on"></i><i class="on"></i><i></i><i></i></span></span>
          <span class="chip chip-warn">Low on salt</span>
        </div>
        <h2>Crisp-skin pork belly</h2>
        <p class="why">Dry the skin overnight; the rub goes on the meat side only.</p>
      </div>
      <div class="panel panel-rack"><div class="rack-label">Left rack · row 2</div>{rack(letter)}</div>
      <div class="panel salt-panel"><h3>Salt</h3>
        <div class="salt-big">2 ¾ tsp</div>
        <p class="salt-msg">Rub it into the meat side, then rest it uncovered.</p>
        <p class="salt-why">7.5 g/lb on 1.5 lb, Diamond Crystal.</p></div>
      <div class="panel"><h3>Bowls</h3>
        <div class="bowl"><div class="bowl-head"><span class="bowl-n">1</span>
          <span class="bowl-when"><strong>Bloom</strong><em>into the hot oil, first</em></span></div>
          <ul class="blend">
            <li class="blend-row"><span class="blend-swatch" style="background:#9c7a4a"></span><span class="blend-main">Cumin<em>whole</em></span><span class="blend-amount">2 tsp</span></li>
            <li class="blend-row"><span class="blend-swatch" style="background:#b02010"></span><span class="blend-main">Chilli<em>ground</em></span><span class="blend-amount">1 tsp</span></li>
          </ul></div></div>
      <div class="panel"><h3>Steps</h3><ol class="steps"><li class="step">
        <div class="step-head"><span class="step-n">2</span><h4>Score and season</h4></div>
        <p class="step-body">Rub <span class="stamp"><i style="background:#e8dcc0"></i><span class="stamp-name">salt</span><span class="stamp-amount">1 <b class="unit-tbsp">TBSP</b></span></span>
          into the cuts, then tip in <span class="step-bowl-ref">bowl 1</span> for <span class="step-time">40 sec</span>.</p>
        <p class="step-watch"><span>Watch</span>cumin darkens fast once it pops.</p></li></ol></div>
      <fieldset class="segmented"><legend>Heat</legend>
        <button>Mild</button><button class="on">Medium<em>default</em></button><button>Hot</button></fieldset>
      <button class="primary big">What do I make?</button>
      <ul class="history"><li><a><span class="history-main">Mapo tofu<em>Sichuan · 2026-10-02</em></span><span class="history-side"><span class="score s5">5</span></span></a></li>
        <li><a><span class="history-main">Dal tadka<em>Indian · 2026-09-28</em></span><span class="history-side"><span class="score s3">3</span></span></a></li></ul>
    </div>
    <nav class="tabs"><a class="on"><span>🍳</span>Ask</a><a><span>🧂</span>Rack</a><a><span>📖</span>Cookbook</a><a><span>⚙️</span>Settings</a></nav>
  </div>
</section>'''


PAGE = '''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spice palettes</title><style>{css}
/* preview chrome */
html, body {{ height: auto; }}
body {{ background: #2a2a2a; color: #eee; padding: 24px; }}
body::before {{ display: none; }}
.grid {{ display: flex; flex-wrap: wrap; gap: 32px; justify-content: center; }}
.option {{ width: 375px; }}
.option header h2 {{ font-size: 20px; margin: 0 0 4px; }}
.option header p {{ font-size: 13px; color: #bbb; margin: 0 0 8px; min-height: 2.6em; }}
.option .ratios {{ font-size: 11px; min-height: 0; }}
.sw {{ display: flex; gap: 3px; margin-bottom: 6px; }}
.sw i {{ flex: 1; height: 18px; border-radius: 3px; border: 1px solid #0006; }}
.phone {{ background: var(--bg); color: var(--text); border-radius: 28px; overflow: hidden;
          border: 6px solid #111; box-shadow: 0 10px 40px #0008; }}
.phone .pad {{ padding: 18px 14px 6px; }}
.phone .tabs, .phone .tabs[class] {{ position: static; top: auto; left: auto; right: auto;
          bottom: auto; transform: none; width: auto; border-radius: 0; box-shadow: none;
          border: 0; border-top: 1px solid var(--line); }}
.phone .history a {{ cursor: default; }}
.intro {{ max-width: 760px; margin: 0 auto 28px; font-size: 14px; color: #ccc; }}
.intro b {{ color: #fff; }}
</style></head><body>
<div class="intro"><h1 style="margin:0 0 6px">Spice palettes</h1>
Each phone is the real stylesheet with a different variable block. Wood shelf and jar
contents never change. Ratios: WCAG contrast, <b>4.5+</b> is comfortable for body text.</div>
<div class="grid">{phones}</div></body></html>'''


def main() -> None:
    css = CSS.read_text(encoding='utf-8')
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(PAGE.format(css=css, phones=''.join(phone(*p) for p in PALETTES)),
                   encoding='utf-8')
    print(OUT)


if __name__ == '__main__':
    main()
