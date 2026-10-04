"""Supertonic 3 캘리브레이션 하네스 — 결과와 해석은 ../CALIB.md

준비 (이 폴더에서):
    git clone --depth 1 https://github.com/supertone-inc/supertonic st      # 공식 py/helper.py
    python -m venv venv && venv/Scripts/pip install onnxruntime numpy soundfile scipy         faster-whisper pyloudnorm pykakasi "fugashi[unidic-lite]"
    m/fp32/{onnx,voice_styles}   Supertone/supertonic-3 @3cadd1ee
    m/int8/                      csukuangfj2/sherpa-onnx-supertonic-3-tts-int8-2026-05-11 @cca5a0e6
    m/mob/                       WilburDev/supertonic-3-mobile @2d53d752
    m/f16/                       likelion-axp/supertonic-3-fp16 @d2f6d3e1

    python calib.py synth variants=fp32,mob steps=4,6,8 [voice=F1 n=3 speed=1.05 tag=_x]
    python calib.py asr dev=cuda           # Whisper large-v3-turbo 받아쓰기 → asr.json
    python calib.py report                 # CER/WER · 같은 잡음 씨앗 fp32@8 대비 멜 거리
    python ltas.py                         # 목소리별 1/3 옥타브 장기 평균 스펙트럼 · 라우드니스
bench.html 은 브라우저 실측(WASM 1·6 스레드, WebGPU fp32/fp16, GPU 상주 잠재 변수)용.
"""
import sys, os, json, time, re, unicodedata
import numpy as np
import onnxruntime as ort
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "st", "py"))
import helper as H
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
M = os.path.join(HERE, "m")
FP = os.path.join(M, "fp32", "onnx")
VARIANTS = {
    "fp32": dict(ve=FP + "/vector_estimator.onnx", voc=FP + "/vocoder.onnx"),
    "s8": dict(ve=M + "/int8/vector_estimator.int8.onnx", voc=M + "/int8/vocoder.int8.onnx"),
    "mob": dict(ve=M + "/mob/vector_estimator.int8.onnx", voc=M + "/int8/vocoder.int8.onnx"),
    "f16": dict(f16=True, dp=M + "/f16/duration_predictor.onnx", te=M + "/f16/text_encoder.onnx",
                ve=M + "/f16/vector_estimator.onnx", voc=M + "/f16/vocoder.onnx"),
    "mobV32": dict(ve=M + "/mob/vector_estimator.int8.onnx", voc=FP + "/vocoder.onnx"),
}
S = json.load(open(os.path.join(HERE, "samples.json"), encoding="utf-8"))
OUT = os.path.join(HERE, "wav")
os.makedirs(OUT, exist_ok=True)


def sess(p, threads):
    o = ort.SessionOptions()
    o.intra_op_num_threads = threads
    o.inter_op_num_threads = 1
    return ort.InferenceSession(p, o, providers=["CPUExecutionProvider"])


class F16:
    """fp16 입출력 모델을 fp32 처럼 부르기"""
    def __init__(self, s): self.s = s
    def run(self, out, feeds):
        f = {k: (v.astype(np.float16) if v.dtype == np.float32 else v) for k, v in feeds.items()}
        return [o.astype(np.float32) for o in self.s.run(out, f)]


def load(variant, threads=1):
    v = VARIANTS[variant]
    cfg = H.load_cfgs(FP)
    tp = H.load_text_processor(FP)
    w = (lambda p: F16(sess(p, threads))) if v.get("f16") else (lambda p: sess(p, threads))
    return H.TextToSpeech(cfg, tp, w(v.get("dp", FP + "/duration_predictor.onnx")),
                          w(v.get("te", FP + "/text_encoder.onnx")), w(v["ve"]), w(v["voc"]))


