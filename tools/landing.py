# -*- coding: utf-8 -*-
"""Build the front door: ROOT/index.html.

The library is the product; this page is the shopfront. Same constraint as
everything else here — one file, no network, no webfonts, no build step at
runtime. Every number on it is computed from the catalogue, so the page
cannot claim more than the shelf actually holds.
"""
from __future__ import annotations
import os as _os
import io, html

ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
HERE = _os.path.join(ROOT, "tools")
SITE_DIR = chr(49436) + chr(51116)                     # 서재
SITE_HREF = "%EC%84%9C%EC%9E%AC/index.html"            # 서재/index.html, percent-encoded

from jacket import mark, jacket

LCSS = io.open(_os.path.join(HERE, "landing.css"), encoding="utf-8").read()

FAVICON = ("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'"
           "%3E%3Crect%20width='24'%20height='24'%20rx='3'%20fill='%23FAF8F4'/%3E"
           "%3Cg%20fill='none'%20stroke='%238A2E22'%20stroke-width='1.3'%3E"
           "%3Cpath%20d='M6%204.6h12v14.8H6z'/%3E%3Cpath%20d='M12%204.6v14.8'/%3E%3C/g%3E%3C/svg%3E")

# A spread across the five hands and four decades. Anything missing from the
# catalogue is simply dropped, so this list can never break the build.
WALL_A = ["wells-the-time-machine", "kafka-the-metamorphosis", "fitzgerald-the-great-gatsby",
          "wells-the-war-of-the-worlds", "harbou-metropolis", "wells-the-invisible-man",
          "fitzgerald-this-side-of-paradise", "wells-the-island-of-doctor-moreau",
          "kafka-the-trial", "wells-tono-bungay", "fitzgerald-tales-of-the-jazz-age",
          "wells-the-first-men-in-the-moon", "blackwood-the-willows"]
WALL_B = ["kafka-the-castle", "wells-a-modern-utopia", "fitzgerald-the-beautiful-and-damned",
          "wells-ann-veronica", "wells-the-world-set-free", "fitzgerald-all-the-sad-young-men",
          "wells-the-food-of-the-gods", "kafka-poseidon", "wells-kipps",
          "fitzgerald-the-vegetable", "wells-the-sleeper-awakes", "wells-the-dream",
          "blackwood-the-wendigo", "blackwood-john-silence-physician-extraordinary"]

# The reading surface, shown rather than described. Written for this page —
# a type specimen, not an extract.
SPECIMEN = (
    "<p><span class=\"drop\">T</span>he lamp had been trimmed twice already, and still the "
    "page held him. Outside, the last tram let go of the wire and the street went quiet "
    "by degrees, the way a room does when someone stops talking mid-sentence.</p>"
    "<p>He read the paragraph again, not because it was difficult, but because it was "
    "the sort of sentence a person wants to arrive at twice.</p>")

ICONS = {
 "type": '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">'
         '<path d="M5 6h14M12 6v14M8.5 20h7"/><path d="M5 6V4.5h14V6" opacity=".45"/></g>',
 "anchor": '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">'
           '<circle cx="12" cy="5.6" r="2.1"/><path d="M12 7.7V20"/>'
           '<path d="M5 13.4a7 7 0 0 0 14 0"/><path d="M8.6 10.6h6.8" opacity=".45"/></g>',
 "off": '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">'
        '<path d="M12 19.4v.1"/><path d="M8.4 15.6a5 5 0 0 1 7.2 0"/>'
        '<path d="M5 12.1a10 10 0 0 1 14 0" opacity=".45"/><path d="M4 4l16 16"/></g>',
 "sun": '<g fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round">'
        '<circle cx="12" cy="12" r="4"/><path d="M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2'
        'M5.4 5.4l1.6 1.6M17 17l1.6 1.6M18.6 5.4L17 7M7 17l-1.6 1.6"/></g>',
 "leaf": '<g fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round">'
         '<path d="M19 5c0 8-5 13-12 13 0-8 5-13 12-13Z"/><path d="M5 19c3-3 6-5 9-6" opacity=".5"/></g>',
 "moon": '<g fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round">'
         '<path d="M19.2 14.6A8 8 0 0 1 9.4 4.8a8 8 0 1 0 9.8 9.8Z"/></g>',
 "moonf": '<path fill="currentColor" d="M19.2 14.6A8 8 0 0 1 9.4 4.8a8 8 0 1 0 9.8 9.8Z"/>',
 "arrow": '<g fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
          'stroke-linejoin="round"><path d="M4.5 12h14"/><path d="M13 6.5 18.5 12 13 17.5"/></g>',
}
def icon(k, cls=""):
    return '<svg class="%s" viewBox="0 0 24 24" aria-hidden="true" focusable="false">%s</svg>' % (cls, ICONS[k])


