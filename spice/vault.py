"""One checklist in the owner's Obsidian vault, so a paid-for recipe gets rated.

Every generated recipe costs real money and, more importantly, is worth nothing
to the app until it is rated: ratings drive the salt correction, the heat
correction and the cuisine rotation. The evidence that this was needed is stark
— of the recipes this app has generated, none has ever been rated, while twelve
of the fourteen dishes entered by hand carry a score. The app was never short of
a rating screen; it was short of anything that asked.

What this deliberately is NOT:

* Not a note per recipe. The vault was rebuilt specifically to undo that shape —
  Spore's `rules.toml` records 231 imported pages whose entire content was three
  frontmatter keys, and the cost as "231 entries in the quick switcher, the
  graph and every search result". A rating nudge is a name, a date and a link.
  It is a line, not a document.
* Not a card on the Spice engineering board. `Projects.base` selects tickets
  vault-wide on `file.hasProperty("project")`, so that property IS board
  membership and there is no folder to hide in. Ten real tickets would be buried
  under dinners.
* Not anywhere under `Food/`. Spore recognises a restaurant by folder SHAPE, so
  a recipes folder there would become restaurant #121 and get rewritten.
* Not a read-back. A checkbox carries one bit; a rating carries a score, a salt
  delta, a heat delta and notes — and the salt delta is the number that moves
  the baseline. Ticking a box in Obsidian means "stop asking", nothing more.

Be honest about what most lines will do: the owner generates recipes he never
cooks — four in one morning while testing. Most of these get ticked as "never
made it", and that tick is the feature working, not failing.

Nothing here may ever break a recipe. By the time this runs the model has been
paid; a vault on an unmounted drive, a locked file or a bad path must cost a log
line and nothing else.
"""
from __future__ import annotations

import os
import re
from datetime import date

from . import config

OPEN_HEADING = '## To rate'
DONE_HEADING = '## Rated'

# Matches the other four data notes in `To Do/`, so the folder's CSS applies.
# `source: spice` rather than `spore` because Spore does not own this file yet;
# if the tab is ever registered there, Spore rewrites the key itself.
_FRONTMATTER = '---\ncssclasses:\n  - todo-data\nsource: spice\n---\n'

# Characters the To Do tooling parses as metadata rather than as text: priority
# marks, a due date, a completion stamp. A recipe title has no business carrying
# them, but a model writes the title and this file is parsed by code in another
# repo, so they are stripped rather than trusted.
_RESERVED = re.compile('[⏫⏬\U0001f53a\U0001f53c\U0001f53d]'
                       '|[\U0001f4c5✅]\\s*\\d{4}-\\d{2}-\\d{2}')


def _enabled() -> bool:
    """False under pytest, and false when the vault simply is not there.

    The pytest guard is not belt-and-braces. The suite drives recipe generation
    to a 200 at eleven call sites with the model stubbed, each against a fresh
    database where ids restart at 1 — so an unguarded hook would append a dozen
    fake dinners to the real vault on every run, and collide with the owner's
    genuine recipe #1 while doing it.

    `config.TODO_FILE` is read through the module on every call, never bound at
    import, so a test can point it somewhere harmless.
    """
    if os.environ.get('PYTEST_CURRENT_TEST'):
        return False
    return config.TODO_FILE.parent.is_dir()


def _clean(title: str) -> str:
    text = _RESERVED.sub('', str(title or 'Untitled')).replace('|', '/').strip()
    return text or 'Untitled'


def _link(recipe_id: int) -> str:
    """A tailnet link, or no link at all.

    Never the public origin. `spice.yaqzan.dev` is a CNAME to the cloudflared
    tunnel and the tunnel connects over loopback, so a phone ON the tailnet
    still arrives looking like a stranger and the page 403s — being on the
    tailnet only helps if you connect to the tailnet address. And the SPA route
    is singular: `/recipe/<id>`, not `/recipes/<id>`, which renders empty chrome.

    With Tailscale down there is no honest link, so it falls back to naming the
    command rather than emitting one that will not work.
    """
    base = config.tailnet_url()
    if not base:
        return '`spice rate %d`' % recipe_id
    return '[rate](%s/recipe/%d)' % (base.rstrip('/'), recipe_id)


