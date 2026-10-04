/* ============================================================
   낭독 — 책 읽어주기
   ------------------------------------------------------------
   엔진 둘.
     neural  Supertonic 3 를 브라우저 안(워커 · WebGPU 또는 WASM)에서 돌립니다. 처음 한 번
             모델을 받아 Cache Storage 에 두고, 그 뒤로는 오프라인으로도 됩니다.
             수치의 근거는 tools/tts/CALIB.md.
     system  기기의 speechSynthesis. file:// 로 열었거나 신경망 엔진을 못 쓰는
             기기, 또는 받기 전 바로 듣고 싶을 때.
   어느 쪽이든 같은 문장 목록을 같은 순서로 읽고, 지금 읽는 문장을 CSS Custom
   Highlight 로 칠합니다(DOM 을 건드리지 않으므로 위치 저장 계산이 그대로).
   소리는 Web Audio 한 그래프 — 문장 사이 쉼은 구두점과 문단·장 경계에 따라
   정해진 길이만큼 실제 시계로 예약해서 끊김 없이 이어 붙입니다.
   ============================================================ */
var NR_CFG = __NR_CFG__;
var NR = {
  state: "off",            /* off | prep | play | pause */
  engine: null,            /* "neural" | "system" */
  workers: [], pend: {}, seq: 0,
  ctx: null, out: null, room: null, amb: null,
  q: [],                   /* 다음 문장들 (생성 요청됨) */
  cur: null,               /* 지금 소리 나는 문장 */
  cursor: null,            /* 다음에 꺼낼 위치 {b, s} */
  blocks: [], segCache: {},
  playT: 0, follow: true, followHoldT: 0,
  rtf: [], steps: 0, gen: 0, errs: 0, sleepAt: 0, sleepCh: -1, bufs: {}, bufKeys: []
};
var NR_VOICES = ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"];

/* 일본어 원작의 한자 읽기(tools/tts/yomi.py) — 처음 낭독할 때 한 번 불러옴 */
var NR_YOMI = {}, NR_YOMI_WAIT = {};
SJ.receiveYomi = function (d) {
  NR_YOMI[d.id] = d;
  var cbs = NR_YOMI_WAIT[d.id] || []; delete NR_YOMI_WAIT[d.id];
  cbs.forEach(function (cb) { cb(); });
};
function nrLoadYomi(cb) {
  var id = WORK.id;
  if (WORK.orig !== "ja" || nrLangPick() !== "ja" || NR_YOMI[id]) return cb();
  if (NR_YOMI_WAIT[id]) return NR_YOMI_WAIT[id].push(cb);
  NR_YOMI_WAIT[id] = [cb];
  inject("data/yomi/" + encodeURIComponent(id) + ".js", function () {
    var cbs = NR_YOMI_WAIT[id] || []; delete NR_YOMI_WAIT[id]; NR_YOMI[id] = { p: {}, h: {} };
    cbs.forEach(function (c) { c(); });
  });
}
function nrCanNeural() {
  return /^https?:$/.test(location.protocol) && typeof WebAssembly === "object" &&
         "caches" in window && typeof Worker === "function" && !!window.AudioContext &&
         !(navigator.deviceMemory && navigator.deviceMemory < 2);
}
function nrCanSystem() { return "speechSynthesis" in window && typeof SpeechSynthesisUtterance === "function"; }

/* ---------------- 읽을 덩어리 ----------------
   보이는 언어를 그대로 읽습니다. 대역(both)에서는 설정의 '낭독 언어'를 따릅니다. */
function nrLangPick() {
  if (WORK.lang === "en") return WORK.orig;
  if (WORK.lang === "ko") return "ko";
  return S.nrBoth === "orig" ? WORK.orig : "ko";
}
function nrBuildBlocks() {
  var want = nrLangPick(), out = [];
  var tp = $("#book .titlepage");
  if (tp) {
    var h1 = tp.querySelector("h1"), by = tp.querySelector(".byline");
    if (h1) out.push({ el: h1, lang: tp.lang === "ko" ? "ko" : WORK.orig, kind: "title", p: -1 });
    if (by) out.push({ el: by, lang: tp.lang === "ko" ? "ko" : (WORK.lang === "en" ? "en" : "ko"), kind: "by", p: -1 });
  }
  $$("#book h2, #book p[data-p]").forEach(function (el) {
    if (el.tagName === "H2") {
      /* #book 자체에 lang=ko 가 붙으므로 조상은 보지 않음 — 번역 안 된 장 제목은 원문 */
      var hl = el.getAttribute("lang") || WORK.orig;
      if (WORK.lang === "both") {
        var tr = el.querySelector(".h-tr");
        if (want === "ko" && tr) { out.push({ el: tr, lang: "ko", kind: "h", p: -1 }); return; }
      }
      out.push({ el: el, lang: hl === "ko" ? "ko" : WORK.orig, kind: "h", p: -1, skipTr: true });
      return;
    }
    var p = +el.dataset.p, use = el, lang = el.dataset.ko ? "ko" : WORK.orig;
    if (WORK.lang === "both" && want === "ko") {
      var sib = el.nextElementSibling;
      if (sib && sib.dataset.tr === String(p)) { use = sib; lang = "ko"; }
    }
    out.push({ el: use, lang: lang, kind: "p", p: p });
  });
  if (!WORK.orig || WORK.orig === "en") out.forEach(function (b) { if (b.lang !== "ko" && b.lang !== "ja") b.lang = "en"; });
  return out;
}

