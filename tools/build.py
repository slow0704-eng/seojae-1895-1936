# -*- coding: utf-8 -*-
"""Build the single-page portal: index.html + data/orig/<id>.js for each work.

fetch() is blocked under file://, but a dynamically appended <script src> is
not — so each book's text ships as a small JS file that calls SEOJAE.receive().
Everything then lives in one document and one origin, which is what makes
localStorage work across the whole library.
"""
from __future__ import annotations
import os as _os
import re, io, json, html

ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
HERE = _os.path.join(ROOT, "tools")
SITE = _os.path.join(ROOT, chr(49436) + chr(51116))          # 소설/서재
DATA = _os.path.join(SITE, "data")
ORIG = _os.path.join(DATA, "orig")   # 원문 본문 (곁 자료는 data/ko · act · yomi)

import bookparse
from meta import build as build_catalog, GENRE_KO

CSS = io.open(_os.path.join(HERE, "reader.css"), encoding="utf-8").read()
IDXCSS = io.open(_os.path.join(HERE, "index.css"), encoding="utf-8").read()
JS = io.open(_os.path.join(HERE, "portal.js"), encoding="utf-8").read()

# 낭독: 정규화·낭독 코드를 포털 IIFE 안에 넣고, 캘리브레이션 값(tools/tts/config.json)을 박습니다.
TTS = _os.path.join(HERE, "tts")
NR_CFG = json.load(io.open(_os.path.join(TTS, "config.json"), encoding="utf-8"))
# 워커·정규화 코드가 바뀌면 주소가 바뀌어 브라우저 캐시가 옛 워커를 쥐고 있지 않게
import hashlib as _hl
NR_CFG["ver"] = _hl.sha1(b"".join(io.open(_os.path.join(TTS, f), "rb").read()
                                  for f in ("worker.js", "normalize.js"))).hexdigest()[:10]
_NARR = io.open(_os.path.join(HERE, "narrate.js"), encoding="utf-8").read().replace(
    "__NR_CFG__", json.dumps(NR_CFG, ensure_ascii=False, separators=(",", ":")))
_NORM = io.open(_os.path.join(TTS, "normalize.js"), encoding="utf-8").read()
# 연기 대본의 대사 세기 — act.py spans() 의 JS 짝을 그대로 넣음
_SPANS = io.open(_os.path.join(HERE, "act", "spans.js"), encoding="utf-8").read()
JS = JS.replace("/* ---------- go ---------- */",
                _NORM + "\nvar TTSNorm = self.TTSNorm;\n" + _SPANS + "\n" + _NARR + "\n/* ---------- go ---------- */", 1)
for _k, _v in (("__VKO__", NR_CFG["voices"]["ko"]), ("__VEN__", NR_CFG["voices"]["en"]), ("__VJA__", NR_CFG["voices"]["ja"])):
    JS = JS.replace(_k, _v)


def write_tts():
    """서재/tts/ — 워커와 작은 자산. 큰 ONNX 는 config 의 고정 리비전 URL 에서 받습니다."""
    out = _os.path.join(SITE, "tts")
    if not _os.path.isdir(out):
        _os.makedirs(out)
    w = io.open(_os.path.join(TTS, "worker.js"), encoding="utf-8").read()
    w = w.replace('import "./normalize.js";', 'import "./normalize.js?v=%s";' % NR_CFG["ver"])
    for name, body in (("worker.js", w), ("normalize.js", _NORM)):
        with open(_os.path.join(out, name), "wb") as f:
            f.write(body.encode("utf-8"))

from jacket import mark, title_split, len_bucket, FORM_KO, roll
import landing

HEAD_RX = re.compile(r'^<h2 class="(chapter|part)" id="([^"]+)"[^>]*>(.*)</h2>$')
P_RX = re.compile(r'^<p[^>]*data-p="(\d+)"')
TAG_RX = re.compile(r"<[^>]+>")


def strip_tags(s):
    return html.unescape(TAG_RX.sub("", s))