def bucket(n, q):
    b = q if n <= q * 4 else q * 2 if n <= q * 8 else q * 4
    return -(-n // b) * b


def infer_pad(tts, text, lang, style, steps, speed):
    """워커의 GPU 경로와 같은 모양 칸 맞춤(마스크 0 채움)"""
    ids, _ = tts.text_processor([text], [lang])
    L0 = ids.shape[1]; L = bucket(L0, 32)
    i2 = np.zeros((1, L), np.int64); i2[:, :L0] = ids
    m2 = np.zeros((1, 1, L), np.float32); m2[:, :, :L0] = 1
    dur, *_ = tts.dp_ort.run(None, {"text_ids": i2, "style_dp": style.dp, "text_mask": m2})
    dur = dur / speed
    emb, *_ = tts.text_enc_ort.run(None, {"text_ids": i2, "style_ttl": style.ttl, "text_mask": m2})
    T0 = int(np.ceil(dur[0] * 44100 / 3072)); Tn = bucket(T0, 16)
    x = np.zeros((1, 144, Tn), np.float32); x[:, :, :T0] = np.random.randn(1, 144, T0)
    lm = np.zeros((1, 1, Tn), np.float32); lm[:, :, :T0] = 1
    for s in range(steps):
        x, *_ = tts.vector_est_ort.run(None, {"noisy_latent": x, "text_emb": emb, "style_ttl": style.ttl, "text_mask": m2,
                                             "latent_mask": lm, "current_step": np.array([s], np.float32),
                                             "total_step": np.array([steps], np.float32)})
    w, *_ = tts.vocoder_ort.run(None, {"latent": x})
    return w, dur


def synth_one(tts, text, lang, style, steps, speed, seed):
    """single chunk, deterministic noise so variants are comparable"""
    np.random.seed(seed)
    t = time.perf_counter()
    wav, dur = infer_pad(tts, text, lang, style, steps, speed) if getattr(tts, "pad", False) else tts._infer([text], [lang], style, steps, speed)
    el = time.perf_counter() - t
    n = int(dur[0] * tts.sample_rate)
    return wav[0, :n], el, float(dur[0])


def items(maxn=None):
    for lang in ("ko", "en", "ja"):
        for i, t in enumerate(S[lang][:maxn] if maxn else S[lang]):
            yield lang, i, t


def cmd_synth(args):
    variants = args.get("variants", "fp32,s8,mob,mobV32").split(",")
    steps_l = [int(x) for x in args.get("steps", "4,6,8").split(",")]
    voice = args.get("voice", "F1")
    threads = int(args.get("threads", "1"))
    speed = float(args.get("speed", "1.05"))
    maxn = int(args.get("n", "0")) or None
    tag = args.get("tag", "")
    style = H.load_voice_style([M + "/fp32/voice_styles/%s.json" % voice])
    timing = {}
    tf = os.path.join(HERE, "timings%s%s.json" % (tag, args.get("tf", "")))
    if os.path.exists(tf):
        timing = json.load(open(tf))
    for var in variants:
        tts = load(var.replace("pad", ""), threads)
        tts.pad = var.endswith("pad")
        for steps in steps_l:
            tot_el = tot_dur = 0
            for lang, i, text in items(maxn):
                # chunks the way the reader would: by sentence groups
                wav, el, dur = synth_one(tts, text[:300 if lang == "en" else 120], lang, style, steps, speed, 1000 + i)
                name = "%s_%d_%s_%s%d%s" % (var, steps, voice, lang, i, tag)
                sf.write(os.path.join(OUT, name + ".wav"), wav, tts.sample_rate)
                tot_el += el; tot_dur += dur
            timing["%s_%d_%s_t%d" % (var, steps, voice, threads)] = dict(el=tot_el, dur=tot_dur, rtf=tot_el / tot_dur)
            print("%-7s steps=%d threads=%d  RTF=%.3f  (%.1fs for %.1fs audio)" % (var, steps, threads, tot_el / tot_dur, tot_el, tot_dur), flush=True)
    json.dump(timing, open(tf, "w"), indent=1)


def cmd_asr(args):
    import glob, site
    for sp in site.getsitepackages():
        for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
    from faster_whisper import WhisperModel
    dev = args.get("dev", "cpu")
    model = WhisperModel(args.get("model", "large-v3-turbo"), device=dev,
                         compute_type="int8_float32" if dev == "cuda" else "int8", cpu_threads=int(args.get("thr", "6")))
    af = os.path.join(HERE, "asr.json")
    res = json.load(open(af, encoding="utf-8")) if os.path.exists(af) else {}
    pat = args.get("pat", "")
    PRI = ["fp32_8_", "fp32pad_8_", "mob_8_", "mob_6_", "f16_6_", "mobV32_8_", "fp32_6_", "mob_4_", "fp32_4_", "mobV32_4_", "s8_"]
    def pri(f):
        for i, p in enumerate(PRI):
            if f.startswith(p): return (i, f)
        return (99, f)
    for f in sorted(os.listdir(OUT), key=pri):
        if not f.endswith(".wav") or f in res or pat not in f:
            continue
        lang = re.search(r"_(ko|en|ja)\d+", f).group(1)
        from scipy.signal import resample_poly
        x, sr = sf.read(os.path.join(OUT, f), dtype="float32")
        x = resample_poly(x, 160, 441).astype(np.float32)
        segs, _ = model.transcribe(x, language=lang, beam_size=5, vad_filter=False,
                                   condition_on_previous_text=False)
        res[f] = "".join(s.text for s in segs).strip()
        print(f, res[f][:60], flush=True)
        json.dump(res, open(af, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


_KKS = None
def kana(s):
    global _KKS
    if _KKS is None:
        import pykakasi; _KKS = pykakasi.kakasi()
    return "".join(x["hira"] for x in _KKS.convert(s))


def normtxt(s, lang):
    s = unicodedata.normalize("NFKC", s).lower()
    if lang == "ja":
        s = kana(s)
    s = re.sub(r"[^\w]", "", s) if lang != "en" else re.sub(r"[^\w ]", " ", s)
    return s


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def err(ref, hyp, lang):
    r, h = normtxt(ref, lang), normtxt(hyp, lang)
    if lang == "en":
        r, h = r.split(), h.split()
    return lev(r, h), max(1, len(r))


def mel(w, sr=44100):
    n, hop = 2048, 512
    if len(w) < n:
        w = np.pad(w, (0, n - len(w)))
    fr = np.lib.stride_tricks.sliding_window_view(w, n)[::hop] * np.hanning(n)
    sp = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    # 80 mel bands
    f = np.linspace(0, sr / 2, sp.shape[1])
    mf = lambda x: 2595 * np.log10(1 + x / 700)
    edges = np.linspace(mf(0), mf(sr / 2), 82)
    hz = 700 * (10 ** (edges / 2595) - 1)
    fb = np.zeros((80, len(f)))
    for k in range(80):
        l, c, r = hz[k], hz[k + 1], hz[k + 2]
        fb[k] = np.clip(np.minimum((f - l) / (c - l), (r - f) / (r - c)), 0, None)
    return np.log10(sp @ fb.T + 1e-8)


def cmd_report(args):
    asr = json.load(open(os.path.join(HERE, "asr.json"), encoding="utf-8"))
    refs = {}
    for lang, i, t in items():
        refs["%s%d" % (lang, i)] = (t[:300 if lang == "en" else 120], lang)
    agg = {}
    for f, hyp in asr.items():
        m = re.match(r"([a-z0-9A-Z]+?)_(\d+)_(\w\d)_(ko|en|ja)(\d+)(.*)\.wav", f)
        var, steps, voice, lang, i, tag = m.groups()
        ref, _ = refs[lang + i]
        e, n = err(ref, hyp, lang)
        k = (var, steps, voice, tag, lang)
        a = agg.setdefault(k, [0, 0, 0.0, 0])
        a[0] += e; a[1] += n
        base = os.path.join(OUT, "fp32_8_%s_%s%s%s.wav" % (voice, lang, i, tag))
        if os.path.exists(base) and var != "fp32" or steps != "8":
            if os.path.exists(base):
                x, _ = sf.read(os.path.join(OUT, f)); y, _ = sf.read(base)
                L = min(len(x), len(y)); mx, my = mel(x[:L]), mel(y[:L])
                a[2] += float(np.mean(np.abs(mx - my))); a[3] += 1
    tm = json.load(open(os.path.join(HERE, "timings.json")))
    print("%-7s %-5s %-3s %-4s %-3s %7s %8s" % ("var", "steps", "vc", "tag", "lg", "CER/WER", "melΔ"))
    for k in sorted(agg):
        a = agg[k]
        print("%-7s %-5s %-3s %-4s %-3s %6.1f%% %8.3f" % (k + (100 * a[0] / a[1], a[2] / a[3] if a[3] else 0)))
    for k, v in sorted(tm.items()):
        print("%-24s RTF %.3f" % (k, v["rtf"]))


if __name__ == "__main__":
    a = dict(x.split("=", 1) for x in sys.argv[2:])
    {"synth": cmd_synth, "asr": cmd_asr, "report": cmd_report}[sys.argv[1]](a)
