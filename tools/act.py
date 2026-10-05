# -*- coding: utf-8 -*-
"""낭독 '연기 대본' 파이프라인 — 서재 1895—1936.

누가 말하나(who)·어떻게 말하나(how)를 문단 번호(data-p)와 '문단 안 n번째 따옴표 대사'
순번에 겁니다. 글자 오프셋을 쓰지 않으므로 같은 대본을 영어 원문·한국어판·일본어 원문에
그대로 씁니다. 번역에서 대사 수가 달라지면 런타임이 순번 일치를 검사하고 물러납니다
(align() 과 tools/act/GUIDE.md '런타임 정렬 규칙').

    python act.py plan  <id|--all>          # act/jobs/<id>/NNN.json (배역표가 있어야 함)
    python act.py todo  [N]                 # 아직 출력이 없는 작업
    python act.py check <id/NNN|id|--all>   # 써 둔 out/*.json 검사
    python act.py cast  <id|--all>          # 배역표 act/cast/<id>.json 검사
    python act.py build <id|--all>          # out/*.json + cast -> 서재/data/act/<id>.js
    python act.py align <id>                # 대사 수 일치율 (원문·한국어판) 다시 셈
    python act.py status                    # 현황표

불변식: 대본은 원문에 없는 문단 번호를 만들지 않고, 원문(작품의 원어) 대사 수와 길이가
다른 q 목록을 싣지 않는다. build 는 검사를 통과한 것만 모은다.
"""
from __future__ import annotations
import os, io, re, json, sys, html as _html

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import translate as T  # read_payload, units, metaof, DATA, KODATA 를 함께 씀

ROOT, DATA, KODATA = T.ROOT, T.DATA, T.KODATA
ACT = os.path.join(HERE, "act")
JOBS = os.path.join(ACT, "jobs")
OUT = os.path.join(ACT, "out")
CAST = os.path.join(ACT, "cast")
ACTDATA = os.path.join(DATA, "act")
CFG = json.load(io.open(os.path.join(ACT, "config.json"), encoding="utf-8"))

ID_RX = re.compile(r"^[a-z][a-z0-9-]*$")


# ------------------------------------------------------------------ 대사 세기
# !! JS 짝: tools/act/spans.js 의 actSpans()·actAlign() (낭독 런타임 tools/tts/act.js 가
# !! 대본 순번을 셀 때 쓸 것). 한쪽을 고치면 다른 쪽도 똑같이 고칠 것 — 대본의 q 순번은
# !! 이 규칙으로 센 '문단 안 n번째 대사'입니다. tts/act.js 의 spans()+classify() 는 서술 속
# !! 인용구를 언어별 휴리스틱으로 빼므로 순번이 언어마다 달라질 수 있어 대본 순번에는 쓰지 않는다.
#
# 규칙
#  1. 문단 텍스트 = <rt>·<rp> 내용을 지우고, 태그를 지우고, 문자 참조를 푼 것.
#  2. 여는 따옴표 집합(opens)은 책·언어마다 하나로 정해 대본 파일 qs 에 싣는다
#     (detect_opens). 영어·한국어는 “ 또는 ‘ 중 하나, 일본어는 「『.
#     집합에 없는 따옴표(‘ ’ 안의 “ 등)는 안쪽 인용이라 세지 않는다.
#  3. 짝: “→” ‘→’ 「→」 『→』. ‘ 는 앞 글자가 글자·숫자가 아닐 때만 열고,
#     ’ 는 뒤 글자가 글자가 아닐 때만 닫는다(don’t 의 ’ 는 아포스트로피).
#  4. 대사가 열린 채 같은 여는 따옴표가 또 나오면
#     - “ ‘ : 앞 대사를 거기서 끊고 새 대사를 연다(원문 오류 복구).
#     - 「 『 : 겹침(깊이 +1). 깊이 0 으로 닫힐 때 대사 하나.
#     열린 대사 안의 다른 종류 따옴표는 무시한다.
#  5. 문단 끝까지 닫히지 않으면 대사는 문단 끝에서 끝나고, 열린 따옴표를 다음 문단으로
#     넘긴다(carry). 다음 문단이
#     - 같은 여는 따옴표로 시작하면(영어식) 그 대사가 0번이고 cont=True,
#     - 아니면(일본어식) 처음 나오는 닫는 따옴표가 어떤 여는 따옴표보다 앞설 때만
#       문단 머리~그 닫는 따옴표를 0번 대사(cont=True)로 친다. 그렇지 않으면 carry 를 버린다.
#     장 제목(h2)을 지나면 carry 를 버린다.
PAIR = {"“": "”", "‘": "’", "「": "」", "『": "』"}
NEST = set("「『")
LET = re.compile(r"\w", re.U)


