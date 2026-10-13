# -*- coding: utf-8 -*-
"""The jacket vocabulary shared by the portal and the landing page.

One author mark, one title split, one length bucket — defined once so the
two pages cannot drift apart. Marks are drawn, never fetched: 24×24 line
work on `currentColor`, so they inherit the author tint and the theme.
"""
from __future__ import annotations
import html, io, json, unicodedata
import os as _os

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
 "blackwood": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
          '<path d="M7.6 9.4 12 3l4.4 6.4"/><path d="M6 13.9 12 6.9l6 7"/><path d="M4.6 18.2 12 10.8l7.4 7.4"/>'
          '<path d="M12 18.2v3.3"/><path d="M2.8 21.5h18.4" opacity=".45"/></g>',
 "chambers": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linejoin="miter">'
          '<path d="M4.6 17.4 3.6 7.6l4.9 4.1L12 5.2l3.5 6.5 4.9-4.1-1 9.8z"/>'
          '<path d="M2.8 21.5h18.4" opacity=".45"/></g><circle cx="12" cy="14.2" r=".85" fill="currentColor"/>',
 "machen": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
          '<path d="M9.6 17.6V6.4c0-2.2 4.8-2.2 4.8 0v11.2"/>'
          '<path d="M2.8 21.5c3.6-3.9 14.8-3.9 18.4 0" opacity=".45"/></g>'
          '<circle cx="12" cy="9.4" r=".8" fill="currentColor"/>',
 "andreyev": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
          '<path d="M6.5 21.5V3.2h10.4"/><path d="M6.5 7.4 10.7 3.2" opacity=".6"/>'
          '<path d="M16.9 3.2v5.3"/><circle cx="16.9" cy="10.4" r="1.9"/>'
          '<path d="M2.8 21.5h18.4" opacity=".45"/></g>',
 "jacobs": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round">'
          '<path d="M9 21.5v-6.3c-1.6-.6-2.4-2-2.4-3.6"/><path d="M15 21.5v-6.3c1.2-.9 1.9-2.4 1.9-4.1"/>'
          '<path d="M9.6 14.6V6.1c0-1.2 1.6-1.2 1.6 0v6.2"/><path d="M11.2 12.3V4.4c0-1.2 1.6-1.2 1.6 0v7.9"/>'
          '<path d="M12.8 12.3V6.3c0-1.2 1.6-1.2 1.6 0v6"/>'
          '<path d="M2.8 21.5h18.4" opacity=".45"/></g>',
 "yumeno": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round">'
          '<path d="M12 11.6c.6 0 .9.5.8 1-.2.8-1.2 1.1-1.9.7-1-.6-1.1-2-.4-2.9 1-1.2 2.9-1.2 4-.2 1.4 1.3 1.3 3.6-.1 4.9-1.7 1.6-4.5 1.5-6.1-.2-1.9-2-1.7-5.3.3-7.2 2.3-2.2 6.1-2 8.3.4"/>'
          '<path d="M2.8 21.5h18.4" opacity=".45"/></g>',
 "akutagawa": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
          '<path d="M3.4 6.2h17.2"/><path d="M4.8 9.6h14.4"/><path d="M5.2 14h13.6" opacity=".6"/>'
          '<path d="M6.6 6.2v15.3"/><path d="M17.4 6.2v15.3"/><path d="M12 9.6v4.4"/>'
          '<path d="M2.8 21.5h18.4" opacity=".45"/></g>',
 "harbou": '<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
          '<path d="M5 21.5V16h14v5.5"/><path d="M7.2 16v-5h9.6v5"/><path d="M9.4 11V5.6h5.2V11"/>'
          '<path d="M12 5.6V2.6"/><path d="M2.8 21.5h18.4" opacity=".45"/></g>',
}


# The house mark — redrawn as line work from the brand image (Gemini, 2026-10):
# a gabled roof over an open book, one line from the ridge down the spine.
# 48-unit grid, stroke on currentColor, so it takes the theme like the author marks.
LOGO_PATHS = ('<path d="M8 22.5H2L24 2L46 22.5H40"/><path d="M24 2V46"/>'
              '<path d="M8 22.5V40.2Q17 40.6 24 46Q31 40.6 40 40.2V22.5"/>'
              '<path d="M11 20.2V38.4Q18.5 38.9 24 43.6Q29.5 38.9 37 38.4V20.2"/>'
              '<path d="M14 18.2Q20.5 19.4 24 26Q27.5 19.4 34 18.2V36.6Q28.6 37.2 24 41.2Q19.4 37.2 14 36.6Z"/>')


