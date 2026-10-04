# -*- coding: utf-8 -*-
"""낭독 자산 꾸리기 — 서재/tts/ 의 작은 파일과 config.json 의 모델 목록.

    python tts/pack.py

Supertonic 3 공식 저장소(고정 리비전)에서 목소리 10개·글자표·설정을 받아
목소리는 float32 한 덩어리(voices.bin), 글자표는 int16(indexer.bin)으로 줄입니다.
JSON 으로는 3MB 가 넘던 것이 650KB 가 됩니다. 큰 ONNX 네 개는 저장소에 넣지 않고
config.json 의 files 에 고정 리비전 URL 과 크기만 적어 둡니다 — 워커가 그 URL 에서
받아 브라우저 Cache Storage 에 둡니다.
"""
import io, os, json, struct, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "서재", "tts")

OFFICIAL = ("Supertone/supertonic-3", "3cadd1ee6394adea1bd021217a0e650ede09a323")
VOICES = ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]


def url(repo, rev, path):
    return "https://huggingface.co/%s/resolve/%s/%s" % (repo, rev, path)


def get(u):
    with urllib.request.urlopen(u) as r:
        return r.read()


def size(u):
    req = urllib.request.Request(u, method="HEAD")
    with urllib.request.urlopen(req) as r:
        return int(r.headers.get("x-linked-size") or r.headers["content-length"])


def main():
    cfg_path = os.path.join(HERE, "config.json")
    cfg = json.load(io.open(cfg_path, encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    repo, rev = OFFICIAL

    tts = get(url(repo, rev, "onnx/tts.json"))
    open(os.path.join(OUT, "tts.json"), "wb").write(tts)

    idx = json.loads(get(url(repo, rev, "onnx/unicode_indexer.json")))
    assert max(idx) < 32768 and min(idx) >= -1
    open(os.path.join(OUT, "indexer.bin"), "wb").write(struct.pack("<%dh" % len(idx), *idx))

    blob = io.BytesIO()
    for v in VOICES:
        j = json.loads(get(url(repo, rev, "voice_styles/%s.json" % v)))
        for k, dims in (("style_ttl", [1, 50, 256]), ("style_dp", [1, 8, 16])):
            assert j[k]["dims"] == dims, (v, k, j[k]["dims"])
            flat = []
            def walk(x):
                if isinstance(x, list):
                    for y in x: walk(y)
                else: flat.append(float(x))
            walk(j[k]["data"])
            blob.write(struct.pack("<%df" % len(flat), *flat))
    open(os.path.join(OUT, "voices.bin"), "wb").write(blob.getvalue())

    lic = get(url(repo, rev, "LICENSE"))
    open(os.path.join(OUT, "LICENSE-model.txt"), "wb").write(lic)

    cfg["shared"] = [{"key": "cfg", "url": "tts.json", "size": len(tts)},
                     {"key": "idx", "url": "indexer.bin", "size": len(idx) * 2},
                     {"key": "voices", "url": "voices.bin", "size": len(blob.getvalue())}]
    for name, prof in cfg["profiles"].items():
        prof["files"] = []
        for key, (r, rv, path) in zip(["dp", "te", "ve", "voc"], prof["models"]):
            u = url(r, rv, path)
            prof["files"].append({"key": key, "url": u, "size": size(u)})
        print("%-6s %12s" % (name, "{:,}".format(sum(f["size"] for f in prof["files"]))))
    cfg.pop("files", None)
    io.open(cfg_path, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
