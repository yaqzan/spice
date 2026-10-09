# Colour schemes

- **One site-wide theme**, the `theme` setting. The owner picks it in Settings (tailnet only);
  every visitor sees it. Not a per-browser preference, so no localStorage.
- **Names live in `spice/themes.py`, colours only in `styles.css`** as `[data-theme="<key>"]`
  blocks. Default `olive` is also `:root`, so an unstamped page draws the default. A test fails
  if a key has no block.
- **Stamped server-side**: `api._spa()` writes `data-theme` onto `<html>` in the served
  `index.html` (`Cache-Control: no-cache`), so first paint is already right. `theme.ts`
  re-applies it after `/api/health` (Vite dev serves the page unstamped) and on a Settings change,
  and moves `<meta name="theme-color">` to the theme's `--bg`. Manifest colours are static (Olive).
- **All schemes stay dark** (jar colours wash out on a light ground; see the `styles.css`
  header). Wood shelf and caps are themed only to sit on each ground; jar contents never change.
- **A green accent rings green herb jars weakly**; the filled number badge carries them.
- **Every chrome colour is a variable.** A raw hex outside the theme blocks belongs to the
  physical jar (paper label, scrim), not the app.
- **Compare or tune**: `py -3.11 tools/palette_preview.py` writes `.work/palettes.html`, every
  theme as a mock phone using the real stylesheet, with WCAG contrast ratios.
