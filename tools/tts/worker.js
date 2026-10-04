/* 서재 낭독 — 합성 워커 (module worker).
   Supertonic 3 (Supertone, OpenRAIL-M) 을 onnxruntime-web 으로 돌립니다.
   본 스레드가 문장 하나를 보내면 여기서 정규화 → 길이 예측 → 텍스트 인코딩
   → 흐름 정합(steps 회) → 보코더 → 라우드니스 맞춤 → 앞뒤 무음 다듬기까지 해서
   PCM 을 돌려줍니다.

   실행 프로필(본 스레드가 기기를 보고 고름 — calib 실측 근거는 tools/tts/CALIB.md)
     gpu16  WebGPU + fp16 모델   shader-f16 이 있는 GPU      (측정 기기에 없어 미측정)
     gpu32  WebGPU + fp32 모델   shader-f16 이 없는 GPU      RTF 0.08 (GTX 1050)
     cpu8   WASM + int8 모델     WebGPU 가 없는 기기          RTF 0.66 (1스레드, 일꾼 여럿으로 메움)
   큰 모델은 Hugging Face 의 고정 리비전에서 받아 Cache Storage 에 둡니다.

   메시지
     → {type:"init", cfg}            ← {type:"progress", got, total} … {type:"ready", info}
     → {type:"synth", id, text, lang, voice, speed, steps, lufs}
                                     ← {type:"audio", id, pcm, sr, ms, dur}  (pcm 은 transfer)
     ← {type:"error", id?, fatal?, gpu?, message} */
import "./normalize.js";
const N = self.TTSNorm;

let ort = null, CFG = null, S = {}, IDX = null, STYLES = {}, SR = 44100, TTSCFG = null;
let F16 = false, GPU = false;

/* ---------------- fp16 ↔ fp32 ---------------- */
const _f = new Float32Array(1), _u = new Uint32Array(_f.buffer);
function toHalf(a) {
  const o = new Uint16Array(a.length);
  for (let i = 0; i < a.length; i++) {
    _f[0] = a[i];
    const x = _u[0], s = (x >>> 16) & 0x8000, e = ((x >>> 23) & 0xff) - 112, m = x & 0x7fffff;
    if (e <= 0) o[i] = e < -10 ? s : s | ((m | 0x800000) >> (1 - e)) + 0x1000 >> 13;
    else if (e >= 31) o[i] = s | 0x7c00;
    else o[i] = s | (e << 10) | ((m + 0x1000) >> 13);
  }
  return o;
}
function fromHalf(h) {
  if (h instanceof Float32Array) return h;
  if (typeof Float16Array !== "undefined" && h instanceof Float16Array) return Float32Array.from(h);
  const o = new Float32Array(h.length);
  for (let i = 0; i < h.length; i++) {
    const x = h[i], s = x & 0x8000 ? -1 : 1, e = (x >> 10) & 0x1f, m = x & 0x3ff;
    o[i] = e === 0 ? s * m * 5.960464477539063e-8 : e === 31 ? (m ? NaN : s * Infinity) : s * Math.pow(2, e - 15) * (1 + m / 1024);
  }
  return o;
}
const T = (data, dims) => F16 ? new ort.Tensor("float16", toHalf(data), dims) : new ort.Tensor("float32", data, dims);
async function cpuData(t) {
  const d = t.location && t.location !== "cpu" ? await t.getData(true) : t.data;
  return t.type === "float16" ? fromHalf(d) : d;
}

/* ---------------- 내려받기 + 캐시 ---------------- */
async function cached(url, onBytes) {
  let cache = null;
  try { cache = await caches.open(CFG.cacheName); } catch (e) {}
  if (cache) {
    const hit = await cache.match(url);
    if (hit) { const b = await hit.arrayBuffer(); onBytes(b.byteLength); return b; }
  }
  const res = await fetch(url, { mode: "cors" });
  if (!res.ok) throw new Error("내려받기 실패 (" + res.status + ") " + url.split("/").pop());
  const reader = res.body.getReader(), parts = [];
  let got = 0;
  for (;;) {
    const r = await reader.read();
    if (r.done) break;
    parts.push(r.value); got += r.value.byteLength; onBytes(r.value.byteLength);
  }
  const buf = new Uint8Array(got); let o = 0;
  for (const p of parts) { buf.set(p, o); o += p.byteLength; }
  if (cache) {
    try { await cache.put(url, new Response(buf, { headers: { "content-type": "application/octet-stream" } })); }
    catch (e) { /* 저장 공간이 모자라도 이번 세션은 돕니다 */ }
  }
  return buf.buffer;
}

