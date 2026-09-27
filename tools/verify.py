# -*- coding: utf-8 -*-
"""Invariant checks over the built portal: index.html + data/<id>.js."""
from __future__ import annotations
import os, io, re, json, html as H, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, chr(49436) + chr(51116))          # 소설/서재
DATA = os.path.join(SITE, "data")

TAG = re.compile(r"<[^>]+>")
P_RX = re.compile(r'<p[^>]*data-p="(\d+)"[^>]*>(.*?)</p>', re.S)


def alnum(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if c.isalnum())


def text_of(body):
    return " ".join(H.unescape(TAG.sub("", b)) for _, b in P_RX.findall(body))


def main():
    idx = io.open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    m = re.search(r"var MANIFEST=(\[.*?\]);", idx, re.S)
    MAN = json.loads(m.group(1))
    print("index.html %s bytes · manifest %d works" % ("{:,}".format(len(idx)), len(MAN)))

    # the portal shell must carry every hook portal.js queries by id/class
    hooks = ["id=\"book\"", "id=\"hairline\"", "id=\"hud-top\"", "id=\"hud-bot\"",
             "id=\"drawer\"", "id=\"settings\"", "id=\"palette\"", "id=\"scrim\"",
             "id=\"grid\"", "id=\"grid-author\"", "id=\"now\"", "id=\"nowlist\"",
             "id=\"find\"", "id=\"count\"", "id=\"theme\"", "id=\"mine\"",
             "id=\"dimmer\"", "SEOJAE.receive", "data-view=\"library\"",
             "id=\"facets\"", "id=\"sugg\"", "id=\"authnav\"", "id=\"facetbtn\"",
             "data-act=\"lang\"", "data-k=\"lang\"", "SEOJAE.koIndex"]
    missing = [h for h in hooks if h not in idx]
    if missing:
        print("MISSING SHELL HOOKS:", missing)

    ids = set()
    fails, chars_total = [], 0
    hdr = "%-44s %6s %5s %6s %10s  %s" % ("work", "paras", "ch", "secs", "chars", "checks")
    print("\n" + hdr + "\n" + "-" * len(hdr))

    for w in MAN:
        p = os.path.join(DATA, w["id"] + ".js")
        bad = []
        if not os.path.exists(p):
            fails.append((w["id"], "data file missing")); print("FAIL", w["id"], "missing"); continue
        raw = io.open(p, encoding="utf-8").read()
        if not raw.startswith("SEOJAE.receive("):
            bad.append("bad wrapper")
        inner = raw.strip()
        assert inner.endswith(");"), "unexpected wrapper tail"
        payload = json.loads(inner[len("SEOJAE.receive("):-2])
        body = payload["html"]
        ps = P_RX.findall(body)
        idxs = [int(a) for a, _ in ps]
        if idxs != list(range(len(idxs))):
            bad.append("data-p not 0..n contiguous")
        if payload["id"] != w["id"]:
            bad.append("id mismatch")
        if payload["id"] in ids:
            bad.append("duplicate id")
        ids.add(payload["id"])
        secs = body.count('<section class="ch"')
        if secs != body.count("</section>"):
            bad.append("section mismatch")
        for c in payload["chapters"]:
            if not (0 <= c["firstP"] < len(idxs)):
                bad.append("firstP out of range")
        fp = [c["firstP"] for c in payload["chapters"]]
        if fp != sorted(fp):
            bad.append("chapters unordered")
        for tag in ("blockquote", "div"):
            o = len(re.findall(r"<%s[ >]" % tag, body)); c2 = body.count("</%s>" % tag)
            if o != c2:
                bad.append("%s %d/%d" % (tag, o, c2))
        txt = text_of(body)
        chars_total += len(txt)
        if re.search(r"(?<![A-Za-z0-9])_[A-Za-z]", txt): bad.append("stray _italic_")
        if ". . ." in txt: bad.append("unfolded ellipsis")
        if "--" in txt: bad.append("unconverted --")
        if "Transcriber" in txt or "Project Gutenberg" in txt: bad.append("boilerplate")
        # Imprint-page wording only. A bare publisher name is not enough: Wells
        # thanks "Messrs. Macmillan" in a preface and a character in Bealby
        # names MACMILLAN'S MAGAZINE, and both are body text we must keep.
        if re.search(r"(?i)(electrotyped"
                     r"|macmillan (?:company|and co|& co|co\.)"
                     r"|scribner(?:['’]s sons| co))", txt[:400]): bad.append("imprint")
        if len(txt) < 400: bad.append("suspiciously short")

        status = "ok" if not bad else "; ".join(bad)
        if bad:
            fails.append((w["id"], status))
        print("%-44s %6d %5d %6d %10s  %s"
              % (w["title"][:44], len(idxs), len(payload["chapters"]), secs,
                 "{:,}".format(len(txt)), status))

    print("\nworks=%d  clean=%d  body chars=%s"
          % (len(MAN), len(MAN) - len(fails), "{:,}".format(chars_total)))

    fails += verify_ko(MAN)
    print("FAILURES:", len(fails))
    for a, b in fails:
        print("  ", a, "->", b)


