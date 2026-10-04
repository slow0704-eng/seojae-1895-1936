# -*- coding: utf-8 -*-
"""일본어 원작의 읽기(요미) — 낭독용.

    pip install "fugashi[unidic-lite]"
    python tts/yomi.py

Supertonic 은 글자 단위 모델이라 한자를 '보고' 읽습니다. 흔한 한자는 맞게 읽지만
옛 소설의 한자(乞食·梯子·蹲る·云う)는 엉뚱하게 읽습니다 — calib 에서 받아쓰기
가나 오류율이 11.6% 였습니다(tools/tts/CALIB.md). 형태소 분석기(MeCab + UniDic)로
문맥에 맞는 읽기를 미리 구해 두고, 낭독할 때 한자 낱말만 히라가나로 바꿔 넘깁니다.
아오조라 문고의 후리가나(<ruby>)가 달린 곳은 원문의 읽기를 그대로 씁니다.

출력: 서재/data/yomi/<id>.js
  SEOJAE.receiveYomi({"id":…, "p":{"<data-p>":[[시작, 길이, "よみ"], …]}, "h":{"<h2 id>":[…]}})
위치는 화면 글자(루비의 <rt> 를 뺀 textContent) 기준이라 리더의 문장 나누기와 맞습니다.
빌드(build.py)는 표준 라이브러리만 쓰므로 이 단계는 따로 돌리고 결과를 저장소에 둡니다.
"""
import os, re, io, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "서재", "data")
OUT = os.path.join(DATA, "yomi")

KANJI = re.compile(r"[㐀-䶿一-鿿豈-﫿々〆ヶ]")
RX_RUBY = re.compile(r"<ruby>(.*?)<rt>(.*?)</rt></ruby>", re.S)
RX_TAG = re.compile(r"<[^>]+>")


def display(inner):
    """<p> 안쪽 HTML → (화면 글자, 루비 본자 구간들)"""
    out, spans, pos = [], [], 0
    for m in RX_RUBY.finditer(inner):
        pre = html.unescape(RX_TAG.sub("", inner[pos:m.start()]))
        out.append(pre)
        start = sum(len(x) for x in out)
        base = html.unescape(RX_TAG.sub("", m.group(1)))
        out.append(base)
        spans.append((start, start + len(base)))
        pos = m.end()
    out.append(html.unescape(RX_TAG.sub("", inner[pos:])))
    return "".join(out), spans


def hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def readings(tagger, text, ruby):
    subs, pos = [], 0
    for w in tagger(text):
        s = w.surface
        i = text.find(s, pos)
        if i < 0:
            continue
        pos = i + len(s)
        if not KANJI.search(s):
            continue
        if any(a < i + len(s) and i < b for a, b in ruby):
            continue
        r = getattr(w.feature, "kana", None) or getattr(w.feature, "pron", None)
        if not r or r == "*":
            continue
        subs.append([i, len(s), hira(r)])
    return subs


def main():
    import fugashi
    tagger = fugashi.Tagger()
    idx = io.open(os.path.join(ROOT, "서재", "index.html"), encoding="utf-8").read()
    man = json.loads(re.search(r"var MANIFEST=(\[.*?\]);", idx).group(1))
    titles = {w["id"]: w["title"] for w in man if w.get("orig") == "ja"}
    os.makedirs(OUT, exist_ok=True)
    made = 0
    for f in sorted(os.listdir(DATA)):
        if not f.endswith(".js"):
            continue
        src = io.open(os.path.join(DATA, f), encoding="utf-8").read()
        j = json.loads(src[src.index("(") + 1:src.rindex(")")])
        body = j.get("html", "")
        if "<ruby>" not in body and not re.search(r"[\u3040-\u30ff]", body[:4000]):
            continue
        res = {"id": j["id"], "p": {}, "h": {}}
        title = titles.get(j["id"], "")
        if title:
            res["t"] = readings(tagger, title, [])
        for m in re.finditer(r'<p[^>]*\sdata-p="(\d+)"[^>]*>(.*?)</p>', body, re.S):
            text, ruby = display(m.group(2))
            subs = readings(tagger, text, ruby)
            if subs:
                res["p"][m.group(1)] = subs
        for m in re.finditer(r'<h2 class="(?:chapter|part)" id="([^"]+)"[^>]*>(.*?)</h2>', body, re.S):
            text, ruby = display(m.group(2))
            subs = readings(tagger, text, ruby)
            if subs:
                res["h"][m.group(1)] = subs
        js = "SEOJAE.receiveYomi(" + json.dumps(res, ensure_ascii=False, separators=(",", ":")) + ");\n"
        with open(os.path.join(OUT, j["id"] + ".js"), "wb") as fh:
            fh.write(js.encode("utf-8"))
        n = sum(len(v) for v in res["p"].values())
        print("%-28s %6d 낱말  %9s bytes" % (j["id"], n, "{:,}".format(len(js))))
        made += 1
    print("%d works" % made)


if __name__ == "__main__":
    main()