/* 문단 → [보이는 글자, 읽을 글자] 토큰. 루비는 보이는 건 본자, 읽는 건 후리가나. */
function nrTokens(el, skipTr) {
  var toks = [], nodes = [];
  (function walk(n) {
    for (var c = n.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 3) {
        nodes.push({ node: c, start: toks.length });
        for (var i = 0; i < c.data.length; i++) toks.push({ d: c.data[i], s: c.data[i] });
      } else if (c.nodeType === 1) {
        var tn = c.tagName;
        if (tn === "RT" || tn === "RP") continue;
        if (skipTr && c.classList.contains("h-tr")) continue;
        if (tn === "RUBY") {
          var rt = c.querySelector("rt"), base = [];
          (function wb(m) { for (var k = m.firstChild; k; k = k.nextSibling) {
            if (k.nodeType === 3) base.push(k); else if (k.nodeType === 1 && k.tagName !== "RT" && k.tagName !== "RP") wb(k); } })(c);
          var reading = rt ? rt.textContent : "", first = true;
          base.forEach(function (tnode) {
            nodes.push({ node: tnode, start: toks.length });
            for (var j = 0; j < tnode.data.length; j++) {
              toks.push({ d: tnode.data[j], s: first ? reading : "" }); first = false;
            }
          });
          continue;
        }
        walk(c);
      }
    }
  })(el);
  return { toks: toks, nodes: nodes, text: toks.map(function (t) { return t.d; }).join("") };
}
function nrSegs(bi) {
  var b = NR.blocks[bi]; if (!b) return [];
  if (NR.segCache[bi]) return NR.segCache[bi];
  var tk = nrTokens(b.el, b.skipTr);
  /* 한자 낱말을 미리 구한 읽기로 — 후리가나가 있는 곳은 이미 읽기가 들어 있음 */
  var Y = b.lang === "ja" && NR_YOMI[WORK.id];
  var ys = Y && (b.kind === "p" ? Y.p[b.p] : b.kind === "h" && b.el.id ? Y.h[b.el.id] : b.kind === "title" ? Y.t : null);
  if (ys) ys.forEach(function (y) {
    var t0 = tk.toks[y[0]]; if (!t0 || t0.s !== t0.d) return;
    for (var k = 1; k < y[1]; k++) { var tt = tk.toks[y[0] + k]; if (!tt || tt.s !== tt.d) return; }
    t0.s = y[2];
    for (k = 1; k < y[1]; k++) tk.toks[y[0] + k].s = "";
  });
  var rs = TTSNorm.sentences(tk.text, b.lang);
  var segs = rs.map(function (r, i) {
    var sp = "";
    for (var k = r[0]; k < r[1]; k++) sp += tk.toks[k].s;
    return { b: bi, i: i, a: r[0], z: r[1], text: sp, lang: b.lang, last: i === rs.length - 1 };
  }).filter(function (s) { return /[\p{L}\p{N}]/u.test(s.text); });
  segs.forEach(function (s, i) { s.i = i; s.last = i === segs.length - 1; });
  segs.nodes = tk.nodes;
  NR.segCache[bi] = segs;
  return segs;
}
function nrRange(seg) {
  var sc = NR.segCache[seg.b]; if (!sc || sc.indexOf(seg) < 0) return null;
  var nodes = sc.nodes, r = document.createRange(), set = 0;
  for (var i = 0; i < nodes.length; i++) {
    var n = nodes[i], len = n.node.data.length;
    if (!set && seg.a < n.start + len) { r.setStart(n.node, Math.max(0, seg.a - n.start)); set = 1; }
    if (set && seg.z <= n.start + len) { r.setEnd(n.node, Math.max(0, seg.z - n.start)); return r; }
  }
  if (set) { var ln = nodes[nodes.length - 1]; r.setEnd(ln.node, ln.node.data.length); return r; }
  return null;
}
/* 쉼 — 문장 끝 구두점과 경계에 따라. 사람 낭독자의 평균값에서 출발해
   측정(calib)으로 맞춘 값. 말 속도를 올리면 쉼도 같은 비율로 줄입니다. */
function nrGap(seg, next) {
  var P = NR_CFG.pause, t;
  var blk = NR.blocks[seg.b];
  if (!seg.last) {
    var tail = seg.text.replace(/[\s”’"'」』）)]+$/, "").slice(-1);
    t = /[?？!！]/.test(tail) ? P.q : /[,，、;:]/.test(tail) ? P.comma : /…/.test(tail) ? P.ellip : P.sent;
  } else if (blk.kind === "title" || blk.kind === "by") t = P.title;
  else if (blk.kind === "h") t = P.head;
  else if (next && NR.blocks[next.b] && NR.blocks[next.b].kind === "h") t = P.chapter;
  else t = P.para;
  /* 대사가 끝나거나 시작하는 자리(말하는 이가 바뀌는 자리)는 숨 한 번 더 */
  if (next && (/[”"」』]\s*$/.test(seg.text) || /^\s*[“"「『]/.test(next.text))) t += P.turn;
  return t / Math.max(0.7, S.nrRate);
}

/* 다음 문장 꺼내기 */
function nrNext() {
  var c = NR.cursor; if (!c) return null;
  for (var guard = 0; guard < 5000 && c.b < NR.blocks.length; guard++) {
    var segs = nrSegs(c.b);
    if (c.s < segs.length) { var s = segs[c.s]; NR.cursor = { b: c.b, s: c.s + 1 }; return s; }
    c = { b: c.b + 1, s: 0 };
  }
  NR.cursor = null;
  return null;
}
function nrPeek() {
  var c = NR.cursor; if (!c) return null;
  for (var g = 0; g < 50 && c.b < NR.blocks.length; g++) {
    var segs = nrSegs(c.b);
    if (c.s < segs.length) return segs[c.s];
    c = { b: c.b + 1, s: 0 };
  }
  return null;
}

/* ---------------- 시작 위치 ----------------
   읽기선(화면 위 18%) 아래 첫 문단, 그 안에서도 읽기선이 걸린 문장부터. */
function nrStartFromView() {
  var line = READLINE() + 4, best = 0;
  for (var i = 0; i < NR.blocks.length; i++) {
    var r = NR.blocks[i].el.getBoundingClientRect();
    if (r.bottom >= line) { best = i; break; }
    best = i;
  }
  if (scrollY < 40) best = 0;
  var segs = nrSegs(best), si = 0;
  for (var k = 0; k < segs.length; k++) {
    var rg = nrRange(segs[k]); if (!rg) continue;
    var rr = rg.getBoundingClientRect();
    if (rr.bottom >= line) { si = k; break; }
  }
  return { b: best, s: si };
}

/* ---------------- 오디오 그래프 ----------------
   목소리 → 럼블 컷(70Hz) → 진흙 대역 정리(250Hz) → 존재감(3.2kHz) → 치찰음 눌림(7.5kHz)
          → 부드러운 압축 → ┬ 드라이 ─────────────────────┬→ 천장(소프트 클립) → 출력
                            └ 방울림(합성 IR, 0.6s) ──────┘
   값의 출처는 calib — 10개 목소리의 장기 평균 스펙트럼(LTAS)을 표준 낭독 음성
   스펙트럼에 대 보고 나온 평균 보정, 그리고 PULSE·16 마스터 체인의 IR·천장 커브. */
function nrIR(ctx, sec, decay, pre, damp) {
  var rate = ctx.sampleRate, len = Math.floor(rate * sec), pd = Math.floor(rate * pre);
  var buf = ctx.createBuffer(2, len + pd, rate);
  for (var ch = 0; ch < 2; ch++) {
    var d = buf.getChannelData(ch), lp = 0, seed = 1 + ch * 7919;
    for (var i = 0; i < len; i++) {
      seed = (seed * 16807) % 2147483647;
      var t = i / len, w = seed / 1073741823.5 - 1;
      lp += (w - lp) * damp; d[pd + i] = lp * Math.pow(1 - t, decay) * (1 - t);
    }
  }
  return buf;
}
function nrCeiling(thr, ceil) {
  var n = 4096, c = new Float32Array(n), k = ceil - thr;
  for (var i = 0; i < n; i++) {
    var x = i / (n / 2) - 1, a = Math.abs(x);
    c[i] = a <= thr ? x : Math.sign(x) * (thr + k * Math.tanh((a - thr) / k));
  }
  return c;
}
function nrAudio() {
  if (NR.ctx) { if (NR.ctx.state === "suspended") NR.ctx.resume(); return NR.ctx; }
  var ctx = NR.ctx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: "playback", sampleRate: 44100 });
  var E = NR_CFG.eq, bq = function (type, f, q, g) { var b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; if (g != null) b.gain.value = g; return b; };
  var inp = ctx.createGain();
  /* 목소리별 보정(깎기만): calib 의 1/3 옥타브 장기 평균 스펙트럼에서 같은 성별 평균보다
     2 dB 넘게 튀는 대역의 절반만큼. 쉿소리(F3), 웅웅거림(M5·F5)을 다듬되 음색은 살림 */
  NR.veq = [bq("lowshelf", 180, 0.7, 0), bq("peaking", 330, 1.0, 0), bq("peaking", 3000, 0.9, 0), bq("peaking", 8000, 1.4, 0)];
  var chain = NR.veq.concat([bq("highpass", E.hp, 0.7), bq("peaking", E.mud.f, E.mud.q, E.mud.g),
               bq("peaking", E.pres.f, E.pres.q, E.pres.g), bq("highshelf", E.air.f, 0.7, E.air.g),
               bq("peaking", E.ess.f, E.ess.q, E.ess.g)]);
  var comp = ctx.createDynamicsCompressor();
  comp.threshold.value = E.comp.thr; comp.ratio.value = E.comp.ratio; comp.knee.value = E.comp.knee;
  comp.attack.value = E.comp.att; comp.release.value = E.comp.rel;
  var node = inp;
  chain.forEach(function (f) { node.connect(f); node = f; });
  node.connect(comp);
  var makeup = ctx.createGain(); makeup.gain.value = Math.pow(10, E.comp.makeup / 20);
  comp.connect(makeup);
  var dry = ctx.createGain();
  var conv = ctx.createConvolver(); conv.buffer = nrIR(ctx, 0.62, 2.4, 0.011, 0.36);
  var wetHP = bq("highpass", 320, 0.7), wetLP = bq("lowpass", 6500, 0.7), wet = ctx.createGain();
  makeup.connect(dry); makeup.connect(conv); conv.connect(wetHP); wetHP.connect(wetLP); wetLP.connect(wet);
  var sum = ctx.createGain();
  dry.connect(sum); wet.connect(sum);
  var ceil = ctx.createWaveShaper(); ceil.curve = nrCeiling(0.6, Math.pow(10, -1.5 / 20)); ceil.oversample = "2x";
  var master = ctx.createGain();
  sum.connect(ceil); ceil.connect(master); master.connect(ctx.destination);
  NR.out = inp; NR.room = wet; NR.master = master; NR.sum = sum;
  nrApplyMix();
  return ctx;
}
function nrVoiceEq(v, at) {
  var g = (NR_CFG.veq || {})[v] || [0, 0, 0, 0];
  if (NR.engine !== "neural") g = [0, 0, 0, 0];
  NR.veq.forEach(function (f, i) { f.gain.setValueAtTime(g[i], at); });
}
function nrApplyMix() {
  if (!NR.ctx) return;
  var t = NR.ctx.currentTime;
  NR.room.gain.setTargetAtTime(S.nrRoom ? NR_CFG.roomWet : 0, t, 0.08);
  NR.master.gain.setTargetAtTime(Math.pow(10, (S.nrVol - 100) / 40), t, 0.05);
  nrAmbient();
}