def man(n):
    """25,087,817 → '2,509' 만. Korean reads large numbers in 만, not in K/M."""
    return "{:,}".format(int(round(n / 10000.0)))


def hm(minutes):
    return "%d시간 %d분" % (minutes // 60, minutes % 60) if minutes >= 60 else "%d분" % minutes


KEYS = [
    ("Space", "다음 화면 · 두 줄 겹쳐서"), ("← →", "이전 · 다음 장"),
    ("[ ]", "같은 작가의 앞뒤 작품"), ("t", "목차"),
    ("b", "책갈피"), (", ", "설정"),
    ("+ − 0", "글자 크기"), ("&lt; &gt;", "본문 너비"),
    ("d", "테마 전환"), ("w", "작품 전환"),
    ("/", "서재에서 찾기"), ("?", "단축키 전체"),
]


def build_landing(cat, works):
    by_id = {w["id"]: w for w in works}
    tot_words = sum(w["words"] for w in works)
    tot_chars = sum(w["chars"] for w in works)
    tot_min = sum(w["minutes"] for w in works)
    longest = max(works, key=lambda w: w["chars"])
    span = (min(w["year"] for w in works), max(w["year"] for w in works))

    def wall(ids):
        picked = [by_id[i] for i in ids if i in by_id]
        one = "\n".join(jacket(w, cls="jkt", href="%s#/w/%s" % (SITE_HREF, w["id"])) for w in picked)
        return one + "\n" + one          # doubled: the marquee loops on -50%

    facts = [(man(tot_words), "만", "단어"), ("%d" % len(works), "", "편"),
             ("%d" % (tot_min // 60), "", "시간 분량"), ("0", "", "네트워크 요청")]
    facts_h = "\n".join(
        '<div class="fact"><dd>%s%s</dd><dt>%s</dt></div>'
        % (v, ('<i>%s</i>' % u if u else ""), l) for v, u, l in facts)

    auths_h = []
    for a in cat["authors"]:
        ws = sorted([x for x in works if x["author"] == a["slug"]], key=lambda x: x["year"])
        auths_h.append("""<article class="auth" style="--au:var(--%(s)s)">
  %(mark)s
  <h3 class="auth__n">%(en)s</h3>
  <p class="auth__life">%(life)s</p>
  <p class="auth__note">%(note)s</p>
  <p class="auth__ct"><b>%(n)d</b>편 &middot; %(span)s &middot; %(h)d시간</p>
</article>""" % {"s": a["slug"], "mark": mark(a["slug"], "auth__mark"),
                 "en": html.escape(a["en"]), "life": a["life"], "note": html.escape(a["note"]),
                 "n": len(ws), "span": ("%d–%d" % (ws[0]["year"], ws[-1]["year"]))
                 if ws[0]["year"] != ws[-1]["year"] else str(ws[0]["year"]),
                 "h": sum(x["minutes"] for x in ws) // 60})

    keys_h = "\n".join(
        '<div class="key"><span class="key__c">%s</span><span class="key__d">%s</span></div>'
        % ("".join("<kbd>%s</kbd>" % k for k in c.split(" ") if k), d) for c, d in KEYS)

    return """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>서재 %(y0)d—%(y1)d · 퍼블릭 도메인 소설 %(n)d편</title>
<meta name="description" content="카프카 · H. G. 웰스 · F. 스콧 피츠제럴드 · 테아 폰 하르부 · 앨저넌 블랙우드. 퍼블릭 도메인 영문 소설 %(n)d편을 한 페이지에 담은 오프라인 독서 서재. 네트워크 요청 없음.">
<meta name="theme-color" content="#FAF8F4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#191817" media="(prefers-color-scheme: dark)">
<link rel="icon" href="%(fav)s">
<link rel="alternate" href="%(site)s">
<style>%(css)s</style>
<script>
/* pre-paint: honour the theme the reader last chose, before the first frame */
(function(){try{
  var s=JSON.parse(localStorage.getItem("rdr/v1/settings")||"{}");
  if(s.theme) document.documentElement.dataset.theme=s.theme;
}catch(e){}})();
</script>
</head>
<body>
<div class="grain" aria-hidden="true"></div>
<div class="shell">

<header class="nav" id="nav">
  <a class="nav__mark" href="#top"><b>서재</b><span>%(y0)d—%(y1)d</span></a>
  <nav class="nav__links" aria-label="바로가기">
    <a href="#wall">소장작</a><a href="#craft">조판</a><a href="#authors">작가</a><a href="#keys">단축키</a>
  </nav>
  <div class="nav__act">
    <div class="tmg" role="group" aria-label="테마">
      <button data-theme-set="light" aria-label="종이" title="종이">%(i_sun)s</button>
      <button data-theme-set="sepia" aria-label="세피아" title="세피아">%(i_leaf)s</button>
      <button data-theme-set="dark"  aria-label="야간" title="야간">%(i_moon)s</button>
      <button data-theme-set="night" aria-label="심야" title="심야">%(i_moonf)s</button>
    </div>
    <a class="btn btn--pri btn--sm" href="%(site)s">서재 열기</a>
  </div>
</header>

<main id="top">

<section class="hero wrap">
  <p class="kicker hero__kick">개인 서재 &middot; 퍼블릭 도메인</p>
  <h1 class="hero__t">%(y0)d<em>—</em>%(y1)d</h1>
  <p class="hero__roll">Kafka &nbsp;·&nbsp; Wells &nbsp;·&nbsp; Fitzgerald &nbsp;·&nbsp; von Harbou</p>
  <p class="lede hero__lede">한 시대를 통째로 옮겨 둔 책장입니다.
    소설 %(n)d편이 한 페이지 안에 있고, 덮은 자리의 <b>글자</b> 위에 다시 세워 둡니다.
    설치도, 계정도, 네트워크도 필요하지 않습니다.</p>
  <div class="hero__cta">
    <a class="btn btn--pri" href="%(site)s">서재 열기 %(i_arrow)s</a>
    <a class="btn btn--gh" href="#craft">어떻게 만들었나</a>
  </div>
  <dl class="facts">%(facts)s</dl>
</section>

<section class="wall" id="wall" aria-label="소장작">
  <div class="wall__row wall__row--a">%(wall_a)s</div>
  <div class="wall__row wall__row--b">%(wall_b)s</div>
</section>

<section class="sec wrap" id="craft">
  <div class="sec__hd rv">
    <p class="sec__n">01 &nbsp;/&nbsp; 조판</p>
    <h2 class="sec__t">읽는 데 영향을 주는 것만 손봤습니다.</h2>
    <p class="lede">화면에서 %(hours)d시간을 견디는 책은 장식이 아니라 조판으로 만들어집니다.
      아래 세 가지가 이 서재가 다른 이유입니다.</p>
  </div>
  <div class="trio">
    <article class="tile rv">%(i_type)s
      <h3 class="tile__t">한 줄 글자 수가 고정됩니다</h3>
      <p class="tile__d">본문 너비를 <code>ch</code>가 아니라 서체별 실측 평균 자폭으로 계산합니다.
        글자 크기를 15px에서 30px로 키우고 서체를 바꿔도 한 줄에 들어가는 글자 수는 그대로입니다.</p>
      <p class="tile__m">Sitka <b>0.4709em</b> &middot; Constantia 0.4328 &middot; Georgia 0.4390</p>
    </article>
    <article class="tile rv rv-d1">%(i_anchor)s
      <h3 class="tile__t">픽셀이 아니라 글자를 기억합니다</h3>
      <p class="tile__d">읽던 위치를 스크롤 값이 아니라 (문단 번호, 문자 오프셋) 앵커로 저장합니다.
        창 크기·글자 크기·서체를 전부 바꾸고 돌아와도 읽던 그 글자가 같은 자리에 있습니다.</p>
      <p class="tile__m">기준선 화면 <b>18%%</b> &middot; 앞 문맥 두어 줄이 남습니다</p>
    </article>
    <article class="tile rv rv-d2">%(i_off)s
      <h3 class="tile__t">네트워크 요청이 0입니다</h3>
      <p class="tile__d">프레임워크도, CDN도, 웹폰트도, 추적 코드도 없습니다.
        비행기 안에서도, 10년 뒤에도 같은 파일이 같은 방식으로 열립니다.</p>
      <p class="tile__m">본문 <b>%(mchars)s만 자</b> &middot; 파일 %(n)d개 &middot; 의존성 없음</p>
    </article>
  </div>
</section>

<section class="sec spec">
 <div class="wrap spec__grid">
  <div class="rv">
    <div class="sec__hd" style="margin-bottom:26px">
      <p class="sec__n">02 &nbsp;/&nbsp; 본문</p>
      <h2 class="sec__t">인쇄된 책의 대비 대역에 맞췄습니다.</h2>
    </div>
    <div class="dl">
      <div class="dl__row"><span class="dl__k">본문 서체</span><i class="dl__dot"></i><span class="dl__v">Sitka Text</span></div>
      <div class="dl__row"><span class="dl__k">본문 대비</span><i class="dl__dot"></i><span class="dl__v">종이 <b>14.0:1</b> &middot; 심야 8.0:1</span></div>
      <div class="dl__row"><span class="dl__k">테마</span><i class="dl__dot"></i><span class="dl__v">종이 · 세피아 · 야간 · 심야</span></div>
      <div class="dl__row"><span class="dl__k">글자 크기</span><i class="dl__dot"></i><span class="dl__v">15–30px</span></div>
      <div class="dl__row"><span class="dl__k">한 줄 글자 수</span><i class="dl__dot"></i><span class="dl__v">45–92자</span></div>
      <div class="dl__row"><span class="dl__k">가장 긴 작품</span><i class="dl__dot"></i><span class="dl__v">%(longest)s · %(lch)s만 자</span></div>
    </div>
    <p class="spec__note">순백도 순흑도 쓰지 않습니다. 다크 테마의 글자 번짐은 흰색 대신
      난색 회색으로 글자당 발광량을 낮춰서 잡았습니다. 강조색은 사본 채식과 책등의 매더 레드입니다.</p>
  </div>
  <figure class="leaf rv rv-d1">
    <figcaption class="leaf__hd"><span>본문 조판 견본</span><span>Sitka Text · 17px</span></figcaption>
    <div class="leaf__b">%(spec)s</div>
    <div class="leaf__ft"><span>4장</span><i class="leaf__bar"><i></i></i><span>38%% &middot; 남은 2시간 11분</span></div>
  </figure>
 </div>
</section>

<section class="sec wrap" id="authors">
  <div class="sec__hd rv">
    <p class="sec__n">03 &nbsp;/&nbsp; 작가</p>
    <h2 class="sec__t">다섯 사람이 %(yspan)d년을 나눠 씁니다.</h2>
    <p class="lede">한 명은 세기말의 런던에서, 한 명은 프라하의 보험국에서,
      한 명은 재즈 시대의 파티에서, 한 명은 바이마르의 촬영장에서,
      한 명은 캐나다의 숲과 알프스의 눈 속에서 썼습니다.</p>
  </div>
  <div class="auths">%(auths)s</div>
</section>

<section class="sec wrap" id="keys">
  <div class="sec__hd rv">
    <p class="sec__n">04 &nbsp;/&nbsp; 손</p>
    <h2 class="sec__t">읽는 동안 손이 마우스를 찾지 않도록.</h2>
  </div>
  <div class="keys rv">%(keys)s</div>
</section>

<section class="end wrap">
  <h2 class="end__t rv">덮은 자리에서,<br><em>그 글자부터</em> 다시.</h2>
  <p class="lede end__s rv rv-d1">지금 열면 %(n)d편이 전부 그대로 있습니다.
    가입도 결제도 없습니다 — 파일 하나면 됩니다.</p>
  <div class="end__cta rv rv-d2">
    <a class="btn btn--pri" href="%(site)s">서재 열기 %(i_arrow)s</a>
  </div>
  <p class="end__fine rv rv-d2">%(chars)s자 &middot; 약 %(hours)d시간 &middot; 오프라인</p>
</section>

</main>

<footer class="ft">
 <div class="wrap">
  <div class="ft__grid">
    <div>
      <p class="ft__t">서재 %(y0)d—%(y1)d</p>
      <p>퍼블릭 도메인 영문 소설 %(n)d편을 위한<br>오프라인 장시간 독서 사이트.</p>
    </div>
    <div>
      <h4>원문 출처</h4>
      <ul>
        <li><a href="https://www.gutenberg.org">Project Gutenberg</a></li>
        <li><a href="https://standardebooks.org">Standard Ebooks</a></li>
        <li><a href="https://en.wikisource.org">Wikisource</a></li>
      </ul>
    </div>
    <div>
      <h4>저작권</h4>
      <ul>
        <li>Franz Kafka &middot; 1924</li>
        <li>H. G. Wells &middot; 1946</li>
        <li>F. Scott Fitzgerald &middot; 1940</li>
        <li>Thea von Harbou &middot; 1954</li>
      </ul>
    </div>
  </div>
  <div class="ft__bot">
    <span>수록된 작품은 모두 퍼블릭 도메인입니다.</span>
    <span>번역본에는 별도 저작권이 붙기 때문에 영문판에는 구멍이 있습니다.</span>
  </div>
 </div>
</footer>

</div>
<script>
(function(){
  var d=document.documentElement, nav=document.getElementById("nav");

  /* theme — written back into the reader's own settings so the library opens
     in whatever was chosen here */
  function paint(t){
    [].forEach.call(document.querySelectorAll("[data-theme-set]"), function(b){
      b.setAttribute("aria-pressed", b.dataset.themeSet===t ? "true":"false");
    });
  }
  function current(){
    if(d.dataset.theme) return d.dataset.theme;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  paint(current());
  [].forEach.call(document.querySelectorAll("[data-theme-set]"), function(b){
    b.addEventListener("click", function(){
      var t=b.dataset.themeSet; d.dataset.theme=t; paint(t);
      try{
        var s=JSON.parse(localStorage.getItem("rdr/v1/settings")||"{}");
        s.theme=t; s.updated=Date.now();
        localStorage.setItem("rdr/v1/settings", JSON.stringify(s));
      }catch(e){}
    });
  });

  /* hairline under the bar, only once the page has moved */
  var stick=new IntersectionObserver(function(es){
    nav.classList.toggle("is-stuck", !es[0].isIntersecting);
  },{rootMargin:"-1px 0px 0px 0px", threshold:1});
  var probe=document.createElement("div");
  probe.style.cssText="position:absolute;top:0;height:1px;width:1px";
  document.body.appendChild(probe); stick.observe(probe);

  /* reveal on scroll */
  var rv=[].slice.call(document.querySelectorAll(".rv"));
  if(!matchMedia("(prefers-reduced-motion: reduce)").matches && "IntersectionObserver" in window){
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting){ e.target.classList.add("in"); io.unobserve(e.target); } });
    },{rootMargin:"0px 0px -12%% 0px"});
    rv.forEach(function(el){ io.observe(el); });
  } else rv.forEach(function(el){ el.classList.add("in"); });
})();
</script>
</body>
</html>
""" % {"css": LCSS, "fav": FAVICON, "site": SITE_HREF,
       "n": len(works), "y0": span[0], "y1": span[1], "yspan": span[1] - span[0],
       "chars": "{:,}".format(tot_chars), "mchars": man(tot_chars),
       "hours": tot_min // 60, "facts": facts_h,
       "wall_a": wall(WALL_A), "wall_b": wall(WALL_B),
       "auths": "\n".join(auths_h), "keys": keys_h, "spec": SPECIMEN,
       "longest": html.escape(longest["titleKo"]), "lch": man(longest["chars"]),
       "i_sun": icon("sun"), "i_leaf": icon("leaf"), "i_moon": icon("moon"),
       "i_moonf": icon("moonf"), "i_arrow": icon("arrow"),
       "i_type": icon("type", "tile__i"), "i_anchor": icon("anchor", "tile__i"),
       "i_off": icon("off", "tile__i")}


def write(cat, works):
    p = _os.path.join(ROOT, "index.html")
    h = build_landing(cat, works)
    with open(p, "wb") as f:
        f.write(h.encode("utf-8"))
    return len(h)


if __name__ == "__main__":
    from meta import build as build_catalog
    c = build_catalog()
    print("index.html  %s bytes" % "{:,}".format(write(c, c["works"])))
