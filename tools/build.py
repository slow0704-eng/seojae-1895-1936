# -*- coding: utf-8 -*-
"""Build the offline reading site: 60 standalone work pages + a library index."""
from __future__ import annotations
import os, re, io, json, html, sys
import bookparse
from meta import build as build_catalog

HERE = os.path.dirname(os.path.abspath(__file__))
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
SITE = os.path.join(ROOT, chr(49436) + chr(51116))          # 소설\서재

CSS = io.open(os.path.join(HERE, "reader.css"), encoding="utf-8").read()
JS = io.open(os.path.join(HERE, "runtime.js"), encoding="utf-8").read()
IDXCSS = io.open(os.path.join(HERE, "index.css"), encoding="utf-8").read()
IDXJS = io.open(os.path.join(HERE, "index.js"), encoding="utf-8").read()

AUTHOR_SLUG = {"Franz Kafka": "kafka", "H. G. Wells": "wells",
               "F. Scott Fitzgerald": "fitzgerald", "Thea von Harbou": "harbou"}

# author monograms — door ajar / dial over horizon / deco fan / new tower
MARKS = {
 "kafka":'<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
         '<path d="M6 21.5V2.8h12v18.7"/><path d="M14.7 3.6v17.9"/>'
         '<path d="M3 21.5h18" opacity=".45"/></g><circle cx="13.4" cy="12.7" r=".75" fill="currentColor"/>',
 "wells":'<g fill="none" stroke="currentColor" stroke-width="1"><circle cx="12" cy="12" r="8.4"/>'
         '<path d="M3.6 12h16.8" opacity=".45"/><path d="M12 12 16.6 7.4"/></g>'
         '<circle cx="12" cy="12" r=".85" fill="currentColor"/>',
 "fitzgerald":'<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
         '<path d="M4 20a8 8 0 0 1 16 0"/><path d="M12 20V11.6"/><path d="M12 20 6.1 14.1"/>'
         '<path d="M12 20 17.9 14.1"/><path d="M2.8 20h18.4" opacity=".45"/></g>',
 "harbou":'<g fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="square">'
         '<path d="M5 21.5V16h14v5.5"/><path d="M7.2 16v-5h9.6v5"/><path d="M9.4 11V5.6h5.2V11"/>'
         '<path d="M12 5.6V2.6"/><path d="M2.8 21.5h18.4" opacity=".45"/></g>',
}
def mark(slug, cls="mark"):
    return ('<svg class="%s" viewBox="0 0 24 24" aria-hidden="true" focusable="false">%s</svg>'
            % (cls, MARKS[slug]))

END_ORN = ('<svg viewBox="0 0 14 14" width="14" height="14" aria-hidden="true">'
           '<path d="M7 .7 13.3 7 7 13.3.7 7Z" fill="none" stroke="currentColor" stroke-width="1" opacity=".55"/>'
           '<path d="M7 4.1 9.9 7 7 9.9 4.1 7Z" fill="currentColor"/></svg>')

HEAD_RX = re.compile(r'^<h2 class="(chapter|part)" id="([^"]+)"[^>]*>(.*)</h2>$')
P_RX = re.compile(r'^<p[^>]*data-p="(\d+)"')
TAG_RX = re.compile(r"<[^>]+>")


def strip_tags(s):
    return html.unescape(TAG_RX.sub("", s))


def prepare(html_str, author):
    """Drop the parser's own title/byline (the title page already carries them)
    and renumber data-p from 0, so that a paragraph's data-p is exactly its
    index in the runtime's paragraph array — the cumulative-character table is
    indexed by position, and any gap would silently offset every saved
    reading position."""
    out = []
    dropped_byline = False
    for ln in html_str.split("\n"):
        if ln.startswith('<h1 class="worktitle"'):
            continue
        if not dropped_byline and P_RX.match(ln):
            dropped_byline = True
            # drop it ONLY when it really is the byline — matching on "short"
            # alone deleted a genuine 39-character paragraph in two files
            if strip_tags(ln).strip().rstrip(".") == (author or "\0").strip():
                continue
        out.append(ln)
    n = [0]

    def renum(m):
        s = m.group(0).replace(m.group(1), str(n[0]))
        n[0] += 1
        return s
    body = "\n".join(out)
    body = re.sub(r'data-p="(\d+)"', renum, body)
    return body