def prepare(html_str, author):
    """Drop the parser's title/byline (the portal renders its own title page)
    and renumber data-p from 0, so a paragraph's data-p is its index in the
    runtime's paragraph array — the cumulative-character table is indexed by
    position and any gap would offset every saved reading position."""
    out, dropped_byline = [], False
    for ln in html_str.split("\n"):
        if ln.startswith('<h1 class="worktitle"'):
            continue
        if not dropped_byline and P_RX.match(ln):
            dropped_byline = True
            if strip_tags(ln).strip().rstrip(".") == (author or "\0").strip():
                continue
        out.append(ln)
    n = [0]

    def renum(m):
        s = m.group(0).replace(m.group(1), str(n[0]))
        n[0] += 1
        return s
    return re.sub(r'data-p="(\d+)"', renum, "\n".join(out))


def sectionise(lines):
    """Split the flat element list into <section class="ch"> units (the
    content-visibility unit) and collect the chapter table."""
    secs, cur, chapters = [], [], []
    pending = None

    def flush():
        if not cur:
            return
        chars = sum(len(strip_tags(l)) for l in cur if P_RX.match(l))
        firstp = next((int(P_RX.match(l).group(1)) for l in cur if P_RX.match(l)), None)
        secs.append({"lines": list(cur), "chars": chars, "firstp": firstp, "head": pending})
        del cur[:]

    for ln in lines:
        m = HEAD_RX.match(ln)
        if m:
            flush()
            pending = {"kind": m.group(1), "id": m.group(2), "label": strip_tags(m.group(3))}
        cur.append(ln)
    flush()

    out = []
    for i, s in enumerate(secs):
        h = s["head"]
        if h and s["firstp"] is not None:
            # the id is what the Korean payload keys its heading translations by
            chapters.append({"firstP": s["firstp"], "label": h["label"], "title": "",
                             "kind": h["kind"], "hid": h["id"]})
        est = max(300, int(s["chars"] * 1.25) + 220)
        out.append('<section class="ch" id="sec%d" style="contain-intrinsic-size:auto %dpx">\n%s\n</section>'
                   % (i, est, "\n".join(s["lines"])))
    return "\n".join(out), chapters


def sig(text):
    h = 0x811c9dc5
    for ch in text:
        h ^= ord(ch) & 0xFF
        h = (h * 0x01000193) & 0xFFFFFFFF
    return "%08x" % h


