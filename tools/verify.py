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
             "id=\"dimmer\"", "SEOJAE.receive", "data-view=\"library\""]
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
        if re.search(r"(?i)(macmillan|scribner co|electrotyped)", txt[:400]): bad.append("imprint")
        if len(txt) < 400: bad.append("suspiciously short")

        status = "ok" if not bad else "; ".join(bad)
        if bad:
            fails.append((w["id"], status))
        print("%-44s %6d %5d %6d %10s  %s"
              % (w["title"][:44], len(idxs), len(payload["chapters"]), secs,
                 "{:,}".format(len(txt)), status))

    print("\nworks=%d  clean=%d  body chars=%s"
          % (len(MAN), len(MAN) - len(fails), "{:,}".format(chars_total)))
    print("FAILURES:", len(fails))
    for a, b in fails:
        print("  ", a, "->", b)


if __name__ == "__main__":
    main()
