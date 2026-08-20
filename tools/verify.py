# -*- coding: utf-8 -*-
"""Invariant checks over the 60 built pages."""
import io, os, re, json, sys, unicodedata

import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
SITE = _os.path.join(ROOT, chr(49436) + chr(51116))

P_RX = re.compile(r'<p[^>]*data-p="(\d+)"[^>]*>(.*?)</p>', re.S)
TAG = re.compile(r"<[^>]+>")
import html as H

def alnum(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if c.isalnum())

SRC = {}
for d in os.listdir(ROOT):
    dp = os.path.join(ROOT, d)
    if os.path.isdir(dp) and d != chr(49436) + chr(51116):
        for fn in os.listdir(dp):
            if fn.endswith(".txt") and not fn.startswith("00_"):
                SRC[fn[:-4]] = os.path.join(dp, fn)

fails, warns = [], []
files = sorted(f for f in os.listdir(SITE) if f.endswith(".html") and f != "index.html")
print("pages:", len(files))
hdr = "%-46s %6s %5s %6s %9s  %s" % ("work", "paras", "ch", "secs", "chars", "checks")
print(hdr); print("-" * len(hdr))

for f in files:
    t = io.open(os.path.join(SITE, f), encoding="utf-8").read()
    bad = []

    m = re.search(r"^var WORK=(\{.*?\});$", t, re.M)
    if not m:
        fails.append((f, "no WORK")); print("FAIL", f, "no WORK"); continue
    W = json.loads(m.group(1))
    mm = re.search(r"^var MANIFEST=(\[.*?\]);$", t, re.M)
    MAN = json.loads(mm.group(1)) if mm else []
    if len(MAN) != 60: bad.append("manifest=%d" % len(MAN))

    body = t[t.index('<article id="book"'):t.index("</article>")]
    ps = P_RX.findall(body)
    idx = [int(a) for a, _ in ps]
    if idx != list(range(len(idx))): bad.append("data-p not 0..n contiguous")

    secs = body.count('<section class="ch"')
    if secs != body.count("</section>"): bad.append("section mismatch")

    chars = sum(len(H.unescape(TAG.sub("", b))) for _, b in ps)

    chaps = W.get("chapters", [])
    for c in chaps:
        if not (0 <= c["firstP"] < len(idx)): bad.append("firstP OOR %s" % c["firstP"])
    fp = [c["firstP"] for c in chaps]
    if fp != sorted(fp): bad.append("chapters unordered")

    # nesting sanity: every <blockquote>/<div class="letter"> closed
    for tag in ("blockquote", "div"):
        o = len(re.findall(r"<%s[ >]" % tag, body)); c2 = body.count("</%s>" % tag)
        if o != c2: bad.append("%s %d/%d" % (tag, o, c2))

    # leftover source markup that should have been converted
    txt = " ".join(H.unescape(TAG.sub("", b)) for _, b in ps)
    if re.search(r"(?<![A-Za-z0-9])_[A-Za-z]", txt): bad.append("stray _italic_")
    if ". . ." in txt: bad.append("unfolded ellipsis")
    if "--" in txt: bad.append("unconverted --")
    if "<pre" in body or "</pre>" in body: bad.append("pre leak")
    if "Project Gutenberg" in txt: bad.append("PG boilerplate")
    if "Transcriber" in txt: bad.append("transcriber note")

    # runtime prerequisites
    for need in ("hairline", "RDRBUS1:", chr(108)+chr(97)+chr(110)+chr(103)+chr(61)+chr(34)+"en"):
        if need not in t: bad.append("missing " + need)

    # conservation: the build steps (byline strip, renumber, sectionise) must
    # not lose a single character of what the parser produced
    src_txt = os.path.join(SRC[f[:-5]])
    import bookparse
    pr = bookparse.parse(src_txt)
    want = P_RX.findall(pr["html"])
    a_want = alnum(" ".join(H.unescape(TAG.sub("", b)) for _, b in want))
    a_have = alnum(txt)
    if a_want != a_have:
        # the byline paragraph is deliberately dropped; allow exactly that
        if not (len(a_want) - len(a_have) <= 30 and a_want.endswith(a_have[-200:])):
            bad.append("text loss %d chars" % (len(a_want) - len(a_have)))

    status = "ok" if not bad else "; ".join(bad)
    if bad: fails.append((f, status))
    print("%-46s %6d %5d %6d %9s  %s"
          % (f[:46], len(idx), len(chaps), secs, "{:,}".format(chars), status))

print("\nFAILURES: %d / %d" % (len(fails), len(files)))
for a, b in fails: print("  ", a, "->", b)
