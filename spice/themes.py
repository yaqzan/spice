"""The colour schemes the owner can pick from Settings.

This is the list of names; the colours themselves live only in
frontend/src/styles.css as `[data-theme="<key>"]` blocks (a test checks every
key here has one). The chosen key is the `theme` setting, and everyone sees it:
the owner's pick is the site's look, not a per-browser preference.
"""

DEFAULT = 'olive'

# key -> (label, one-line pitch). Order is the order Settings shows them.
THEMES = {
    'ember': ('Ember', 'Warm char, orange accent. The original look.'),
    'basil': ('Basil', 'Green-black ground, fresh basil accent.'),
    'olive': ('Olive & Brass', 'Olive-tinted dark, chartreuse-olive accent.'),
    'sage': ('Sage & Copper', 'Green ground, copper accent.'),
    'mint': ('Mint', 'Deep teal-black, bright mint accent.'),
    'saffron': ('Saffron Ink', 'Blue-black ground, saffron accent.'),
}


def current(raw: str | None) -> str:
    """The stored key if it is still a theme, else the default."""
    return raw if raw in THEMES else DEFAULT