def sectionise(lines):
    """Split the parser's flat element list into <section class="ch"> units and
    collect the chapter table the reader runtime needs."""
    secs, cur, chapters = [], [], []
    pending = None                       # heading that opens the next section

    def flush():
        if not cur:
            return
        chars = sum(len(strip_tags(l)) for l in cur if P_RX.match(l))
        firstp = next((int(P_RX.match(l).group(1)) for l in cur if P_RX.match(l)), None)
        secs.append({"lines": list(cur), "chars": chars, "firstp": firstp,
                     "head": pending})
        del cur[:]

    for ln in lines:
        m = HEAD_RX.match(ln)
        if m:
            flush()
            pending = {"kind": m.group(1), "id": m.group(2),
                       "label": strip_tags(m.group(3))}
        cur.append(ln)
    flush()

    out, idx = [], 0
    for s in secs:
        h = s["head"]
        if h and s["firstp"] is not None:
            chapters.append({"firstP": s["firstp"], "label": h["label"],
                             "title": "", "chars": s["chars"], "id": h["id"],
                             "kind": h["kind"]})
        est = max(300, int(s["chars"] * 1.25) + 220)
        out.append('<section class="ch" id="sec%d" style="contain-intrinsic-size:auto %dpx">\n%s\n</section>'
                   % (idx, est, "\n".join(s["lines"])))
        idx += 1
    return "\n".join(out), chapters


def sig(text):
    h = 0x811c9dc5
    for ch in text:
        h ^= ord(ch) & 0xFF
        h = (h * 0x01000193) & 0xFFFFFFFF
    return "%08x" % h


def page(work, body_html, chapters, manifest):
    w = dict(work)
    w["chapters"] = chapters
    w["sig"] = sig("%d:%s" % (len(chapters), body_html[:200] + body_html[-200:]))
    for k in ("file", "chars", "words", "minutes", "form"):
        w.pop(k, None)
    title = work["title"]
    return """<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s &middot; %(author)s</title>
<style>%(css)s</style>
<script>
/* pre-paint: apply the reader's stored typography before the first frame,
   so no page ever flashes the wrong theme or jumps from the top.
   Chrome partitions localStorage per file on file://, so settings arrive via
   the window.name bus; adopt them here, before anything renders. */
(function(){try{
var s=JSON.parse(localStorage.getItem("rdr/v1/settings")||"{}");var r=document.documentElement;
try{var n=window.name||"";if(n.indexOf("RDRBUS1:")===0){var b=JSON.parse(n.slice(8));
if(b&&b.s&&(b.s.updated||0)>(s.updated||0)){s=b.s;localStorage.setItem("rdr/v1/settings",JSON.stringify(s));}}}catch(e){}
var fs=s.fs||20,lh=s.lh||1.72,me=s.measure||68;
r.style.setProperty("--fs-num",fs);r.style.setProperty("--fs",fs+"px");
r.style.setProperty("--lh",(lh-(fs-20)*0.007).toFixed(3));
r.style.setProperty("--track",((20-fs)*0.0018).toFixed(4)+"em");
r.style.setProperty("--cpl",me);
r.dataset.theme=s.theme||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
r.dataset.font=s.font||"1";r.dataset.justify=s.justify?"on":"off";
r.dataset.indent=(s.indent===false)?"off":"on";
if(localStorage.getItem("rdr/v1/prog/%(id)s"))r.style.visibility="hidden";
setTimeout(function(){r.style.visibility="";},1200);
}catch(e){}})();
</script>
</head>
<body>
<div id="dimmer"></div>
<article id="book" lang="en">
<div class="titlepage">
<h1 class="work">%(title)s</h1>
<p class="work-ko">%(titleKo)s</p>
<p class="byline">%(author)s</p>
<p class="year">%(year)d</p>
<hr class="tp-rule">
</div>
%(body)s
<p class="endmark">%(orn)s</p>
<p class="colophon">%(yearu)d &middot; %(authoru)s</p>
</article>
<script>
var WORK=%(work)s;
var MANIFEST=%(manifest)s;
%(js)s
</script>
</body>
</html>
""" % {"title": html.escape(title), "titleKo": html.escape(work["titleKo"]),
       "author": html.escape(work["authorEn"]), "authoru": html.escape(work["authorEn"].upper()),
       "year": work["year"], "yearu": work["year"], "id": work["id"],
       "css": CSS, "js": JS, "body": body_html, "orn": END_ORN,
       "work": json.dumps(w, ensure_ascii=False),
       "manifest": json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))}