def _read() -> str:
    try:
        return config.TODO_FILE.read_text(encoding='utf-8')
    except FileNotFoundError:
        return _FRONTMATTER


def _write(text: str) -> None:
    """Atomic, and staged outside the vault.

    The temp file goes in the app's own data directory rather than beside the
    target: same NTFS volume, so `os.replace` is a real atomic rename, while
    Obsidian's file watcher and whatever syncs the vault see one finished file
    appear instead of a half-written one and a stray `.tmp` to replicate.
    """
    tmp = config.DATA_DIR / 'Recipes.md.tmp'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(text, encoding='utf-8', newline='\n')
    os.replace(tmp, config.TODO_FILE)


def _split(text: str):
    """Pull the note apart into (frontmatter, open lines, done lines).

    Parsing and re-rendering, rather than splicing strings. The splice version
    produced headings with no blank line around them, which is not how the other
    four notes in `To Do/` are written.

    It rebuilds from the FILE and never from the database, and that distinction
    is the whole reason a line the owner deletes stays deleted: nothing here
    knows what used to be there, so a deletion in Obsidian is final rather than
    something the next generation undoes.
    """
    head, rest = '', text
    if text.startswith('---\n'):
        end = text.find('\n---\n', 4)
        if end != -1:
            head, rest = text[:end + 5], text[end + 5:]
    section, opened, done = None, [], []
    for line in rest.splitlines():
        stripped = line.strip()
        if stripped == OPEN_HEADING:
            section = opened
        elif stripped == DONE_HEADING:
            section = done
        elif stripped.startswith('- [') and section is not None:
            section.append(stripped)
    return (head or _FRONTMATTER), opened, done


def _render(head: str, opened: list, done: list) -> str:
    """Blank line after every heading, one trailing newline, nothing else."""
    parts = [head.rstrip('\n'), '', OPEN_HEADING, '']
    parts.extend(opened)
    parts.extend(['', DONE_HEADING, ''])
    parts.extend(done)
    return '\n'.join(parts).rstrip('\n') + '\n'


def _index_of(lines: list, recipe_id: int) -> int:
    """Where this recipe's line is, or -1.

    Matched on the id and nothing else — not the title, which a model writes and
    repeats, and not the position. Word-boundaried so `#8` can never match
    inside `#80` and tick the wrong dinner.
    """
    pattern = re.compile('(?<![0-9])#%d(?![0-9])' % recipe_id)
    for index, line in enumerate(lines):
        if pattern.search(line):
            return index
    return -1


def add_recipe(recipe_id: int, title: str) -> None:
    """Add one unticked line. Silent on failure — the recipe is already paid for."""
    if not _enabled():
        return
    try:
        head, opened, done = _split(_read())
        if _index_of(opened, recipe_id) >= 0 or _index_of(done, recipe_id) >= 0:
            return
        # ISO date first, so the To Do app's alphabetical sort is also
        # chronological. Without it "#10" sorts above "#8".
        opened.insert(0, '- [ ] %s — %s #%d — %s' % (
            date.today().isoformat(), _clean(title), recipe_id, _link(recipe_id)))
        _write(_render(head, opened, done))
    except (OSError, ValueError, UnicodeError) as exc:
        print('[spice] could not write the rating reminder: %s' % exc)


def mark_rated(recipe_id: int) -> None:
    """Tick the line and move it under `## Rated`.

    Only ever moves a line it can already find, which is what makes deleting one
    in Obsidian a durable "stop asking me about that".
    """
    if not _enabled():
        return
    try:
        head, opened, done = _split(_read())
        index = _index_of(opened, recipe_id)
        if index < 0:
            return
        line = opened.pop(index).replace('- [ ] ', '- [x] ', 1)
        done.insert(0, '%s ✅ %s' % (line, date.today().isoformat()))
        _write(_render(head, opened, done))
    except (OSError, ValueError, UnicodeError) as exc:
        print('[spice] could not tick the rating reminder: %s' % exc)
