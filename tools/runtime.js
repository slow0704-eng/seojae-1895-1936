/* ============================================================
   서재 — reading runtime
   Inlined into every work page. Vanilla, offline, file:// safe.
   ============================================================ */
(function () {
"use strict";

/* ---------- storage (file:// shares one origin across all files) ---------- */
var LS = (function () {
  try { localStorage.setItem("rdr/probe", "1"); localStorage.removeItem("rdr/probe"); return localStorage; }
  catch (e) { var m = {}; return { getItem: function (k) { return k in m ? m[k] : null; },
    setItem: function (k, v) { m[k] = String(v); }, removeItem: function (k) { delete m[k]; },
    key: function (i) { return Object.keys(m)[i]; }, get length() { return Object.keys(m).length; },
    __mem: true }; }
})();
var EPHEMERAL = !!LS.__mem;

function load(k, dflt) {
  try { var s = LS.getItem(k); return s == null ? dflt : JSON.parse(s); }
  catch (e) {
    try { LS.setItem("rdr/v1/corrupt/" + k + "/" + Date.now(), LS.getItem(k)); LS.removeItem(k); } catch (e2) {}
    return dflt;
  }
}
function save(k, v) {
  try { LS.setItem(k, JSON.stringify(v)); return true; }
  catch (e) { if (e && e.name === "QuotaExceededError") toast("저장 공간이 부족합니다. 설정에서 내보내기 후 정리해 주세요.", 6000); return false; }
}

/* ---------- state bus ----------------------------------------------------
   Chrome partitions localStorage PER FILE on file:// — the 60 pages do NOT
   share a bucket (verified). window.name, however, survives navigation within
   a tab. So each page merges the bus in on arrival and ships it out again on
   the way to the next file. Every page also keeps its own durable copy, so a
   work always remembers its own position even when opened cold.            */
var BUS_TAG = "RDRBUS1:";

function busRead() {
  var raw = "";
  try { raw = window.name || ""; } catch (e) { return; }
  if (raw.indexOf(BUS_TAG) !== 0) return;
  var b;
  try { b = JSON.parse(raw.slice(BUS_TAG.length)); } catch (e) { return; }
  if (!b) return;
  if (b.s && (b.s.updated || 0) > (load("rdr/v1/settings", {}).updated || 0))
    save("rdr/v1/settings", b.s);
  if (b.p) Object.keys(b.p).forEach(function (id) {
    var mine = load("rdr/v1/prog/" + id, null), theirs = b.p[id];
    if (!mine || (theirs.updated || 0) > (mine.updated || 0)) save("rdr/v1/prog/" + id, theirs);
  });
  if (b.m) Object.keys(b.m).forEach(function (id) {
    var mine = load("rdr/v1/marks/" + id, null), theirs = b.m[id];
    if (!mine) return save("rdr/v1/marks/" + id, theirs);
    var seen = {}; (mine.m || []).forEach(function (x) { seen[x.id] = 1; });
    (theirs.m || []).forEach(function (x) { if (!seen[x.id]) mine.m.push(x); });
    save("rdr/v1/marks/" + id, mine);
  });
  if (b.n) {
    var s = load("rdr/v1/session", { v: 1, recent: [], totalMs: 0 });
    if ((b.n.lastAt || 0) > (s.lastAt || 0)) { s.last = b.n.last; s.lastAt = b.n.lastAt; s.recent = b.n.recent || s.recent; }
    s.totalMs = Math.max(s.totalMs || 0, b.n.totalMs || 0);
    s.seenHint = s.seenHint || b.n.seenHint;
    save("rdr/v1/session", s);
  }
}

function busWrite() {
  try {
    var b = { s: load("rdr/v1/settings", null), p: {}, m: {},
              n: load("rdr/v1/session", null) };
    for (var i = 0; i < LS.length; i++) {
      var k = LS.key(i); if (!k) continue;
      if (k.indexOf("rdr/v1/prog/") === 0) b.p[k.slice(12)] = load(k, null);
      else if (k.indexOf("rdr/v1/marks/") === 0) b.m[k.slice(13)] = load(k, null);
    }
    window.name = BUS_TAG + JSON.stringify(b);
  } catch (e) { /* window.name unavailable — per-file storage still works */ }
}
busRead();

/* ---------- settings ---------- */
var DEFAULTS = {
  v: 1, fs: 20, lh: 1.72, measure: 68,
  theme: null, font: "1", justify: false, indent: true,
  dim: 0, wake: false, showRemaining: true, showSession: true,
  wpm: 200, wpmSamples: 0, seenHint: false, updated: 0
};
var S = Object.assign({}, DEFAULTS, load("rdr/v1/settings", {}));
if (!S.theme) S.theme = (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";

function applySettings() {
  var r = document.documentElement;
  r.style.setProperty("--fs-num", String(S.fs));
  r.style.setProperty("--fs", S.fs + "px");
  /* leading and tracking are derived from the size, not chosen independently:
     larger type needs proportionally less leading and negative tracking. */
  r.style.setProperty("--lh", String(+(S.lh - (S.fs - 20) * 0.007).toFixed(3)));
  r.style.setProperty("--track", ((20 - S.fs) * 0.0018).toFixed(4) + "em");
  /* the column is sized in em from this face's average advance (see CSS) */
  r.style.setProperty("--cpl", String(S.measure));
  r.dataset.theme = S.theme;
  r.dataset.font = S.font;
  r.dataset.justify = S.justify ? "on" : "off";
  r.dataset.indent = S.indent ? "on" : "off";
  var d = document.getElementById("dimmer");
  if (d) d.style.opacity = (S.dim / 100);
}
applySettings();                       /* runs pre-paint from <head> */

var saveSettingsSoon = throttle(function () {
  S.updated = Date.now(); save("rdr/v1/settings", S); busWrite();
}, 400);

/* ---------- generic helpers ---------- */
function throttle(fn, ms) {
  var t = null, pending = false;
  return function () {
    pending = true;
    if (t) return;
    t = setTimeout(function () { t = null; if (pending) { pending = false; fn(); } }, ms);
  };
}
function $(s, c) { return (c || document).querySelector(s); }
function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
function fmtInt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
function fmtMin(m) {
  if (m < 1) return "1분 미만";
  if (m < 60) return m + "분";
  var h = Math.floor(m / 60), r = m % 60;
  return r ? h + "시간 " + r + "분" : h + "시간";
}
function ago(ts) {
  var s = (Date.now() - ts) / 1000;
  if (s < 60) return "방금";
  if (s < 3600) return Math.floor(s / 60) + "분 전";
  if (s < 86400) return Math.floor(s / 3600) + "시간 전";
  if (s < 172800) return "어제";
  if (s < 604800) return Math.floor(s / 86400) + "일 전";
  if (s < 2592000) return Math.floor(s / 604800) + "주 전";
  return Math.floor(s / 2592000) + "개월 전";
}

/* ---------- toast ---------- */
var toastEl = null, toastT = null;
function toast(msg, ms) {
  if (!toastEl) { toastEl = document.createElement("div"); toastEl.id = "toast"; document.body.appendChild(toastEl); }
  toastEl.textContent = msg;
  toastEl.classList.add("on");
  clearTimeout(toastT);
  toastT = setTimeout(function () { toastEl.classList.remove("on"); }, ms || 1400);
}

/* ============================================================
   Reader (only on work pages, where WORK is defined)
   ============================================================ */
if (typeof WORK === "undefined") {
  window.RDR = { S: S, load: load, save: save, applySettings: applySettings,
    saveSettingsSoon: saveSettingsSoon, toast: toast, ago: ago, fmtInt: fmtInt,
    fmtMin: fmtMin, EPHEMERAL: EPHEMERAL, busWrite: busWrite };
  addEventListener("pagehide", busWrite);
  addEventListener("visibilitychange", function () { if (document.hidden) busWrite(); });
  busWrite();
  return;
}

var PROG_KEY = "rdr/v1/prog/" + WORK.id;
var MARK_KEY = "rdr/v1/marks/" + WORK.id;
var paras = [], cum = null, prog = null, marks = null;
var TINY = false;

function READLINE() { return Math.round(innerHeight * 0.18); }

function boot() {
  paras = $$("#book p[data-p]");
  cum = new Uint32Array(paras.length + 1);
  for (var i = 0; i < paras.length; i++) cum[i + 1] = cum[i] + paras[i].textContent.length;
  /* derive the denominator from the DOM so it can never drift from the build */
  WORK.chars = cum[paras.length] || 1;
  WORK.paras = paras.length;
  TINY = WORK.chars < 4000;

  prog = load(PROG_KEY, null);
  marks = load(MARK_KEY, { v: 1, sig: WORK.sig, m: [] });
  if (!marks.m) marks.m = [];

  buildChapterIndex();
  buildHud();
  buildDrawer();
  buildSettings();
  bindKeys();
  bindPointer();
  paintMarkTicks();

  var restored = false;
  if (prog) {
    if (prog.sig !== WORK.sig) {
      var el = document.querySelector('[data-p="' + prog.p + '"]');
      var ok = el && norm(el.textContent).indexOf(prog.sample) === 0;
      if (ok) { prog.sig = WORK.sig; } else { prog = resyncByFraction(prog.frac); toast("본문이 갱신되어 위치를 대략 복원했습니다", 5000); }
    }
    if (prog && prog.frac > 0.002 && !TINY) { restoreAnchor(prog, function () { showResumeToast(); }); restored = true; }
  }
  if (!restored) settle();

  if (!S.seenHint) { S.seenHint = true; saveSettingsSoon(); setTimeout(function () { toast("?  단축키   ·   ,  설정   ·   t  목차", 6000); }, 900); }
  if (EPHEMERAL) { var w = document.createElement("div"); w.id = "nostore"; w.textContent = "저장할 수 없는 환경입니다. 읽은 위치가 기억되지 않습니다."; document.body.appendChild(w); }

  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", throttle(repin, 200));
  ["visibilitychange", "pagehide", "blur"].forEach(function (ev) {
    addEventListener(ev, function () { if (ev !== "visibilitychange" || document.hidden) flush(true); });
  });
  setInterval(heartbeat, 15000);
  updateHud();
}

function settle() { document.documentElement.style.visibility = ""; }
function norm(s) { return s.replace(/\s+/g, " ").trim().slice(0, 21).toLowerCase(); }

/* ---------- anchor ---------- */
function findFirstParaBelow(line) {
  var lo = 0, hi = paras.length - 1, best = null;
  while (lo <= hi) {
    var mid = (lo + hi) >> 1, r = paras[mid].getBoundingClientRect();
    if (r.bottom < line) lo = mid + 1; else { best = paras[mid]; hi = mid - 1; }
  }
  return best || paras[paras.length - 1] || null;
}
function captureAnchor() {
  if (!paras.length) return null;
  var line = READLINE(), p = findFirstParaBelow(line);
  if (!p) return null;
  var node = p.firstChild;
  if (!node || node.nodeType !== 3) return { p: +p.dataset.p, o: 0 };
  var len = node.length, lo = 0, hi = len, r = document.createRange();
  while (lo < hi) {
    var mid = (lo + hi) >> 1;
    r.setStart(node, mid); r.setEnd(node, Math.min(mid + 1, len));
    if (r.getBoundingClientRect().top < line) lo = mid + 1; else hi = mid;
  }
  return { p: +p.dataset.p, o: lo };
}
function restoreAnchor(a, done) {
  var el = document.querySelector('[data-p="' + a.p + '"]');
  if (!el) { settle(); if (done) done(); return false; }
  var sec = el.closest(".ch"); if (sec) sec.style.contentVisibility = "visible";
  var node = el.firstChild;
  var line = READLINE(), r = document.createRange();
  if (node && node.nodeType === 3) {
    r.setStart(node, Math.min(a.o || 0, node.length));
    r.setEnd(node, Math.min((a.o || 0) + 1, node.length));
  } else { r.selectNode(el); }
  var pass = 0;
  (function step() {
    var dy = r.getBoundingClientRect().top - line;
    if (Math.abs(dy) <= 2 || ++pass > 6) {
      if (sec) sec.style.contentVisibility = "";
      settle(); updateHud(); if (done) done();
      return;
    }
    scrollBy(0, dy);
    requestAnimationFrame(step);
  })();
  return true;
}
function repin() { var a = captureAnchor(); if (a) restoreAnchor(a); }
function withPin(fn) { var a = captureAnchor(); fn(); requestAnimationFrame(function () { if (a) restoreAnchor(a); }); }
function resyncByFraction(frac) {
  var target = (frac || 0) * WORK.chars, lo = 0, hi = paras.length - 1;
  while (lo < hi) { var mid = (lo + hi) >> 1; if (cum[mid + 1] < target) lo = mid + 1; else hi = mid; }
  return { v: 1, sig: WORK.sig, p: lo, o: 0, frac: frac, ch: chapterOf(lo), sample: norm(paras[lo] ? paras[lo].textContent : ""),
    paras: paras.length, maxFrac: frac, readMs: (prog && prog.readMs) || 0, opened: Date.now(), updated: Date.now(), finished: false };
}

/* ---------- progress ---------- */
function fracNow() {
  var a = captureAnchor(); if (!a) return 0;
  return Math.min(1, (cum[a.p] + a.o) / WORK.chars);
}
function chapterOf(pIdx) {
  var cs = WORK.chapters, r = 0;
  for (var i = 0; i < cs.length; i++) if (cs[i].firstP <= pIdx) r = i; else break;
  return r;
}
var lastFlush = 0, lastChars = null, lastActive = Date.now(), segStart = Date.now(), segChars = null;
var sessionStart = Date.now(), sessionMs = 0;

function flush(force) {
  var a = captureAnchor(); if (!a) return;
  var frac = Math.min(1, (cum[a.p] + a.o) / WORK.chars);
  var pv = prog || { v: 1, readMs: 0, opened: Date.now(), maxFrac: 0 };
  prog = {
    v: 1, sig: WORK.sig, p: a.p, o: a.o, frac: frac, ch: chapterOf(a.p),
    sample: norm(paras[a.p] ? paras[a.p].textContent : ""), paras: paras.length,
    maxFrac: Math.max(pv.maxFrac || 0, frac), readMs: pv.readMs || 0,
    opened: pv.opened || Date.now(), updated: Date.now(),
    finished: (Math.max(pv.maxFrac || 0, frac) >= 0.985)
  };
  save(PROG_KEY, prog);
  var sess = load("rdr/v1/session", { v: 1, recent: [], totalMs: 0 });
  sess.last = WORK.id; sess.lastAt = Date.now();
  sess.recent = [WORK.id].concat((sess.recent || []).filter(function (x) { return x !== WORK.id; })).slice(0, 12);
  save("rdr/v1/session", sess);
  busWrite();
  lastFlush = Date.now();
}
var flushSoon = throttle(function () { flush(); }, 1500);

function heartbeat() {
  if (document.hidden) return;
  if (Date.now() - lastActive > 90000) return;
  sessionMs += 15000;
  if (prog) { prog.readMs = (prog.readMs || 0) + 15000; save(PROG_KEY, prog); }
  var sess = load("rdr/v1/session", { v: 1, recent: [], totalMs: 0 });
  sess.totalMs = (sess.totalMs || 0) + 15000; save("rdr/v1/session", sess);
  /* adaptive wpm */
  var a = captureAnchor(); if (!a) return;
  var nowChars = cum[a.p] + a.o;
  if (segChars == null) { segChars = nowChars; segStart = Date.now(); return; }
  var dt = Date.now() - segStart;
  if (dt >= 300000) {
    var dc = nowChars - segChars;
    if (dc > 0) {
      var sample = (dc / 5.5) / (dt / 60000);
      if (sample > 60 && sample < 450) {
        S.wpm = Math.round(S.wpm + (sample - S.wpm) * (S.wpmSamples < 5 ? 0.35 : 0.15));
        S.wpmSamples++; saveSettingsSoon();
      }
    }
    segChars = nowChars; segStart = Date.now();
  }
  updateHud();
}

function onScroll() {
  lastActive = Date.now();
  flushSoon();
  updateHud();
  if (scrollDir() < 0) hideHud(); else maybeRevealOnScrollUp();
}
var lastY = 0, upAccum = 0, upT = 0;
function scrollDir() { var y = scrollY, d = y - lastY; lastY = y; return d; }
function maybeRevealOnScrollUp() {
  var now = Date.now();
  if (now - upT > 400) { upAccum = 0; upT = now; }
  upAccum += 1;
  if (upAccum > 3) revealHud();
}
window.__rdrFlush = flush;

/* ============================================================
   HUD
   ============================================================ */
var hud = {}, hudOn = false, hudPinned = false, hideT = null;

function buildHud() {
  var top = document.createElement("div"); top.id = "hud-top"; top.className = "hud";
  top.innerHTML =
    '<a class="hbtn" href="index.html" id="h-lib">‹ 서재</a>' +
    '<span class="h-title"></span>' +
    '<span class="h-ch"></span>' +
    '<span class="h-right">' +
      '<button class="hbtn" data-act="toc">목차</button>' +
      '<button class="hbtn" data-act="bm">책갈피</button>' +
      '<button class="hbtn" data-act="set">설정</button>' +
    '</span>';
  var bot = document.createElement("div"); bot.id = "hud-bot"; bot.className = "hud";
  bot.innerHTML =
    '<span class="h-pct"></span><span class="h-rem"></span>' +
    '<span class="h-sess"></span>';
  var bar = document.createElement("div"); bar.id = "hairline";
  bar.innerHTML = '<div id="hair-fill"></div><div id="hair-ticks"></div>';
  document.body.appendChild(top); document.body.appendChild(bot); document.body.appendChild(bar);

  hud.top = top; hud.bot = bot; hud.bar = bar;
  hud.title = $(".h-title", top); hud.ch = $(".h-ch", top);
  hud.pct = $(".h-pct", bot); hud.rem = $(".h-rem", bot); hud.sess = $(".h-sess", bot);
  hud.fill = $("#hair-fill", bar);

  hud.title.innerHTML = '<b>' + esc(WORK.title) + '</b> <i>' + esc(WORK.authorKo) + '</i>';
  if (TINY) bar.classList.add("hidden");

  top.addEventListener("click", function (e) {
    var b = e.target.closest("[data-act]"); if (!b) return;
    if (b.dataset.act === "toc") openDrawer("toc");
    if (b.dataset.act === "bm") toggleBookmark();
    if (b.dataset.act === "set") openSettings();
  });
  bar.addEventListener("click", function (e) {
    if (!hudOn) return;
    var f = e.clientX / innerWidth;
    jumpToFraction(f);
  });
  hud.rem.addEventListener("mouseenter", function () { hud.rem.dataset.hover = "1"; updateHud(); });
  hud.rem.addEventListener("mouseleave", function () { delete hud.rem.dataset.hover; updateHud(); });
}
function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }

function updateHud() {
  if (!hud.fill) return;
  var a = captureAnchor(); if (!a) return;
  var chars = cum[a.p] + a.o, frac = Math.min(1, chars / WORK.chars);
  hud.fill.style.transform = "scaleX(" + frac + ")";
  if (TINY) {
    hud.pct.textContent = "약 " + Math.max(1, Math.round(WORK.chars / 5.5 / S.wpm)) + "분";
    hud.rem.textContent = ""; hud.ch.textContent = "";
  } else {
    hud.pct.textContent = Math.floor(frac * 100) + "%";
    if (S.showRemaining) {
      if (hud.rem.dataset.hover) {
        var ci = chapterOf(a.p), c = WORK.chapters[ci];
        var end = (WORK.chapters[ci + 1] ? cum[WORK.chapters[ci + 1].firstP] : WORK.chars);
        hud.rem.textContent = " · 이 장 남은 시간 " + fmtMin(Math.max(0, Math.round((end - chars) / 5.5 / S.wpm)));
      } else {
        var m = Math.round((WORK.chars - chars) / 5.5 / S.wpm);
        hud.rem.textContent = frac >= 0.999 ? " · 완독" : (m < 1 ? " · 곧 끝납니다" : " · 남은 시간 " + fmtMin(m));
      }
    } else hud.rem.textContent = "";
    var cn = WORK.chapters[chapterOf(a.p)];
    hud.ch.textContent = cn ? cn.label : "";
  }
  hud.sess.textContent = S.showSession ? "이번 세션 " + fmtMin(Math.max(1, Math.round((Date.now() - sessionStart) / 60000))) : "";
  markCurrentInToc();
}

function revealHud() {
  if (!hudOn) { hudOn = true; document.body.classList.add("hud-on"); }
  clearTimeout(hideT);
  if (!hudPinned && !anyOverlay()) hideT = setTimeout(hideHud, 2500);
}
function hideHud() { if (hudPinned || anyOverlay()) return; hudOn = false; document.body.classList.remove("hud-on"); }
function anyOverlay() { return document.body.classList.contains("drawer-on") || document.body.classList.contains("set-on") || document.body.classList.contains("pal-on"); }

var escMute = 0;
function bindPointer() {
  var curT = null;
  addEventListener("mousemove", function (e) {
    lastActive = Date.now();
    document.documentElement.style.cursor = "";
    clearTimeout(curT); curT = setTimeout(function () { document.documentElement.style.cursor = "none"; }, 3000);
    if (Date.now() < escMute) return;
    if (e.clientY < 72 || e.clientY > innerHeight - 72) revealHud();
  }, { passive: true });
  addEventListener("touchstart", function (e) {
    lastActive = Date.now();
    if (anyOverlay()) return;
    var x = e.touches[0].clientX / innerWidth, y = e.touches[0].clientY / innerHeight;
    if (x > 0.2 && x < 0.8 && y > 0.2 && y < 0.8) { hudOn ? hideHud() : revealHud(); }
    else if (x <= 0.18) { pageBy(-1); }
    else if (x >= 0.82) { pageBy(1); }
  }, { passive: true });
}

/* ---------- movement ---------- */
function pageBy(dir) {
  var overlap = 2 * S.fs * S.lh;
  scrollBy({ top: dir * (innerHeight - overlap - 24), behavior: "smooth" });
  lastActive = Date.now(); flushSoon();
}
function jumpToFraction(f) {
  var target = f * WORK.chars, lo = 0, hi = paras.length - 1;
  while (lo < hi) { var mid = (lo + hi) >> 1; if (cum[mid + 1] < target) lo = mid + 1; else hi = mid; }
  pushUndo();
  restoreAnchor({ p: lo, o: 0 }, function () { flush(true); });
}
function gotoChapter(i) {
  var cs = WORK.chapters;
  if (!cs.length) { toast("장 구분이 없는 작품입니다"); return; }
  i = Math.max(0, Math.min(cs.length - 1, i));
  pushUndo();
  restoreAnchor({ p: cs[i].firstP, o: 0 }, function () { flush(true); toast(cs[i].label + (cs[i].title ? " · " + cs[i].title : ""), 1200); });
}
var lastPTime = 0;
function chapterNav(d) {
  var cs = WORK.chapters; if (cs.length < 2) { toast("장 구분이 없는 작품입니다"); return; }
  var a = captureAnchor(); if (!a) return;
  var ci = chapterOf(a.p);
  if (d > 0) return gotoChapter(ci + 1);
  var into = cum[a.p] + a.o - cum[cs[ci].firstP];
  var now = Date.now();
  if (into > 300 && now - lastPTime > 1500) { lastPTime = now; return gotoChapter(ci); }
  lastPTime = now; gotoChapter(ci - 1);
}
var undoStack = [];
function pushUndo() { var a = captureAnchor(); if (a) { undoStack.push({ a: a, t: Date.now() }); if (undoStack.length > 5) undoStack.shift(); } }
function popUndo() {
  var u = undoStack.pop();
  if (!u || Date.now() - u.t > 30000) { toast("되돌릴 이동이 없습니다"); return; }
  restoreAnchor(u.a, function () { flush(true); toast("이동을 취소했습니다"); });
}

/* ============================================================
   Drawer: 목차 / 책갈피
   ============================================================ */
var drawer, drawerTab = "toc";
function buildChapterIndex() {
  if (!WORK.chapters || !WORK.chapters.length) WORK.chapters = [{ firstP: 0, label: WORK.title, title: "", chars: WORK.chars }];
  WORK.chapters.forEach(function (c, i) { c.frac = cum[c.firstP] / WORK.chars; c.i = i; });
}
function buildDrawer() {
  drawer = document.createElement("aside"); drawer.id = "drawer";
  drawer.innerHTML =
    '<div class="dw-tabs"><button data-tab="toc" class="on">목차</button><button data-tab="bm">책갈피</button>' +
    '<button class="dw-x" title="닫기">✕</button></div>' +
    '<input class="dw-filter" placeholder="장 제목 검색" hidden>' +
    '<div class="dw-body"></div>';
  var scrim = document.createElement("div"); scrim.id = "scrim";
  document.body.appendChild(scrim); document.body.appendChild(drawer);
  scrim.addEventListener("click", closeOverlays);
  drawer.addEventListener("click", function (e) {
    var t = e.target.closest("[data-tab]"); if (t) { drawerTab = t.dataset.tab; renderDrawer(); return; }
    if (e.target.closest(".dw-x")) return closeOverlays();
    var row = e.target.closest("[data-ch]");
    if (row) { closeOverlays(); gotoChapter(+row.dataset.ch); return; }
    var bm = e.target.closest("[data-bm]");
    if (bm) {
      if (e.target.closest(".bm-del")) { delMark(bm.dataset.bm); renderDrawer(); return; }
      var m = marks.m.filter(function (x) { return x.id === bm.dataset.bm; })[0];
      if (m) { closeOverlays(); pushUndo(); restoreAnchor({ p: m.p, o: 0 }, function () { flush(true); }); }
    }
  });
  $(".dw-filter", drawer).addEventListener("input", renderDrawer);
}
function openDrawer(tab) { drawerTab = tab || "toc"; document.body.classList.add("drawer-on"); revealHud(); renderDrawer(); }
function closeOverlays() {
  document.body.classList.remove("drawer-on", "set-on", "pal-on");
  escMute = Date.now() + 600;
  clearTimeout(hideT); hideT = setTimeout(hideHud, 2500);
}
function renderDrawer() {
  $$(".dw-tabs [data-tab]", drawer).forEach(function (b) { b.classList.toggle("on", b.dataset.tab === drawerTab); });
  var body = $(".dw-body", drawer), filt = $(".dw-filter", drawer);
  filt.hidden = !(drawerTab === "toc" && WORK.chapters.length > 15);
  var h = "";
  if (drawerTab === "toc") {
    var q = filt.hidden ? "" : filt.value.trim().toLowerCase();
    var cur = prog ? chapterOf(prog.p) : 0;
    var mf = prog ? prog.maxFrac || 0 : 0;
    WORK.chapters.forEach(function (c) {
      var label = (c.label || "") + (c.title ? " " + c.title : "");
      if (q && label.toLowerCase().indexOf(q) < 0) return;
      if (c.kind === "part") {          /* BOOK ONE / PART II — a group header */
        h += '<div class="dw-part' + (c.i === cur ? " cur" : "") + '" data-ch="' + c.i + '">' +
             esc(c.label || "") + '</div>';
        return;
      }
      var endF = WORK.chapters[c.i + 1] ? WORK.chapters[c.i + 1].frac : 1;
      var dot = mf >= endF ? "●" : (mf > c.frac ? "◐" : "○");
      h += '<div class="dw-row' + (c.i === cur ? " cur" : "") + '" data-ch="' + c.i + '">' +
           '<span class="dot">' + dot + '</span><span class="lbl">' + esc(c.label || "") +
           (c.title ? ' <em>' + esc(c.title) + '</em>' : "") + '</span>' +
           '<span class="pc">' + Math.floor(c.frac * 100) + '%</span></div>';
    });
    if (!h) h = '<p class="dw-empty">일치하는 장이 없습니다.</p>';
  } else {
    var bms = marks.m.slice().sort(function (a, b) { return a.frac - b.frac; });
    h += '<div class="dw-head">책갈피 · ' + bms.length + '개</div>';
    if (!bms.length) h += '<p class="dw-empty">아직 책갈피가 없습니다.<br><kbd>b</kbd> 를 눌러 현재 위치를 표시하세요.</p>';
    bms.forEach(function (m) {
      h += '<div class="bm-row" data-bm="' + m.id + '">' +
           '<div class="bm-meta"><span class="pc">' + Math.floor(m.frac * 100) + '%</span> ' +
           esc((WORK.chapters[m.ch] || {}).label || "") + '</div>' +
           '<div class="bm-txt">' + esc(m.text) + '</div>' +
           '<div class="bm-foot">' + ago(m.created) + '<button class="bm-del" title="삭제">✕</button></div></div>';
    });
  }
  body.innerHTML = h;
  var c = $(".dw-row.cur", body); if (c) c.scrollIntoView({ block: "center" });
}
function markCurrentInToc() {
  if (!document.body.classList.contains("drawer-on") || drawerTab !== "toc") return;
}

/* ---------- bookmarks ---------- */
function toggleBookmark() {
  var a = captureAnchor(); if (!a) return;
  var ex = marks.m.filter(function (m) { return m.t === "bm" && m.p === a.p; })[0];
  if (ex) { delMark(ex.id); toast("책갈피 삭제"); return; }
  if (marks.m.length >= 500) { toast("이 작품의 표시가 500개를 넘었습니다", 3000); return; }
  var frac = Math.min(1, cum[a.p] / WORK.chars);
  marks.m.push({ id: "bm_" + Date.now(), t: "bm", p: a.p, o: 0, frac: frac, ch: chapterOf(a.p),
    text: (paras[a.p] ? paras[a.p].textContent : "").replace(/\s+/g, " ").trim().slice(0, 120), created: Date.now() });
  marks.sig = WORK.sig; save(MARK_KEY, marks);
  paintMarkTicks(); paintMarkTabs();
  toast("책갈피 추가 · " + Math.floor(frac * 100) + "%");
}
function delMark(id) {
  marks.m = marks.m.filter(function (m) { return m.id !== id; });
  save(MARK_KEY, marks); paintMarkTicks(); paintMarkTabs();
}
function paintMarkTicks() {
  var box = $("#hair-ticks"); if (!box) return;
  var h = "";
  if (WORK.chapters.length <= 40) WORK.chapters.forEach(function (c) {
    if (c.frac > 0) h += '<i class="tk-ch" style="left:' + (c.frac * 100) + '%"></i>';
  });
  marks.m.forEach(function (m) { h += '<i class="tk-bm" style="left:' + (m.frac * 100) + '%"></i>'; });
  box.innerHTML = h;
}
function paintMarkTabs() {
  $$("#book p.bmk").forEach(function (p) { p.classList.remove("bmk"); });
  marks.m.forEach(function (m) { var p = document.querySelector('[data-p="' + m.p + '"]'); if (p) p.classList.add("bmk"); });
}

/* ---------- resume toast ---------- */
function showResumeToast() {
  if (!prog || prog.frac < 0.005 || TINY) return;
  setTimeout(function () {
    var t = document.createElement("div"); t.id = "resume";
    var cn = WORK.chapters[prog.ch];
    t.innerHTML = '<span>이어서 읽는 중 · ' + Math.floor(prog.frac * 100) + '%' + (cn ? ' · ' + esc(cn.label) : "") + '</span><button>처음부터</button>';
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add("on"); });
    var kill = function () { t.classList.remove("on"); setTimeout(function () { t.remove(); }, 300);
      removeEventListener("scroll", kill); removeEventListener("keydown", kill); };
    t.querySelector("button").addEventListener("click", function (e) {
      e.stopPropagation(); scrollTo({ top: 0, behavior: "auto" }); kill();
    });
    setTimeout(kill, 4000);
    addEventListener("scroll", kill, { once: true, passive: true });
    addEventListener("keydown", kill, { once: true });
  }, 300);
}

