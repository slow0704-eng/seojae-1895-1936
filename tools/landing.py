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

from jacket import mark, jacket, roll, logo

LCSS = (io.open(_os.path.join(HERE, "landing.css"), encoding="utf-8").read() + "\n" +
        io.open(_os.path.join(HERE, "cover.css"), encoding="utf-8").read())

FAVICON = "data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2048%2048'%3E%3Cstyle%3Eg%7Bstroke:%238A2E22%7D%40media%20%28prefers-color-scheme:dark%29%7Bg%7Bstroke:%23E0906E%7D%7D%3C/style%3E%3Cg%20fill='none'%20stroke-width='3.4'%3E%3Cpath%20d='M8%2022.5H2L24%202L46%2022.5H40'/%3E%3Cpath%20d='M24%202V46'/%3E%3Cpath%20d='M8%2022.5V40.2Q17%2040.6%2024%2046Q31%2040.6%2040%2040.2V22.5'/%3E%3Cpath%20d='M14%2018.2Q20.5%2019.4%2024%2026Q27.5%2019.4%2034%2018.2V36.6Q28.6%2037.2%2024%2041.2Q19.4%2037.2%2014%2036.6Z'/%3E%3C/g%3E%3C/svg%3E"  # the house mark (jacket.LOGO_PATHS), small-size cut without the middle page

# A spread across the eleven hands and four decades. Anything missing from the
# catalogue is simply dropped, so this list can never break the build.
WALL_A = ["wells-the-time-machine", "kafka-the-metamorphosis", "fitzgerald-the-great-gatsby",
          "wells-the-war-of-the-worlds", "harbou-metropolis", "wells-the-invisible-man",
          "fitzgerald-this-side-of-paradise", "wells-the-island-of-doctor-moreau",
          "kafka-the-trial", "wells-tono-bungay", "fitzgerald-tales-of-the-jazz-age",
          "wells-the-first-men-in-the-moon", "blackwood-the-willows",
          "chambers-the-king-in-yellow",
          "machen-the-white-people",
          "andreyev-the-seven-who-were-hanged",
          "jacobs-the-monkey-s-paw",
          "akutagawa-rashomon", "yumeno-shojo-jigoku"]
WALL_B = ["kafka-the-castle", "wells-a-modern-utopia", "fitzgerald-the-beautiful-and-damned",
          "wells-ann-veronica", "wells-the-world-set-free", "fitzgerald-all-the-sad-young-men",
          "wells-the-food-of-the-gods", "kafka-poseidon", "wells-kipps",
          "fitzgerald-the-vegetable", "wells-the-sleeper-awakes", "wells-the-dream",
          "blackwood-the-wendigo", "blackwood-john-silence-physician-extraordinary",
          "chambers-the-slayer-of-souls"]

# The reading surface, shown rather than described. Written for this page —
# a type specimen, not an extract.
SPECIMEN = (
    # the opening of 『타임머신』 as the reader shows it in 대역: original, then ours
    "<p class=\"en\" lang=\"en\">The Time Traveller (for so it will be convenient to speak of him) was "
    "expounding a recondite matter to us. His grey eyes shone and twinkled, and his usually "
    "pale face was flushed and animated.</p>"
    "<p class=\"ko\" lang=\"ko\">시간 여행자는(그렇게 부르는 편이 편할 테니) 우리에게 난해한 문제를 "
    "설명하고 있었다. 잿빛 눈은 빛나며 반짝였고, 평소 창백하던 얼굴은 붉게 달아올라 생기가 돌았다.</p>"
    "<p class=\"en\" lang=\"en\">“You must follow me carefully. I shall have to controvert one or two "
    "ideas that are almost universally accepted.”</p>"
    "<p class=\"ko\" lang=\"ko\">“잘 따라오셔야 합니다. 거의 누구나 받아들이는 생각 한둘을 "
    "반박해야 하니까요.”</p>")