def _isopen(t, i):
    c = t[i]
    if c == "‘":
        return i == 0 or not LET.match(t[i - 1])
    return True


def _isclose(t, i):
    if t[i] == "’":
        return i + 1 >= len(t) or not LET.match(t[i + 1])
    return True


def spans(t, opens, carry=None):
    """문단 t 의 대사 구간 [(시작, 끝, cont)] 과 다음 문단으로 넘길 carry."""
    out, i, n = [], 0, len(t)
    cur, depth, start, cont = None, 0, 0, False
    if carry:
        lead = len(t) - len(t.lstrip())
        if t[lead:lead + 1] == carry:
            cont = True                                    # 영어식 다시 열기
        else:
            cl = PAIR[carry]
            j = next((k for k in range(n) if t[k] == cl and _isclose(t, k)), -1)
            o = next((k for k in range(n) if t[k] in opens and _isopen(t, k)), -1)
            if j >= 0 and (o < 0 or j < o):
                out.append((0, j + 1, True))               # 일본어식 이어짐
                i = j + 1
    while i < n:
        c = t[i]
        if cur is None:
            if c in opens and _isopen(t, i):
                cur, depth, start = c, 1, i
        elif c == cur and _isopen(t, i):
            if c in NEST:
                depth += 1
            else:
                out.append((start, i, cont)); cont = False
                start = i
        elif c == PAIR[cur] and _isclose(t, i):
            depth -= 1
            if depth == 0:
                out.append((start, i + 1, cont)); cont = False
                cur = None
        i += 1
    if cur is not None:
        out.append((start, n, cont))
    return out, cur


def detect_opens(texts, lang):
    """책·언어 하나의 여는 따옴표 집합. 정하면 대본 파일 qs 에 실어 런타임은 다시 정하지 않는다."""
    if lang == "ja":
        return "「『"
    # 문단 머리의 따옴표로 정한다. 전체 개수로 정하면 액자 이야기 안의 ‘ ’ 대화가 많은
    # 책(wells-the-dream)에서 바깥 따옴표를 잘못 고른다. 같으면 “.
    dq = sum(1 for t in texts if t.lstrip().startswith("“"))
    sq = sum(1 for t in texts if t.lstrip().startswith("‘"))
    return "“" if dq >= sq else "‘"


RT_RX = re.compile(r"<(rt|rp)>.*?</\1>", re.S)
TAG_RX = re.compile(r"<[^>]+>")


def plain(s):
    return _html.unescape(TAG_RX.sub("", RT_RX.sub("", s or "")))


def paras(bid, lang):
    """[(키, 텍스트) | ('h', 제목)] 원문 순서. lang 이 'ko' 면 한국어판 문단(없는 문단은 None)."""
    us = T.units(bid)
    ko = load_ko(bid) if lang == "ko" else None
    out = []
    for u in us:
        if u[0] == "h":
            out.append(("h", plain(u[2])))   # 장 제목 글자 (작업 파일의 문맥용)
        elif ko is None:
            out.append((u[1], plain(u[2])))
        else:
            v = ko.get(u[1])
            out.append((u[1], plain(v) if v is not None else None))
    return out


