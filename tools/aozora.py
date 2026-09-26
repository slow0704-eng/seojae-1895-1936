# -*- coding: utf-8 -*-
"""Japanese originals from Aozora Bunko (青空文庫).

The English shelf is parsed by bookparse.py, which knows Gutenberg's habits.
Aozora texts follow a different, documented notation (注記), so they get their
own small parser that emits the *same* shape bookparse does — one element per
line, <h2 class="chapter" id="chNNN"> and <p data-p="N"> — and from there the
build treats them like any other book.

    python aozora.py fetch          # download every work in WORKS

Notation handled:
  ｜漢字《かんじ》 / 漢字《かんじ》   ruby            -> <ruby>漢字<rt>かんじ</rt></ruby>
  ［＃「X」に傍点］ ・ 傍線             emphasis        -> <em>X</em>
  ［＃「X」は大/中/小見出し］          headings        -> chapter (part when both 大 and 中 exist)
  any other ［＃…］                    layout notes    -> dropped
  ※［＃…］                             gaiji notes     -> the described character if given, else dropped
Header (title, author, the ----- notation key) and the 底本 colophon are dropped.
"""
from __future__ import annotations
import io, os, re, sys, zipfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# folder -> [(card url, year, romanised file title)]
WORKS = {
    u"유메노": [
        ("https://www.aozora.gr.jp/cards/000096/card935.html", 1936, "Shojo Jigoku"),
        ("https://www.aozora.gr.jp/cards/000096/card2382.html", 1936, "Akuma Kitosho"),
        ("https://www.aozora.gr.jp/cards/000096/card926.html", 1931, "Masayume"),
    ],
    u"아쿠타가와": [
        ("https://www.aozora.gr.jp/cards/000879/card127.html", 1915, "Rashomon"),
        ("https://www.aozora.gr.jp/cards/000879/card60.html", 1918, "Jigokuhen"),
        ("https://www.aozora.gr.jp/cards/000879/card179.html", 1922, "Yabu no Naka"),
    ],
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=90).read()


def fetch():
    for folder, items in WORKS.items():
        d = os.path.join(ROOT, folder)
        os.makedirs(d, exist_ok=True)
        for card, year, name in items:
            page = _get(card).decode("utf-8", "replace")
            m = re.search(r'href="(\./files/[^"]+\.zip)"', page)
            if not m:
                print("FAIL no zip", card); continue
            zurl = card.rsplit("/", 1)[0] + "/" + m.group(1)[2:]
            z = zipfile.ZipFile(io.BytesIO(_get(zurl)))
            txt = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
            text = z.read(txt).decode("cp932", "replace").replace("\r\n", "\n")
            title = re.search(r'<title>[^<]*?([^ <]+)</title>', page)
            out = os.path.join(d, "%d_%s.txt" % (year, name))
            io.open(out, "w", encoding="utf-8", newline="\n").write(text)
            print("ok  ", folder, year, name, len(text))


# ------------------------------------------------------------------ parse
RUBY_BAR = re.compile(r"｜([^《｜\n]+)《([^》\n]+)》")
KANJI = r"[々〆一-鿿豈-﫿㐀-䶿仝〆〇ヶ]"
RUBY_AUTO = re.compile(r"(%s+)《([^》\n]+)》" % KANJI)
RUBY_ANY = re.compile(r"([^\s《》]{1,12}?)《([^》\n]+)》")
NOTE = re.compile(r"［＃([^］]*)］")
GAIJI = re.compile(r"※［＃([^］]*)］")
HEAD = re.compile(r"［＃「([^」]+)」は(大|中|小)見出し］")
HEAD_BLOCK = re.compile(r"［＃(?:ここから)?(大|中|小)見出し］(.+?)［＃(?:ここで)?\1見出し終わり］")
EMPH = re.compile(r"［＃「([^」]+)」に(?:白?[丸三角]?傍点|傍点|傍線|二重傍線|白ゴマ傍点|ばつ傍点)］")