ICONS = {
 "type": '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">'
         '<path d="M5 6h14M12 6v14M8.5 20h7"/><path d="M5 6V4.5h14V6" opacity=".45"/></g>',
 "anchor": '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">'
           '<circle cx="12" cy="5.6" r="2.1"/><path d="M12 7.7V20"/>'
           '<path d="M5 13.4a7 7 0 0 0 14 0"/><path d="M8.6 10.6h6.8" opacity=".45"/></g>',
 "off": '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">'
        '<path d="M12 19.4v.1"/><path d="M8.4 15.6a5 5 0 0 1 7.2 0"/>'
        '<path d="M5 12.1a10 10 0 0 1 14 0" opacity=".45"/><path d="M4 4l16 16"/></g>',
 "pair": '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">'
         '<path d="M3.5 5h7M3.5 9h7M3.5 13h7M3.5 17h5"/><path d="M13.5 5h7M13.5 9h7M13.5 13h7M13.5 17h5" opacity=".5"/></g>',
 "voice": '<g fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">'
         '<path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2"/></g>',
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
<title>모던문고 — %(y0)d–%(y1)d 근대 소설 %(n)d편, 원문과 새 번역으로</title>
<meta name="description" content="모던문고 — %(y0)d–%(y1)d년 근대 소설 %(n)d편을 원문과 새 한국어 번역으로. 카프카 · H. G. 웰스 · F. 스콧 피츠제럴드 · 테아 폰 하르부 · 앨저넌 블랙우드 · 로버트 W. 체임버스 · 아서 마켄 · 레오니트 안드레예프 · W. W. 제이컵스 · 유메노 규사쿠 · 아쿠타가와 류노스케. 원문·한글·대역으로 읽고, 소리 내어 들을 수 있습니다.">
<meta name="theme-color" content="#FAF8F4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#191817" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website">
<meta property="og:site_name" content="모던문고">
<meta property="og:title" content="모던문고 — 원문과 새 번역으로 읽는 근대 소설">
<meta property="og:description" content="1895–1936 근대 소설 %(n)d편. 카프카, 웰스, 피츠제럴드, 아쿠타가와 … 원문과 새 한국어 번역, 대역·낭독.">
<meta property="og:image" content="https://slow0704-eng.github.io/seojae-1895-1936/og.jpg">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="%(fav)s">
<link rel="alternate" href="%(site)s">
<link rel="stylesheet" href="서재/fonts/pretendard/pretendard.css">
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
  <a class="nav__mark" href="#top" aria-label="모던문고 맨 위로">%(logo)s<b>모던문고</b></a>
  <nav class="nav__links" aria-label="바로가기">
    <a href="#wall">책장</a><a href="#craft">읽는 법</a><a href="#authors">작가</a><a href="#keys">단축키</a>
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
  <div class="hero__brand">%(logo_l)s<p class="hero__bw"><b>모던문고</b></p></div>
  <h1 class="hero__t">원문과 새 번역으로 읽는 근대 소설</h1>
  <p class="lede hero__lede">카프카, 피츠제럴드, 아쿠타가와를 비롯한 작가 %(nauth)d명이 %(y0)d년부터 %(y1)d년까지 쓴 소설 %(n)d편.
    모두 새로 옮긴 한국어판이 있어, 원문과 번역을 나란히 놓고 읽을 수 있습니다.</p>
  <div class="hero__cta">
    <a class="btn btn--pri" href="%(site)s">서재 열기</a>
    <a class="btn btn--gh" href="#craft">읽는 법 보기</a>
  </div>
</section>

<section class="wall" id="wall" aria-label="소장작">
  <div class="wall__row wall__row--a">%(wall_a)s</div>
  <div class="wall__row wall__row--b">%(wall_b)s</div>
</section>

<section class="sec wrap" id="craft">
  <div class="sec__hd">
    <h2 class="sec__t">원문과 번역 사이를 오가며 읽습니다.</h2>
    <p class="lede">%(n)d편 전부 이 서재를 위해 새로 옮겼습니다. 읽는 방법은 셋 가운데 고르고, 읽는 도중에도 바꿀 수 있습니다.</p>
  </div>
  <div class="trio">
    <article class="tile">%(i_pair)s
      <h3 class="tile__t">원문, 한글, 대역</h3>
      <p class="tile__d">영어·일본어 원문만, 한국어판만, 또는 문단마다 원문과 번역을 나란히 놓은 대역으로 읽습니다.
        읽던 자리는 그대로 두고 <kbd>l</kbd> 키 하나로 바꿉니다.</p>
    </article>
    <article class="tile">%(i_anchor)s
      <h3 class="tile__t">덮은 자리를 기억합니다</h3>
      <p class="tile__d">읽던 위치를 화면 좌표가 아니라 문단과 글자 단위로 저장합니다.
        글자 크기나 기기를 바꿔도 읽던 그 문장에서 다시 시작합니다.</p>
    </article>
    <article class="tile">%(i_voice)s
      <h3 class="tile__t">소리 내어 읽어 줍니다</h3>
      <p class="tile__d">브라우저 안에서 돌아가는 음성 합성으로 원문과 한국어판을 읽어 줍니다.
        대사는 말하는 인물에 맞춘 목소리로 읽습니다.</p>
    </article>
  </div>
</section>

<section class="sec spec">
 <div class="wrap spec__grid">
  <div>
    <div class="sec__hd" style="margin-bottom:26px">
      <h2 class="sec__t">인쇄된 책의 대비에 맞춰 짰습니다.</h2>
    </div>
    <div class="dl">
      <div class="dl__row"><span class="dl__k">한국어 본문</span><i class="dl__dot"></i><span class="dl__v">Noto Serif KR</span></div>
      <div class="dl__row"><span class="dl__k">원문 본문</span><i class="dl__dot"></i><span class="dl__v">Sitka Text, Source Serif 4</span></div>
      <div class="dl__row"><span class="dl__k">본문 대비</span><i class="dl__dot"></i><span class="dl__v">종이 <b>14.0:1</b> &middot; 심야 8.0:1</span></div>
      <div class="dl__row"><span class="dl__k">테마</span><i class="dl__dot"></i><span class="dl__v">종이, 세피아, 야간, 심야</span></div>
      <div class="dl__row"><span class="dl__k">글자 크기</span><i class="dl__dot"></i><span class="dl__v">15–30px</span></div>
      <div class="dl__row"><span class="dl__k">한 줄 글자 수</span><i class="dl__dot"></i><span class="dl__v">45–92자</span></div>
      <div class="dl__row"><span class="dl__k">가장 긴 작품</span><i class="dl__dot"></i><span class="dl__v">%(longest)s · %(lch)s만 자</span></div>
    </div>
    <p class="spec__note">순백도 순흑도 쓰지 않습니다. 다크 테마의 글자 번짐은 흰색 대신
      난색 회색으로 글자당 발광량을 낮춰서 잡았습니다. 강조색은 사본 채식과 책등의 매더 레드입니다.</p>
  </div>
  <figure class="leaf">
    <figcaption class="leaf__hd"><span>대역 견본 · 『타임머신』 첫머리</span><span>17px</span></figcaption>
    <div class="leaf__b">%(spec)s</div>
    <div class="leaf__ft"><span>1장</span><i class="leaf__bar"><i></i></i><span>38%% &middot; 남은 2시간 11분</span></div>
  </figure>
 </div>
</section>

<section class="sec wrap" id="authors">
  <div class="sec__hd">
    <h2 class="sec__t">열한 사람이 %(yspan)d년을 나눠 씁니다.</h2>
    <p class="lede">한 명은 세기말의 런던에서, 한 명은 프라하의 보험국에서,
      한 명은 재즈 시대의 파티에서, 한 명은 바이마르의 촬영장에서,
      한 명은 캐나다의 숲과 알프스의 눈 속에서, 한 명은 파리의 화실과 뉴욕의 잡지사에서,
      한 명은 웨일스의 언덕을 등진 런던의 하숙방에서,
      한 명은 혁명 전야 페테르부르크의 감옥 곁에서,
      한 명은 템스강 부두의 우체국 창구 뒤에서,
      두 명은 다이쇼와 쇼와의 도쿄에서 썼습니다.</p>
  </div>
  <div class="auths">%(auths)s</div>
</section>

<section class="sec wrap" id="keys">
  <div class="sec__hd">
    <h2 class="sec__t">읽는 동안 손이 마우스를 찾지 않도록.</h2>
  </div>
  <div class="keys">%(keys)s</div>
</section>

<section class="end wrap">
  <h2 class="end__t">덮은 자리에서,<br>그 글자부터 다시.</h2>
  <p class="lede end__s">가입도 결제도 없습니다. 서재를 열면 %(n)d편이 모두 그 자리에 있습니다.</p>
  <div class="end__cta">
    <a class="btn btn--pri" href="%(site)s">서재 열기</a>
  </div>
</section>

</main>

<footer class="ft">
 <div class="wrap">
  <div class="ft__grid">
    <div>
      <p class="ft__t">%(logo)s<b>모던문고</b></p>
      <p>%(y0)d–%(y1)d 근대 소설 %(n)d편을<br>원문과 새 번역으로 읽는 서재.</p>
    </div>
    <div>
      <h2 class="ft__h">원문 출처</h2>
      <ul>
        <li><a href="https://www.gutenberg.org">Project Gutenberg</a></li>
        <li><a href="https://standardebooks.org">Standard Ebooks</a></li>
        <li><a href="https://en.wikisource.org">Wikisource</a></li>
      </ul>
    </div>
    <div>
      <h2 class="ft__h">저작권</h2>
      <ul>
        %(deaths)s
      </ul>
    </div>
  </div>
  <div class="ft__bot">
    <span>수록된 작품은 모두 퍼블릭 도메인입니다.</span>
    <span>한국어판은 이 서재를 위해 새로 옮긴 번역입니다.</span>
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

})();
</script>
</body>
</html>
""" % {"css": LCSS, "fav": FAVICON, "logo": logo("brand__logo", 3, small=True), "logo_l": logo("hero__logo", 1.3), "site": SITE_HREF,
       "n": len(works), "y0": span[0], "y1": span[1], "yspan": span[1] - span[0],
       "chars": "{:,}".format(tot_chars), "mchars": man(tot_chars),
       "hours": tot_min // 60, "facts": facts_h, "nauth": len(cat["authors"]), "roll": roll(cat["authors"]),
       "deaths": "\n        ".join("<li>%s &middot; %s</li>" % (html.escape(a["en"]), a["life"][-4:])
                                   for a in cat["authors"]),
       "i_pair": icon("pair", "tile__i"), "i_voice": icon("voice", "tile__i"), "wall_a": wall(WALL_A), "wall_b": wall(WALL_B),
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