# Below ~32px the three nested pages run together, so the small cut drops the
# middle one (as the favicon does) and thickens the line.
LOGO_SMALL = LOGO_PATHS.replace('<path d="M11 20.2V38.4Q18.5 38.9 24 43.6Q29.5 38.9 37 38.4V20.2"/>', '')


def logo(cls="logo", sw=2.6, small=False):
    """The mark at any size (sw is the stroke in grid units)."""
    return ('<svg class="%s" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="%s"'
            ' stroke-linejoin="miter" aria-hidden="true" focusable="false">%s</svg>'
            % (cls, sw, LOGO_SMALL if small else LOGO_PATHS))


def surname(en, orig="en"):
    """'Thea von Harbou' -> 'von Harbou', 'H. G. Wells' -> 'Wells'.
    Japanese names are written family name first: 'Yumeno Kyūsaku' -> 'Yumeno'."""
    w = en.split()
    if orig == "ja":
        return w[0]
    return " ".join(w[-2:]) if len(w) > 2 and w[-2].islower() else w[-1]


def roll(authors):
    """The masthead name line, from the catalogue so it can never fall behind.
    Each name is one unbreakable unit and the dot rides at its head, so a
    narrow screen never splits 'von / Harbou' or starts a line with a dot."""
    last = len(authors) - 1
    return " ".join('<span class="nm">%s%s</span>' % (surname(a["en"], a.get("orig", "en")),
                                                      "" if i == last else "&nbsp;&nbsp;·")
                    for i, a in enumerate(authors))


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


_ADV = None
# the decade's title setting in cover.css: case, tracking (em), weight factor
TITLE_SET = {1890: ("U", .095, 1.0), 1900: ("U", .05, 1.02), 1910: ("SC", .06, 1.0),
             1920: ("U", .015, 1.05), 1930: ("I", 0.0, 1.0)}


def title_fit(t, decade, lang):
    """Width in em of the title's widest word as cover.css sets it, so the
    board can cap the type size and a long single word (METAMORPHOSIS in
    small capitals) never runs through the frame. Widths are the shipped
    Source Serif 4 advances (tools/serif_adv.json, `python fonts.py adv`)."""
    global _ADV
    words = t.split() or [t]
    if lang == "ja":
        return max(len(w) for w in words) * 1.12
    if _ADV is None:
        _ADV = json.load(io.open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                               "serif_adv.json"), encoding="utf-8"))
    case, trk, wt = TITLE_SET[min(1930, decade)]

    def ch(c):
        if case == "U":
            c = c.upper()
            return _ADV["R"].get(c) or _ADV["R"].get(_base(c), .7)
        if case == "SC":
            tab = "R" if c.isupper() else "SC"
            return _ADV[tab].get(c) or _ADV[tab].get(_base(c), .6)
        return _ADV["I"].get(c) or _ADV["I"].get(_base(c), .5)
    return max(sum(ch(c) + trk for c in w) for w in words) * wt


def _base(c):
    return unicodedata.normalize("NFKD", c)[:1]


FORM_KO = {
    "novel": "장편", "novella": "중편", "story": "단편",
    "collection": "단편집", "play": "희곡",
    "miscellany": "잡문집", "essay-novel": "사변소설",
}


# ---------------------------------------------------------------- the cover
# One board for the library and the front door (tools/cover.css). Every part
# carries one fact; see the table at the top of cover.css.
NATION = {"kafka": "de", "harbou": "de", "wells": "uk", "blackwood": "uk", "machen": "uk",
          "jacobs": "uk", "fitzgerald": "us", "chambers": "us", "andreyev": "ru",
          "yumeno": "jp", "akutagawa": "jp"}