async function init(cfg) {
  CFG = cfg;
  GPU = cfg.ep === "webgpu"; F16 = !!cfg.f16;
  ort = await import(cfg.ortBase + (GPU ? "ort.webgpu.min.mjs" : "ort.wasm.min.mjs"));
  ort.env.wasm.wasmPaths = cfg.ortBase;
  ort.env.wasm.numThreads = cfg.threads || 1;
  ort.env.logLevel = "error";
  const files = cfg.files, total = files.reduce((a, f) => a + f.size, 0);
  let got = 0, last = 0;
  const tick = (n) => {
    got += n;
    const now = Date.now();
    if (now - last > 150 || got >= total) { last = now; postMessage({ type: "progress", got, total }); }
  };
  const bufs = {};
  const q = files.slice();
  async function lane() { for (let f; (f = q.shift());) bufs[f.key] = await cached(f.url, tick); }
  await Promise.all([lane(), lane(), lane()]);

  TTSCFG = JSON.parse(new TextDecoder().decode(bufs.cfg));
  SR = TTSCFG.ae.sample_rate;
  IDX = new Int16Array(bufs.idx);
  const sv = new Float32Array(bufs.voices), per = 50 * 256 + 8 * 16;
  cfg.voiceNames.forEach((name, i) => {
    STYLES[name] = { ttl: T(sv.slice(i * per, i * per + 50 * 256), [1, 50, 256]),
                     dp: T(sv.slice(i * per + 50 * 256, (i + 1) * per), [1, 8, 16]) };
  });
  for (const k of ["dp", "te", "ve", "voc"]) {
    const opt = { executionProviders: [GPU ? "webgpu" : "wasm"], graphOptimizationLevel: "all", logSeverityLevel: 3 };
    /* GPU 에서는 텍스트 임베딩과 잠재 변수를 GPU 에 둔 채로 단계 사이를 넘깁니다 */
    if (GPU && (k === "te" || k === "ve")) opt.preferredOutputLocation = "gpu-buffer";
    try { S[k] = await ort.InferenceSession.create(new Uint8Array(bufs[k]), opt); }
    catch (e) { const err = new Error(String(e && e.message || e)); err.gpu = GPU; throw err; }
    delete bufs[k];
  }
  /* 첫 문장이 셰이더 컴파일을 기다리지 않도록 길이가 다른 두 문장으로 데워 둠 */
  const t0 = performance.now();
  await synth({ text: "준비.", lang: "ko", voice: cfg.voiceNames[0], speed: 1, steps: 2, lufs: -20 });
  await synth({ text: "The library is ready to read aloud to you.", lang: "en", voice: cfg.voiceNames[0], speed: 1, steps: 2, lufs: -20 });
  postMessage({ type: "ready", info: { sr: SR, ep: GPU ? "webgpu" : "wasm", f16: F16, warm: Math.round(performance.now() - t0) } });
}