/* ============================================================
   Settings drawer
   ============================================================ */
var setEl;
function buildSettings() {
  setEl = document.createElement("aside"); setEl.id = "settings";
  setEl.innerHTML =
    '<div class="st-hd">설정<button class="st-x">✕</button></div><div class="st-body">' +
    grp("활자") +
    row("글자 크기", slider("fs", 15, 30, 1) + '<span class="v" data-v="fs"></span>') +
    row("줄 간격", slider("lh", 1.30, 2.10, 0.02) + '<span class="v" data-v="lh"></span>') +
    row("본문 너비", slider("measure", 45, 92, 1) + '<span class="v" data-v="measure"></span>') +
    row("글꼴", seg("font", [["1", "시트카"], ["2", "콘스탄시아"], ["3", "조지아"], ["4", "산세리프"]])) +
    row("양쪽 정렬", tog("justify")) +
    row("첫 줄 들여쓰기", tog("indent")) +
    grp("화면") +
    row("테마", seg("theme", [["light", "종이"], ["sepia", "세피아"], ["dark", "야간"], ["night", "심야"]])) +
    row("화면 어둡기", slider("dim", 0, 55, 5) + '<span class="v" data-v="dim"></span>') +
    row("화면 켜두기", tog("wake")) +
    grp("표시") +
    row("남은 시간 표시", tog("showRemaining")) +
    row("세션 시간 표시", tog("showSession")) +
    grp("자료") +
    row("읽기 속도", '<span class="v" data-v="wpm"></span><button class="mini" data-do="wpmreset">초기화</button>') +
    row("내보내기", '<button class="mini" data-do="export">저장</button>') +
    row("가져오기", '<label class="mini">파일 선택<input type="file" accept="application/json" hidden data-do="import"></label>') +
    grp("초기화") +
    row("모두 기본값으로", '<button class="mini" data-do="reset">되돌리기</button>') +
    '</div>';
  document.body.appendChild(setEl);

  setEl.addEventListener("input", function (e) {
    var k = e.target.dataset.k;
    if (k) {
      var val = e.target.type === "range" ? parseFloat(e.target.value) : e.target.value;
      withPin(function () { S[k] = val; applySettings(); });
      syncSettings(); saveSettingsSoon(); updateHud();
    }
    if (e.target.dataset.do === "import") doImport(e.target.files[0]);
  });
  setEl.addEventListener("click", function (e) {
    if (e.target.closest(".st-x")) return closeOverlays();
    var sg = e.target.closest("[data-seg]");
    if (sg) { var k = sg.parentNode.dataset.k; withPin(function () { S[k] = sg.dataset.seg; applySettings(); }); syncSettings(); saveSettingsSoon(); return; }
    var tg = e.target.closest("[data-tog]");
    if (tg) { var k2 = tg.dataset.tog; withPin(function () { S[k2] = !S[k2]; applySettings(); }); syncSettings(); saveSettingsSoon(); updateHud(); if (k2 === "wake") setWake(); return; }
    var d = e.target.dataset.do;
    if (d === "wpmreset") { S.wpm = 200; S.wpmSamples = 0; saveSettingsSoon(); syncSettings(); updateHud(); }
    if (d === "export") doExport();
    if (d === "reset") { if (confirm("표시 설정을 모두 기본값으로 되돌립니다.")) { var keep = { wpm: S.wpm, wpmSamples: S.wpmSamples, seenHint: true }; S = Object.assign({}, DEFAULTS, keep); S.theme = (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light"; withPin(applySettings); syncSettings(); saveSettingsSoon(); } }
  });
  syncSettings();
  if (!("wakeLock" in navigator)) { var r = setEl.querySelector('[data-tog="wake"]'); if (r) r.closest(".st-row").hidden = true; }
}
function grp(t) { return '<div class="st-grp">' + t + '</div>'; }
function row(l, c) { return '<div class="st-row"><span class="st-l">' + l + '</span><span class="st-c">' + c + '</span></div>'; }
function slider(k, a, b, s) { return '<input type="range" data-k="' + k + '" min="' + a + '" max="' + b + '" step="' + s + '">'; }
function seg(k, opts) { return '<span class="st-seg" data-k="' + k + '">' + opts.map(function (o) { return '<button data-seg="' + o[0] + '">' + o[1] + '</button>'; }).join("") + '</span>'; }
function tog(k) { return '<button class="st-tog" data-tog="' + k + '"><i></i></button>'; }
function syncSettings() {
  if (!setEl) return;
  ["fs", "lh", "measure", "dim"].forEach(function (k) { var i = setEl.querySelector('[data-k="' + k + '"]'); if (i) i.value = S[k]; });
  var u = { fs: S.fs + "px", lh: S.lh.toFixed(2), measure: S.measure + "자", dim: S.dim + "%", wpm: "분당 " + S.wpm + "단어" };
  Object.keys(u).forEach(function (k) { var e = setEl.querySelector('[data-v="' + k + '"]'); if (e) e.textContent = u[k]; });
  $$(".st-seg", setEl).forEach(function (sg) {
    $$("[data-seg]", sg).forEach(function (b) { b.classList.toggle("on", S[sg.dataset.k] === b.dataset.seg); });
  });
  $$(".st-tog", setEl).forEach(function (b) { b.classList.toggle("on", !!S[b.dataset.tog]); });
}
function openSettings() { document.body.classList.add("set-on"); revealHud(); syncSettings(); }

var wakeRef = null;
function setWake() {
  if (S.wake && "wakeLock" in navigator) navigator.wakeLock.request("screen").then(function (w) { wakeRef = w; }).catch(function () {});
  else if (wakeRef) { wakeRef.release(); wakeRef = null; }
}
addEventListener("visibilitychange", function () { if (!document.hidden && S.wake) setWake(); });

function doExport() {
  var out = {};
  for (var i = 0; i < LS.length; i++) { var k = LS.key(i); if (k && k.indexOf("rdr/v1/") === 0) out[k] = LS.getItem(k); }
  var blob = new Blob([JSON.stringify({ app: "seojae", v: 1, at: Date.now(), data: out }, null, 1)], { type: "application/json" });
  var d = new Date(), pad = function (n) { return n < 10 ? "0" + n : n; };
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "reading-backup-" + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + ".json";
  a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
}
function doImport(file) {
  if (!file) return;
  var fr = new FileReader();
  fr.onload = function () {
    try {
      var j = JSON.parse(fr.result);
      if (!j || j.app !== "seojae") throw 0;
      var n = 0;
      Object.keys(j.data).forEach(function (k) {
        if (k.indexOf("rdr/v1/prog/") === 0) {
          var incoming = JSON.parse(j.data[k]), cur = load(k, null);
          if (!cur || (incoming.maxFrac || 0) > (cur.maxFrac || 0)) { LS.setItem(k, j.data[k]); n++; }
        } else if (k.indexOf("rdr/v1/marks/") === 0) {
          var inc = JSON.parse(j.data[k]), c2 = load(k, { m: [] });
          var ids = {}; (c2.m || []).forEach(function (m) { ids[m.id] = 1; });
          (inc.m || []).forEach(function (m) { if (!ids[m.id]) { c2.m.push(m); n++; } });
          save(k, c2);
        } else if (k === "rdr/v1/settings" || k === "rdr/v1/session") { LS.setItem(k, j.data[k]); }
      });
      toast(n + "개 항목을 가져왔습니다. 새로 고칩니다.", 2500);
      setTimeout(function () { location.reload(); }, 1200);
    } catch (e) { toast("가져오기에 실패했습니다", 3000); }
  };
  fr.readAsText(file);
}

/* ============================================================
   Work-switch palette (w)
   ============================================================ */
var pal;
function buildPalette() {
  if (pal) return;
  pal = document.createElement("div"); pal.id = "palette";
  pal.innerHTML = '<div class="pl-box"><input class="pl-q" placeholder="작품 또는 작가 검색"><div class="pl-list"></div></div>';
  document.body.appendChild(pal);
  $(".pl-q", pal).addEventListener("input", renderPalette);
  $(".pl-q", pal).addEventListener("keydown", function (e) {
    var rows = $$(".pl-row", pal), i = rows.findIndex(function (r) { return r.classList.contains("on"); });
    if (e.key === "ArrowDown") { e.preventDefault(); if (rows[i]) rows[i].classList.remove("on"); (rows[Math.min(i + 1, rows.length - 1)] || {}).classList && rows[Math.min(i + 1, rows.length - 1)].classList.add("on"); scrollRow(pal); }
    if (e.key === "ArrowUp") { e.preventDefault(); if (rows[i]) rows[i].classList.remove("on"); (rows[Math.max(i - 1, 0)] || {}).classList && rows[Math.max(i - 1, 0)].classList.add("on"); scrollRow(pal); }
    if (e.key === "Enter") { var r = $(".pl-row.on", pal); if (r) go(r.dataset.href); }
  });
  pal.addEventListener("click", function (e) {
    var r = e.target.closest(".pl-row"); if (r) go(r.dataset.href);
    else if (e.target === pal) closeOverlays();
  });
}
function scrollRow(root) { var r = $(".pl-row.on", root); if (r) r.scrollIntoView({ block: "nearest" }); }
function go(href) { flush(true); busWrite(); location.href = href; }
function openPalette() {
  buildPalette(); document.body.classList.add("pal-on"); revealHud();
  $(".pl-q", pal).value = ""; renderPalette(); setTimeout(function () { $(".pl-q", pal).focus(); }, 30);
}
function fuzzy(q, s) {
  q = q.toLowerCase(); s = s.toLowerCase();
  var i = 0, score = 0, streak = 0;
  for (var j = 0; j < s.length && i < q.length; j++) {
    if (s[j] === q[i]) { i++; streak++; score += streak * 2 + (j === 0 ? 6 : 0); }
    else streak = 0;
  }
  return i === q.length ? score : -1;
}
function renderPalette() {
  var q = $(".pl-q", pal).value.trim();
  var list = $(".pl-list", pal), h = "";
  var progOf = function (id) { return load("rdr/v1/prog/" + id, null); };
  if (!q) {
    var reading = MANIFEST.map(function (w) { return { w: w, p: progOf(w.id) }; })
      .filter(function (x) { return x.p && x.p.frac > 0.002 && !x.p.finished && x.w.id !== WORK.id; })
      .sort(function (a, b) { return b.p.updated - a.p.updated; }).slice(0, 5);
    if (reading.length) { h += '<div class="pl-h">이어서 읽기</div>'; reading.forEach(function (x) { h += palRow(x.w, x.p); }); }
    var same = MANIFEST.filter(function (w) { return w.author === WORK.author; }).sort(function (a, b) { return a.year - b.year; });
    var idx = same.findIndex(function (w) { return w.id === WORK.id; });
    var near = [same[idx - 1], same[idx + 1]].filter(Boolean);
    if (near.length) { h += '<div class="pl-h">같은 작가</div>'; near.forEach(function (w) { h += palRow(w, progOf(w.id)); }); }
    var sess = load("rdr/v1/session", { recent: [] });
    var rec = (sess.recent || []).filter(function (id) { return id !== WORK.id; }).slice(0, 4)
      .map(function (id) { return MANIFEST.filter(function (w) { return w.id === id; })[0]; }).filter(Boolean);
    if (rec.length) { h += '<div class="pl-h">최근 연 작품</div>'; rec.forEach(function (w) { h += palRow(w, progOf(w.id)); }); }
  } else {
    var scored = MANIFEST.map(function (w) {
      var s = Math.max(fuzzy(q, w.title), fuzzy(q, w.titleKo || ""), fuzzy(q, w.authorKo), fuzzy(q, w.authorEn), fuzzy(q, w.author));
      return { w: w, s: s };
    }).filter(function (x) { return x.s >= 0; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 40);
    if (!scored.length) h = '<p class="pl-empty">일치하는 작품이 없습니다.</p>';
    scored.forEach(function (x) { h += palRow(x.w, progOf(x.w.id)); });
  }
  list.innerHTML = h;
  var f = $(".pl-row", list); if (f) f.classList.add("on");
}
function palRow(w, p) {
  var right = p ? (p.finished ? "완독" : Math.floor(p.frac * 100) + "%") : "—";
  var when = p ? ago(p.updated) : "";
  return '<div class="pl-row" data-href="' + esc(w.href) + '"><span class="pl-t">' + esc(w.title) + '</span>' +
    '<span class="pl-m">' + esc(w.authorKo) + ' · ' + w.year + '</span>' +
    '<span class="pl-p">' + right + '</span><span class="pl-w">' + when + '</span></div>';
}
function siblingWork(d) {
  var same = MANIFEST.filter(function (w) { return w.author === WORK.author; }).sort(function (a, b) { return a.year - b.year || a.title.localeCompare(b.title); });
  var i = same.findIndex(function (w) { return w.id === WORK.id; });
  var t = same[i + d];
  if (!t) { toast(d > 0 ? "이 작가의 마지막 작품입니다" : "이 작가의 첫 작품입니다"); return; }
  go(t.href);
}

/* ============================================================
   Keyboard
   ============================================================ */
function bindKeys() {
  addEventListener("keydown", function (e) {
    lastActive = Date.now();
    var tag = (e.target.tagName || "").toLowerCase();
    var typing = tag === "input" || tag === "textarea" || e.target.isContentEditable;
    if (e.key === "Escape") {
      if (anyOverlay()) { closeOverlays(); e.preventDefault(); return; }
      hudPinned = false; hideHud(); escMute = Date.now() + 600; return;
    }
    if (typing) return;
    if (e.ctrlKey && e.key.toLowerCase() === "z") { e.preventDefault(); popUndo(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    var k = e.key;
    switch (k) {
      case " ": case "PageDown": e.preventDefault(); pageBy(e.shiftKey ? -1 : 1); return;
      case "PageUp": e.preventDefault(); pageBy(-1); return;
      case "ArrowDown": case "j": e.preventDefault(); scrollBy(0, 3 * S.fs * S.lh); flushSoon(); return;
      case "ArrowUp": case "k": e.preventDefault(); scrollBy(0, -3 * S.fs * S.lh); flushSoon(); return;
      case "ArrowRight": case "n": e.preventDefault(); chapterNav(1); revealHud(); return;
      case "ArrowLeft": case "p": e.preventDefault(); chapterNav(-1); revealHud(); return;
      case "]": e.preventDefault(); siblingWork(1); return;
      case "[": e.preventDefault(); siblingWork(-1); return;
      case "Home": e.preventDefault(); pushUndo(); scrollTo({ top: 0 }); flushSoon(); return;
      case "End": e.preventDefault(); pushUndo(); scrollTo({ top: document.body.scrollHeight }); flushSoon(); return;
      case "Enter": if (prog) { e.preventDefault(); restoreAnchor(prog); } return;
      case "t": e.preventDefault(); document.body.classList.contains("drawer-on") && drawerTab === "toc" ? closeOverlays() : openDrawer("toc"); return;
      case "b": e.preventDefault(); toggleBookmark(); revealHud(); return;
      case "B": e.preventDefault(); openDrawer("bm"); return;
      case ",": e.preventDefault(); document.body.classList.contains("set-on") ? closeOverlays() : openSettings(); return;
      case "w": e.preventDefault(); openPalette(); return;
      case "?": e.preventDefault(); showHelp(); return;
      case "Backspace": e.preventDefault(); go("index.html"); return;
      case "+": case "=": e.preventDefault(); bump("fs", 1, 15, 30); return;
      case "-": e.preventDefault(); bump("fs", -1, 15, 30); return;
      case "0": e.preventDefault(); withPin(function () { S.fs = DEFAULTS.fs; S.lh = DEFAULTS.lh; S.measure = DEFAULTS.measure; applySettings(); }); syncSettings(); saveSettingsSoon(); toast("기본값"); return;
      case ">": e.preventDefault(); bump("measure", 2, 45, 92); return;
      case "<": e.preventDefault(); bump("measure", -2, 45, 92); return;
      case "d": e.preventDefault(); cycleTheme(); return;
      case "f": e.preventDefault(); document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen().catch(function () {}); return;
      case "u": e.preventDefault(); hudPinned = !hudPinned; hudPinned ? revealHud() : hideHud(); toast(hudPinned ? "상태 표시줄 고정" : "상태 표시줄 자동 숨김"); return;
    }
  });
}
function bump(k, d, lo, hi) {
  withPin(function () { S[k] = Math.max(lo, Math.min(hi, +(S[k] + d).toFixed(2))); applySettings(); });
  syncSettings(); saveSettingsSoon(); updateHud();
  toast(k === "fs" ? "글자 크기 " + S.fs + "px" : "본문 너비 " + S.measure + "자");
}
var THEMES = ["light", "sepia", "dark", "night"], THEME_KO = { light: "종이", sepia: "세피아", dark: "야간", night: "심야" };
function cycleTheme() {
  S.theme = THEMES[(THEMES.indexOf(S.theme) + 1) % THEMES.length];
  applySettings(); syncSettings(); saveSettingsSoon(); toast(THEME_KO[S.theme]);
}
function showHelp() {
  var ex = $("#help"); if (ex) { ex.remove(); return; }
  var rows = [
    ["이동", [["Space", "다음 화면"], ["Shift+Space", "이전 화면"], ["↓ / j", "조금 아래로"], ["↑ / k", "조금 위로"],
      ["→ / n", "다음 장"], ["← / p", "이전 장"], ["]", "같은 작가 다음 작품"], ["[", "같은 작가 이전 작품"],
      ["Home / End", "작품 처음 / 끝"], ["Enter", "저장된 위치로"], ["Ctrl+Z", "이동 취소"]]],
    ["패널", [["t", "목차"], ["b", "책갈피 추가·삭제"], ["B", "책갈피 목록"], [",", "설정"], ["w", "작품 전환"],
      ["Esc", "닫기"], ["?", "단축키"], ["Backspace", "서재로"]]],
    ["표시", [["+ / -", "글자 크게 / 작게"], ["0", "기본값"], ["> / <", "본문 넓게 / 좁게"], ["d", "테마 전환"],
      ["f", "전체화면"], ["u", "상태 표시줄 고정"]]]
  ];
  var h = '<div class="hp-box"><div class="hp-hd">단축키<button class="hp-x">✕</button></div><div class="hp-cols">';
  rows.forEach(function (g) {
    h += '<div class="hp-g"><h4>' + g[0] + '</h4>' + g[1].map(function (r) {
      return '<div class="hp-r"><kbd>' + esc(r[0]) + '</kbd><span>' + r[1] + '</span></div>'; }).join("") + '</div>';
  });
  h += '</div></div>';
  var d = document.createElement("div"); d.id = "help"; d.innerHTML = h;
  document.body.appendChild(d);
  d.addEventListener("click", function (e) { if (e.target === d || e.target.closest(".hp-x")) d.remove(); });
}

/* ---------- go ---------- */
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();

})();
