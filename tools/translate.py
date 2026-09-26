# -*- coding: utf-8 -*-
"""Korean translation pipeline for 서재 1895—1936.

The English text already ships as 서재/data/<id>.js (a SEOJAE.receive() call).
This module slices that text into translation *jobs*, collects the Korean that
agents write back, and assembles 서재/data/ko/<id>.js — a parallel payload keyed
by the same data-p indices, so the runtime can swap languages without touching
the anchor arithmetic that stores reading positions.

    python translate.py plan  <id|--tier1|--tier2|--all>  # write tr/jobs/<id>/NNN.json
    python translate.py todo  [N]                  # jobs still missing output
    python translate.py build <id|--all>           # out/*.json -> data/ko/<id>.js
    python translate.py check <id/NNN|id|--all>    # verify written output only
    python translate.py status                     # coverage table

Invariant: a Korean payload never invents or drops a paragraph index. Every key
must exist in the English source; assembly drops what does not verify.
"""
from __future__ import annotations
import os, io, re, json, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "tools")
SITE = os.path.join(ROOT, "서재")
DATA = os.path.join(SITE, "data")
KODATA = os.path.join(DATA, "ko")
TR = os.path.join(HERE, "tr")
JOBS = os.path.join(TR, "jobs")
OUT = os.path.join(TR, "out")

P_RX = re.compile(r'^<p([^>]*)\sdata-p="(\d+)"([^>]*)>(.*)</p>$')
H_RX = re.compile(r'^<h2 class="(chapter|part)" id="([^"]+)"([^>]*)>(.*)</h2>$')

# Works translated first: shortest and best known, so whole books finish rather
# than sixty half-books. This is also the order they get translated in.
TIER1 = [
    "kafka-give-it-up", "kafka-the-helmsman", "kafka-poseidon",
    "kafka-the-knock-at-the-manor-gate", "wells-the-red-room", "wells-the-star",
    "kafka-the-metamorphosis", "wells-the-time-machine",
    "fitzgerald-the-great-gatsby", "wells-the-island-of-doctor-moreau",
    "wells-the-invisible-man", "wells-select-conversations-with-an-uncle",
    "fitzgerald-the-vegetable", "wells-the-war-of-the-worlds",
    "wells-the-door-in-the-wall-and-other-stories", "harbou-metropolis",
]

# The next six, chosen the same way: short enough to finish whole. Kafka's
# The Trial and The Castle are held back — their source text lost its
# paragraph breaks (single blocks over 30,000 chars, larger than a whole job
# unit), and The Trial's English carries a translator copyright notice.
TIER2 = [
    "wells-the-undying-fire", "wells-the-stolen-bacillus-and-other-incidents",
    "wells-boon", "wells-the-world-set-free", "wells-a-modern-utopia",
    "wells-the-wonderful-visit",
]

META = None


def metaof(bid):
    global META
    if META is None:
        sys.path.insert(0, HERE)
        import meta
        META = {w["id"]: w for w in meta.build()["works"]}
    return META.get(bid, {})


def read_payload(bid):
    p = os.path.join(DATA, bid + ".js")
    s = io.open(p, encoding="utf-8").read()
    return json.loads(s[s.index("(") + 1:s.rindex(")")])


def units(bid):
    """Ordered translation units: ('h', head-id, inner) and ('p', index, inner)."""
    out = []
    for ln in read_payload(bid)["html"].split("\n"):
        m = H_RX.match(ln)
        if m:
            out.append(("h", m.group(2), m.group(4)))
            continue
        m = P_RX.match(ln)
        if m:
            out.append(("p", m.group(2), m.group(4)))
    return out


def key(u):
    return ("h:" if u[0] == "h" else "p:") + str(u[1])


# ------------------------------------------------------------------ planning
def plan(bid, chunk_chars=7000):
    us = units(bid)
    w = metaof(bid)
    jd = os.path.join(JOBS, bid)
    if not os.path.isdir(jd):
        os.makedirs(jd)
    for f in os.listdir(jd):
        os.remove(os.path.join(jd, f))

    chunks, cur, n = [], [], 0
    for u in us:
        # a chapter heading opens a new job once the current one is half full
        if u[0] == "h" and n > chunk_chars * 0.45:
            chunks.append(cur)
            cur, n = [], 0
        cur.append(u)
        n += len(u[2])
        if n >= chunk_chars:
            chunks.append(cur)
            cur, n = [], 0
    if cur:
        chunks.append(cur)

    flat = {key(u): u[2] for u in us}
    order = [key(u) for u in us]
    for i, ch in enumerate(chunks):
        first = order.index(key(ch[0]))
        tail = ""
        if first:
            tail = re.sub(r"<[^>]+>", "", flat[order[first - 1]])[-320:]
        job = {
            "book": bid, "chunk": i + 1, "of": len(chunks),
            "title": w.get("title", bid), "titleKo": w.get("titleKo", ""),
            "author": w.get("authorEn", ""), "year": w.get("year", 0),
            "form": w.get("form", "novel"),
            "prevTail": tail,
            "items": [{"k": key(u), "t": u[2]} for u in ch],
        }
        p = os.path.join(jd, "%03d.json" % (i + 1))
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(job, ensure_ascii=False, indent=1))
    return len(chunks)