/* ---------------- 글자 → 토큰 ---------------- */
const RX_EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu;
function prep(text, lang) {
  /* 공식 전처리(helper.js preprocessText)와 같은 순서 */
  let t = text.normalize("NFKD").replace(RX_EMOJI, "");
  const R = { "–": "-", "‑": "-", "—": "-", "_": " ", "“": '"', "”": '"', "‘": "'", "’": "'",
              "´": "'", "`": "'", "[": " ", "]": " ", "|": " ", "/": " ", "#": " ", "→": " ", "←": " " };
  for (const k in R) t = t.split(k).join(R[k]);
  t = t.replace(/[♥☆♡©\\]/g, "");
  t = t.replace(/ ([,.!?;:'])/g, "$1").replace(/""+/g, '"').replace(/''+/g, "'").replace(/\s+/g, " ").trim();
  if (!/[.!?;:,'")\]}…。」』】〉》›»]$/.test(t)) t += ".";
  return "<" + lang + ">" + t + "</" + lang + ">";
}
function ids(str) {
  const a = new BigInt64Array(str.length);
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i);
    a[i] = BigInt(c < IDX.length ? IDX[c] : -1);
  }
  return a;
}
function bucket(n, q) { const b = n <= q * 4 ? q : n <= q * 8 ? q * 2 : q * 4; return Math.ceil(n / b) * b; }
/* 같은 문장은 같은 소리 — 되감아 다시 들어도 억양이 바뀌지 않게 잡음 씨앗을 문장에서 뽑음 */
function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
}
function hash(str) { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

async function synth(m) {
  const t0 = performance.now();
  const style = STYLES[m.voice] || STYLES[CFG.voiceNames[0]];
  const spoken = N.normalize(m.text, m.lang);
  if (!/[\p{L}\p{N}]/u.test(spoken)) return { pcm: new Float32Array(0), ms: 0, dur: 0 };
  /* GPU 는 텐서 모양이 바뀔 때마다 셰이더를 새로 만듭니다. 길이를 몇 개의 칸으로
     올려 맞추고(빈 칸은 마스크 0 — 배치 추론과 같은 방식) 모양이 되풀이되게 합니다. */
  const str = prep(spoken, m.lang), L0 = str.length, L = GPU ? bucket(L0, 32) : L0;
  const id0 = ids(str), idv = new BigInt64Array(L); idv.set(id0);
  const tid = new ort.Tensor("int64", idv, [1, L]);
  const tm = new Float32Array(L); tm.fill(1, 0, L0);
  const tmask = T(tm, [1, 1, L]);

  const dp = await S.dp.run({ text_ids: tid, style_dp: style.dp, text_mask: tmask });
  /* 모델 자체 속도는 0.9–1.2 안에서만(calib: 1.5 에서 한국어 CER 11.7%, 1.75 에서 43%).
     나머지는 음높이를 지키는 시간 늘이기·줄이기(WSOLA)로 — 1.75 에서도 CER 1.6%. */
  const MS = CFG.modelSpeed || [0.9, 1.2];
  const ms = Math.max(MS[0], Math.min(MS[1], m.speed)), stretch = m.speed / ms;
  const dur = (await cpuData(dp.duration))[0] / ms;
  const te = await S.te.run({ text_ids: tid, style_ttl: style.ttl, text_mask: tmask });

  const chunk = TTSCFG.ae.base_chunk_size * TTSCFG.ttl.chunk_compress_factor;
  const wavLen = Math.floor(dur * SR);
  const T0 = Math.max(1, Math.ceil(wavLen / chunk)), Tn = GPU ? bucket(T0, 16) : T0;
  const D = TTSCFG.ttl.latent_dim * TTSCFG.ttl.chunk_compress_factor;
  const x0 = new Float32Array(D * Tn);
  const r = rng(hash(m.voice + "|" + spoken));
  for (let d = 0; d < D; d++) for (let t = 0; t < T0; t += 2) {   /* Box–Muller, 빈 칸은 0 */
    const u1 = Math.max(1e-7, r()), u2 = r(), mag = Math.sqrt(-2 * Math.log(u1));
    x0[d * Tn + t] = mag * Math.cos(2 * Math.PI * u2);
    if (t + 1 < T0) x0[d * Tn + t + 1] = mag * Math.sin(2 * Math.PI * u2);
  }
  let xt = T(x0, [1, D, Tn]), prev = null;
  const lm = new Float32Array(Tn); lm.fill(1, 0, T0);
  const lmask = T(lm, [1, 1, Tn]);
  const tot = T(new Float32Array([m.steps]), [1]);
  for (let s = 0; s < m.steps; s++) {
    const out = await S.ve.run({
      noisy_latent: xt, text_emb: te.text_emb, style_ttl: style.ttl, latent_mask: lmask, text_mask: tmask,
      current_step: T(new Float32Array([s]), [1]), total_step: tot });
    if (prev && prev.dispose) prev.dispose();
    xt = prev = out.denoised_latent;
    if (!GPU) xt = new ort.Tensor(xt.type, xt.data, xt.dims);
  }
  const voc = await S.voc.run({ latent: xt });
  if (prev && prev.dispose) prev.dispose();
  if (te.text_emb.dispose) te.text_emb.dispose();
  const wav = await cpuData(voc.wav_tts);
  let pcm = Float32Array.from(wav.subarray(0, Math.min(wavLen, wav.length)));
  if (Math.abs(stretch - 1) > 0.02) pcm = wsola(pcm, stretch);
  pcm = master(pcm, m.lufs, m.expect);
  return { pcm, ms: performance.now() - t0, dur: pcm.length / SR };
}

/* ---------------- WSOLA ----------------
   40ms 해닝 창을 반씩 겹쳐 다시 놓되, 각 창을 ±12ms 안에서 앞 창의 자연스러운 이음과
   가장 닮은 자리(상관 최대)로 옮겨 붙입니다. factor>1 이면 빨라짐. */
function wsola(x, factor) {
  const N = Math.round(SR * 0.04) & ~1, Hs = N >> 1, Ha = Hs * factor, tol = Math.round(SR * 0.012);
  const w = new Float32Array(N); for (let i = 0; i < N; i++) w[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (N - 1));
  const outLen = Math.floor(x.length / factor);
  const pad = tol + N + Math.ceil(Ha) + N;
  const xp = new Float32Array(tol + x.length + pad); xp.set(x, tol);
  const y = new Float32Array(outLen + 2 * N), ws = new Float32Array(outLen + 2 * N);
  let prev = 0, opos = 0;
  for (let k = 0; ; k++) {
    const nom = Math.round(k * Ha);
    if (nom >= x.length) break;
    let best = 0;
    if (k > 0) {
      /* 상관은 두 칸씩 건너 계산 — 소리에는 차이 없고 4배 빠름 */
      const t0 = tol + prev + Hs, lo = nom - tol;
      let bc = -Infinity;
      for (let d = 0; d <= 2 * tol; d += 2) {
        const s0 = tol + lo + d; let c = 0;
        for (let i = 0; i < N; i += 2) c += xp[s0 + i] * xp[t0 + i];
        if (c > bc) { bc = c; best = lo + d - nom; }
      }
    }
    const pos = tol + nom + best;
    for (let i = 0; i < N; i++) { y[opos + i] += xp[pos + i] * w[i]; ws[opos + i] += w[i]; }
    prev = nom + best; opos += Hs;
  }
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) out[i] = ws[i] > 1e-3 ? y[i] / ws[i] : y[i];
  return out;
}

/* ---------------- 라우드니스 · 다듬기 ----------------
   문장마다 생성 레벨이 몇 dB 씩 흔들립니다(calib: 문장 간 표준편차). 귀는 그 흔들림을
   '기계'로 듣기 때문에 ITU-R BS.1770 K-가중 라우드니스(400ms 블록, −70 LUFS 절대 게이트,
   −10 상대 게이트)로 재고 목표치로 맞춥니다. 짧은 문장은 블록이 적어 상한을 둡니다. */
function kweights(fs) {
  /* pyloudnorm 과 같은 해석적 설계 — 48k 계수를 44.1k 에 그대로 쓰면 어긋남 */
  let G = 4.0, Q = 1 / Math.SQRT2, fc = 1500;
  let A = Math.pow(10, G / 40), w = 2 * Math.PI * fc / fs, al = Math.sin(w) / (2 * Q), c = Math.cos(w);
  let a0 = (A + 1) - (A - 1) * c + 2 * Math.sqrt(A) * al;
  const shelf = { b0: A * ((A + 1) + (A - 1) * c + 2 * Math.sqrt(A) * al) / a0, b1: -2 * A * ((A - 1) + (A + 1) * c) / a0,
                  b2: A * ((A + 1) + (A - 1) * c - 2 * Math.sqrt(A) * al) / a0, a1: 2 * ((A - 1) - (A + 1) * c) / a0,
                  a2: ((A + 1) - (A - 1) * c - 2 * Math.sqrt(A) * al) / a0 };
  fc = 38; Q = 0.5; w = 2 * Math.PI * fc / fs; al = Math.sin(w) / (2 * Q); c = Math.cos(w); a0 = 1 + al;
  const hp = { b0: (1 + c) / 2 / a0, b1: -(1 + c) / a0, b2: (1 + c) / 2 / a0, a1: -2 * c / a0, a2: (1 - al) / a0 };
  return [shelf, hp];
}
function filt(x, f) {
  const y = new Float32Array(x.length); let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < x.length; i++) {
    const v = f.b0 * x[i] + f.b1 * x1 + f.b2 * x2 - f.a1 * y1 - f.a2 * y2;
    x2 = x1; x1 = x[i]; y2 = y1; y1 = v; y[i] = v;
  }
  return y;
}
let KW = null;
function lufs(x) {
  KW = KW || kweights(SR);
  const y = filt(filt(x, KW[0]), KW[1]);
  const blk = Math.round(0.4 * SR), hop = Math.round(0.1 * SR), z = [];
  for (let s = 0; s + blk <= y.length; s += hop) {
    let e = 0; for (let i = s; i < s + blk; i++) e += y[i] * y[i];
    z.push(e / blk);
  }
  if (!z.length) { let e = 0; for (let i = 0; i < y.length; i++) e += y[i] * y[i]; z.push(e / Math.max(1, y.length)); }
  const L = (p) => -0.691 + 10 * Math.log10(p + 1e-12);
  let g = z.filter((p) => L(p) > -70);
  if (!g.length) return -70;
  const rel = L(g.reduce((a, b) => a + b, 0) / g.length) - 10;
  g = g.filter((p) => L(p) > rel);
  return L(g.reduce((a, b) => a + b, 0) / g.length);
}
function master(x, target, expect) {
  /* 1) 앞뒤 무음: −48 dBFS 아래를 걷되 앞 20ms·뒤 60ms 는 남겨 자음과 숨 꼬리를 살림 */
  const th = Math.pow(10, -48 / 20), win = Math.round(0.005 * SR);
  let a = 0, b = x.length;
  const loud = (i) => { let m = 0; for (let k = i; k < Math.min(x.length, i + win); k++) m = Math.max(m, Math.abs(x[k])); return m > th; };
  while (a < b && !loud(a)) a += win;
  while (b > a && !loud(Math.max(0, b - win))) b -= win;
  a = Math.max(0, a - Math.round(0.02 * SR)); b = Math.min(x.length, b + Math.round(0.06 * SR));
  x = x.slice(a, b);
  if (!x.length) return x;
  /* 2) 라우드니스 맞춤 */
  /* 목소리·프로필마다 잰 평균 라우드니스(expect)로 기준 이득을 정하고, 문장별로는
     ±3 dB 안에서만 고칩니다 — 속삭임과 외침의 차이까지 지우지 않게. */
  const L = lufs(x), tg = target || -21;
  const base = expect != null ? tg - expect : tg - L, lo = base - 3, hi = base + 3;
  let g = Math.pow(10, Math.max(lo, Math.min(hi, tg - L)) / 20);
  /* 첨두는 −2 dBFS 아래로 — 뒤의 압축기·천장이 일할 여유. 넘치면 이득을 줄임 */
  let pk = 0; for (let i = 0; i < x.length; i++) { const v = Math.abs(x[i]); if (v > pk) pk = v; }
  if (pk * g > 0.79) g = 0.79 / pk;
  /* 3) 5ms 페이드 — 이어 붙일 때 딸깍 소리 방지 */
  const f = Math.min(Math.round(0.005 * SR), x.length >> 1);
  for (let i = 0; i < x.length; i++) {
    let v = x[i] * g;
    if (i < f) v *= i / f; else if (i > x.length - f) v *= (x.length - i) / f;
    x[i] = v;
  }
  return x;
}

/* ---------------- 메시지 ---------------- */
let chain = Promise.resolve();
self.onmessage = (e) => {
  const m = e.data;
  if (m.type === "init") {
    chain = chain.then(() => init(m.cfg)).catch((err) => postMessage({
      type: "error", fatal: true, gpu: !!(err && err.gpu) || GPU, message: String(err && err.message || err) }));
  } else if (m.type === "synth") {
    chain = chain.then(async () => {
      try {
        const r = await synth(m);
        postMessage({ type: "audio", id: m.id, pcm: r.pcm, sr: SR, ms: r.ms, dur: r.dur }, [r.pcm.buffer]);
      } catch (err) {
        postMessage({ type: "error", id: m.id, gpu: GPU, message: String(err && err.message || err) });
      }
    });
  }
};