def load_ko(bid):
    p = os.path.join(KODATA, bid + ".js")
    if not os.path.exists(p):
        return None
    s = io.open(p, encoding="utf-8").read()
    return json.loads(s[s.index("(") + 1:s.rindex(")")])["p"]


def count_book(bid, lang, opens=None):
    """{문단 키: [(시작, 끝, cont)]} 와 opens. 문단을 순서대로 지나며 carry 를 넘긴다."""
    ps = paras(bid, lang)
    if opens is None:
        opens = detect_opens([t for k, t in ps if k != "h" and t], lang)
    res, carry = {}, None
    for k, t in ps:
        if k == "h" or t is None:
            carry = None
            continue
        sp, carry = spans(t, opens, carry)
        res[k] = sp
    return res, opens


def orig_lang(bid):
    return T.metaof(bid).get("orig", "en")


# ------------------------------------------------------------------ 배역표
def cast_path(bid):
    return os.path.join(CAST, bid + ".json")


def load_cast(bid):
    p = cast_path(bid)
    if not os.path.exists(p):
        return None
    return json.load(io.open(p, encoding="utf-8"))


def check_cast(c, bid=None):
    """배역표 검사. (문제, 경고)."""
    prob, warn = [], []
    if not isinstance(c, dict):
        return ["배역표가 객체가 아님"], warn
    if bid and c.get("id") != bid:
        prob.append("id 가 파일 이름과 다름")
    cast = c.get("cast") or []
    ids = [m.get("id") for m in cast]
    if len(set(ids)) != len(ids):
        prob.append("id 중복")
    V = CFG["voices"]
    for m in cast:
        mid = m.get("id", "?")
        if not ID_RX.match(str(mid)):
            prob.append("%s: id 는 영문 소문자·숫자·- 만" % mid)
        nm = m.get("names") or {}
        if not nm.get("en") and not nm.get("ja"):
            prob.append("%s: names.en/ja 없음" % mid)
        if not nm.get("ko"):
            prob.append("%s: names.ko 없음" % mid)
        if m.get("gender") not in CFG["genders"]:
            prob.append("%s: gender 는 %s" % (mid, "/".join(CFG["genders"])))
        if m.get("age") not in CFG["ages"]:
            prob.append("%s: age 는 %s" % (mid, "/".join(CFG["ages"])))
        if m.get("role") not in ("narrator", "lead", "support", "minor"):
            prob.append("%s: role 은 narrator/lead/support/minor" % mid)
        v = m.get("voice") or {}
        if v.get("base") not in V:
            prob.append("%s: voice.base 는 F1..M5" % mid)
        mix = v.get("mix") or {}
        if any(k not in V or not (0 < float(w) < 1) for k, w in mix.items()) or sum(map(float, mix.values())) >= 1:
            prob.append("%s: voice.mix 는 {목소리: 0–1}, 합 < 1" % mid)
        if v.get("speed") is not None and not (0.8 <= float(v["speed"]) <= 1.2):
            prob.append("%s: voice.speed 는 0.8–1.2" % mid)
        g = m.get("gender")
        if v.get("base") in V and g in ("f", "m") and v["base"][0].lower() != g:
            warn.append("%s: gender %s 인데 목소리 %s" % (mid, g, v["base"]))
    if c.get("narrator") not in ids:
        prob.append("narrator 가 cast 에 없음")
    # 목소리가 겹치면 안 되는 사람들: 서술자 + lead + support (minor 는 겹쳐도 됨)
    key = lambda m: (m.get("voice", {}).get("base"), json.dumps(m.get("voice", {}).get("mix") or {}, sort_keys=True))
    major = [m for m in cast if m.get("role") in ("narrator", "lead") or m.get("id") == c.get("narrator")]
    sup = [m for m in cast if m.get("role") == "support"]
    seen = {}
    for m in major:
        if key(m) in seen:
            prob.append("목소리 겹침: %s · %s" % (seen[key(m)], m["id"]))
        seen[key(m)] = m["id"]
    for m in sup:
        if key(m) in seen:
            warn.append("조연 목소리가 주요 배역과 같음: %s · %s" % (seen[key(m)], m["id"]))
        seen.setdefault(key(m), m["id"])
    return prob, warn