def _strip_frame(text):
    lines = text.split("\n")
    # header: up to and including the second ------ rule of the notation key
    rules = [i for i, l in enumerate(lines[:80]) if re.fullmatch(r"-{20,}", l.strip())]
    start = rules[1] + 1 if len(rules) >= 2 else 0
    if not rules:                       # no key: skip title/author lines up to first blank
        start = next((i for i, l in enumerate(lines) if not l.strip()), 0)
    end = len(lines)
    for i in range(len(lines) - 1, start, -1):
        if lines[i].startswith("底本："):
            end = i; break
    return lines[start:end]


def _inline(s):
    """One source line -> inline HTML (headings already removed)."""
    import html as _h
    # emphasis refers to the text just before the note; wrap the last occurrence
    def emph(line):
        while True:
            m = EMPH.search(line)
            if not m:
                return line
            target, before = m.group(1), line[:m.start()]
            k = before.rfind(target)
            if k < 0:
                line = line[:m.start()] + line[m.end():]
                continue
            line = before[:k] + "\x01" + target + "\x02" + before[k + len(target):] + line[m.end():]
    s = emph(s)
    s = GAIJI.sub(lambda m: (re.search(r"「(.)」", m.group(1)) or [None, ""])[1] if False else "", s)
    s = NOTE.sub("", s)
    s = _h.escape(s, quote=False)
    s = RUBY_BAR.sub(lambda m: "\x03%s\x04%s\x05" % (m.group(1), m.group(2)), s)
    s = RUBY_AUTO.sub(lambda m: "\x03%s\x04%s\x05" % (m.group(1), m.group(2)), s)
    s = RUBY_ANY.sub(lambda m: "\x03%s\x04%s\x05" % (m.group(1), m.group(2)), s)
    s = s.replace("｜", "")
    s = (s.replace("\x01", "<em>").replace("\x02", "</em>")
          .replace("\x03", "<ruby>").replace("\x04", "<rt>").replace("\x05", "</rt></ruby>"))
    return s.strip().lstrip("　")


def parse(path):
    text = io.open(path, encoding="utf-8").read()
    lines = _strip_frame(text)
    heads = []                                      # (index, level, title)
    body = []
    for ln in lines:
        m = HEAD.search(ln) or HEAD_BLOCK.search(ln)
        if m:
            if HEAD.search(ln):
                title, lvl = m.group(1), m.group(2)
            else:
                lvl, title = m.group(1), m.group(2)
            heads.append((len(body), lvl, _inline(title)))
            body.append(None)
            continue
        body.append(ln)
    levels = {l for _, l, _ in heads}
    part_lvl = "大" if ("大" in levels and "中" in levels) else None
    out, n, ch, pt = [], 0, 0, 0
    hmap = {i: (l, t) for i, l, t in heads}
    for i, ln in enumerate(body):
        if ln is None:
            l, t = hmap[i]
            if l == part_lvl:
                pt += 1
                out.append('<h2 class="part" id="pt%02d">%s</h2>' % (pt, t))
            elif l == "小" and ("中" in levels or "大" in levels):
                out.append('<h3 class="subhead">%s</h3>' % t)
            else:
                ch += 1
                out.append('<h2 class="chapter" id="ch%03d">%s</h2>' % (ch, t))
            continue
        s = _inline(ln)
        if not s:
            continue
        n += 1
        out.append('<p data-p="%d">%s</p>' % (n, s))
    title = next((l for l in text.split("\n") if l.strip()), "").strip()
    return {"title": title, "author": "", "html": "\n".join(out)}


if __name__ == "__main__":
    if sys.argv[1:2] == ["fetch"]:
        fetch()
    elif sys.argv[1:2] == ["show"]:
        r = parse(sys.argv[2]); sys.stdout.reconfigure(encoding="utf-8"); print(r["html"][:3000])