def jobfiles(bid):
    jd = os.path.join(JOBS, bid)
    if not os.path.isdir(jd):
        return []
    return sorted(os.path.join(jd, f) for f in os.listdir(jd) if f.endswith(".json"))


def outpath(jobpath):
    bid = os.path.basename(os.path.dirname(jobpath))
    return os.path.join(OUT, bid, os.path.basename(jobpath))


def todo(limit=None):
    rows = []
    if os.path.isdir(JOBS):
        for bid in sorted(os.listdir(JOBS)):
            for j in jobfiles(bid):
                if not os.path.exists(outpath(j)):
                    rows.append(j)
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------- assembling
# the parser emits exactly two inline constructs; anything else is invention
BAD_TAG = re.compile(r'<(?!/?em>|span class="smallcaps">|/span>)[^>]+>')
HANGUL = re.compile(r"[가-힣]")


def check(job, got):
    """A job's output must cover exactly its keys. Returns (clean, problems)."""
    src = {it["k"]: it["t"] for it in job["items"]}
    prob, clean = [], {}
    for k in [it["k"] for it in job["items"]]:
        v = got.get(k)
        if not str(src[k]).strip():
            clean[k] = ""          # an empty source paragraph stays empty
            continue
        if v is None or not str(v).strip():
            prob.append("missing " + k)
            continue
        v = unicodedata.normalize("NFC", str(v)).strip()
        if BAD_TAG.search(v):
            prob.append("stray markup in " + k)
            continue
        if v.count("<em>") != v.count("</em>") or v.count("<span") != v.count("</span>"):
            prob.append("unbalanced inline markup in " + k)
            continue
        # a "Korean" paragraph with no Hangul at all is almost always untouched
        s = re.sub(r"<[^>]+>", "", v)
        # (only for English originals: in a Japanese book a line that is already
        #  in Roman letters — a book title, a sign — is kept as it stands)
        if (not HANGUL.search(s) and len(re.sub(r"[^A-Za-z]", "", s)) > 12
                and metaof(job.get("book", "")).get("orig", "en") == "en"):
            prob.append("looks untranslated: " + k)
            continue
        clean[k] = v
    extra = [k for k in got if k not in src]
    if extra:
        prob.append("unknown keys: " + ", ".join(sorted(extra)[:4]))
    return clean, prob


def build(bid, quiet=False):
    us = units(bid)
    total = len(us)
    got, problems = {}, []
    for j in jobfiles(bid):
        o = outpath(j)
        if not os.path.exists(o):
            continue
        job = json.load(io.open(j, encoding="utf-8"))
        try:
            raw = json.load(io.open(o, encoding="utf-8"))
        except Exception as e:
            problems.append("%s: unreadable (%r)" % (os.path.basename(o), e))
            continue
        clean, prob = check(job, raw)
        got.update(clean)
        problems += ["%s: %s" % (os.path.basename(o), p) for p in prob]

    if not got:
        return 0, total, problems

    pmap = {u[1]: got[key(u)] for u in us if u[0] == "p" and key(u) in got}
    hmap = {u[1]: got[key(u)] for u in us if u[0] == "h" and key(u) in got}
    cov = len(got) / float(total)
    w = metaof(bid)
    payload = {"id": bid, "cov": round(cov, 4), "n": len(got), "of": total,
               "titleKo": w.get("titleKo", ""), "authorKo": w.get("authorKo", ""),
               "p": pmap, "h": hmap}
    if not os.path.isdir(KODATA):
        os.makedirs(KODATA)
    js = "SEOJAE.receiveKo(" + json.dumps(payload, ensure_ascii=False,
                                          separators=(",", ":")) + ");\n"
    io.open(os.path.join(KODATA, bid + ".js"), "w", encoding="utf-8", newline="\n").write(js)
    if not quiet:
        print("%-52s %4d/%-4d  %5.1f%%  %s bytes" % (
            bid, len(got), total, cov * 100, "{:,}".format(len(js.encode("utf-8")))))
        for p in problems[:8]:
            print("   ! " + p)
    return len(got), total, problems


