# -*- coding: utf-8 -*-
"""V2 다듬기 일괄 진행 도우미 (REVISE.md 참고).

    python tr/revq.py start  <책>      # revise 계획 + 다듬는 이에게 줄 범위 목록
    python tr/revq.py finish <책>      # 전체 check · 전후 비교 · log → 노트 결정 기록 · build

finish 는 마지막 줄에 요약 한 줄(TSV)을 tr/rev/summary.tsv 에 덧붙인다.
"""
import io, json, os, re, subprocess, sys, glob

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import translate as T  # noqa: E402

PER = 5


def ranges(n):
    rs, i = [], 1
    while i <= n:
        j = min(n, i + PER - 1)
        if n - j <= 2:          # 꼬리 1–2청크는 앞 범위에 붙임
            j = n
        rs.append((i, j))
        i = j + 1
    return rs


def start(bid):
    n, missing = T.revise_plan(bid)
    note = os.path.join(T.TR, "notes", bid + ".md")
    s = io.open(note, encoding="utf-8").read() if os.path.exists(note) else None
    if s is not None and "결정 기록" not in s:
        io.open(note, "a", encoding="utf-8", newline="\n").write(
            "\n\n## 결정 기록\n- (V2 다듬기) 이후 결정은 청크 번호와 함께 아래에.\n")
    print(json.dumps({"book": bid, "chunks": n, "missing": missing, "note": s is not None,
                      "ranges": ["%03d-%03d" % r for r in ranges(n)]}, ensure_ascii=False))


def finish(bid):
    jobs = T.jobfiles(bid)
    bad, warn_dlg, warn_pron = 0, 0, 0
    for j in jobs:
        job = json.load(io.open(j, encoding="utf-8"))
        o = T.outpath(j)
        try:
            got = json.load(io.open(o, encoding="utf-8"))
        except Exception:
            bad += 1
            continue
        clean, prob = T.check(job, got)
        if prob:
            bad += 1
        for m in T.style_warnings(job, clean):
            if m.startswith("대사"):
                warn_dlg += 1
            else:
                warn_pron += 1
    base = json.load(io.open(os.path.join(T.REV, bid, "base.json"), encoding="utf-8"))
    now = {}
    for j in jobs:
        o = T.outpath(j)
        if os.path.exists(o):
            now.update(json.load(io.open(o, encoding="utf-8")))
    keys = [k for k in base if base[k]]
    changed = sum(1 for k in keys if now.get(k, base[k]) != base[k])
    a = T._density([base[k] for k in keys])
    b = T._density([now.get(k, base[k]) for k in keys])
    # 결정 log → 노트
    lines = []
    for f in sorted(glob.glob(os.path.join(T.REV, bid, "*.log.md"))):
        lines += [ln.rstrip() for ln in io.open(f, encoding="utf-8") if ln.startswith("- ")]
    note = os.path.join(T.TR, "notes", bid + ".md")
    if lines and os.path.exists(note):
        s = io.open(note, encoding="utf-8").read()
        if "결정 기록" not in s:
            s += "\n\n## 결정 기록\n"
        new = [ln for ln in lines if ln not in s]
        io.open(note, "w", encoding="utf-8", newline="\n").write(s.rstrip("\n") + "\n" + "\n".join(new) + "\n")
    if not bad:
        T.build(bid, quiet=True)
        T.write_index()
    row = [bid, len(jobs), bad, len(keys), changed, "%.1f" % a["그녀"], "%.1f" % b["그녀"],
           "%.1f" % a["그는"], "%.1f" % b["그는"], warn_dlg, warn_pron, len(lines)]
    io.open(os.path.join(T.REV, "summary.tsv"), "a", encoding="utf-8", newline="\n").write(
        "\t".join(map(str, row)) + "\n")
    print("%s chunks=%d BAD=%d changed=%d/%d (%.0f%%) 그녀 %.1f→%.1f 그는 %.1f→%.1f warn대사=%d warn대명사=%d 결정=%d"
          % (bid, len(jobs), bad, changed, len(keys), 100.0 * changed / max(1, len(keys)),
             a["그녀"], b["그녀"], a["그는"], b["그는"], warn_dlg, warn_pron, len(lines)))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    {"start": start, "finish": finish}[sys.argv[1]](sys.argv[2])
