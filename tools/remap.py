# -*- coding: utf-8 -*-
"""Carry a finished translation across a parser change.

When bookparse.py changes how a book is cut (a false heading becomes a
paragraph, a dropped line comes back), every key after the change moves.
This aligns the book as committed (git HEAD) with the book as now built,
by text, and rewrites tools/tr/out/<id>/ against freshly planned jobs.

    python remap.py <id> [<id> ...]      # after build.py, before committing
"""
from __future__ import annotations
import difflib, glob, html as H, io, json, os, re, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, chr(49436) + chr(51116), "data")
OUT = os.path.join(ROOT, "tools", "tr", "out")
UNIT = re.compile(r'<h2 class="(?:chapter|part)" id="([^"]+)"[^>]*>(.*?)</h2>'
                  r'|<p[^>]*data-p="(\d+)"[^>]*>(.*?)</p>', re.S)


def units(src):
    body = json.loads(src[src.index("(") + 1:src.rindex(")")])["html"]
    out = []
    for m in UNIT.finditer(body):
        key = "h:" + m.group(1) if m.group(1) else "p:" + m.group(3)
        txt = H.unescape(re.sub(r"<[^>]+>", "", m.group(2) or m.group(4) or ""))
        out.append((key, "".join(c for c in unicodedata.normalize("NFKD", txt).lower()
                                 if c.isalnum())))
    return out


def remap(bid):
    rel = "%s/data/%s.js" % (chr(49436) + chr(51116), bid)
    old = subprocess.run(["git", "show", "HEAD:" + rel], cwd=ROOT,
                         capture_output=True).stdout.decode("utf-8")
    new = io.open(os.path.join(DATA, bid + ".js"), encoding="utf-8").read()
    a, b = units(old), units(new)
    tr = {}
    for f in sorted(glob.glob(os.path.join(OUT, bid, "*.json"))):
        tr.update(json.load(io.open(f, encoding="utf-8")))
    sm = difflib.SequenceMatcher(None, [t for _, t in a], [t for _, t in b], autojunk=False)
    moved, lost, fresh = {}, [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for i, j in zip(range(i1, i2), range(j1, j2)):
                if a[i][0] in tr:
                    moved[b[j][0]] = tr[a[i][0]]
        else:
            lost += [a[i][0] for i in range(i1, i2)]
            fresh += [b[j][0] for j in range(j1, j2)]
    # a heading turned paragraph keeps its words
    for k_old, k_new in zip(lost, fresh):
        if k_old in tr and k_new not in moved:
            moved[k_new] = tr[k_old]
    print("%s: %d keys carried, %d old units unmatched %s, %d new units %s"
          % (bid, len(moved), len(lost), lost[:4], len(fresh), fresh[:4]))
    import shutil
    shutil.rmtree(os.path.join(ROOT, "tools", "tr", "jobs", bid), ignore_errors=True)
    subprocess.run([sys.executable, "translate.py", "plan", bid],
                   cwd=os.path.join(ROOT, "tools"), capture_output=True)
    for f in glob.glob(os.path.join(OUT, bid, "*.json")):
        os.remove(f)
    for jf in sorted(glob.glob(os.path.join(ROOT, "tools", "tr", "jobs", bid, "*.json"))):
        job = json.load(io.open(jf, encoding="utf-8"))
        chunk = {it["k"]: moved.get(it["k"], "") for it in job["items"]}
        miss = [k for k, v in chunk.items() if not v]
        if miss:
            print("   %s: untranslated %s" % (os.path.basename(jf), miss[:6]))
        io.open(os.path.join(OUT, bid, os.path.basename(jf)), "w", encoding="utf-8",
                newline="\n").write(json.dumps(chunk, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    for bid in sys.argv[1:]:
        remap(bid)
