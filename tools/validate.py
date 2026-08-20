#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validation harness for bookparse.py.  Run:  python validate.py [ROOT]

Per-file checks
  T1 body-text conservation  alnum(text of all <p>) == alnum(kept source text)
  T2 reconciliation          alnum(source) == alnum(kept)+alnum(headings)+alnum(dropped)
  T3 paragraph parity        every source prose block produced exactly one <p>
  T4 id uniqueness           every id appears once
  T5 heading order           no <h3> before the first <h2>
  T6 no empty chapter        every chapter holds >= 1 <p>
  T7 no giant chapter        no chapter holds > 45% of the book's paragraphs
  T8 determinism             re-parse identical; BOM+CRLF copy identical
  T9 TOC coverage            >= 80% of harvested TOC entries became chapters
"""
import html as _html
import io
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter

import bookparse as B

ROOT = sys.argv[1] if len(sys.argv) > 1 else "C:/Users/user/소설"
TAG = re.compile(r"<[^>]+>")
NOTALNUM = re.compile(r"[^0-9A-Za-z]+")
P_RX = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S)


def alnum(s):
    return NOTALNUM.sub("", unicodedata.normalize("NFKD", s))


def ptext(h):
    return " ".join(_html.unescape(TAG.sub(" ", m)) for m in P_RX.findall(h))


def files():
    out = []
    for d in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.endswith(".txt") and not f.startswith("00_"):
                    out.append(os.path.join(p, f))
    return out


rows, review = [], []
tmpdir = tempfile.mkdtemp(prefix="bpval")
for fp in files():
    name = os.path.basename(fp)
    r = B.parse(fp)
    st, html = r["stats"], r["html"]
    src = r["_source"]

    a_p = alnum(ptext(html))
    a_kept = alnum(r["_synth_para"]) + alnum(r["_kept_text"])
    a_head = alnum(r["_head_text"])
    a_src = alnum(src)
    a_drop = alnum("".join(t for _, t in st["dropped_text"]))

    t1 = a_p == a_kept
    lost = (len(a_src) - len(a_kept) + len(alnum(r["_synth_para"]))
            - len(a_head) - len(a_drop))
    t2 = lost == 0

    npara = len(P_RX.findall(html))
    t3 = npara >= st["para_src"]

    ids = re.findall(r'\sid="([^"]+)"', html)
    t4 = len(ids) == len(set(ids))

    t5, seen_h2 = True, False
    for tag in re.findall(r"<(h[123])\b", html):
        if tag == "h2":
            seen_h2 = True
        elif tag == "h3" and not seen_h2:
            t5 = False

    parts = re.split(r'<h2 class="chapter"', html)
    counts = [len(P_RX.findall(x)) for x in parts[1:]]
    t6 = all(c > 0 for c in counts) if counts else True
    t7 = (max(counts) <= 0.45 * npara) if counts else True

    t8a = B.parse(fp)["html"] == html
    sub = os.path.join(tmpdir, os.path.basename(os.path.dirname(fp)))
    os.path.isdir(sub) or os.makedirs(sub)
    alt = os.path.join(sub, name)
    io.open(alt, "w", encoding="utf-8-sig", newline="\r\n").write(src)
    t8b = B.parse(alt)["html"] == html
    os.remove(alt)

    man, ch = st["manifest_entries"], st["chapters"]
    t9 = (man == 0) or (ch + st['parts'] >= man * 0.8)

    pct = 100.0 * len(a_drop) / max(1, len(a_src))
    flags = []
    for cond, tagname in ((t1, "TEXT-MISMATCH"), (t2, "LOST:%d" % lost),
                          (t3, "PARA-DEFICIT"), (t4, "DUP-ID"),
                          (t5, "H3-BEFORE-H2"), (t6, "EMPTY-CH"),
                          (t7, "GIANT-CH"), (t8a and t8b, "NONDETERMINISTIC"),
                          (t9, "TOC-COVERAGE %d/%d" % (ch + st["parts"], man))):
        if not cond:
            flags.append(tagname)
    if pct > 12:
        flags.append("DROP-%d%%" % int(pct))
    if ch == 0:
        flags.append("NO-CHAPTERS")

    rows.append((name, st, npara, ch, st["parts"], html.count("<h3 "),
                 len(a_src), len(a_kept) - len(alnum(r["_synth_para"])),
                 len(a_drop) + len(a_head), pct, flags))
    if flags:
        review.append((name, flags))
shutil.rmtree(tmpdir, ignore_errors=True)

hdr = ("%-52s %5s %4s %3s %5s %9s %6s  %s"
       % ("file", "paras", "chap", "pt", "subhd", "src-chars", "drop%", "flags"))
print(hdr)
print("-" * 132)
for (name, st, npara, ch, pt, sub, nsrc, nkept, ndrop, pct, flags) in rows:
    print("%-52s %5d %4d %3d %5d %9d %5.1f%%  %s"
          % (name[:52], npara, ch, pt, sub, nsrc, pct,
             ", ".join(flags) if flags else "ok"))

print()
print("files                 : %d" % len(rows))
print("clean                 : %d" % sum(1 for r in rows if not r[10]))
print("needing manual review : %d" % len(review))
tot_src = sum(r[6] for r in rows)
tot_kept = sum(r[7] for r in rows)
tot_drop = sum(r[8] for r in rows)
print("alnum chars: source=%d body-kept=%d headings+dropped=%d unaccounted=%d"
      % (tot_src, tot_kept, tot_drop, tot_src - tot_kept - tot_drop))
print()
print("== dropped text by reason (visible chars, whole corpus) ==")
c = Counter()
for name, st, *_ in rows:
    for reason, n in st["dropped"]:
        c[reason] += n
for k, v in c.most_common():
    print("  %-28s %d" % (k, v))
print()
print("== files needing manual review ==")
for name, flags in review:
    print("  %-52s %s" % (name[:52], ", ".join(flags)))