# genre emblems, 24-unit line work like the author marks
EMBLEMS = {
 "sf": '<circle cx="12" cy="12" r="5.2"/><ellipse cx="12" cy="12" rx="10.4" ry="3.1" transform="rotate(-18 12 12)"/>',
 "weird": '<path d="M15.5 3.2a8.8 8.8 0 1 0 0 17.6a7.2 7.2 0 0 1 0-17.6z"/><path d="M19 6.5v3M17.5 8h3"/>',
 "fable": '<path d="M19.5 3.5C11.5 4.5 6 10.5 4.5 20.5"/><path d="M19.5 3.5c-.5 6.5-5 10.5-11.5 11.5"/><path d="M10 13.5 8 11M13 10.5l-1.6-2.8"/>',
 "mystery": '<circle cx="7.5" cy="12" r="3.6"/><path d="M11.1 12H21M17.2 12v3.2M20.2 12v2.2"/>',
 "society": '<path d="M3 20.5V11l4.2-3.2L11.4 11v9.5"/><path d="M11.4 20.5V8.2L16.2 4 21 8.2v12.3"/><path d="M2 20.5h20"/><path d="M15 11h2.4M15 14.5h2.4" opacity=".6"/>',
 "romance": '<circle cx="9.3" cy="12" r="5.2"/><circle cx="14.7" cy="12" r="5.2"/>',
 "comic": '<path d="M4.6 5.2c4.6-2.2 10.2-2.2 14.8 0 0 8.2-3.4 13.6-7.4 13.6S4.6 13.4 4.6 5.2z"/><path d="M8 9.9c.8-1 2-1 2.8 0M13.2 9.9c.8-1 2-1 2.8 0"/><path d="M8.8 13.2c1.7 2 4.7 2 6.4 0"/>',
 "history": '<path d="M6.5 3h11M6.5 21h11"/><path d="M8 3c0 5 8 6 8 9s-8 4-8 9M16 3c0 5-8 6-8 9s8 4 8 9"/>',
 "ideas": '<circle cx="12" cy="12" r="3.6"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
}


def spine_width(minutes):
    """Spine band width in cqw from reading time, on a log scale:
    a one-minute parable gets a thin strip, a 15-hour novel a broad band."""
    import math
    f = math.log(max(1, minutes)) / math.log(900.0)
    return 2.5 + 14.0 * min(1.0, f)


def cover_board(w, title_tag="h2", extra=""):
    main, sub = title_split(w["title"])
    lang = w.get("orig", "en")
    pv = int(__import__("hashlib").md5(w["id"].encode()).hexdigest()[:4], 16) % 4
    subh = '<span class="sub">%s</span>' % html.escape(sub) if sub else ""
    emb = EMBLEMS.get(w.get("genre", ""), "")
    return ('<div class="cover" data-author="%(a)s" data-decade="%(d)d" data-genre="%(g)s" data-form="%(f)s"'
            ' data-nat="%(n)s" data-len="%(len)s" data-lang="%(lang)s" data-pv="%(pv)d"'
            ' style="--pv:%(pv)d;--spw:%(spw).2fcqw;--wl:%(wl).2f;--au:var(--author-%(a)s, var(--%(a)s))">'
            '<i class="cover__frame"></i><i class="cover__pat"></i>%(mark)s<i class="rule rule--head"></i>'
            '<%(tt)s class="cover__title" lang="%(lang)s">%(main)s%(sub)s</%(tt)s>'
            '<p class="cover__kt" lang="ko">%(ko)s</p>'
            '<i class="rule rule--foot"></i>'
            '<svg class="cover__emb" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width=".95"'
            ' aria-hidden="true" focusable="false">%(emb)s</svg>'
            '<p class="cover__author">%(auth)s</p><p class="cover__year">%(y)d</p>%(extra)s</div>') % {
        "a": w["author"], "d": min(1930, (w["year"] // 10) * 10), "g": html.escape(w.get("genre", "")),
        "f": html.escape(w.get("form", "novel")), "n": NATION.get(w["author"], "uk"),
        "len": len_bucket(main), "lang": lang, "wl": title_fit(main, w["year"] // 10 * 10, lang), "pv": pv, "spw": spine_width(w["minutes"]),
        "mark": mark(w["author"], "cover__mark"), "tt": title_tag,
        "main": html.escape(main), "sub": subh, "ko": html.escape(w.get("titleKo", "")),
        "emb": emb, "auth": html.escape(w["authorEn"]), "y": w["year"], "extra": extra}


def jacket(w, cls="jkt", tag="div", href=None, extra=""):
    """The front door's jacket: a link around the shared board."""
    if href:
        return '<a class="%s" href="%s"%s>%s</a>' % (cls, href, extra, cover_board(w, "p"))
    return '<%s class="%s"%s>%s</%s>' % (tag, cls, extra, cover_board(w, "p"), tag)