def coverage():
    """{book id: (korean units, total units)} for everything with a ko payload."""
    out = {}
    if not os.path.isdir(KODATA):
        return out
    for f in sorted(os.listdir(KODATA)):
        if not f.endswith(".js") or f == "index.js":
            continue
        s = io.open(os.path.join(KODATA, f), encoding="utf-8").read()
        d = json.loads(s[s.index("(") + 1:s.rindex(")")])
        out[d["id"]] = (d["n"], d["of"])
    return out


# -------------------------------------------------------------- plain text
KO_OUT = os.path.join(ROOT, "한국어판")
TAG_RX = re.compile(r"<[^>]+>")
BQ_OPEN = re.compile(r"^<blockquote")
BQ_CLOSE = re.compile(r"^</blockquote>")


def plain(s):
    """Inline markup off, entities back to characters."""
    return html_unescape(TAG_RX.sub("", s)).strip()


def html_unescape(s):
    import html as _h
    return _h.unescape(s)


def wcwidth(s):
    """Display columns: Hangul and CJK punctuation take two."""
    n = 0
    for c in s:
        o = ord(c)
        n += 2 if (0x1100 <= o <= 0x115F or 0x2E80 <= o <= 0xA4CF
                   or 0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF
                   or 0xFF00 <= o <= 0xFF60) else 1
    return n


def wrap(s, cols, indent=""):
    """Break on spaces only — Korean words must never be split mid-word."""
    if not cols:
        return [indent + s] if s else [""]
    out, line = [], indent
    for word in s.split(" "):
        cand = word if line.strip() == "" else line + " " + word
        if wcwidth(cand) > cols and line.strip():
            out.append(line)
            line = indent + word
        else:
            line = cand
    if line.strip():
        out.append(line)
    return out or [""]