KO_TAG = re.compile(r'<(?!/?em>|span class="smallcaps">|/span>)[^>]+>')
H_ID = re.compile(r'<h2 class="(?:chapter|part)" id="([^"]+)"')


def verify_ko(MAN):
    """Korean payloads must key off the English spine: every index they carry
    has to exist in the source, or a language switch would land nowhere."""
    kod = os.path.join(DATA, "ko")
    if not os.path.isdir(kod):
        return []
    idxp = os.path.join(kod, "index.js")
    index = {}
    if os.path.exists(idxp):
        s = io.open(idxp, encoding="utf-8").read()
        index = json.loads(s[s.index("(") + 1:s.rindex(")")])
    fails, tot_n, tot_of = [], 0, 0
    hdr = "\n%-44s %8s %8s %7s  %s" % ("korean payload", "keys", "of", "cov", "checks")
    print(hdr + "\n" + "-" * (len(hdr) - 1))
    for f in sorted(os.listdir(kod)):
        if not f.endswith(".js") or f == "index.js":
            continue
        bid = f[:-3]
        raw = io.open(os.path.join(kod, f), encoding="utf-8").read().strip()
        bad = []
        if not raw.startswith("SEOJAE.receiveKo("):
            bad.append("bad wrapper")
        d = json.loads(raw[raw.index("(") + 1:raw.rindex(")")])
        src = io.open(os.path.join(DATA, bid + ".js"), encoding="utf-8").read()
        body = json.loads(src[src.index("(") + 1:src.rindex(")")])["html"]
        pn = set(a for a, _ in P_RX.findall(body))
        hn = set(H_ID.findall(body))
        stray_p = [k for k in d["p"] if k not in pn]
        stray_h = [k for k in d["h"] if k not in hn]
        if stray_p: bad.append("unknown paragraph %s" % stray_p[:3])
        if stray_h: bad.append("unknown heading %s" % stray_h[:3])
        n = len(d["p"]) + len(d["h"])
        if n != d["n"]: bad.append("count %d != %d" % (n, d["n"]))
        if d["of"] != len(pn) + len(hn): bad.append("total drifted from source")
        markup = [k for k, v in list(d["p"].items())[:4000] if KO_TAG.search(v)]
        if markup: bad.append("stray markup %s" % markup[:3])
        orig = next((w.get("orig", "en") for w in MAN if w["id"] == bid), "en")
        srcp = dict(P_RX.findall(body))
        plain = lambda t: re.sub(r"[\s“”‘’\"]+", " ", H.unescape(TAG.sub("", t))).strip()
        latin = [k for k, v in d["p"].items()
                 if orig == "en" and v and not re.search(r"[가-힣]", v)
                 and len(re.sub(r"[^A-Za-z]", "", v)) > 12
                 # a Latin line kept as written (Love and Mr Lewisham)
                 and not (plain(srcp.get(k, "")) == plain(v) and not re.search(
                     r"(?i)\b(?:the|and|of|to|is|you|that|with|was|his|her|it|in|for)\b", v))]
        if latin: bad.append("untranslated %s" % latin[:3])
        if bid not in index: bad.append("absent from index.js")
        elif index[bid]["n"] != d["n"]: bad.append("index.js out of date")
        tot_n += d["n"]; tot_of += d["of"]
        if bad: fails.append((bid, "; ".join(bad)))
        print("%-44s %8d %8d %6.1f%%  %s"
              % (bid[:44], d["n"], d["of"], 100.0 * d["n"] / max(1, d["of"]),
                 "ok" if not bad else "; ".join(bad)))
    try:
        import fonts
        gone = fonts.missing()
    except ImportError:                       # fontTools absent: nothing to check with
        gone = []
    if gone is None:
        fails.append(("서재/fonts", "bundled Korean serif missing — run tools/fonts.py"))
    elif gone:
        fails.append(("서재/fonts", "%d syllables not in the bundled font %s — run tools/fonts.py"
                      % (len(gone), "".join(gone[:10]))))
    ids = set(w["id"] for w in MAN)
    orphan = [k for k in index if k not in ids]
    if orphan:
        fails.append(("data/ko/index.js", "unknown works %s" % orphan[:3]))
    lib = 0
    for w in MAN:
        s2 = io.open(os.path.join(DATA, w["id"] + ".js"), encoding="utf-8").read()
        b2 = json.loads(s2[s2.index("(") + 1:s2.rindex(")")])["html"]
        lib += len(P_RX.findall(b2)) + len(H_ID.findall(b2))
    print("korean %s of %s units in these %d works · %s of %s across all %d  (%.1f%%)"
          % ("{:,}".format(tot_n), "{:,}".format(tot_of), len(index),
             "{:,}".format(tot_n), "{:,}".format(lib), len(MAN), 100.0 * tot_n / max(1, lib)))
    return fails


if __name__ == "__main__":
    main()