# ---------------------------------------------------------------- index page
DECADE = lambda y: min(1930, (y // 10) * 10)


def man(n):
    """Bulk, the way Korean actually reads it: 만 units, one decimal under 100만."""
    if n < 10000:
        return "{:,}자".format(n)
    v = n / 10000.0
    return ("%.1f만 자" % v).replace(".0만", "만") if v < 100 else "{:,}만 자".format(round(v))


ORIG_KO = {"en": "영문", "ja": "일본어"}   # what the original-language button says
FACET_KO = {"author": "작가", "genre": "장르", "decade": "연대", "form": "형식", "size": "분량",
            "state": "상태", "lang": "언어"}


def cover(w, i):
    """A card is: the board, then the shelf label under it.

    The runtime owns .cap (it appends a bookmark count) and .cap__pct, and it
    sorts on the data-* here — see the contract in portal.js. Everything else
    on the card is free."""
    main, sub = title_split(w["title"])
    subh = '<span class="sub">%s</span>' % html.escape(sub) if sub else ""
    mins = w["minutes"]
    return """<article class="card" data-author="%(a)s" data-decade="%(d)d" data-len="%(len)s"
 data-year="%(y)d" data-id="%(id)s" data-title="%(tl)s" data-ko="%(ko)s" data-mins="%(mins)d"
 data-form="%(formk)s" style="--i:%(i)d">
<a class="card__link" href="#/w/%(idq)s">
 <div class="cover"><i class="cover__frame"></i>%(mark)s<i class="rule rule--head"></i>
  <h3 class="cover__title">%(main)s%(sub)s</h3>
  <i class="rule rule--foot"></i>
  <p class="cover__author">%(auth)s</p><p class="cover__year">%(y)d</p>
  <span class="cover__ko" hidden></span></div>
 <div class="mt">
  <p class="mt__ko">%(ko)s</p>
  <p class="openas" hidden><span class="openas__l">열기</span><span data-open="en">%(origlab)s</span><span data-open="ko">한글</span><span data-open="both">대역</span></p>
  <p class="mt__by"><span class="form">%(form)s</span><span>%(authko)s</span></p>
  <p class="cap"><span class="cap__pct"></span><span>%(chars)s</span><b>&middot;</b><span>%(time)s</span></p>
 </div>
</a></article>""" % {
        "a": w["author"], "d": DECADE(w["year"]), "len": len_bucket(main), "y": w["year"],
        "id": html.escape(w["id"]), "idq": html.escape(w["id"]), "i": i,
        "tl": html.escape(w["title"]), "ko": html.escape(w["titleKo"]), "mins": mins,
        "formk": w.get("form", "novel"),
        "mark": mark(w["author"], "cover__mark"), "main": html.escape(main), "sub": subh,
        "auth": html.escape(w["authorEn"]), "authko": html.escape(w["authorKo"]),
        "form": FORM_KO.get(w.get("form", "novel"), "장편"), "chars": man(w["chars"]),
        "origlab": ORIG_KO.get(w.get("orig", "en"), "원문"),
        "time": ("%d시간 %d분" % (mins // 60, mins % 60)) if mins >= 60 else ("%d분" % mins)}


READER_SHELL = """
<div id="reader">
  <div id="hud-top" class="hud">
    <button class="hbtn" data-act="lib">&lsaquo; 서재</button>
    <span class="h-title"></span><span class="h-ch"></span>
    <span class="h-right">
      <span class="lseg lseg--hud" data-act="lang" role="group" aria-label="본문 언어 (l)"><button data-lang="en">영문</button><button data-lang="ko">한글</button><button data-lang="both">대역</button></span>
      <button class="hbtn hbtn--read" data-act="read" title="낭독 (r)">듣기</button>
      <button class="hbtn hbtn--auto" data-act="auto" title="자동 스크롤 (a)">자동</button>
      <button class="hbtn" data-act="toc">목차</button>
      <button class="hbtn" data-act="bm">책갈피</button>
      <button class="hbtn" data-act="set">설정</button>
    </span>
  </div>
  <div id="hud-bot" class="hud"><span class="h-pct"></span><span class="h-rem"></span><span class="h-sess"></span></div>
  <div id="folio" aria-hidden="true"></div>
  <div id="asctl" role="group" aria-label="자동 스크롤 속도"><button data-as="-1" aria-label="느리게">&minus;</button><span class="as-v"></span><button data-as="1" aria-label="빠르게">+</button><button data-as="stop" class="as-stop" aria-label="자동 스크롤 멈춤">&#9632;</button></div>
  <div id="nrbar" role="group" aria-label="낭독" hidden>
    <button data-nr="prev" aria-label="앞 문장"><svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 4v12M16 4.5v11L7.5 10z" fill="currentColor" stroke="currentColor" stroke-width="1.6"/></svg></button>
    <button data-nr="play" class="nr-play" aria-label="일시정지"></button>
    <button data-nr="next" aria-label="다음 문장"><svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M15 4v12M4 4.5v11l8.5-5.5z" fill="currentColor" stroke="currentColor" stroke-width="1.6"/></svg></button>
    <span class="nr-st" aria-live="polite"></span><span class="nr-eng"></span>
    <button data-nr="follow" class="nr-follow" hidden>읽는 곳으로</button>
    <button data-nr="rate" class="nr-rate" aria-label="낭독 속도">×1</button>
    <button data-nr="sleep" class="nr-sleep" aria-label="잠자기 타이머"></button>
    <button data-nr="more" aria-label="낭독 설정"><svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><circle cx="4.5" cy="10" r="1.5" fill="currentColor"/><circle cx="10" cy="10" r="1.5" fill="currentColor"/><circle cx="15.5" cy="10" r="1.5" fill="currentColor"/></svg></button>
    <button data-nr="stop" class="nr-stop" aria-label="낭독 끝">&#9632;</button>
  </div>
  <div id="langsw" class="lseg lseg--float" role="group" aria-label="본문 언어" hidden><button data-lang="en">영문</button><button data-lang="ko">한글</button><button data-lang="both">대역</button></div>
  <div id="hairline"><div id="hair-fill"></div><div id="hair-ticks"></div></div>
  <article id="book" lang="en"></article>
</div>

<div id="scrim"></div>
<aside id="drawer">
  <div class="dw-tabs"><button data-tab="toc" class="on">목차</button><button data-tab="bm">책갈피</button><button class="dw-x" title="닫기">✕</button></div>
  <input class="dw-filter" placeholder="장 제목 검색" hidden>
  <div class="dw-body"></div>
</aside>
<aside id="settings">
  <div class="st-hd">설정<button class="st-x">✕</button></div>
  <div class="st-body">
    <div class="st-grp">활자</div>
    <div class="st-row"><span class="st-l">글자 크기</span><span class="st-c"><input type="range" data-k="fs" min="15" max="30" step="1"><span class="v" data-v="fs"></span></span></div>
    <div class="st-row"><span class="st-l">줄 간격</span><span class="st-c"><input type="range" data-k="lh" min="1.30" max="2.10" step="0.02"><span class="v" data-v="lh"></span></span></div>
    <div class="st-row"><span class="st-l">본문 너비</span><span class="st-c"><input type="range" data-k="measure" min="45" max="92" step="1"><span class="v" data-v="measure"></span></span></div>
    <div class="st-row"><span class="st-l">글꼴</span><span class="st-c"><span class="st-seg" data-k="font"><button data-seg="1">시트카</button><button data-seg="2">콘스탄시아</button><button data-seg="3">조지아</button><button data-seg="4">산세리프</button></span></span></div>
    <div class="st-row"><span class="st-l">양쪽 정렬</span><span class="st-c"><button class="st-tog" data-tog="justify"><i></i></button></span></div>
    <div class="st-row"><span class="st-l">첫 줄 들여쓰기</span><span class="st-c"><button class="st-tog" data-tog="indent"><i></i></button></span></div>
    <div class="st-grp">화면</div>
    <div class="st-row"><span class="st-l">테마</span><span class="st-c"><span class="st-seg" data-k="theme"><button data-seg="light">종이</button><button data-seg="sepia">세피아</button><button data-seg="dark">야간</button><button data-seg="night">심야</button></span></span></div>
    <div class="st-row"><span class="st-l">화면 어둡기</span><span class="st-c"><input type="range" data-k="dim" min="0" max="55" step="5"><span class="v" data-v="dim"></span></span></div>
    <div class="st-row"><span class="st-l">자동 스크롤 속도</span><span class="st-c"><input type="range" data-k="asLpm" min="2" max="60" step="1"><span class="v" data-v="asLpm"></span></span></div>
    <div class="st-row"><span class="st-l">화면 켜두기</span><span class="st-c"><button class="st-tog" data-tog="wake"><i></i></button></span></div>
    <div class="st-grp">언어</div>
    <div class="st-row"><span class="st-l">본문 언어</span><span class="st-c"><span class="st-seg" data-k="lang"><button data-seg="en">원문</button><button data-seg="ko">한글</button><button data-seg="both">대역</button></span></span></div>
    <div class="st-row"><span class="st-l">대역 원문 크기</span><span class="st-c"><input type="range" data-k="trScale" min="70" max="100" step="5"><span class="v" data-v="trScale"></span></span></div>
    <div class="st-row"><span class="st-l">미번역 문단 표시</span><span class="st-c"><button class="st-tog" data-tog="markUntr"><i></i></button></span></div>
    <div class="st-grp">낭독</div>
    <div class="st-row"><span class="st-l">음성</span><span class="st-c"><span class="st-seg" data-k="nrEngine"><button data-seg="auto">고품질</button><button data-seg="system">기기 음성</button></span></span></div>
    <div class="st-row"><span class="st-l">속도</span><span class="st-c"><span class="st-seg st-seg--tight" data-k="nrRate">%(rates)s</span></span></div>
    <div class="st-row"><span class="st-l">한국어 목소리</span><span class="st-c"><select data-k="nrVoiceKo">%(vopts)s</select></span></div>
    <div class="st-row"><span class="st-l">영어 목소리</span><span class="st-c"><select data-k="nrVoiceEn">%(vopts)s</select></span></div>
    <div class="st-row"><span class="st-l">일본어 목소리</span><span class="st-c"><select data-k="nrVoiceJa">%(vopts)s</select></span></div>
    <div class="st-row"><span class="st-l">목소리 연기</span><span class="st-c"><button class="st-tog" data-tog="nrAct"><i></i></button></span></div>
    <div class="st-row"><span class="st-l">미리 듣기</span><span class="st-c"><button class="mini" data-do="nrpreview">들어 보기</button></span></div>
    <div class="st-row"><span class="st-l">음량</span><span class="st-c"><input type="range" data-k="nrVol" min="40" max="140" step="5"><span class="v" data-v="nrVol"></span></span></div>
    <div class="st-row"><span class="st-l">방 울림</span><span class="st-c"><button class="st-tog" data-tog="nrRoom"><i></i></button></span></div>
    <div class="st-row"><span class="st-l">배경 소리</span><span class="st-c"><span class="st-seg" data-k="nrAmb"><button data-seg="off">없음</button><button data-seg="rain">빗소리</button><button data-seg="fire">벽난로</button><button data-seg="room">서재</button></span></span></div>
    <div class="st-row"><span class="st-l">배경 음량</span><span class="st-c"><input type="range" data-k="nrAmbVol" min="-40" max="-8" step="2"><span class="v" data-v="nrAmbVol"></span></span></div>
    <div class="st-row"><span class="st-l">대역에서 읽을 말</span><span class="st-c"><span class="st-seg" data-k="nrBoth"><button data-seg="ko">한글</button><button data-seg="orig">원문</button></span></span></div>
    <div class="st-row"><span class="st-l">음성 모델</span><span class="st-c"><button class="mini" data-do="nrclear">기기에서 지우기</button></span></div>
    <div class="st-grp">표시</div>
    <div class="st-row"><span class="st-l">남은 시간 표시</span><span class="st-c"><button class="st-tog" data-tog="showRemaining"><i></i></button></span></div>
    <div class="st-row"><span class="st-l">세션 시간 표시</span><span class="st-c"><button class="st-tog" data-tog="showSession"><i></i></button></span></div>
    <div class="st-row"><span class="st-l">쪽수 항상 표시</span><span class="st-c"><button class="st-tog" data-tog="showFolio"><i></i></button></span></div>
    <div class="st-grp">자료</div>
    <div class="st-row"><span class="st-l">읽기 속도</span><span class="st-c"><span class="v" data-v="wpm"></span><button class="mini" data-do="wpmreset">초기화</button></span></div>
    <div class="st-row"><span class="st-l">내보내기</span><span class="st-c"><button class="mini" data-do="export">저장</button></span></div>
    <div class="st-row"><span class="st-l">가져오기</span><span class="st-c"><label class="mini">파일 선택<input type="file" accept="application/json" hidden data-do="import"></label></span></div>
    <div class="st-grp">초기화</div>
    <div class="st-row"><span class="st-l">모두 기본값으로</span><span class="st-c"><button class="mini" data-do="reset">되돌리기</button></span></div>
  </div>
</aside>
<div id="palette"><div class="pl-box"><input class="pl-q" placeholder="작품 또는 작가 검색"><div class="pl-list"></div></div></div>
"""
READER_SHELL = READER_SHELL.replace("%(rates)s", "".join(
    '<button data-seg="%g">%s</button>' % (r, ("%g" % r)) for r in NR_CFG["rates"])).replace("%(vopts)s", "".join(
    '<option value="%s">%s</option>' % (v, ("여성 " if v[0] == "F" else "남성 ") + v[1]) for v in
    ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]))



def index_page(cat, works):
    tot_chars = sum(w["chars"] for w in works)
    tot_min = sum(w["minutes"] for w in works)
    by_dec = {}
    for w in sorted(works, key=lambda x: (x["year"], x["authorEn"], x["title"])):
        by_dec.setdefault(DECADE(w["year"]), []).append(w)
    grid, i = [], 0
    for d in sorted(by_dec):
        grid.append('<div class="era" data-decade="%d" role="separator"><span class="era__n">%d</span>'
                    '<span class="era__lab">년대</span><i class="era__line"></i>'
                    '<span class="era__ct">%d편</span></div>' % (d, d, len(by_dec[d])))
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

    manifest = [dict({k: w[k] for k in ("id", "title", "titleKo", "author", "authorKo",
                                        "authorEn", "year", "chars", "minutes", "words")},
                     titleOrig=w.get("titleOrig", ""), form=w.get("form", "novel"),
                     genre=w.get("genre", ""),
                     orig=w.get("orig", "en"))
                for w in works]

    # ---- facet chips -------------------------------------------------------
    def chips(facet, items):
        return ('<div class="facet" data-facet="%s"><span class="facet__l">%s</span>%s</div>'
                % (facet, FACET_KO[facet],
                   "".join('<button class="chip" data-v="%s">%s<span class="chip__n">%s</span></button>'
                           % (v, html.escape(lab), n) for v, lab, n in items)))

    auth_ct = {}
    form_ct = {}
    dec_ct = {}
    for w in works:
        auth_ct[w["author"]] = auth_ct.get(w["author"], 0) + 1
        form_ct[w.get("form", "novel")] = form_ct.get(w.get("form", "novel"), 0) + 1
        dec_ct[DECADE(w["year"])] = dec_ct.get(DECADE(w["year"]), 0) + 1
    a_ko = {a["slug"]: a["ko"] for a in cat["authors"]}
    # the same author facet, always in view: one tap narrows the shelf to one hand
    aubar = ('<div class="aubar" id="aubar" role="group" aria-label="작가별로 보기">'
             '<button class="aub" data-v="">전체<span class="aub__n">%d</span></button>%s</div>'
             % (len(works), "".join(
                 '<button class="aub" data-v="%s" data-author="%s">%s%s<span class="aub__n">%d</span></button>'
                 % (a["slug"], a["slug"], mark(a["slug"], "aub__mark"), html.escape(a["ko"]),
                    auth_ct.get(a["slug"], 0))
                 for a in cat["authors"] if auth_ct.get(a["slug"]))))
    # 장르도 늘 보이게 — 작가 막대 밑 한 줄, 한 번에 한 장르
    gen_ct = {}
    for w in works:
        gen_ct[w.get("genre")] = gen_ct.get(w.get("genre"), 0) + 1
    aubar += ('<div class="aubar genbar" id="genbar" role="group" aria-label="장르별로 보기">'
              '<button class="aub" data-v="">전체 장르</button>%s</div>'
              % "".join('<button class="aub" data-v="%s">%s<span class="aub__n">%d</span></button>'
                        % (g, html.escape(GENRE_KO[g]), gen_ct[g]) for g in GENRE_KO if gen_ct.get(g)))
    facets = "\n".join([
        chips("author", [(s, a_ko[s], auth_ct[s]) for s in
                         sorted(auth_ct, key=lambda s: -auth_ct[s])]),
        chips("genre", [(g, GENRE_KO[g], sum(1 for w in works if w.get("genre") == g))
                        for g in GENRE_KO if any(w.get("genre") == g for w in works)]),
        chips("decade", [(str(d), "%d년대" % d, dec_ct[d]) for d in sorted(dec_ct)]),
        chips("form", [(f, FORM_KO.get(f, f), form_ct[f]) for f in
                       sorted(form_ct, key=lambda f: -form_ct[f])]),
        chips("size", [("short", "3시간 이내", sum(1 for w in works if w["minutes"] < 180)),
                       ("mid", "3–8시간", sum(1 for w in works if 180 <= w["minutes"] < 480)),
                       ("long", "8시간 이상", sum(1 for w in works if w["minutes"] >= 480))]),
        chips("state", [("unread", "안 읽음", ""), ("reading", "읽는 중", ""),
                        ("done", "완독", ""), ("marked", "책갈피 있음", "")]),
        chips("lang", [("ko", "한글본 있음", ""), ("kofull", "완역", ""), ("enonly", "원문만", "")]),
    ])

    authnav = "".join(
        '<button class="authnav__b" data-go="%s">%s<span>%d</span></button>'
        % (a["slug"], html.escape(a["ko"]), auth_ct.get(a["slug"], 0)) for a in cat["authors"])

    return """<!doctype html>
<html lang="ko" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>서재 1895—1936</title>
<meta name="description" content="퍼블릭 도메인 소설 %(n)d편을 위한 오프라인 독서 사이트. 카프카 · H. G. 웰스 · F. 스콧 피츠제럴드 · 테아 폰 하르부 · 앨저넌 블랙우드 · 로버트 W. 체임버스 · 아서 마켄 · 레오니트 안드레예프 · W. W. 제이컵스 · 유메노 규사쿠 · 아쿠타가와 류노스케.">
<meta name="theme-color" content="#FAF8F4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#191817" media="(prefers-color-scheme: dark)">
<link rel="icon" href="%(fav)s">
<style>%(css)s
%(icss)s</style>
<script>
/* pre-paint: apply stored typography before the first frame */
(function(){try{
var s=JSON.parse(localStorage.getItem("rdr/v1/settings")||"{}");var r=document.documentElement;
var fs=s.fs||20,lh=s.lh||1.72,me=s.measure||68;
r.style.setProperty("--fs-num",fs);r.style.setProperty("--fs",fs+"px");
r.style.setProperty("--lh",(lh-(fs-20)*0.007).toFixed(3));
r.style.setProperty("--track",((20-fs)*0.0018).toFixed(4)+"em");
r.style.setProperty("--cpl",me);
r.dataset.theme=s.theme||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
r.dataset.font=s.font||"1";r.dataset.justify=s.justify?"on":"off";
r.dataset.indent=(s.indent===false)?"off":"on";
}catch(e){}})();
</script>
</head>
<body data-view="library">
<div id="dimmer"></div>

<div id="library">
<div class="topbar"><div class="topbar__in">
  <a class="topbar__home" href="../index.html"><b>서재</b><span>1895—1936</span></a>
  <span class="topbar__hint"><kbd>/</kbd> 찾기 &nbsp; <kbd>Enter</kbd> 이어읽기 &nbsp; <kbd>?</kbd> 단축키</span>
</div></div>
<div class="wrap">
<header class="masthead">
  <p class="mh__kicker">개인 서재</p>
  <h1 class="mh__title">1895<em>—</em>1936</h1>
  <p class="mh__roll">%(roll)s</p>
  <i class="rule mh__rule"></i>
  <p class="mh__stat">%(n)d편 &nbsp;·&nbsp; %(nauth)d인 &nbsp;·&nbsp; %(mchars)s &nbsp;·&nbsp; 약 %(hours)d시간<span class="mh__mine" id="mine"></span></p>
</header>
<section class="now" id="now" hidden><h2 class="now__h">읽는&nbsp;중</h2><ul class="now__list" id="nowlist"></ul></section>
<nav class="ctl">
  <div class="ctl__sort" role="tablist">
    <button role="tab" data-sort="era" aria-selected="true">연대순</button>
    <button role="tab" data-sort="author">저자별</button>
    <button role="tab" data-sort="title">제목순</button>
    <button role="tab" data-sort="len">길이순</button>
    <button role="tab" data-sort="recent">최근순</button>
  </div>
  <span class="ctl__search">
    <input class="ctl__find" type="search" id="find" placeholder="제목 · 작가 · 연도 · ㅊㅅ" aria-label="찾기"
           autocomplete="off" spellcheck="false">
    <span class="ctl__hint" id="findhint"></span>
  </span>
  <button class="ctl__facet" id="facetbtn" aria-expanded="false">거르기<span class="ctl__facetn" hidden></span></button>
  <span class="ctl__count" id="count"></span>
  <select class="ctl__theme" id="theme" aria-label="테마">
    <option value="light">종이</option><option value="sepia">세피아</option>
    <option value="dark">야간</option><option value="night">심야</option>
  </select>
  %(aubar)s
</nav>
<div class="facets" id="facets" hidden>%(facets)s
  <button class="facet__clear" id="facetclear">모두 해제</button>
</div>
<div class="sugg" id="sugg" hidden></div>
<main class="grid" id="grid">%(grid)s</main>
<div class="grid" id="grid-author" hidden><nav class="authnav" id="authnav">%(authnav)s</nav>%(plates)s</div>
<footer class="lib-foot">
  <p>모든 작품은 퍼블릭 도메인입니다. 출처 — <a href="https://www.gutenberg.org">Project Gutenberg</a>
     &middot; <a href="https://standardebooks.org">Standard Ebooks</a>
     &middot; <a href="https://en.wikisource.org">Wikisource</a></p>
  <p class="lib-foot__k"><kbd>/</kbd> 찾기 &nbsp; <kbd>Enter</kbd> 이어읽기 &nbsp; <kbd>1</kbd>–<kbd>4</kbd> 정렬 &nbsp; <kbd>?</kbd> 단축키</p>
</footer>
</div></div>
%(shell)s
<script>var MANIFEST=%(manifest)s;
var SEOJAE={ko:{},koIndex:function(m){SEOJAE.ko=m||{};}};</script>
<script src="data/ko/index.js" onerror="void 0"></script>
<script>%(js)s</script>
</body>
</html>
""" % {"css": CSS, "icss": IDXCSS, "js": JS, "shell": READER_SHELL,
       "fav": landing.FAVICON,
       "n": len(works), "mchars": man(tot_chars), "hours": tot_min // 60,
       "roll": roll(cat["authors"]), "nauth": len(cat["authors"]),
       "grid": "\n".join(grid), "plates": "\n".join(plates),
       "facets": facets, "authnav": authnav, "aubar": aubar,
       "manifest": json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))}


# ---------------------------------------------------------------------- main
def main():
    cat = build_catalog()
    works = cat["works"]
    for d in (SITE, DATA, ORIG):
        if not _os.path.isdir(d):
            _os.makedirs(d)
    # the portal replaces the old one-file-per-work site
    for f in _os.listdir(SITE):
        if f.endswith(".html") and f != "index.html":
            _os.remove(_os.path.join(SITE, f))

    bad, total = [], 0
    for w in works:
        src = _os.path.join(ROOT, w["file"].replace("/", _os.sep))
        try:
            if w.get("orig") == "ja":
                import aozora
                r = aozora.parse(src)
            else:
                r = bookparse.parse(src)
            body, chapters = sectionise(prepare(r["html"], r["author"]).split("\n"))
            payload = {"id": w["id"], "sig": sig("%d:%s" % (len(chapters), body[:200] + body[-200:])),
                       "chapters": chapters, "html": body}
            js = "SEOJAE.receive(" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ");\n"
            p = _os.path.join(ORIG, w["id"] + ".js")
            with open(p, "wb") as f:
                f.write(js.encode("utf-8"))
            total += len(js)
            print("ok   %-46s ch=%-3d %9s bytes" % (w["title"][:46], len(chapters), "{:,}".format(len(js))))
        except Exception as e:
            print("FAIL %-46s %r" % (w["title"][:46], e))
            bad.append((w["title"], repr(e)))

    # the Korean coverage index is a separate script so growing the translation
    # does not mean rebuilding the portal
    import translate
    translate.write_index()
    import fonts
    fonts.build()
    write_tts()

    idx = index_page(cat, works)
    with open(_os.path.join(SITE, "index.html"), "wb") as f:
        f.write(idx.encode("utf-8"))
    print("\n서재/index.html  %s bytes" % "{:,}".format(len(idx)))
    print("index.html      %s bytes  (front door)" % "{:,}".format(landing.write(cat, works)))
    print("data/orig/  %s bytes across %d files" % ("{:,}".format(total), len(works) - len(bad)))
    print("FAILURES:", len(bad))
    for b in bad:
        print("  ", b)


if __name__ == "__main__":
    main()
