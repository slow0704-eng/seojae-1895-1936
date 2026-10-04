import numpy as np
def wsola(x, factor, sr=44100, frame_ms=40, tol_ms=12):
    """factor>1: faster (shorter). Pitch preserved."""
    N = int(sr*frame_ms/1000) & ~1; Hs = N//2; Ha = Hs*factor; tol = int(sr*tol_ms/1000)
    w = np.hanning(N)
    outlen = int(len(x)/factor)+N
    y = np.zeros(outlen+N); ws = np.zeros(outlen+N)
    xp = np.concatenate([np.zeros(tol), x, np.zeros(N+tol+int(Ha)+N)])
    prev = 0  # actual input pos of previous frame (in xp coords, minus tol)
    k = 0; opos = 0
    while True:
        nom = int(round(k*Ha))
        if nom >= len(x): break
        if k == 0: best = 0
        else:
            target = xp[tol+prev+Hs: tol+prev+Hs+N]
            lo = nom - tol; seg = xp[tol+lo: tol+lo+N+2*tol]
            # correlate (decimated by 2)
            t = target[::2]; s = seg
            c = np.correlate(s[::2], t, mode='valid')
            best = lo + 2*int(np.argmax(c)) - nom
        pos = nom + best
        y[opos:opos+N] += xp[tol+pos:tol+pos+N]*w; ws[opos:opos+N] += w
        prev = pos; opos += Hs; k += 1
    ws[ws < 1e-3] = 1
    return (y/ws)[:int(len(x)/factor)]