def to_text(bid, cols=0, partial=False):
    """Render one work as a plain-text Korean edition, or None if not ready."""
    cov = coverage().get(bid)
    if not cov:
        return None
    n, of = cov
    if not partial and n < of:
        return None
    ko = json.loads(io.open(os.path.join(KODATA, bid + ".js"), encoding="utf-8")
                    .read().split("(", 1)[1].rsplit(")", 1)[0])
    w = metaof(bid)
    body = read_payload(bid)["html"]

    lines, chapters, depth = [], [], 0
    for ln in body.split("\n"):
        if BQ_OPEN.match(ln):
            depth += 1
            continue
        if BQ_CLOSE.match(ln):
            depth = max(0, depth - 1)
            continue
        if ln.startswith("<hr"):
            lines.append(("rule", "", 0))
            continue
        m = H_RX.match(ln)
        if m:
            t = plain(ko["h"].get(m.group(2), m.group(4)))
            chapters.append(t)
            lines.append(("head", t, 0))
            continue
        m = P_RX.match(ln)
        if m:
            t = plain(ko["p"].get(m.group(2), m.group(4)))
            lines.append(("para", t, depth))
    # front matter, in the shape the English source files already use
    head = [w.get("titleKo") or w["title"], "", w.get("authorKo", ""), str(w["year"]), "",
            "원제  " + w["title"]]
    if w.get("titleOrig"):
        head.append("원어  " + w["titleOrig"])
    head += ["", "서재 1895—1936 · 새로 옮긴 한국어판",
             "원문은 퍼블릭 도메인, 번역은 이 서재에서 새로 옮긴 것입니다."]
    if n < of:
        head.append("번역 %d%% · 나머지 문단은 원문 그대로입니다." % (100 * n // of))
    if len(chapters) > 1:
        head += ["", "", "차례", ""] + ["  " + c for c in chapters]
    out = head + ["", ""]

    for kind, t, d in lines:
        if kind == "rule":
            out += ["", "*", ""]
        elif kind == "head":
            out += ["", "", t, ""]
        elif t:
            out += wrap(t, cols, "    " * d)
            out.append("")
    while out and not out[-1]:
        out.pop()
    return "\n".join(out) + "\n"


def write_text(cols=0, partial=False):
    made = []
    for bid in sorted(coverage()):
        s = to_text(bid, cols, partial)
        if s is None:
            continue
        w = metaof(bid)
        folder = w["file"].split("/")[0]
        d = os.path.join(KO_OUT, folder)
        if not os.path.isdir(d):
            os.makedirs(d)
        name = re.sub(r'[\\/:*?"<>|]', "-", w.get("titleKo") or w["title"])
        p = os.path.join(d, "%d_%s.txt" % (w["year"], name))
        io.open(p, "w", encoding="utf-8", newline="\n").write(s)
        made.append((os.path.relpath(p, ROOT).replace("\\", "/"), len(s)))
    return made


def write_index():
    """data/ko/index.js — the coverage table the library reads at paint time."""
    if not os.path.isdir(KODATA):
        os.makedirs(KODATA)
    idx = {bid: {"n": n, "of": of, "cov": round(n / float(of or 1), 4)}
           for bid, (n, of) in sorted(coverage().items())}
    js = "SEOJAE.koIndex(" + json.dumps(idx, ensure_ascii=False, separators=(",", ":")) + ");\n"
    io.open(os.path.join(KODATA, "index.js"), "w", encoding="utf-8", newline="\n").write(js)
    return len(idx)


def status():
    ids = [f[:-3] for f in sorted(os.listdir(DATA)) if f.endswith(".js")]
    cov = coverage()
    tw = tdone = 0
    print("%-52s %8s %8s %7s" % ("work", "units", "korean", "cov"))
    for bid in ids:
        n = len(units(bid))
        ko = cov.get(bid, (0, n))[0]
        tw += n
        tdone += ko
        if ko:
            print("%-52s %8d %8d %6.1f%%" % (bid, n, ko, 100.0 * ko / n))
    print("-" * 80)
    print("%-52s %8d %8d %6.1f%%" % ("TOTAL", tw, tdone, 100.0 * tdone / max(1, tw)))


def check_cli(args):
    """Verify already-written out/*.json against their jobs. Prints problems."""
    targets = []
    for a in args:
        if a == "--all":
            targets += sorted(
                os.path.relpath(os.path.join(r, f), OUT).replace("\\", "/")[:-5]
                for r, _, fs in os.walk(OUT) for f in fs if f.endswith(".json"))
        else:
            targets.append(a.replace("\\", "/").replace(".json", ""))
    bad = 0
    for t in targets:
        jp = os.path.join(JOBS, t + ".json")
        op = os.path.join(OUT, t + ".json")
        if not os.path.exists(jp):
            print("%-56s no such job" % t); bad += 1; continue
        if not os.path.exists(op):
            print("%-56s no output yet" % t); bad += 1; continue
        job = json.load(io.open(jp, encoding="utf-8"))
        try:
            got = json.load(io.open(op, encoding="utf-8"))
        except Exception as e:
            print("%-56s unreadable JSON (%s)" % (t, e)); bad += 1; continue
        if not isinstance(got, dict):
            print("%-56s not a flat object" % t); bad += 1; continue
        clean, prob = check(job, got)
        # emphasis is easy to drop in translation and the key check cannot see it;
        # a count mismatch is only a warning (merging two <em> can be right)
        src = {it["k"]: str(it["t"]) for it in job["items"]}
        warn = [k for k, v in clean.items()
                if src[k].count("<em>") != v.count("<em>")
                or src[k].count("<span") != v.count("<span")]
        for k in warn[:12]:
            print("    warn: emphasis count differs in %s (%d -> %d)"
                  % (k, src[k].count("<em>") + src[k].count("<span"),
                     clean[k].count("<em>") + clean[k].count("<span")))
        if prob:
            bad += 1
            print("%-56s %d problem(s)" % (t, len(prob)))
            for m in prob[:12]:
                print("    " + m)
        else:
            print("%-56s ok  %d keys" % (t, len(clean)))
    print("-" * 72)
    print("%d checked, %d with problems" % (len(targets), bad))
    return bad


def main(argv):
    # Titles carry em-dashes and Hangul; a cp949 console would die printing them.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cmd = argv[1] if len(argv) > 1 else "status"
    arg = argv[2] if len(argv) > 2 else ""
    ids = [f[:-3] for f in sorted(os.listdir(DATA)) if f.endswith(".js")]
    if cmd == "plan":
        targets = (TIER1 if arg == "--tier1" else TIER2 if arg == "--tier2"
                   else ids if arg == "--all" else [arg])
        tot = 0
        for bid in targets:
            n = plan(bid)
            tot += n
            print("%-52s %3d jobs" % (bid, n))
        print("total jobs:", tot)
    elif cmd == "todo":
        lim = int(arg) if arg else None
        for j in todo(lim):
            print(os.path.relpath(j, ROOT).replace("\\", "/"))
    elif cmd == "build":
        targets = ids if arg in ("--all", "") else [arg]
        for bid in targets:
            if jobfiles(bid):
                build(bid)
        print("data/ko/index.js  ->  %d works" % write_index())
    elif cmd == "txt":
        cols = 0
        for a in argv[2:]:
            if a.startswith("--wrap"):
                cols = int(a.split("=", 1)[1]) if "=" in a else 74
        made = write_text(cols, partial=("--partial" in argv[2:]))
        for p, n in made:
            print("%-58s %9s bytes" % (p, "{:,}".format(n)))
        print("%d files" % len(made))
    elif cmd == "check":
        bad = check_cli(argv[2:] or ["--all"])
        return 1 if bad else 0
    elif cmd == "status":
        status()
    else:
        print(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