/* ---------------- 배경 소리 ----------------
   빗소리·벽난로·서재(방 소리). 전부 실시간 합성이라 파일이 없습니다.
   음성 대역(300Hz–3kHz)을 피해 깔고, 목소리가 나올 때 2dB 내려 줍니다. */
function nrNoise(ctx, sec, kind) {
  var n = Math.floor(ctx.sampleRate * sec), buf = ctx.createBuffer(2, n, ctx.sampleRate);
  for (var ch = 0; ch < 2; ch++) {
    var d = buf.getChannelData(ch), b0 = 0, b1 = 0, b2 = 0, last = 0, seed = 12345 + ch * 999;
    var rnd = function () { seed = (seed * 16807) % 2147483647; return seed / 1073741823.5 - 1; };
    for (var i = 0; i < n; i++) {
      var w = rnd();
      if (kind === "brown") { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; }
      else { b0 = 0.99765 * b0 + w * 0.0990460; b1 = 0.96300 * b1 + w * 0.2965164; b2 = 0.57000 * b2 + w * 1.0526913;
             d[i] = (b0 + b1 + b2 + w * 0.1848) * 0.11; }
    }
    /* 이음매: 끝 0.5초를 앞에 겹쳐 고리처럼 */
    var xf = Math.floor(ctx.sampleRate * 0.5);
    for (var j = 0; j < xf; j++) { var a = j / xf; d[j] = d[j] * a + d[n - xf + j] * (1 - a); }
  }
  return buf;
}
function nrAmbient() {
  var ctx = NR.ctx, want = (NR.state === "play" || NR.state === "prep") ? S.nrAmb : "off";
  if (NR.amb && NR.amb.kind === want) { NR.amb.gain.gain.setTargetAtTime(Math.pow(10, S.nrAmbVol / 20) * NR.amb.base, ctx.currentTime, 0.3); return; }
  if (NR.amb) {
    var old = NR.amb; old.gain.gain.setTargetAtTime(0, ctx.currentTime, 0.4);
    setTimeout(function () { old.nodes.forEach(function (n) { try { n.stop && n.stop(); n.disconnect(); } catch (e) {} }); }, 2500);
    NR.amb = null;
  }
  if (want === "off" || !ctx) return;
  var g = ctx.createGain(), nodes = [g], base = 1;
  g.gain.value = 0; g.connect(NR.master);
  var loop = function (buf, f) { var s = ctx.createBufferSource(); s.buffer = buf; s.loop = true; s.loopEnd = buf.duration - 0.5; f.forEach(function (x, i) { (i ? f[i - 1] : s).connect(x); }); f[f.length - 1].connect(g); s.start(); nodes.push(s); return s; };
  var bq = function (type, f, q) { var b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q || 0.7; return b; };
  if (want === "rain") {
    var pink = nrNoise(ctx, 7, "pink");
    loop(pink, [bq("highpass", 380), bq("peaking", 4200, 0.6), bq("lowpass", 9000)]);
    /* 지붕을 두드리는 굵은 빗방울: 저역 브라운 노이즈를 천천히 일렁이게 */
    var swell = ctx.createGain(); swell.gain.value = 0.55;
    loop(nrNoise(ctx, 9, "brown"), [bq("lowpass", 220), bq("highpass", 60), swell]);
    var lfo = ctx.createOscillator(), lg = ctx.createGain(); lfo.frequency.value = 0.09; lg.gain.value = 0.3;
    lfo.connect(lg); lg.connect(swell.gain); lfo.start(); nodes.push(lfo);
    base = 0.16;
  } else if (want === "fire") {
    loop(nrNoise(ctx, 8, "brown"), [bq("lowpass", 520), bq("highpass", 45)]);
    /* 장작 튀는 소리: 짧은 고역 펄스를 불규칙하게 */
    var crackle = function () {
      if (!NR.amb || NR.amb.kind !== "fire") return;
      var t = ctx.currentTime + 0.05, n = 1 + (Math.random() * 3 | 0);
      for (var k = 0; k < n; k++) {
        var len = Math.floor(ctx.sampleRate * (0.004 + Math.random() * 0.01)), b = ctx.createBuffer(1, len, ctx.sampleRate), d = b.getChannelData(0);
        for (var i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
        var s = ctx.createBufferSource(), f = bq("bandpass", 2500 + Math.random() * 3000, 1.4), pg = ctx.createGain();
        pg.gain.value = 0.35 + Math.random() * 0.9;
        s.buffer = b; s.connect(f); f.connect(pg); pg.connect(g); s.start(t + k * (0.02 + Math.random() * 0.07));
      }
      setTimeout(crackle, 180 + Math.random() * 1400);
    };
    setTimeout(crackle, 400);
    base = 0.22;
  } else if (want === "room") {
    loop(nrNoise(ctx, 6, "pink"), [bq("lowpass", 900), bq("highpass", 90)]);
    base = 0.07;
  }
  NR.amb = { kind: want, gain: g, nodes: nodes, base: base };
  g.gain.setTargetAtTime(Math.pow(10, S.nrAmbVol / 20) * base, ctx.currentTime, 0.8);
}

/* ---------------- 신경망 엔진 ---------------- */
function nrWorkerUrl() { return NR_CFG.base + "worker.js?v=" + NR_CFG.ver; }
function nrSpawn(cb) {
  var w;
  try { w = new Worker(nrWorkerUrl(), { type: "module" }); }
  catch (e) { cb(e); return; }
  w.busy = 0;
  w.onmessage = function (e) {
    var m = e.data;
    if (m.type === "progress") nrPrepProgress(m.got, m.total);
    else if (m.type === "ready") { w.ready = true; cb(null, w); }
    else if (m.type === "audio") { w.busy--; nrGotAudio(m); }
    else if (m.type === "error") {
      if (m.fatal) { cb(new Error(m.message)); return; }
      w.busy--; var p = NR.pend[m.id]; if (p) { p.err = m.message; p.ready = true; }
      /* 연달아 실패하면(GPU 장치 분실 등) 조용히 건너뛰지 말고 멈추고 알림 */
      if (++NR.errs >= 3) { nrFail(m.message, m.gpu); return; }
      nrPump();
    }
  };
  w.onerror = function (e) { cb(new Error(e.message || "워커 오류")); };
  var P = NR_CFG.profiles[NR.prof];
  w.postMessage({ type: "init", cfg: {
    ortBase: NR_CFG.ortBase, cacheName: NR_CFG.cacheName, files: NR_CFG.shared.concat(P.files),
    ep: P.ep, f16: P.f16, voiceNames: NR_VOICES, threads: 1, modelSpeed: NR_CFG.modelSpeed } });
}
/* 기기 보고 실행 프로필 고르기 — WebGPU 가 있으면 GPU(fp16 셰이더가 되면 fp16 모델),
   없으면 WASM int8. 한 번 실패한 GPU 는 기억해 두고 다시 고르지 않습니다. */
function nrDetect(cb) {
  if (NR.prof) return cb(NR.prof);
  var done = function (p) { NR.prof = p; cb(p); };
  /* GPU 가 한 번 막혔으면 반나절은 CPU 로 — 드라이버 문제를 매번 다시 밟지 않게. 그 뒤엔 다시 시도 */
  var failed = S.nrGpuFail && Date.now() - S.nrGpuFail < 12 * 3600e3;
  if (failed || !navigator.gpu || !navigator.gpu.requestAdapter) return done("cpu8");
  navigator.gpu.requestAdapter({ powerPreference: "high-performance" }).then(function (ad) {
    if (!ad) return done("cpu8");
    done(ad.features && ad.features.has("shader-f16") ? "gpu16" : "gpu32");
  }).catch(function () { done("cpu8"); });
}
function nrProfCfg() { return NR_CFG.profiles[NR.prof] || NR_CFG.profiles.cpu8; }
function nrIsGpu() { return nrProfCfg().ep === "webgpu"; }
function nrSynthReq(seg) {
  var id = ++NR.seq;
  var w = NR.workers.filter(function (x) { return x.ready; }).sort(function (a, b) { return a.busy - b.busy; })[0];
  var job = { id: id, seg: seg, ready: false, gen: NR.gen, t0: performance.now(), voice: nrVoiceFor(seg.lang) };
  NR.pend[id] = job;
  if (NR.engine !== "neural" || !w) { job.ready = true; return job; }
  var key = nrKey(seg), hit = NR.bufs[key];
  if (hit) { job.ready = true; job.buf = hit; job.key = key; return job; }
  job.key = key;
  w.busy++;
  w.postMessage({ type: "synth", id: id, text: seg.text, lang: seg.lang, voice: nrVoiceFor(seg.lang),
                  speed: NR_CFG.speedBase[seg.lang] * S.nrRate, steps: NR.steps, lufs: NR_CFG.lufs, expect: nrExpect(nrVoiceFor(seg.lang)) });
  return job;
}
/* 최근 문장 소리를 기억 — 일시정지·되감기가 즉시 */
function nrKey(seg) { return seg.b + ":" + seg.i + ":" + nrVoiceFor(seg.lang) + ":" + S.nrRate + ":" + NR.steps; }
function nrRemember(key, buf) {
  NR.bufs[key] = buf; NR.bufKeys.push(key);
  while (NR.bufKeys.length > 40) delete NR.bufs[NR.bufKeys.shift()];
}
function nrVoiceFor(lang) { return lang === "ko" ? S.nrVoiceKo : lang === "ja" ? S.nrVoiceJa : S.nrVoiceEn; }
function nrGotAudio(m) {
  var job = NR.pend[m.id]; if (!job || job.preview) return;
  job.ready = true;
  if (job.gen !== NR.gen || !NR.ctx) { delete NR.pend[m.id]; return; }
  if (m.pcm.length) {
    var buf = NR.ctx.createBuffer(1, m.pcm.length, m.sr);
    buf.copyToChannel(m.pcm, 0);
    job.buf = buf; nrRemember(job.key, buf); NR.errs = 0;
    /* 적응: 합성 시간 / 소리 길이 */
    NR.rtf.push(m.ms / 1000 / buf.duration); if (NR.rtf.length > 6) NR.rtf.shift();
    nrAdapt();
  }
  nrPump();
}
/* 기기가 따라오지 못하면(생성이 재생보다 느리면) 일꾼을 하나 더 두고,
   그래도 모자라면 샘플링 단계를 줄입니다. 남으면 다시 올립니다. */
function nrAdapt() {
  if (NR.rtf.length < 4) return;
  /* 중앙값 — GPU 의 셰이더 컴파일처럼 한 번씩 튀는 값에 휘둘리지 않게 */
  var avg = NR.rtf.slice().sort(function (a, b) { return a - b; })[NR.rtf.length >> 1];
  var eff = avg / Math.max(1, NR.workers.filter(function (w) { return w.ready; }).length);
  var cores = navigator.hardwareConcurrency || 2;
  if (!nrIsGpu() && eff > 0.75 && NR.workers.length < Math.min(NR_CFG.maxWorkers, Math.max(1, cores - 1)) && !NR.spawning) {
    NR.spawning = true;
    nrSpawn(function (err, w) { NR.spawning = false; if (!err) { NR.workers.push(w); NR.rtf = []; } });
  } else if (eff > 0.85 && NR.steps > NR_CFG.minSteps) { NR.steps -= 1; NR.rtf = []; }
  else if (eff < 0.35 && NR.steps < nrMaxSteps()) { NR.steps += 1; NR.rtf = []; }
}

/* ---------------- 재생 펌프 ----------------
   앞으로 읽을 문장을 일정량(초 단위) 미리 만들어 두고, 지금 문장이 끝날 시각에
   다음 버퍼를 예약합니다. 예약은 오디오 시계 기준이라 탭이 백그라운드여도 정확. */
function nrAheadSec() {
  var s = 0; NR.q.forEach(function (j) { s += j.buf ? j.buf.duration : 3; }); return s;
}
function nrPump() {
  if (NR.state !== "play" && NR.state !== "prep") return;
  /* 1) 미리 만들기 */
  var target = NR.engine === "neural" ? NR_CFG.aheadSec : 0;
  while (NR.q.length < 2 || (nrAheadSec() < target && NR.q.length < 12)) {
    var s = nrNext(); if (!s) break;
    NR.q.push(nrSynthReq(s));
  }
  if (NR.state === "prep" && NR.q.length && NR.q[0].ready) { NR.state = "play"; nrPaintBar(); }
  /* 2) 예약 */
  if (NR.engine === "system") return nrSysPump();
  while (NR.q.length && NR.q[0].ready && NR.state === "play") {
    var j = NR.q[0];
    if (NR.sched && NR.sched.length >= 2) break;            /* 둘 넘게는 앞서 예약하지 않음 */
    NR.q.shift(); delete NR.pend[j.id];
    if (!j.buf) continue;                                    /* 실패·빈 문장 */
    var ctx = NR.ctx, now = ctx.currentTime;
    var at = Math.max(now + 0.03, NR.playT);
    var src = ctx.createBufferSource(); src.buffer = j.buf; src.connect(NR.out);
    nrVoiceEq(j.voice, at);
    src.start(at);
    var nxt = NR.q[0] ? NR.q[0].seg : nrPeek();
    NR.playT = at + j.buf.duration + nrGap(j.seg, nxt);
    var ent = { src: src, seg: j.seg, at: at, end: at + j.buf.duration };
    NR.sched = NR.sched || []; NR.sched.push(ent);
    nrAtTime(at, (function (e, g) { return function () { if (g === NR.gen) nrShow(e.seg); }; })(ent, NR.gen));
    src.onended = (function (e) { return function () {
      NR.sched = (NR.sched || []).filter(function (x) { return x !== e; });
      nrAfterSeg(e.seg);
      nrPump();
    }; })(ent);
  }
  if (!NR.q.length && !(NR.sched && NR.sched.length) && !NR.cursor) nrFinish();
  nrPaintBar();
}
/* 오디오 시계의 t 에 맞춰 화면을 바꾸기. 백그라운드 탭에선 타이머가 1초로 묶이니
   다음 onended 에서 다시 맞춥니다. */
function nrAtTime(t, fn) {
  var lat = NR.ctx.outputLatency || NR.ctx.baseLatency || 0;
  var ms = Math.max(0, (t - NR.ctx.currentTime + lat) * 1000);
  setTimeout(fn, ms);
}
function nrAfterSeg(seg) {
  /* 잠자기 타이머 */
  if (NR.sleepAt && Date.now() >= NR.sleepAt && seg.last) { nrStop(true); toast("잠자기 타이머 — 낭독을 멈췄습니다", 3000); return; }
  if (NR.sleepCh >= 0 && seg.last) {
    var nx = nrPeek();
    if (nx && NR.blocks[nx.b].kind === "h") { nrStop(true); toast("장이 끝나 낭독을 멈췄습니다", 3000); }
  }
}
function nrFail(msg, gpu) {
  var cur = NR.cur;
  nrStop(true);
  NR.workers.forEach(function (w) { try { w.terminate(); } catch (e) {} }); NR.workers = []; NR.errs = 0;
  if (gpu && NR.prof !== "cpu8") {
    S.nrGpuFail = Date.now(); NR.prof = "cpu8"; saveSettingsSoon();
    toast("GPU 음성이 멈춰 CPU 음성으로 바꿉니다", 3500);
    return nrStart(cur ? { b: cur.b, s: cur.i } : null);
  }
  toast("음성을 만들지 못했습니다 — " + String(msg || "").slice(0, 80), 5000);
}
function nrFinish() {
  if (NR.state === "off") return;
  nrStop(true);
  toast("작품 끝까지 읽었습니다", 3000);
}

/* ---------------- 기기 음성 ---------------- */
function nrSysVoice(lang) {
  var vs = speechSynthesis.getVoices(), want = lang === "ko" ? "ko" : lang === "ja" ? "ja" : "en";
  var c = vs.filter(function (v) { return v.lang && v.lang.toLowerCase().indexOf(want) === 0; });
  /* 자연스러운 쪽을 먼저: 이름에 Natural/Neural/Online/Premium/Enhanced/Google 이 붙은 것 */
  var score = function (v) { var n = v.name; return (/Natural|Neural|Online/i.test(n) ? 4 : 0) + (/Premium|Enhanced/i.test(n) ? 3 : 0) + (/Google/i.test(n) ? 2 : 0) + (v.localService ? 0 : 1) + (/GB|UK/.test(v.lang) && want === "en" ? 1 : 0); };
  c.sort(function (a, b) { return score(b) - score(a); });
  return c[0] || null;
}
function nrSysPump() {
  if (NR.sysBusy || NR.state !== "play") return;
  var j = NR.q.shift(); if (!j) { if (!NR.cursor) nrFinish(); return; }
  delete NR.pend[j.id];
  var u = new SpeechSynthesisUtterance(TTSNorm.normalize(j.seg.text, j.seg.lang));
  var v = nrSysVoice(j.seg.lang); if (v) u.voice = v;
  u.lang = v ? v.lang : (j.seg.lang === "ko" ? "ko-KR" : j.seg.lang === "ja" ? "ja-JP" : "en-GB");
  u.rate = Math.max(0.5, Math.min(2, S.nrRate * (j.seg.lang === "ko" ? 1.05 : 1)));
  u.volume = Math.min(1, S.nrVol / 100);
  NR.sysBusy = true;
  var gen = NR.gen;
  var started = false;
  u.onstart = function () { started = true; NR.errs = 0; nrShow(j.seg); };
  u.onend = u.onerror = function (ev) {
    if (gen !== NR.gen) return;
    NR.sysBusy = false;
    /* 소리 없이 끝난 문장이 이어지면(음성 없음·차단) 책을 건너뛰지 말고 멈춤 */
    if ((ev.type === "error" || !started) && ++NR.errs >= 3) {
      nrStop(true); NR.errs = 0;
      toast("이 기기에서 음성을 낼 수 없습니다 — 설정에서 다른 음성을 골라 보세요", 4500); return;
    }
    var nxt = NR.q[0] ? NR.q[0].seg : nrPeek();
    var pause = nrGap(j.seg, nxt) * 1000 * 0.6;            /* 기기 음성은 끝에 제 쉼이 있음 */
    nrAfterSeg(j.seg);
    setTimeout(function () { if (gen === NR.gen) nrPump(); }, pause);
  };
  speechSynthesis.speak(u);
}

/* ---------------- 강조 · 따라가기 ---------------- */
var NR_HL = (window.CSS && CSS.highlights && window.Highlight) ? new Highlight() : null;
if (NR_HL) CSS.highlights.set("nr-cur", NR_HL);
function nrShow(seg) {
  if (!seg || NR.state === "off") return;
  NR.cur = seg;
  var b = NR.blocks[seg.b]; if (!b) return;
  $$("#book .nr-on").forEach(function (x) { if (x !== b.el) x.classList.remove("nr-on"); });
  b.el.classList.add("nr-on");
  var r = nrRange(seg);
  if (NR_HL) { NR_HL.clear(); if (r) NR_HL.add(r); }
  if (r && NR.follow && !document.hidden && Date.now() > NR.followHoldT) {
    var rr = r.getBoundingClientRect(), top = READLINE(), bot = innerHeight * 0.62;
    if (rr.top < top - 2 || rr.bottom > bot) {
      NR.selfScroll = Date.now();
      scrollBy({ top: rr.top - top, behavior: Math.abs(rr.top - top) > innerHeight * 1.5 ? "auto" : "smooth" });
    }
  }
  touched = true; flushSoon();
  nrMedia();
  nrPaintBar();
}
function nrClearShow() {
  if (NR_HL) NR_HL.clear();
  $$("#book .nr-on").forEach(function (x) { x.classList.remove("nr-on"); });
}
/* 손으로 스크롤하면 따라가기를 잠시 놓고 '읽는 곳으로' 단추를 띄웁니다 */
function nrUserScrolled() {
  if (NR.state === "off" || (NR.selfScroll && Date.now() - NR.selfScroll < 900) || restoring) return;
  if (!NR.follow) return;
  NR.follow = false; nrPaintBar();
}

/* ---------------- 조작 ---------------- */
function nrToggle() {
  if (view !== "reader") return;
  if (NR.state === "play" || NR.state === "prep") return nrPause();
  if (NR.state === "pause") return nrResume();
  nrStart();
}
function nrStart(from) {
  if (view !== "reader") return;
  if (WORK.orig === "ja" && !NR_YOMI[WORK.id] && nrLangPick() === "ja") return nrLoadYomi(function () { nrStart(from); });
  stopAutoScroll(true);
  NR.blocks = nrBuildBlocks(); NR.segCache = {}; NR.bufs = {}; NR.bufKeys = [];
  NR.cursor = from || nrStartFromView();
  NR.follow = true;
  var eng = S.nrEngine === "system" ? "system" : nrCanNeural() ? "neural" : nrCanSystem() ? "system" : null;
  if (!eng) { toast("이 브라우저에서는 낭독을 쓸 수 없습니다", 3000); return; }
  if (eng === "neural" && !NR.workers.some(function (w) { return w.ready; })) {
    return nrDetect(function () {
      if (S.nrEngine === "auto" && S.nrGot !== NR.prof && nrCanSystem()) return nrAskDownload();
      nrBootNeural();
    });
  }
  nrGo(eng);
}
function nrGo(eng) {
  NR.engine = eng; NR.gen++;
  NR.q = []; NR.pend = {}; NR.sched = [];
  NR.steps = NR.steps || nrMaxSteps();
  if (eng === "neural") { var ctx = nrAudio(); NR.playT = ctx.currentTime + 0.05; }
  else { if (S.nrAmb !== "off") nrAudio(); speechSynthesis.cancel(); NR.sysBusy = false; }
  NR.state = "prep";
  document.body.classList.add("narrating");
  setWake(); nrPaintBar(); nrMedia(); nrApplyMix();
  nrPump();
}
function nrPause() {
  if (NR.state === "off") return;
  NR.state = "pause";
  if (NR.engine === "system") { NR.gen++; speechSynthesis.cancel(); NR.sysBusy = false; NR.q = []; }
  else nrDropScheduled();
  if (NR.cur) NR.cursor = { b: NR.cur.b, s: NR.cur.i };   /* 멈춘 문장을 처음부터 다시 */
  if (NR.ctx) NR.ctx.suspend && setTimeout(function () { if (NR.state === "pause") NR.ctx.suspend(); }, 300);
  nrAmbient(); nrPaintBar(); nrMedia(); setWake();
}
function nrResume() {
  if (NR.state !== "pause") return;
  if (NR.ctx && NR.ctx.state === "suspended") NR.ctx.resume();
  NR.follow = true;
  nrGo(NR.engine);
}
function nrDropScheduled() {
  NR.gen++;
  (NR.sched || []).forEach(function (e) { try { e.src.onended = null; e.src.stop(); } catch (x) {} });
  NR.sched = []; NR.q = []; NR.pend = {};
  if (NR.ctx) NR.playT = NR.ctx.currentTime + 0.05;
}
function nrStop(quiet) {
  if (NR.state === "off") return;
  nrDropScheduled();
  if (NR.engine === "system") { speechSynthesis.cancel(); NR.sysBusy = false; }
  NR.state = "off"; NR.cur = null; NR.sleepAt = 0; NR.sleepCh = -1;
  document.body.classList.remove("narrating");
  nrClearShow(); nrAmbient(); nrPaintBar(); setWake();
  if ("mediaSession" in navigator) navigator.mediaSession.playbackState = "none";
  flush();
  if (!quiet) toast("낭독 멈춤");
}
/* 문장·문단 단위 건너뛰기 */
function nrSkip(dir, unit) {
  if (NR.state === "off" || !NR.cur) return;
  var c = NR.cur, to;
  if (unit === "p") {
    var b = c.b + dir;
    while (b > 0 && b < NR.blocks.length && !nrSegs(b).length) b += dir;
    to = { b: Math.max(0, Math.min(NR.blocks.length - 1, b)), s: 0 };
  } else {
    if (dir > 0) to = c.last ? { b: c.b + 1, s: 0 } : { b: c.b, s: c.i + 1 };
    else if (c.i > 0) to = { b: c.b, s: c.i - 1 };
    else { var pb = c.b - 1; while (pb > 0 && !nrSegs(pb).length) pb--; to = { b: Math.max(0, pb), s: Math.max(0, nrSegs(Math.max(0, pb)).length - 1) }; }
  }
  nrJump(to);
}
function nrJump(to) {
  var was = NR.state;
  nrDropScheduled();
  if (NR.engine === "system") { speechSynthesis.cancel(); NR.sysBusy = false; }
  NR.cursor = to; NR.follow = true;
  if (was === "pause") { var s = nrPeek(); if (s) nrShow(s); NR.cur = s; return; }
  NR.state = "prep"; nrPump();
}
/* 본문을 두 번 누르면(더블클릭) 그 문장부터 */
function nrJumpToPoint(x, y) {
  var pos = document.caretPositionFromPoint ? document.caretPositionFromPoint(x, y) :
            document.caretRangeFromPoint ? (function (r) { return r && { offsetNode: r.startContainer, offset: r.startOffset }; })(document.caretRangeFromPoint(x, y)) : null;
  if (!pos) return false;
  for (var bi = 0; bi < NR.blocks.length; bi++) {
    if (!NR.blocks[bi].el.contains(pos.offsetNode)) continue;
    var segs = nrSegs(bi), nodes = segs.nodes, off = -1;
    for (var k = 0; k < nodes.length; k++) if (nodes[k].node === pos.offsetNode) { off = nodes[k].start + pos.offset; break; }
    var si = 0;
    for (var s = 0; s < segs.length; s++) if (off >= segs[s].a) si = s;
    nrJump({ b: bi, s: si });
    return true;
  }
  return false;
}

/* ---------------- 처음 한 번: 모델 받기 ---------------- */
/* calib 에서 잰 목소리별 평균 라우드니스 + 프로필(양자화)별 차이 */
function nrExpect(v) {
  var L = NR_CFG.loud || {}; if (L.voice == null) return null;
  return (L.voice[v] != null ? L.voice[v] : -25.5) + ((L.prof || {})[NR.prof] || 0);
}
function nrMaxSteps() { return nrIsGpu() ? NR_CFG.steps : NR_CFG.cpuSteps; }
function nrMB(prof) {
  var P = NR_CFG.profiles[prof || NR.prof] || NR_CFG.profiles.cpu8;
  return Math.round(NR_CFG.shared.concat(P.files).reduce(function (a, f) { return a + f.size; }, 0) / 1048576);
}
function nrAskDownload() {
  var ex = $("#nr-ask"); if (ex) ex.remove();
  var d = document.createElement("div"); d.id = "nr-ask";
  d.innerHTML = '<div class="nr-box"><h4>고품질 낭독 음성</h4>' +
    "<p>사람 목소리에 가까운 음성 모델(Supertonic 3, 약 " + nrMB() + "MB)을 한 번 내려받습니다. " +
    "이 기기 안에서만 돌아가고, 다음부터는 내려받지 않습니다.</p>" +
    '<div class="nr-btns"><button data-nr="dl" class="pri">내려받고 듣기</button>' +
    '<button data-nr="sys">기기 음성으로 바로 듣기</button><button data-nr="x">취소</button></div></div>';
  document.body.appendChild(d);
  d.addEventListener("click", function (e) {
    var b = e.target.closest("[data-nr]");
    if (!b && e.target !== d) return;
    d.remove();
    if (!b) return;
    if (b.dataset.nr === "dl") nrBootNeural();
    if (b.dataset.nr === "sys") nrGo("system");
  });
}
function nrBootNeural() {
  nrAudio();                                  /* 사용자 동작 안에서 오디오를 깨워 둠 */
  NR.state = "prep"; NR.engine = "neural";
  document.body.classList.add("narrating");
  nrPrepProgress(0, 1, true); nrPaintBar();
  if (NR.workers.length) return;
  if (!NR.prof) return nrDetect(nrBootNeural);
  nrSpawn(function (err, w) {
    if (err) {
      NR.workers = [];
      /* GPU 에서 막히면(드라이버·메모리) CPU 프로필로 한 번 더 */
      if (NR.prof !== "cpu8") {
        S.nrGpuFail = Date.now(); NR.prof = "cpu8"; saveSettingsSoon();
        toast("GPU 음성을 쓸 수 없어 CPU 음성으로 준비합니다", 3500);
        return nrBootNeural();
      }
      NR.state = "off"; document.body.classList.remove("narrating"); nrPaintBar();
      toast("음성 모델을 불러오지 못했습니다 — " + (err.message || err), 5000);
      if (nrCanSystem()) setTimeout(function () { nrGo("system"); }, 600);
      return;
    }
    NR.workers = [w];
    if (S.nrGot !== NR.prof) { S.nrGot = NR.prof; saveSettingsSoon(); }
    nrPrepProgress(1, 1);
    nrGo("neural");
  });
}
function nrPrepProgress(got, total, first) {
  var el = $("#nrbar .nr-st"); if (!el) return;
  if (got >= total && !first) { el.textContent = ""; return; }
  el.textContent = total > 1 ? "음성 준비 " + Math.floor(got / total * 100) + "%" : "음성 준비 중…";
}

/* ---------------- 막대 (화면 아래) ---------------- */
function nrBuildBar() {
  var bar = $("#nrbar"); if (!bar) return;
  bar.addEventListener("click", function (e) {
    var b = e.target.closest("[data-nr]"); if (!b) return;
    e.stopPropagation();
    var a = b.dataset.nr;
    if (a === "play") nrToggle();
    if (a === "prev") nrSkip(-1, "s");
    if (a === "next") nrSkip(1, "s");
    if (a === "stop") nrStop();
    if (a === "follow") { NR.follow = true; NR.followHoldT = 0; if (NR.cur) nrShow(NR.cur); }
    if (a === "rate") { var R = NR_CFG.rates, i = R.indexOf(S.nrRate); S.nrRate = R[(i + 1) % R.length]; saveSettingsSoon(); nrRateChanged(); }
    if (a === "sleep") nrSleepCycle();
    if (a === "more") openSettings();
  });
}
function nrRateChanged() {
  toast("낭독 속도 ×" + S.nrRate, 900);
  syncSettings();
  if (NR.state === "play" && NR.cur) nrJump({ b: NR.cur.b, s: NR.cur.i });
  nrPaintBar();
}
var NR_SLEEP = [0, 15, 30, 60, -1];
function nrSleepCycle() {
  var cur = NR.sleepCh >= 0 ? -1 : NR.sleepAt ? Math.round((NR.sleepAt - Date.now()) / 60000) : 0;
  var i = NR_SLEEP.indexOf(cur); if (i < 0) i = NR_SLEEP.findIndex(function (m) { return m > cur; }) - 1;
  var nx = NR_SLEEP[(i + 1) % NR_SLEEP.length];
  NR.sleepAt = nx > 0 ? Date.now() + nx * 60000 : 0; NR.sleepCh = nx < 0 ? 1 : -1;
  toast(nx === 0 ? "잠자기 타이머 끔" : nx < 0 ? "이 장이 끝나면 멈춤" : nx + "분 뒤 멈춤", 1200);
  nrPaintBar();
}
function nrPaintBar() {
  var bar = $("#nrbar"); if (!bar) return;
  var on = NR.state !== "off";
  bar.hidden = !on;
  var pb = bar.querySelector('[data-nr="play"]');
  if (pb) { pb.innerHTML = (NR.state === "play" || NR.state === "prep") ? NR_ICON.pause : NR_ICON.play;
            pb.setAttribute("aria-label", NR.state === "pause" ? "이어 듣기" : "일시정지"); }
  var rb = bar.querySelector('[data-nr="rate"]'); if (rb) rb.textContent = "×" + S.nrRate;
  var fb = bar.querySelector('[data-nr="follow"]'); if (fb) fb.hidden = NR.follow;
  var sl = bar.querySelector('[data-nr="sleep"]');
  if (sl) { var m = NR.sleepAt ? Math.max(1, Math.round((NR.sleepAt - Date.now()) / 60000)) : 0;
            sl.textContent = NR.sleepCh >= 0 ? "장 끝" : m ? m + "분" : "";
            sl.classList.toggle("on", !!(m || NR.sleepCh >= 0)); sl.innerHTML = NR_ICON.moon + (sl.textContent ? "<i>" + sl.textContent + "</i>" : ""); }
  var st = bar.querySelector(".nr-st");
  if (st && NR.state === "prep" && !st.textContent) st.textContent = "준비 중…";
  if (st && NR.state === "play" && /준비/.test(st.textContent)) st.textContent = "";
  if (st && NR.state === "pause") st.textContent = "일시정지";
  var eb = bar.querySelector(".nr-eng"); if (eb) eb.textContent = NR.engine === "system" ? "기기 음성" : "";
  var ab = $('[data-act="read"]'); if (ab) ab.classList.toggle("on", on);
}
var NR_ICON = {
  play: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M6 4.2v11.6L15.6 10z" fill="currentColor"/></svg>',
  pause: '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M5.5 4h3v12h-3zM11.5 4h3v12h-3z" fill="currentColor"/></svg>',
  moon: '<svg viewBox="0 0 20 20" width="15" height="15" aria-hidden="true"><path d="M15.5 12.6A6.5 6.5 0 0 1 7.4 4.5a6.5 6.5 0 1 0 8.1 8.1z" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>'
};

/* ---------------- 잠금화면 · 이어폰 단추 ---------------- */
function nrMedia() {
  if (!("mediaSession" in navigator) || !WORK) return;
  var ms = navigator.mediaSession;
  try {
    var ch = NR.cur ? WORK.chapters[chapterOf(Math.max(0, NR.blocks[NR.cur.b].p))] : null;
    ms.metadata = new MediaMetadata({
      title: (WORK.lang !== "en" && WORK.titleKo ? WORK.titleKo : WORK.title) + (ch && WORK.chapters.length > 1 ? " · " + chLabel(ch) : ""),
      artist: WORK.lang !== "en" ? WORK.authorKo : WORK.authorEn,
      album: "서재 1895—1936"
    });
    ms.playbackState = NR.state === "pause" ? "paused" : NR.state === "off" ? "none" : "playing";
    if (!NR.msBound) {
      NR.msBound = true;
      ms.setActionHandler("play", function () { if (NR.state === "pause") nrResume(); else if (NR.state === "off") nrStart(); });
      ms.setActionHandler("pause", function () { nrPause(); });
      ms.setActionHandler("stop", function () { nrStop(); });
      ms.setActionHandler("previoustrack", function () { nrSkip(-1, "p"); });
      ms.setActionHandler("nexttrack", function () { nrSkip(1, "p"); });
      try { ms.setActionHandler("seekbackward", function () { nrSkip(-1, "s"); }); } catch (e) {}
      try { ms.setActionHandler("seekforward", function () { nrSkip(1, "s"); }); } catch (e) {}
    }
  } catch (e) {}
}

/* ---------------- 묶기 ---------------- */
function nrBind() {
  nrBuildBar();
  addEventListener("wheel", nrUserScrolled, { passive: true });
  addEventListener("touchmove", nrUserScrolled, { passive: true });
  addEventListener("keydown", function (e) {
    if (/^(ArrowUp|ArrowDown|PageUp|PageDown|Home|End| )$/.test(e.key) && NR.state !== "off" && !e.shiftKey) nrUserScrolled();
  }, true);
  $("#book").addEventListener("dblclick", function (e) {
    if (NR.state === "off") return;
    if (nrJumpToPoint(e.clientX, e.clientY)) { var s = getSelection(); if (s) s.removeAllRanges(); }
  });
  if (nrCanSystem()) { speechSynthesis.getVoices(); speechSynthesis.onvoiceschanged = function () {}; }
  /* 다른 작품으로 가거나 언어를 바꾸면 끊고 다시 */
  addEventListener("hashchange", function () { if (NR.state !== "off") nrStop(true); });
}

/* 본문을 다시 그릴 때(언어 전환) 읽던 문단을 기억했다가 같은 곳에서 잇기 */
function nrBeforeRebuild() {
  if (NR.state === "off") return null;
  var x = { p: NR.cur ? NR.blocks[NR.cur.b].p : -1, st: NR.state };
  nrStop(true);
  return x;
}
function nrAfterRebuild(x) {
  if (!x || view !== "reader") return;
  var bl = nrBuildBlocks(), at = 0;
  for (var i = 0; i < bl.length; i++) if (bl[i].p === x.p) { at = i; break; }
  nrStart({ b: at, s: 0 });
}
function nrSettingChanged(k) {
  if (/^nr(Vol|Room|Amb|AmbVol)$/.test(k)) { if (S.nrAmb !== "off" || NR.ctx) { nrAudio(); nrApplyMix(); } return; }
  if (NR.state === "off" || !NR.cur) return;
  if (/^nrVoice/.test(k)) { nrJump({ b: NR.cur.b, s: NR.cur.i }); return; }
  if (k === "nrEngine" || k === "nrBoth") {
    var x = nrBeforeRebuild(); nrAfterRebuild(x);
  }
}
var NR_SAMPLE = {
  ko: "시간 여행자는 우리에게 난해한 문제를 설명하고 있었다. 잿빛 눈은 빛나며 반짝였다.",
  en: "The Time Traveller was expounding a recondite matter to us. His grey eyes shone and twinkled.",
  ja: "ある日の暮方の事である。一人の下人が、羅生門の下で雨やみを待っていた。"
};
function nrPreview() {
  var lang = (WORK && view === "reader") ? nrLangPick() : (S.lang === "en" ? "en" : "ko");
  var w = NR.workers.filter(function (x) { return x.ready; })[0];
  if (!w) {
    if (!nrCanNeural()) { toast("이 환경에서는 기기 음성만 쓸 수 있습니다", 2200); return; }
    toast("낭독을 한 번 시작하면 고품질 음성이 준비됩니다", 2600); return;
  }
  var ctx = nrAudio(), id = "pv" + Date.now();
  NR.pend[id] = { id: id, preview: true };
  var h = function (e) {
    if (e.data.type !== "audio" || e.data.id !== id) return;
    w.removeEventListener("message", h); delete NR.pend[id];
    var b = ctx.createBuffer(1, e.data.pcm.length, e.data.sr); b.copyToChannel(e.data.pcm, 0);
    var s = ctx.createBufferSource(); s.buffer = b; s.connect(NR.out); s.start();
  };
  w.addEventListener("message", h);
  w.busy++;
  w.postMessage({ type: "synth", id: id, text: NR_SAMPLE[lang], lang: lang, voice: nrVoiceFor(lang),
                  speed: NR_CFG.speedBase[lang] * S.nrRate, steps: NR.steps || nrMaxSteps(), lufs: NR_CFG.lufs, expect: nrExpect(nrVoiceFor(lang)) });
}
function nrClearModel() {
  if (!("caches" in window)) return;
  nrStop(true);
  NR.workers.forEach(function (w) { try { w.terminate(); } catch (e) {} }); NR.workers = [];
  var mb = NR.prof ? nrMB() : 0;
  caches.delete(NR_CFG.cacheName).then(function () {
    S.nrGot = false; S.nrGpuFail = 0; NR.prof = null; saveSettingsSoon();
    toast("음성 모델을 지웠습니다" + (mb ? " (" + mb + "MB)" : ""), 2400);
  });
}
if (/[?&]nrdebug\b/.test(location.search)) window.NR_DEBUG = { NR: NR, S: S, cfg: NR_CFG };