# ------------------------------------------------------------------ 작업 나누기
def trim(t, n):
    if len(t) <= n:
        return t
    h = n // 2
    return t[:h].rstrip() + " … " + t[-h:].lstrip()


def plan(bid, chunk_chars=None):
    chunk_chars = chunk_chars or CFG["chunkChars"]
    ctx = CFG["ctxChars"]
    c = load_cast(bid)
    if c is None:
        raise SystemExit("배역표가 없습니다: tools/act/cast/%s.json (GUIDE.md '배역표')" % bid)
    lang = orig_lang(bid)
    sp, opens = count_book(bid, lang)
    ko = load_ko(bid)
    ksp = count_book(bid, "ko")[0] if ko else {}
    seq = paras(bid, lang)
    w = T.metaof(bid)

    items = []
    for k, t in seq:
        if k == "h":
            items.append({"k": "h", "t": t})
            continue
        s = sp.get(k, [])
        it = {"k": k}
        if s:
            it["q"] = len(s)
            it["t"] = t
            it["quotes"] = [trim(t[a:b], 70) for a, b, _ in s]
            if s[0][2]:
                it["cont"] = True
            if ko and k in ko:
                it["ko"] = plain(ko[k])
                if len(ksp.get(k, [])) != len(s):
                    it["koq"] = len(ksp.get(k, []))
        else:
            it["q"] = 0
            it["t"] = trim(t, ctx)
            if ko and k in ko:
                it["ko"] = trim(plain(ko[k]), ctx // 2)
        items.append(it)

    # 장 제목에서 끊기를 좋아하고, 원문 글자 수로 자른다(대사 없는 긴 서술은 반만 셈)
    chunks, cur, n = [], [], 0
    for it in items:
        if it["k"] == "h" and n > chunk_chars * 0.45:
            chunks.append(cur); cur, n = [], 0
        cur.append(it)
        n += len(it["t"]) if it.get("q") else len(it["t"]) // 2
        if n >= chunk_chars and it.get("q", 1) == 0:   # 대화 한가운데서는 자르지 않음
            chunks.append(cur); cur, n = [], 0
    if cur:
        chunks.append(cur)

    jd = os.path.join(JOBS, bid)
    if not os.path.isdir(jd):
        os.makedirs(jd)
    for f in os.listdir(jd):
        os.remove(os.path.join(jd, f))
    castbrief = [{"id": m["id"], "name": m["names"].get("ko", ""),
                  "en": m["names"].get("en") or m["names"].get("ja", ""),
                  "role": m.get("role"), "traits": m.get("traits", "")} for m in c["cast"]]
    flat = [it for it in items if it["k"] != "h"]
    for i, ch in enumerate(chunks):
        first = next((it for it in ch if it["k"] != "h"), None)
        fi = flat.index(first) if first else 0
        prev = [{"k": it["k"], "t": trim(it["t"], 300), "q": it.get("q", 0)}
                for it in flat[max(0, fi - 3):fi]]
        job = {"book": bid, "chunk": i + 1, "of": len(chunks),
               "title": w.get("title", bid), "titleKo": w.get("titleKo", ""),
               "author": w.get("authorEn", ""), "year": w.get("year", 0), "orig": lang,
               "opens": opens, "narrator": c["narrator"], "cast": castbrief,
               "prev": prev, "items": ch}
        io.open(os.path.join(jd, "%03d.json" % (i + 1)), "w", encoding="utf-8", newline="\n").write(
            json.dumps(job, ensure_ascii=False, indent=1))
    return len(chunks)


def jobfiles(bid):
    jd = os.path.join(JOBS, bid)
    if not os.path.isdir(jd):
        return []
    return sorted(os.path.join(jd, f) for f in os.listdir(jd) if f.endswith(".json"))


def outpath(jp):
    return os.path.join(OUT, os.path.basename(os.path.dirname(jp)), os.path.basename(jp))


def todo(limit=None):
    rows = []
    if os.path.isdir(JOBS):
        for bid in sorted(os.listdir(JOBS)):
            rows += [j for j in jobfiles(bid) if not os.path.exists(outpath(j))]
    return rows[:limit] if limit else rows


# ------------------------------------------------------------------ 검사
def norm_how(v):
    if v is None:
        return None
    v = CFG["alias"].get(v, v)
    return v


def check(job, got, cast_ids):
    """작업 하나의 출력 검사. (깨끗한 것, 문제, 경고)."""
    prob, warn, clean = [], [], {}
    if not isinstance(got, dict):
        return {}, ["평평한 객체가 아님"], []
    items = {it["k"]: it for it in job["items"] if it["k"] != "h"}
    for k in [k for k, it in items.items() if it.get("q")]:
        if k not in got:
            prob.append("빠진 대사 문단 " + k)
    nq = nhow = 0
    for k, v in got.items():
        if k not in items:
            prob.append("작업에 없는 키 " + k); continue
        if not isinstance(v, dict):
            prob.append("%s: 객체가 아님" % k); continue
        bad = [f for f in v if f not in ("q", "mood", "nar")]
        if bad:
            prob.append("%s: 모르는 필드 %s" % (k, ",".join(bad))); continue
        e = {}
        if "mood" in v and v["mood"] is not None:
            if v["mood"] not in CFG["mood"]:
                prob.append("%s: mood '%s' 는 어휘에 없음" % (k, v["mood"])); continue
            e["mood"] = v["mood"]
        if "nar" in v and v["nar"] is not None:
            if v["nar"] not in cast_ids:
                prob.append("%s: nar '%s' 는 배역표에 없음" % (k, v["nar"])); continue
            e["nar"] = v["nar"]
        want = items[k].get("q", 0)
        q = v.get("q") or []
        if len(q) != want:
            prob.append("%s: 대사 %d개인데 q 가 %d개" % (k, want, len(q))); continue
        ok, qq = True, []
        for i, x in enumerate(q):
            if not isinstance(x, dict) or "who" not in x:
                prob.append("%s[%d]: {who, how?, n?} 꼴이 아님" % (k, i)); ok = False; break
            if [f for f in x if f not in ("who", "how", "n")]:
                prob.append("%s[%d]: 모르는 필드" % (k, i)); ok = False; break
            if x["who"] is not None and x["who"] not in cast_ids:
                prob.append("%s[%d]: who '%s' 는 배역표에 없음" % (k, i, x["who"])); ok = False; break
            h = norm_how(x.get("how"))
            if h is not None and h not in CFG["how"]:
                prob.append("%s[%d]: how '%s' 는 어휘에 없음" % (k, i, h)); ok = False; break
            n = x.get("n")
            if n is not None and (not isinstance(n, str) or len(n) > CFG["noteMax"]):
                prob.append("%s[%d]: n 은 %d자 이하 문자열" % (k, i, CFG["noteMax"])); ok = False; break
            y = {"who": x["who"]}
            if h:
                y["how"] = h; nhow += 1
            if n:
                y["n"] = n
            qq.append(y); nq += 1
        if not ok:
            continue
        if qq:
            e["q"] = qq
        if e:
            clean[k] = e
    if nq >= 8 and nhow > nq * 0.4:
        warn.append("how 가 대사의 %d%% — 과장 아닌지 (GUIDE: 기본은 null)" % (100 * nhow // nq))
    nul = sum(1 for e in clean.values() for x in e.get("q", []) if x["who"] is None)
    if nul:
        warn.append("화자 미상(who=null) %d개" % nul)
    return clean, prob, warn


def check_cli(args):
    targets = []
    for a in args:
        if a == "--all":
            targets += sorted(os.path.relpath(os.path.join(r, f), OUT).replace("\\", "/")[:-5]
                              for r, _, fs in os.walk(OUT) for f in fs if f.endswith(".json"))
        elif "/" not in a.replace("\\", "/"):
            targets += [a + "/" + os.path.basename(j)[:-5] for j in jobfiles(a)]
        else:
            targets.append(a.replace("\\", "/").replace(".json", ""))
    bad, castok = 0, {}
    for t in targets:
        bid = t.split("/")[0]
        jp, op = os.path.join(JOBS, t + ".json"), os.path.join(OUT, t + ".json")
        if not os.path.exists(jp):
            print("%-48s 그런 작업 없음" % t); bad += 1; continue
        if not os.path.exists(op):
            print("%-48s 출력 아직 없음" % t); bad += 1; continue
        if bid not in castok:
            c = load_cast(bid)
            castok[bid] = {m["id"] for m in c["cast"]} if c else set()
        job = json.load(io.open(jp, encoding="utf-8"))
        try:
            got = json.load(io.open(op, encoding="utf-8"))
        except Exception as e:
            print("%-48s JSON 을 읽을 수 없음 (%s)" % (t, e)); bad += 1; continue
        clean, prob, warn = check(job, got, castok[bid])
        for w in warn:
            print("    warn: " + w)
        if prob:
            bad += 1
            print("%-48s 문제 %d" % (t, len(prob)))
            for m in prob[:12]:
                print("    " + m)
        else:
            nq = sum(len(e.get("q", [])) for e in clean.values())
            print("%-48s ok  문단 %d · 대사 %d" % (t, len(clean), nq))
    print("-" * 64)
    print("%d 검사, %d 문제" % (len(targets), bad))
    return bad


# ------------------------------------------------------------------ 런타임 정렬
def align(q, nspans, narrator=None):
    """런타임 정렬 규칙 (tools/tts/act.js 와 짝). 대본 q 와 그 언어에서 센 대사 수로
    대사마다 {who, how} 또는 None(규칙 기반으로 물러남)의 목록과 판정을 돌려준다.
      1. 같은 수              → 순번대로 ('exact')
      2. 다르지만 q 의 who 가 모두 같음 → 모든 대사에 그 who, how 는 모두 같을 때만 ('same')
      3. 그 밖                → 이 문단의 대사는 전부 None ('fallback'). mood·nar 는 그대로 씀.
      (그 언어에서 대사가 0개면: q 가 모두 서술자 몫이면 'same', 아니면 'fallback'.)"""
    if nspans == len(q):
        return list(q), "exact"
    if not q:
        return [None] * nspans, "fallback"
    whos = {x.get("who") for x in q}
    if nspans == 0:   # 번역에서 따옴표가 사라짐: 서술자 몫이었다면 잃은 것이 없다
        return [], ("same" if whos == {narrator} else "fallback")
    hows = {x.get("how") for x in q}
    if len(whos) == 1 and None not in whos:
        h = hows.pop() if len(hows) == 1 else None
        return [{"who": q[0]["who"], "how": h} for _ in range(nspans)], "same"
    return [None] * nspans, "fallback"


def alignment(bid, payload, lang):
    """대본과 한 언어 본문의 대사 수 일치 통계."""
    sp, _ = count_book(bid, lang, payload["qs"].get(lang))
    st = {"exact": 0, "same": 0, "fallback": 0, "unscripted": 0}
    qst = {"exact": 0, "same": 0, "fallback": 0, "unscripted": 0}
    bad = []
    for k, s in sp.items():
        q = payload["p"].get(k, {}).get("q", [])
        if not s and not q:
            continue
        if not q:
            st["unscripted"] += 1; qst["unscripted"] += len(s); bad.append((k, len(q), len(s))); continue
        _, how = align(q, len(s), payload["narrator"])
        st[how] += 1
        qst[how] += len(s)
        if how != "exact":
            bad.append((k, len(q), len(s)))
    # 대본이 있는데 그 언어엔 문단이 없거나 대사가 0 인 것
    for k, e in payload["p"].items():
        if e.get("q") and k not in sp:
            st["fallback"] += 1; bad.append((k, len(e["q"]), 0))
    return st, qst, bad


# ------------------------------------------------------------------ 모으기
def build(bid, quiet=False):
    c = load_cast(bid)
    if c is None:
        print("%-44s 배역표 없음" % bid); return None

    cprob, _ = check_cast(c, bid)
    if cprob:
        print("%-44s 배역표 문제: %s" % (bid, "; ".join(cprob[:3]))); return None
    ids = {m["id"] for m in c["cast"]}
    lang = orig_lang(bid)
    sp, opens = count_book(bid, lang)
    got, problems = {}, []
    for j in jobfiles(bid):
        o = outpath(j)
        if not os.path.exists(o):
            continue
        job = json.load(io.open(j, encoding="utf-8"))
        try:
            raw = json.load(io.open(o, encoding="utf-8"))
        except Exception as e:
            problems.append("%s: 읽을 수 없음 (%r)" % (os.path.basename(o), e)); continue
        clean, prob, _ = check(job, raw, ids)
        problems += ["%s: %s" % (os.path.basename(o), p) for p in prob]
        for k, e in clean.items():
            # 작업을 짠 뒤 원문이 바뀌었으면 그 문단의 q 는 버리고 mood·nar 만 남김
            if "q" in e and len(sp.get(k, [])) != len(e["q"]):
                problems.append("p%s: 원문 대사 수가 바뀜 (%d→%d) — q 버림" % (k, len(e["q"]), len(sp.get(k, []))))
                e = {f: x for f, x in e.items() if f != "q"}
            if e:
                got[k] = e
    need = [k for k, s in sp.items() if s]
    done = [k for k in need if k in got and got[k].get("q")]
    qs = {lang: opens}
    if load_ko(bid):
        qs["ko"] = count_book(bid, "ko")[1]
    keep = ("id", "names", "gender", "age", "role", "traits", "voice")
    payload = {"id": bid, "v": CFG["ver"], "qs": qs, "narrator": c["narrator"],
               "cast": [{f: m[f] for f in keep if f in m} for m in c["cast"]],
               "p": {k: got[k] for k in sorted(got, key=int)},
               "n": len(done), "of": len(need), "cov": round(len(done) / float(len(need) or 1), 4)}
    if not got:
        return payload
    if not os.path.isdir(ACTDATA):
        os.makedirs(ACTDATA)
    js = "SEOJAE.receiveAct(" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ");\n"
    io.open(os.path.join(ACTDATA, bid + ".js"), "w", encoding="utf-8", newline="\n").write(js)
    if not quiet:
        print("%-44s 대사 문단 %4d/%-4d %5.1f%%  %s bytes" % (
            bid, len(done), len(need), payload["cov"] * 100, "{:,}".format(len(js.encode("utf-8")))))
        for p in problems[:8]:
            print("   ! " + p)
        for L in qs:
            report_align(bid, payload, L)
    return payload


def report_align(bid, payload, lang, verbose=False):
    st, qst, bad = alignment(bid, payload, lang)
    tp, tq = sum(st.values()), sum(qst.values())
    print("   %s 대사 수 일치: 문단 %d/%d (%.1f%%) · 같은 화자로 살림 %d · 물러남 %d · 대본 없음 %d"
          "  | 대사 %d/%d (%.1f%%) 대본대로, %d 살림" % (
              lang, st["exact"], tp, 100.0 * st["exact"] / max(1, tp), st["same"], st["fallback"],
              st["unscripted"], qst["exact"], tq, 100.0 * qst["exact"] / max(1, tq), qst["same"]))
    if verbose:
        for k, a, b in bad:
            print("      p%s  대본 %d · %s %d" % (k, a, lang, b))
    return st, qst


def write_index():
    if not os.path.isdir(ACTDATA):
        return 0
    idx = {}
    for f in sorted(os.listdir(ACTDATA)):
        if f.endswith(".js") and f != "index.js":
            s = io.open(os.path.join(ACTDATA, f), encoding="utf-8").read()
            d = json.loads(s[s.index("(") + 1:s.rindex(")")])
            idx[d["id"]] = {"cov": d["cov"]}
    io.open(os.path.join(ACTDATA, "index.js"), "w", encoding="utf-8", newline="\n").write(
        "SEOJAE.actIndex(" + json.dumps(idx, separators=(",", ":")) + ");\n")
    return len(idx)


def status():
    ids = sorted(set(f[:-5] for f in os.listdir(CAST) if f.endswith(".json")) |
                 set(os.listdir(JOBS) if os.path.isdir(JOBS) else []))
    print("%-44s %5s %5s %5s %7s" % ("work", "cast", "jobs", "out", "built"))
    for bid in ids:
        js = jobfiles(bid)
        built = os.path.join(ACTDATA, bid + ".js")
        cov = ""
        if os.path.exists(built):
            s = io.open(built, encoding="utf-8").read()
            cov = "%.1f%%" % (100 * json.loads(s[s.index("(") + 1:s.rindex(")")])["cov"])
        print("%-44s %5s %5d %5d %7s" % (bid, "yes" if os.path.exists(cast_path(bid)) else "-",
                                          len(js), sum(os.path.exists(outpath(j)) for j in js), cov))


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cmd = argv[1] if len(argv) > 1 else "status"
    arg = argv[2] if len(argv) > 2 else ""
    casts = sorted(f[:-5] for f in os.listdir(CAST) if f.endswith(".json")) if os.path.isdir(CAST) else []
    if cmd == "plan":
        tot = 0
        for bid in (casts if arg == "--all" else [arg]):
            n = plan(bid); tot += n
            print("%-44s %3d jobs" % (bid, n))
        print("total jobs:", tot)
    elif cmd == "todo":
        for j in todo(int(arg) if arg else None):
            print(os.path.relpath(j, ROOT).replace("\\", "/"))
    elif cmd == "check":
        return 1 if check_cli(argv[2:] or ["--all"]) else 0
    elif cmd == "cast":
        bad = 0
        for bid in (casts if arg in ("", "--all") else [arg]):
            c = load_cast(bid)
            if c is None:
                print("%-44s 없음" % bid); bad += 1; continue
            prob, warn = check_cast(c, bid)
            print("%-44s %s  배역 %d · 서술자 %s" % (bid, "ok" if not prob else "문제 %d" % len(prob),
                                                  len(c.get("cast", [])), c.get("narrator")))
            for m in prob + ["warn: " + w for w in warn]:
                print("    " + m)
            bad += bool(prob)
        return 1 if bad else 0
    elif cmd == "build":
        for bid in (casts if arg in ("--all", "") else [arg]):
            if jobfiles(bid):
                build(bid)
        print("data/act/index.js  ->  %d works" % write_index())
    elif cmd == "align":
        s = io.open(os.path.join(ACTDATA, arg + ".js"), encoding="utf-8").read()
        d = json.loads(s[s.index("(") + 1:s.rindex(")")])
        for L in d["qs"]:
            report_align(arg, d, L, verbose=True)
    elif cmd == "status":
        status()
    else:
        print(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