# ---------------------------------------------------------------- index page
DECADE = lambda y: min(1930, (y // 10) * 10)

def title_split(t):
    for sep in (" and Other ", " and a ", ", or ", ": "):
        i = t.find(sep)
        if i > 0:
            return t[:i], (sep.strip(", :") + " " + t[i + len(sep):]).strip()
    return t, ""

def len_bucket(t):
    n = len(t)
    return "s" if n <= 14 else "m" if n <= 24 else "l" if n <= 38 else "xl"

def cover(w, i):
    main, sub = title_split(w["title"])
    subh = '<span class="sub">%s</span>' % html.escape(sub) if sub else ""
    return """<article class="card" data-author="%(a)s" data-decade="%(d)d" data-len="%(len)s"
 data-year="%(y)d" data-id="%(id)s" data-title="%(tl)s" data-ko="%(ko)s" data-mins="%(mins)d"
 style="--i:%(i)d">
<a class="card__link" href="%(href)s">
 <div class="cover">
  %(mark)s
  <i class="rule rule--head"></i>
  <h3 class="cover__title">%(main)s%(sub)s</h3>
  <i class="rule rule--foot"></i>
  <p class="cover__author">%(auth)s</p>
  <p class="cover__year">%(y)d</p>
 </div>
 <p class="cap"><span class="cap__pct"></span><span>%(chars)s자</span><b>&middot;</b><span>%(time)s</span></p>
</a></article>""" % {
        "a": w["author"], "d": DECADE(w["year"]), "len": len_bucket(main),
        "y": w["year"], "id": w["id"], "i": i, "href": html.escape(w["href"]),
        "tl": html.escape(w["title"]), "ko": html.escape(w["titleKo"]),
        "mins": w["minutes"], "mark": mark(w["author"], "cover__mark"),
        "main": html.escape(main), "sub": subh,
        "auth": html.escape(w["authorEn"]),
        "chars": "{:,}".format(w["chars"]),
        "time": ("%d시간 %d분" % (w["minutes"] // 60, w["minutes"] % 60)) if w["minutes"] >= 60 else ("%d분" % w["minutes"]),
    }


def index_page(cat, works):
    tot_chars = sum(w["chars"] for w in works)
    tot_min = sum(w["minutes"] for w in works)
    by_dec = {}
    for w in sorted(works, key=lambda x: (x["year"], x["authorEn"], x["title"])):
        by_dec.setdefault(DECADE(w["year"]), []).append(w)
    grid, i = [], 0
    for d in sorted(by_dec):
        grid.append('<div class="era" role="separator"><span class="era__n">%d</span>'
                    '<span class="era__lab">년대</span><i class="era__line"></i>'
                    '<span class="era__ct">%d편</span></div>' % (d, len(by_dec[d])))
        for w in by_dec[d]:
            grid.append(cover(w, i)); i += 1

    plates = []
    for a in cat["authors"]:
        ws = sorted([x for x in works if x["author"] == a["slug"]], key=lambda x: (x["year"], x["title"]))
        plates.append('<header class="plate" data-author="%s"><span class="plate__mark">%s</span>'
                      '<div class="plate__id"><h2>%s</h2><p>%s &middot; %d편 &middot; %d–%d</p>'
                      '<p class="plate__note">%s</p></div><i class="rule plate__rule"></i></header>'
                      % (a["slug"], mark(a["slug"]), html.escape(a["en"]), a["life"],
                         len(ws), ws[0]["year"], ws[-1]["year"], html.escape(a["note"])))
        for w in ws:
            plates.append(cover(w, i)); i += 1
        if a["slug"] == "harbou":
            plates.append('<p class="solo">단 한 편.<br><i>Metropolis</i>, 1926년 — '
                          '이 서재에서 유일한 독일어권 작가의 작품입니다.</p>')

    return """<!doctype html>
<html lang="ko" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>서재 1895—1936</title>
<style>%(css)s
%(icss)s</style>
<script>(function(){try{var s=JSON.parse(localStorage.getItem("rdr/v1/settings")||"{}");
try{var n=window.name||"";if(n.indexOf("RDRBUS1:")===0){var b=JSON.parse(n.slice(8));
if(b&&b.s&&(b.s.updated||0)>(s.updated||0)){s=b.s;localStorage.setItem("rdr/v1/settings",JSON.stringify(s));}}}catch(e){}
document.documentElement.dataset.theme=s.theme||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
}catch(e){}})();</script>
</head>
<body class="lib">
<div class="wrap">
<header class="masthead">
  <p class="mh__kicker">개인 서재</p>
  <h1 class="mh__title">1895&#8202;—&#8202;1936</h1>
  <p class="mh__roll">Kafka &nbsp;·&nbsp; Wells &nbsp;·&nbsp; Fitzgerald &nbsp;·&nbsp; von Harbou</p>
  <i class="rule mh__rule"></i>
  <p class="mh__stat">%(n)d편 &nbsp;·&nbsp; 4인 &nbsp;·&nbsp; %(chars)s자 &nbsp;·&nbsp; 약 %(hours)d시간
    <span class="mh__mine" id="mine"></span></p>
</header>
<section class="now" id="now" hidden>
  <h2 class="now__h">읽는&nbsp;중</h2>
  <ul class="now__list" id="nowlist"></ul>
</section>
<nav class="ctl">
  <div class="ctl__sort" role="tablist">
    <button role="tab" data-sort="era" aria-selected="true">연대순</button>
    <button role="tab" data-sort="author">저자별</button>
    <button role="tab" data-sort="title">제목순</button>
    <button role="tab" data-sort="len">길이순</button>
  </div>
  <input class="ctl__find" type="search" id="find" placeholder="제목 또는 작가 찾기" aria-label="찾기">
  <span class="ctl__count" id="count"></span>
  <select class="ctl__theme" id="theme" aria-label="테마">
    <option value="light">종이</option><option value="sepia">세피아</option>
    <option value="dark">야간</option><option value="night">심야</option>
  </select>
</nav>
<main class="grid" id="grid" data-view="era">%(grid)s</main>
<div class="grid" id="grid-author" data-view="author" hidden>%(plates)s</div>
<footer class="lib-foot">
  <p>모든 작품은 퍼블릭 도메인입니다. 출처 — Project Gutenberg &middot; Standard Ebooks &middot; Wikisource</p>
  <p class="lib-foot__k"><kbd>/</kbd> 찾기 &nbsp; <kbd>Enter</kbd> 이어읽기 &nbsp; <kbd>1</kbd>–<kbd>4</kbd> 정렬</p>
</footer>
</div>
<script>
var MANIFEST=%(manifest)s;
%(js)s
%(ijs)s
</script>
</body>
</html>
""" % {"css": CSS, "icss": IDXCSS, "js": JS, "ijs": IDXJS,
       "n": len(works), "chars": "{:,}".format(tot_chars), "hours": tot_min // 60,
       "grid": "\n".join(grid), "plates": "\n".join(plates),
       "manifest": json.dumps([{k: w[k] for k in
            ("id", "title", "titleKo", "author", "authorKo", "authorEn", "year",
             "chars", "minutes", "href")} for w in works],
            ensure_ascii=False, separators=(",", ":"))}


# ---------------------------------------------------------------------- main
def main():
    cat = build_catalog()
    works = cat["works"]
    for w in works:
        w["href"] = "%d_%s.html" % (w["year"], re.sub(r'[<>:"/\\|?*]', "", w["title"]))
    manifest = [{k: w[k] for k in ("id", "title", "titleKo", "author", "authorKo",
                                   "authorEn", "year", "chars", "minutes", "href")}
                for w in works]
    if not os.path.isdir(SITE):
        os.makedirs(SITE)

    bad = []
    for w in works:
        src = os.path.join(ROOT, w["file"].replace("/", os.sep))
        try:
            r = bookparse.parse(src)
            body, chapters = sectionise(prepare(r["html"], r["author"]).split("\n"))
            out = page(w, body, chapters, manifest)
            with open(os.path.join(SITE, w["href"]), "wb") as f:
                f.write(out.encode("utf-8"))
            print("ok   %-46s ch=%-3d  %8s bytes" % (w["title"][:46], len(chapters), "{:,}".format(len(out))))
        except Exception as e:
            print("FAIL %-46s %r" % (w["title"][:46], e))
            bad.append((w["title"], repr(e)))

    with open(os.path.join(SITE, "index.html"), "wb") as f:
        f.write(index_page(cat, works).encode("utf-8"))
    print("\nindex.html written")
    print("FAILURES:", len(bad))
    for b in bad:
        print("  ", b)


if __name__ == "__main__":
    main()
