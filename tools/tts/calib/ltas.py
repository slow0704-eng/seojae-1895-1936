"""Long-term average spectrum per voice (1/3-octave), loudness per voice/variant."""
import os, re, glob, json, numpy as np, soundfile as sf, pyloudnorm as pyln
W = "wav"
CF = [63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000]
meter = pyln.Meter(44100)


def trim(x, th=10 ** (-48 / 20)):
    a = np.where(np.abs(x) > th)[0]
    return x[a[0]:a[-1]] if len(a) else x


def ltas(files):
    acc, n = None, 0
    for f in files:
        x, sr = sf.read(f); x = trim(x)
        N = 4096
        fr = np.lib.stride_tricks.sliding_window_view(x, N)[::1024] * np.hanning(N)
        # drop silent frames
        e = (fr ** 2).mean(1); fr = fr[e > e.max() * 1e-3]
        p = (np.abs(np.fft.rfft(fr, axis=1)) ** 2).mean(0)
        acc = p if acc is None else acc + p; n += 1
    f = np.fft.rfftfreq(4096, 1 / 44100)
    out = []
    for c in CF:
        lo, hi = c / 2 ** (1 / 6), c * 2 ** (1 / 6)
        out.append(10 * np.log10(acc[(f >= lo) & (f < hi)].sum() / n + 1e-20))
    out = np.array(out)
    return out - out[CF.index(1000)]


res = {"voices": {}, "loud": {}}
for v in ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]:
    fs = sorted(glob.glob(os.path.join(W, "fp32_8_%s_*_vx.wav" % v)))
    if v == "F1" and not fs:
        fs = sorted(glob.glob(os.path.join(W, "fp32_8_F1_*[0-9].wav")))
    if not fs:
        continue
    L = [meter.integrated_loudness(trim(sf.read(f)[0])) for f in fs]
    res["voices"][v] = [round(x, 1) for x in ltas(fs)]
    res["loud"][v] = round(float(np.mean(L)), 2)
# variant offsets measured on F1 with identical text/noise seeds
for var in ["fp32_8", "mob_8", "mob_6", "f16_6", "fp32pad_8", "mobV32_8"]:
    fs = sorted(glob.glob(os.path.join(W, "%s_F1_*[0-9].wav" % var)))
    if fs:
        res["loud"]["var:" + var] = round(float(np.mean([meter.integrated_loudness(trim(sf.read(f)[0])) for f in fs])), 2)
print("     " + " ".join("%5s" % (c if c < 1000 else "%gk" % (c / 1000)) for c in CF))
for v, a in res["voices"].items():
    print("%-4s " % v + " ".join("%5.1f" % x for x in a), "  LUFS", res["loud"][v])
if res["voices"]:
    m = np.mean(list(res["voices"].values()), axis=0)
    print("mean " + " ".join("%5.1f" % x for x in m))
print({k: v for k, v in res["loud"].items() if k.startswith("var:")})
json.dump(res, open("ltas.json", "w"), indent=1)
