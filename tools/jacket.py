# -*- coding: utf-8 -*-
"""The jacket vocabulary shared by the portal and the landing page.

One author mark, one title split, one length bucket — defined once so the
two pages cannot drift apart. Marks are drawn, never fetched: 24×24 line
work on `currentColor`, so they inherit the author tint and the theme.
"""
from __future__ import annotations
import html

MARKS = {
 "kafka": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
          '<path d="M6 21.5V2.8h12v18.7"/><path d="M14.7 3.6v17.9"/>'
          '<path d="M3 21.5h18" opacity=".45"/></g><circle cx="13.4" cy="12.7" r=".75" fill="currentColor"/>',
 "wells": '<g fill="none" stroke="currentColor" stroke-width="1"><circle cx="12" cy="12" r="8.4"/>'
          '<path d="M3.6 12h16.8" opacity=".45"/><path d="M12 12 16.6 7.4"/></g>'
          '<circle cx="12" cy="12" r=".85" fill="currentColor"/>',
 "fitzgerald": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
          '<path d="M4 20a8 8 0 0 1 16 0"/><path d="M12 20V11.6"/><path d="M12 20 6.1 14.1"/>'
          '<path d="M12 20 17.9 14.1"/><path d="M2.8 20h18.4" opacity=".45"/></g>',
 "harbou": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
          '<path d="M5 21.5V16h14v5.5"/><path d="M7.2 16v-5h9.6v5"/><path d="M9.4 11V5.6h5.2V11"/>'
          '<path d="M12 5.6V2.6"/><path d="M2.8 21.5h18.4" opacity=".45"/></g>',
}


def mark(slug, cls="mark"):
    return ('<svg class="%s" viewBox="0 0 24 24" aria-hidden="true" focusable="false">%s</svg>'
            % (cls, MARKS[slug]))


def title_split(t):
    """Main title / subtitle. Collections carry their `and Other …` half at a
    smaller size so the jacket reads at a glance."""
    for sep in (" and Other ", " and a ", ", or ", ": "):
        i = t.find(sep)
        if i > 0:
            return t[:i], (sep.strip(", :") + " " + t[i + len(sep):]).strip()
    return t, ""


def len_bucket(t):
    """Type size class for the jacket — set by how much title there is."""
    n = len(t)
    return "s" if n <= 14 else "m" if n <= 24 else "l" if n <= 38 else "xl"


FORM_KO = {
    "novel": "장편", "novella": "중편", "story": "단편",
    "collection": "단편집", "play": "희곡",
    "miscellany": "잡문집", "essay-novel": "사변소설",
}


def jacket(w, cls="jkt", tag="div", href=None, extra=""):
    """A standalone book jacket — used by the landing page. The portal builds
    its own (it needs the progress and caption furniture around it)."""
    main, sub = title_split(w["title"])
    subh = '<span class="jkt__s">%s</span>' % html.escape(sub) if sub else ""
    open_tag = ('<a class="%s" data-len="%s" style="--au:var(--%s)" href="%s"%s>'
                % (cls, len_bucket(main), w["author"], href, extra)) if href else (
               '<%s class="%s" data-len="%s" style="--au:var(--%s)"%s>'
               % (tag, cls, len_bucket(main), w["author"], extra))
    close = "</a>" if href else "</%s>" % tag
    return """%(open)s<span class="jkt__in">%(mark)s<i class="jkt__r jkt__r--h"></i><span class="jkt__t">%(main)s%(sub)s</span><i class="jkt__r jkt__r--f"></i><span class="jkt__a">%(auth)s</span><span class="jkt__y">%(year)d</span></span>%(close)s""" % {
        "open": open_tag, "close": close,
        "mark": mark(w["author"], "jkt__mark"),
        "main": html.escape(main), "sub": subh,
        "auth": html.escape(w["authorEn"]), "year": w["year"]}
