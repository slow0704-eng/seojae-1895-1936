/* ============================================================
   서재 1895—1936 — single-page portal
   One document holds the library and the reader. Book text is injected on
   demand with a <script> tag: fetch() is blocked under file://, script src
   is not. One origin, so localStorage simply works.
   ============================================================ */
(function () {
"use strict";

/* ---------- storage ---------- */
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
  r.style.setProperty("--lh", String(+(S.lh - (S.fs - 20) * 0.007).toFixed(3)));
  r.style.setProperty("--track", ((20 - S.fs) * 0.0018).toFixed(4) + "em");
  r.style.setProperty("--cpl", String(S.measure));
  r.dataset.theme = S.theme;
  r.dataset.font = S.font;
  r.dataset.justify = S.justify ? "on" : "off";
  r.dataset.indent = S.indent ? "on" : "off";
  var d = document.getElementById("dimmer");
  if (d) d.style.opacity = (S.dim / 100);
}
applySettings();

/* ---------- helpers ---------- */
function throttle(fn, ms) {
  var t = null, pending = false;
  return function () {
    pending = true;
    if (t) return;
    t = setTimeout(function () { t = null; if (pending) { pending = false; fn(); } }, ms);
  };
}
var saveSettingsSoon = throttle(function () { S.updated = Date.now(); save("rdr/v1/settings", S); }, 400);
function $(s, c) { return (c || document).querySelector(s); }
function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }
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
var toastEl = null, toastT = null;
function toast(msg, ms) {
  if (!toastEl) { toastEl = document.createElement("div"); toastEl.id = "toast"; document.body.appendChild(toastEl); }
  toastEl.textContent = msg;
  toastEl.classList.add("on");
  clearTimeout(toastT);
  toastT = setTimeout(function () { toastEl.classList.remove("on"); }, ms || 1400);
}

/* ---------- catalogue ---------- */
var byId = {};
MANIFEST.forEach(function (w) { byId[w.id] = w; });
function progOf(id) { return load("rdr/v1/prog/" + id, null); }
function marksOf(id) { var m = load("rdr/v1/marks/" + id, null); return (m && m.m) ? m.m.length : 0; }

/* ============================================================
   Book loading — <script src> works under file://, fetch() does not
   ============================================================ */
var CACHE = new Map(), pending = {};
window.SEOJAE = {
  receive: function (d) {
    CACHE.set(d.id, d);
    while (CACHE.size > 4) CACHE.delete(CACHE.keys().next().value);
    var cbs = pending[d.id] || []; delete pending[d.id];
    cbs.forEach(function (cb) { cb(d); });
  }
};
function loadBook(id, cb) {
  if (CACHE.has(id)) { CACHE.set(id, CACHE.get(id)); return cb(CACHE.get(id)); }
  if (pending[id]) { pending[id].push(cb); return; }
  pending[id] = [cb];
  var s = document.createElement("script");
  s.src = "data/" + encodeURIComponent(id) + ".js";
  s.async = true;
  s.onerror = function () {
    delete pending[id];
    document.body.classList.remove("loading");
    toast("본문 파일을 불러오지 못했습니다 · data/" + id + ".js", 6000);
  };
  document.head.appendChild(s);
}

/* ============================================================
   Reader
   ============================================================ */
var WORK = null, paras = [], cum = null, prog = null, marks = null, TINY = false;
var PROG_KEY = "", MARK_KEY = "";
var libScroll = 0;
var view = "library";      /* "library" | "reader" */

function READLINE() { return Math.round(innerHeight * 0.18); }
function norm(s) { return s.replace(/\s+/g, " ").trim().slice(0, 21).toLowerCase(); }

function titlePage(w) {
  return '<div class="titlepage"><h1 class="work">' + esc(w.title) + '</h1>' +
    (w.titleKo && w.titleKo !== w.title ? '<p class="work-ko">' + esc(w.titleKo) + '</p>' : "") +
    '<p class="byline">' + esc(w.authorEn) + '</p>' +
    '<p class="year">' + w.year + '</p><hr class="tp-rule"></div>';
}
var END_ORN = '<svg viewBox="0 0 14 14" width="14" height="14" aria-hidden="true">' +
  '<path d="M7 .7 13.3 7 7 13.3.7 7Z" fill="none" stroke="currentColor" stroke-width="1" opacity=".55"/>' +
  '<path d="M7 4.1 9.9 7 7 9.9 4.1 7Z" fill="currentColor"/></svg>';
function endMatter(w) {
  return '<p class="endmark">' + END_ORN + '</p><p class="colophon">' +
    w.year + ' &middot; ' + esc(w.authorEn.toUpperCase()) + '</p>';
}

function openWork(id, opts) {
  var w = byId[id];
  if (!w) return goLibrary(true);
  if (view === "library") libScroll = scrollY;
  document.body.classList.add("loading");
  loadBook(id, function (d) {
    document.body.classList.remove("loading");
    WORK = { id: w.id, title: w.title, titleKo: w.titleKo, author: w.author,
             authorKo: w.authorKo, authorEn: w.authorEn, year: w.year,
             sig: d.sig, chars: 0, paras: 0,
             chapters: (d.chapters || []).map(function (c) { return Object.assign({}, c); }) };
    PROG_KEY = "rdr/v1/prog/" + WORK.id;
    MARK_KEY = "rdr/v1/marks/" + WORK.id;

    var bookEl = $("#book");
    bookEl.innerHTML = titlePage(w) + d.html + endMatter(w);
    mount(opts || {});
  });
}

function mount(opts) {
  paras = $$("#book p[data-p]");
  cum = new Uint32Array(paras.length + 1);
  for (var i = 0; i < paras.length; i++) cum[i + 1] = cum[i] + paras[i].textContent.length;
  WORK.chars = cum[paras.length] || 1;
  WORK.paras = paras.length;
  TINY = WORK.chars < 4000;

  prog = load(PROG_KEY, null);
  marks = load(MARK_KEY, { v: 1, sig: WORK.sig, m: [] });
  if (!marks.m) marks.m = [];

  buildChapterIndex();
  $("#hairline").classList.toggle("hidden", TINY);
  hud.title.innerHTML = "<b>" + esc(WORK.title) + "</b> <i>" + esc(WORK.authorKo) + "</i>";
  document.title = WORK.title + " · 서재";
  paintMarkTicks(); paintMarkTabs();
  drawerTab = "toc";
  sessionStart = Date.now(); segChars = null; undoStack = [];

  view = "reader";
  touched = false;
  document.body.dataset.view = "reader";

  var restored = false;
  if (prog && !opts.fromStart) {
    if (prog.sig !== WORK.sig) {
      var el = document.querySelector('[data-p="' + prog.p + '"]');
      var ok = el && norm(el.textContent).indexOf(prog.sample) === 0;
      if (ok) prog.sig = WORK.sig;
      else { prog = resyncByFraction(prog.frac); toast("본문이 갱신되어 위치를 대략 복원했습니다", 5000); }
    }
    if (prog && prog.frac > 0.002 && !TINY) {
      restoreAnchor(prog, showResumeToast); restored = true;
    }
  }
  if (!restored) scrollTo({ top: 0, behavior: "auto" });
  updateHud();

  if (!S.seenHint) {
    S.seenHint = true; saveSettingsSoon();
    setTimeout(function () { toast("?  단축키   ·   ,  설정   ·   t  목차   ·   Backspace  서재", 6500); }, 900);
  }
}

function unmount() {
  if (WORK) flush(true);
  closeOverlays(); hideHud();
  $("#book").innerHTML = "";
  WORK = null; paras = []; cum = null; prog = null;
}

function goLibrary(replace) {
  unmount();
  view = "library";
  document.body.dataset.view = "library";
  document.title = "서재 1895—1936";
  paintCards(); paintShelf(); paintMine();
  var h = "#/";
  if (replace) history.replaceState(null, "", h); else if (location.hash !== h) history.pushState(null, "", h);
  scrollTo({ top: libScroll, behavior: "auto" });
}

function goWork(id, opts) {
  var h = "#/w/" + encodeURIComponent(id);
  if (location.hash !== h) history.pushState(null, "", h);
  openWork(id, opts);
}

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
  if (!el) { if (done) done(); return false; }
  var sec = el.closest(".ch"); if (sec) sec.style.contentVisibility = "visible";
  var node = el.firstChild, line = READLINE(), r = document.createRange();
  if (node && node.nodeType === 3) {
    r.setStart(node, Math.min(a.o || 0, node.length));
    r.setEnd(node, Math.min((a.o || 0) + 1, node.length));
  } else r.selectNode(el);
  var pass = 0;
  restoring++;
  (function step() {
    var dy = r.getBoundingClientRect().top - line;
    if (Math.abs(dy) <= 2 || ++pass > 6) {
      if (sec) sec.style.contentVisibility = "";
      /* let the scroll events this caused drain before re-arming the guard */
      setTimeout(function () { restoring = Math.max(0, restoring - 1); }, 120);
      updateHud(); if (done) done();
      return;
    }
    scrollBy(0, dy);
    requestAnimationFrame(step);
  })();
  return true;
}
function withPin(fn) {
  if (view !== "reader") { fn(); return; }
  var a = captureAnchor(); fn(); requestAnimationFrame(function () { if (a) restoreAnchor(a); });
}
function resyncByFraction(frac) {
  var target = (frac || 0) * WORK.chars, lo = 0, hi = paras.length - 1;
  while (lo < hi) { var mid = (lo + hi) >> 1; if (cum[mid + 1] < target) lo = mid + 1; else hi = mid; }
  return { v: 1, sig: WORK.sig, p: lo, o: 0, frac: frac, ch: chapterOf(lo),
    sample: norm(paras[lo] ? paras[lo].textContent : ""), paras: paras.length,
    maxFrac: frac, readMs: (prog && prog.readMs) || 0, opened: Date.now(),
    updated: Date.now(), finished: false };
}

/* ---------- progress ---------- */
function chapterOf(pIdx) {
  var cs = WORK.chapters, r = 0;
  for (var i = 0; i < cs.length; i++) if (cs[i].firstP <= pIdx) r = i; else break;
  return r;
}
var lastActive = Date.now(), segStart = Date.now(), segChars = null;
var sessionStart = Date.now();
/* The browser restores its own scroll position on history navigation, which
   lands *after* our anchor restore and silently reset saved progress to 0%.
   Own the scroll ourselves. */
if ("scrollRestoration" in history) history.scrollRestoration = "manual";
/* Nothing is written until the reader actually moves in this book: opening a
   work and leaving it untouched must never overwrite where they were. */
var touched = false, restoring = 0;

function flush() {
  if (!WORK || !paras.length || !touched) return;
  var a = captureAnchor(); if (!a) return;
  var frac = Math.min(1, (cum[a.p] + a.o) / WORK.chars);
  var pv = prog || { readMs: 0, opened: Date.now(), maxFrac: 0 };
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
}
var flushSoon = throttle(flush, 1500);

function heartbeat() {
  if (document.hidden || view !== "reader" || !WORK) return;
  if (Date.now() - lastActive > 90000) return;
  if (prog) { prog.readMs = (prog.readMs || 0) + 15000; save(PROG_KEY, prog); }
  var sess = load("rdr/v1/session", { v: 1, recent: [], totalMs: 0 });
  sess.totalMs = (sess.totalMs || 0) + 15000; save("rdr/v1/session", sess);
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
setInterval(heartbeat, 15000);

/* ============================================================
   HUD
   ============================================================ */
var hud = {}, hudOn = false, hudPinned = false, hideT = null, escMute = 0;

function buildHud() {
  hud.top = $("#hud-top"); hud.bot = $("#hud-bot"); hud.bar = $("#hairline");
  hud.title = $(".h-title"); hud.ch = $(".h-ch");
  hud.pct = $(".h-pct"); hud.rem = $(".h-rem"); hud.sess = $(".h-sess");
  hud.fill = $("#hair-fill");

  hud.top.addEventListener("click", function (e) {
    var b = e.target.closest("[data-act]"); if (!b) return;
    if (b.dataset.act === "lib") goLibrary();
    if (b.dataset.act === "toc") openDrawer("toc");
    if (b.dataset.act === "bm") toggleBookmark();
    if (b.dataset.act === "set") openSettings();
  });
  hud.bar.addEventListener("click", function (e) {
    if (!hudOn || view !== "reader") return;
    jumpToFraction(e.clientX / innerWidth);
  });
  hud.rem.addEventListener("mouseenter", function () { hud.rem.dataset.hover = "1"; updateHud(); });
  hud.rem.addEventListener("mouseleave", function () { delete hud.rem.dataset.hover; updateHud(); });
}

function updateHud() {
  if (view !== "reader" || !WORK || !hud.fill) return;
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
        var ci = chapterOf(a.p);
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
}

function revealHud() {
  if (view !== "reader") return;
  if (!hudOn) { hudOn = true; document.body.classList.add("hud-on"); }
  clearTimeout(hideT);
  if (!hudPinned && !anyOverlay()) hideT = setTimeout(hideHud, 2500);
}
function hideHud() { if (hudPinned || anyOverlay()) return; hudOn = false; document.body.classList.remove("hud-on"); }
function anyOverlay() { return document.body.classList.contains("drawer-on") || document.body.classList.contains("set-on") || document.body.classList.contains("pal-on"); }

/* ---------- movement ---------- */
function pageBy(dir) {
  touched = true;
  scrollBy({ top: dir * (innerHeight - 2 * S.fs * S.lh - 24), behavior: "smooth" });
  lastActive = Date.now(); flushSoon();
}
function jumpToFraction(f) {
  touched = true;
  var target = f * WORK.chars, lo = 0, hi = paras.length - 1;
  while (lo < hi) { var mid = (lo + hi) >> 1; if (cum[mid + 1] < target) lo = mid + 1; else hi = mid; }
  pushUndo();
  restoreAnchor({ p: lo, o: 0 }, function () { flush(); });
}
function buildChapterIndex() {
  if (!WORK.chapters.length) WORK.chapters = [{ firstP: 0, label: WORK.title, title: "", kind: "chapter" }];
  WORK.chapters.forEach(function (c, i) { c.frac = cum[c.firstP] / WORK.chars; c.i = i; });
}
function gotoChapter(i) {
  var cs = WORK.chapters;
  if (cs.length < 2) { toast("장 구분이 없는 작품입니다"); return; }
  i = Math.max(0, Math.min(cs.length - 1, i));
  touched = true;
  pushUndo();
  restoreAnchor({ p: cs[i].firstP, o: 0 }, function () {
    flush(); toast(cs[i].label + (cs[i].title ? " · " + cs[i].title : ""), 1200);
  });
}
var lastPTime = 0;
function chapterNav(d) {
  var cs = WORK.chapters; if (cs.length < 2) { toast("장 구분이 없는 작품입니다"); return; }
  var a = captureAnchor(); if (!a) return;
  var ci = chapterOf(a.p);
  if (d > 0) return gotoChapter(ci + 1);
  var into = cum[a.p] + a.o - cum[cs[ci].firstP], now = Date.now();
  if (into > 300 && now - lastPTime > 1500) { lastPTime = now; return gotoChapter(ci); }
  lastPTime = now; gotoChapter(ci - 1);
}
var undoStack = [];
function pushUndo() { var a = captureAnchor(); if (a) { undoStack.push({ a: a, t: Date.now() }); if (undoStack.length > 5) undoStack.shift(); } }
function popUndo() {
  var u = undoStack.pop();
  if (!u || Date.now() - u.t > 30000) { toast("되돌릴 이동이 없습니다"); return; }
  restoreAnchor(u.a, function () { flush(); toast("이동을 취소했습니다"); });
}
function siblingWork(d) {
  var same = MANIFEST.filter(function (w) { return w.author === WORK.author; })
    .sort(function (a, b) { return a.year - b.year || a.title.localeCompare(b.title); });
  var i = same.findIndex(function (w) { return w.id === WORK.id; });
  var t = same[i + d];
  if (!t) { toast(d > 0 ? "이 작가의 마지막 작품입니다" : "이 작가의 첫 작품입니다"); return; }
  flush(); goWork(t.id);
}

/* ============================================================
   Drawer
   ============================================================ */
var drawer, drawerTab = "toc";
function buildDrawer() {
  drawer = $("#drawer");
  $("#scrim").addEventListener("click", closeOverlays);
  drawer.addEventListener("click", function (e) {
    var t = e.target.closest("[data-tab]"); if (t) { drawerTab = t.dataset.tab; renderDrawer(); return; }
    if (e.target.closest(".dw-x")) return closeOverlays();
    var row = e.target.closest("[data-ch]");
    if (row) { closeOverlays(); gotoChapter(+row.dataset.ch); return; }
    var bm = e.target.closest("[data-bm]");
    if (bm) {
      if (e.target.closest(".bm-del")) { delMark(bm.dataset.bm); renderDrawer(); return; }
      var m = marks.m.filter(function (x) { return x.id === bm.dataset.bm; })[0];
      if (m) { closeOverlays(); touched = true; pushUndo(); restoreAnchor({ p: m.p, o: 0 }, flush); }
    }
  });
  $(".dw-filter", drawer).addEventListener("input", renderDrawer);
}
function openDrawer(tab) {
  if (view !== "reader") return;
  drawerTab = tab || "toc"; document.body.classList.add("drawer-on"); revealHud(); renderDrawer();
}
function closeOverlays() {
  document.body.classList.remove("drawer-on", "set-on", "pal-on");
  escMute = Date.now() + 600;
  clearTimeout(hideT); hideT = setTimeout(hideHud, 2500);
}
function renderDrawer() {
  if (!WORK) return;
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
      if (c.kind === "part") {
        h += '<div class="dw-part' + (c.i === cur ? " cur" : "") + '" data-ch="' + c.i + '">' + esc(c.label || "") + "</div>";
        return;
      }
      var endF = WORK.chapters[c.i + 1] ? WORK.chapters[c.i + 1].frac : 1;
      var dot = mf >= endF ? "●" : (mf > c.frac ? "◐" : "○");
      h += '<div class="dw-row' + (c.i === cur ? " cur" : "") + '" data-ch="' + c.i + '">' +
        '<span class="dot">' + dot + '</span><span class="lbl">' + esc(c.label || "") +
        (c.title ? ' <em>' + esc(c.title) + "</em>" : "") + "</span>" +
        '<span class="pc">' + Math.floor(c.frac * 100) + "%</span></div>";
    });
    if (!h) h = '<p class="dw-empty">일치하는 장이 없습니다.</p>';
  } else {
    var bms = marks.m.slice().sort(function (a, b) { return a.frac - b.frac; });
    h += '<div class="dw-head">책갈피 · ' + bms.length + "개</div>";
    if (!bms.length) h += '<p class="dw-empty">아직 책갈피가 없습니다.<br><kbd>b</kbd> 를 눌러 현재 위치를 표시하세요.</p>';
    bms.forEach(function (m) {
      h += '<div class="bm-row" data-bm="' + m.id + '"><div class="bm-meta"><span class="pc">' +
        Math.floor(m.frac * 100) + "%</span> " + esc((WORK.chapters[m.ch] || {}).label || "") +
        '</div><div class="bm-txt">' + esc(m.text) + '</div><div class="bm-foot">' +
        ago(m.created) + '<button class="bm-del" title="삭제">✕</button></div></div>';
    });
  }
  body.innerHTML = h;
  var c2 = $(".dw-row.cur", body); if (c2) c2.scrollIntoView({ block: "center" });
}

/* ---------- bookmarks ---------- */
function toggleBookmark() {
  if (view !== "reader") return;
  var a = captureAnchor(); if (!a) return;
  var ex = marks.m.filter(function (m) { return m.t === "bm" && m.p === a.p; })[0];
  if (ex) { delMark(ex.id); toast("책갈피 삭제"); return; }
  if (marks.m.length >= 500) { toast("이 작품의 표시가 500개를 넘었습니다", 3000); return; }
  var frac = Math.min(1, cum[a.p] / WORK.chars);
  marks.m.push({ id: "bm_" + Date.now(), t: "bm", p: a.p, o: 0, frac: frac, ch: chapterOf(a.p),
    text: (paras[a.p] ? paras[a.p].textContent : "").replace(/\s+/g, " ").trim().slice(0, 120),
    created: Date.now() });
  marks.sig = WORK.sig; save(MARK_KEY, marks);
  paintMarkTicks(); paintMarkTabs();
  toast("책갈피 추가 · " + Math.floor(frac * 100) + "%");
}
function delMark(id) {
  marks.m = marks.m.filter(function (m) { return m.id !== id; });
  save(MARK_KEY, marks); paintMarkTicks(); paintMarkTabs();
}
function paintMarkTicks() {
  var box = $("#hair-ticks"); if (!box || !WORK) return;
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

function showResumeToast() {
  if (!prog || prog.frac < 0.005 || TINY) return;
  setTimeout(function () {
    var ex = $("#resume"); if (ex) ex.remove();
    var t = document.createElement("div"); t.id = "resume";
    var cn = WORK.chapters[prog.ch];
    t.innerHTML = "<span>이어서 읽는 중 · " + Math.floor(prog.frac * 100) + "%" +
      (cn ? " · " + esc(cn.label) : "") + "</span><button>처음부터</button>";
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add("on"); });
    var kill = function () { t.classList.remove("on"); setTimeout(function () { t.remove(); }, 300); };
    t.querySelector("button").addEventListener("click", function (e) {
      e.stopPropagation(); scrollTo({ top: 0, behavior: "auto" }); kill();
    });
    setTimeout(kill, 4000);
    addEventListener("scroll", kill, { once: true, passive: true });
    addEventListener("keydown", kill, { once: true });
  }, 300);
}

/* ============================================================
   Settings
   ============================================================ */
var setEl;
function buildSettings() {
  setEl = $("#settings");
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
    if (d === "reset" && confirm("표시 설정을 모두 기본값으로 되돌립니다.")) {
      var keep = { wpm: S.wpm, wpmSamples: S.wpmSamples, seenHint: true };
      S = Object.assign({}, DEFAULTS, keep);
      S.theme = (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
      withPin(applySettings); syncSettings(); saveSettingsSoon();
    }
  });
  syncSettings();
  if (!("wakeLock" in navigator)) { var r = setEl.querySelector('[data-tog="wake"]'); if (r) r.closest(".st-row").hidden = true; }
}
function syncSettings() {
  if (!setEl) return;
  ["fs", "lh", "measure", "dim"].forEach(function (k) { var i = setEl.querySelector('[data-k="' + k + '"]'); if (i) i.value = S[k]; });
  var u = { fs: S.fs + "px", lh: S.lh.toFixed(2), measure: S.measure + "자", dim: S.dim + "%", wpm: "분당 " + S.wpm + "단어" };
  Object.keys(u).forEach(function (k) { var e = setEl.querySelector('[data-v="' + k + '"]'); if (e) e.textContent = u[k]; });
  $$(".st-seg", setEl).forEach(function (sg) {
    $$("[data-seg]", sg).forEach(function (b) { b.classList.toggle("on", S[sg.dataset.k] === b.dataset.seg); });
  });
  $$(".st-tog", setEl).forEach(function (b) { b.classList.toggle("on", !!S[b.dataset.tog]); });
  var th = $("#theme"); if (th) th.value = S.theme;
}
function openSettings() { document.body.classList.add("set-on"); if (view === "reader") revealHud(); syncSettings(); }

var wakeRef = null;
function setWake() {
  if (S.wake && "wakeLock" in navigator) navigator.wakeLock.request("screen").then(function (w) { wakeRef = w; }).catch(function () {});
  else if (wakeRef) { wakeRef.release(); wakeRef = null; }
}
addEventListener("visibilitychange", function () {
  if (!document.hidden && S.wake) setWake();
  if (document.hidden) flush();
});

function doExport() {
  var out = {};
  for (var i = 0; i < LS.length; i++) { var k = LS.key(i); if (k && k.indexOf("rdr/v1/") === 0) out[k] = LS.getItem(k); }
  var blob = new Blob([JSON.stringify({ app: "seojae", v: 1, at: Date.now(), data: out }, null, 1)], { type: "application/json" });
  var d = new Date(), pad = function (n) { return n < 10 ? "0" + n : n; };
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "seojae-backup-" + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + ".json";
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
          var inc = JSON.parse(j.data[k]), cur = load(k, null);
          if (!cur || (inc.maxFrac || 0) > (cur.maxFrac || 0)) { LS.setItem(k, j.data[k]); n++; }
        } else if (k.indexOf("rdr/v1/marks/") === 0) {
          var i2 = JSON.parse(j.data[k]), c2 = load(k, { m: [] });
          var ids = {}; (c2.m || []).forEach(function (m) { ids[m.id] = 1; });
          (i2.m || []).forEach(function (m) { if (!ids[m.id]) { c2.m.push(m); n++; } });
          save(k, c2);
        } else if (k === "rdr/v1/settings" || k === "rdr/v1/session") LS.setItem(k, j.data[k]);
      });
      toast(n + "개 항목을 가져왔습니다. 새로 고칩니다.", 2500);
      setTimeout(function () { location.reload(); }, 1200);
    } catch (e) { toast("가져오기에 실패했습니다", 3000); }
  };
  fr.readAsText(file);
}

/* ============================================================
   Work-switch palette
   ============================================================ */
var pal;
function buildPalette() {
  pal = $("#palette");
  $(".pl-q", pal).addEventListener("input", renderPalette);
  $(".pl-q", pal).addEventListener("keydown", function (e) {
    var rows = $$(".pl-row", pal), i = rows.findIndex(function (r) { return r.classList.contains("on"); });
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      var j = Math.max(0, Math.min(rows.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)));
      if (rows[i]) rows[i].classList.remove("on");
      if (rows[j]) { rows[j].classList.add("on"); rows[j].scrollIntoView({ block: "nearest" }); }
    }
    if (e.key === "Enter") { var r = $(".pl-row.on", pal); if (r) { closeOverlays(); goWork(r.dataset.id); } }
  });
  pal.addEventListener("click", function (e) {
    var r = e.target.closest(".pl-row");
    if (r) { closeOverlays(); goWork(r.dataset.id); }
    else if (e.target === pal) closeOverlays();
  });
}
function openPalette() {
  document.body.classList.add("pal-on"); if (view === "reader") revealHud();
  $(".pl-q", pal).value = ""; renderPalette();
  setTimeout(function () { $(".pl-q", pal).focus(); }, 30);
}
function fuzzy(q, s) {
  q = q.toLowerCase(); s = String(s || "").toLowerCase();
  var i = 0, score = 0, streak = 0;
  for (var j = 0; j < s.length && i < q.length; j++) {
    if (s[j] === q[i]) { i++; streak++; score += streak * 2 + (j === 0 ? 6 : 0); } else streak = 0;
  }
  return i === q.length ? score : -1;
}
function renderPalette() {
  var q = $(".pl-q", pal).value.trim(), list = $(".pl-list", pal), h = "";
  if (!q) {
    var reading = MANIFEST.map(function (w) { return { w: w, p: progOf(w.id) }; })
      .filter(function (x) { return x.p && x.p.frac > 0.002 && !x.p.finished && (!WORK || x.w.id !== WORK.id); })
      .sort(function (a, b) { return b.p.updated - a.p.updated; }).slice(0, 5);
    if (reading.length) { h += '<div class="pl-h">이어서 읽기</div>'; reading.forEach(function (x) { h += palRow(x.w, x.p); }); }
    if (WORK) {
      var same = MANIFEST.filter(function (w) { return w.author === WORK.author; }).sort(function (a, b) { return a.year - b.year; });
      var idx = same.findIndex(function (w) { return w.id === WORK.id; });
      var near = [same[idx - 1], same[idx + 1]].filter(Boolean);
      if (near.length) { h += '<div class="pl-h">같은 작가</div>'; near.forEach(function (w) { h += palRow(w, progOf(w.id)); }); }
    }
    var sess = load("rdr/v1/session", { recent: [] });
    var rec = (sess.recent || []).filter(function (id) { return !WORK || id !== WORK.id; }).slice(0, 4)
      .map(function (id) { return byId[id]; }).filter(Boolean);
    if (rec.length) { h += '<div class="pl-h">최근 연 작품</div>'; rec.forEach(function (w) { h += palRow(w, progOf(w.id)); }); }
  } else {
    var scored = MANIFEST.map(function (w) {
      return { w: w, s: Math.max(fuzzy(q, w.title), fuzzy(q, w.titleKo), fuzzy(q, w.authorKo), fuzzy(q, w.authorEn), fuzzy(q, w.author)) };
    }).filter(function (x) { return x.s >= 0; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 40);
    if (!scored.length) h = '<p class="pl-empty">일치하는 작품이 없습니다.</p>';
    scored.forEach(function (x) { h += palRow(x.w, progOf(x.w.id)); });
  }
  list.innerHTML = h;
  var f = $(".pl-row", list); if (f) f.classList.add("on");
}
function palRow(w, p) {
  return '<div class="pl-row" data-id="' + esc(w.id) + '"><span class="pl-t">' + esc(w.title) + "</span>" +
    '<span class="pl-m">' + esc(w.authorKo) + " · " + w.year + "</span>" +
    '<span class="pl-p">' + (p ? (p.finished ? "완독" : Math.floor(p.frac * 100) + "%") : "—") + "</span>" +
    '<span class="pl-w">' + (p ? ago(p.updated) : "") + "</span></div>";
}

/* ============================================================
   Library view
   ============================================================ */
function paintCards() {
  $$(".card").forEach(function (c) {
    var p = progOf(c.dataset.id), pct = $(".cap__pct", c);
    c.removeAttribute("data-done"); c.style.removeProperty("--progress");
    var oldBm = $(".cap__bm", c); if (oldBm) oldBm.remove();
    if (!p || !p.frac) { pct.textContent = ""; }
    else {
      c.style.setProperty("--progress", p.frac.toFixed(4));
      if (p.finished || p.maxFrac >= 0.98) { c.setAttribute("data-done", ""); pct.textContent = "완독"; }
      else pct.textContent = Math.floor(p.frac * 100) + "%";
    }
    var n = marksOf(c.dataset.id);
    if (n) { var b = document.createElement("span"); b.className = "cap__bm"; b.textContent = "· 책갈피 " + n; $(".cap", c).appendChild(b); }
  });
}
function paintShelf() {
  var rows = MANIFEST.map(function (w) { return { w: w, p: progOf(w.id) }; })
    .filter(function (x) { return x.p && x.p.frac > 0.002 && !x.p.finished; })
    .sort(function (a, b) { return b.p.updated - a.p.updated; });
  var sec = $("#now"), list = $("#nowlist");
  if (!rows.length) { sec.hidden = true; return; }
  sec.hidden = false;
  list.innerHTML = rows.slice(0, 3).map(function (x) {
    var w = x.w, p = x.p;
    var left = Math.round((w.chars - w.chars * p.frac) / 5.5 / (S.wpm || 200));
    var mk = $('.card[data-id="' + w.id + '"] .cover__mark');
    return '<li><a class="slip" href="#/w/' + encodeURIComponent(w.id) + '" data-author="' + w.author +
      '" style="--progress:' + p.frac.toFixed(4) + '"><span class="spine">' + (mk ? mk.outerHTML : "") +
      '</span><span class="slip__body"><span class="slip__title">' + esc(w.title) + "</span>" +
      '<span class="slip__meta">' + esc(w.authorKo) + " · " + w.year + " · 남은 " + fmtMin(left) + " · " + ago(p.updated) + "</span>" +
      '<span class="slip__bar"><i></i><b>' + Math.floor(p.frac * 100) + "%</b></span></span></a></li>";
  }).join("");
  if (rows.length > 3) {
    var li = document.createElement("li");
    li.innerHTML = '<span class="slip__meta">그 외 ' + (rows.length - 3) + "편</span>";
    list.appendChild(li);
  }
}
function paintMine() {
  var sess = load("rdr/v1/session", null);
  var done = 0, reading = 0;
  MANIFEST.forEach(function (w) { var p = progOf(w.id); if (!p) return; if (p.finished) done++; else if (p.frac > 0.002) reading++; });
  var bits = [];
  if (reading) bits.push("읽는 중 " + reading);
  if (done) bits.push("완독 " + done);
  if (sess && sess.totalMs > 60000) bits.push("누적 " + fmtMin(Math.round(sess.totalMs / 60000)));
  $("#mine").textContent = bits.length ? "  ·  " + bits.join(" · ") : "";
}

var libView = "era";
function setLibView(v) {
  libView = v;
  $$(".ctl__sort button").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.sort === v ? "true" : "false"); });
  $("#grid").hidden = (v === "author");
  $("#grid-author").hidden = (v !== "author");
  if (v !== "era" && v !== "author") resort(v);
  else if (v === "era") resort("year");
  applyFilter();
}
function resort(mode) {
  var g = $("#grid");
  var cards = $$(".card", g).filter(function (c) { return c.parentNode === g; });
  cards.sort(function (a, b) {
    if (mode === "title") return a.dataset.title.localeCompare(b.dataset.title);
    if (mode === "len") return (+a.dataset.mins) - (+b.dataset.mins);
    return (+a.dataset.year) - (+b.dataset.year);
  });
  var eras = {};
  $$(".era", g).forEach(function (e) { eras[e.dataset.decade] = e; });
  if (mode === "year") {
    /* chronological run, each decade opened by its rule */
    Object.keys(eras).sort().forEach(function (d) {
      eras[d].hidden = false;
      g.appendChild(eras[d]);
      cards.filter(function (c) { return c.dataset.decade === d; })
           .forEach(function (c) { g.appendChild(c); });
    });
  } else {
    Object.keys(eras).forEach(function (d) { eras[d].hidden = true; g.appendChild(eras[d]); });
    cards.forEach(function (c) { g.appendChild(c); });
  }
}
function applyFilter() {
  var q = $("#find").value.trim().toLowerCase();
  var root = libView === "author" ? $("#grid-author") : $("#grid");
  var n = 0;
  $$(".card", root).forEach(function (c) {
    var w = byId[c.dataset.id];
    var hay = (c.dataset.title + " " + c.dataset.ko + " " + w.authorKo + " " + w.authorEn + " " + w.author + " " + w.year).toLowerCase();
    var hit = !q || hay.indexOf(q) >= 0;
    c.hidden = !hit; if (hit) n++;
  });
  if (q) { $$(".era", root).forEach(function (e) { e.hidden = true; }); $$(".plate", root).forEach(function (e) { e.hidden = true; }); $$(".solo", root).forEach(function (e) { e.hidden = true; }); }
  else {
    if (libView === "author") { $$(".plate", root).forEach(function (e) { e.hidden = false; }); $$(".solo", root).forEach(function (e) { e.hidden = false; }); }
    else $$(".era", root).forEach(function (e) { e.hidden = false; });
  }
  $("#count").textContent = q ? (MANIFEST.length + "편 중 " + n + "편") : "";
  var empty = $(".lib-empty", root);
  if (!n && q) { if (!empty) { var p = document.createElement("p"); p.className = "lib-empty"; p.textContent = "일치하는 작품이 없습니다."; root.appendChild(p); } }
  else if (empty) empty.remove();
}

/* ============================================================
   Keyboard
   ============================================================ */
function bindKeys() {
  addEventListener("keydown", function (e) {
    lastActive = Date.now();
    var tag = (e.target.tagName || "").toLowerCase();
    var typing = tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable;

    if (e.key === "Escape") {
      if (anyOverlay()) { closeOverlays(); e.preventDefault(); return; }
      if (typing) { e.target.blur(); if (e.target.id === "find") { e.target.value = ""; applyFilter(); } return; }
      if (view === "reader") { hudPinned = false; hideHud(); escMute = Date.now() + 600; }
      return;
    }
    if (typing) return;
    if (e.ctrlKey && e.key.toLowerCase() === "z" && view === "reader") { e.preventDefault(); popUndo(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    /* global */
    if (e.key === ",") { e.preventDefault(); document.body.classList.contains("set-on") ? closeOverlays() : openSettings(); return; }
    if (e.key === "w") { e.preventDefault(); document.body.classList.contains("pal-on") ? closeOverlays() : openPalette(); return; }
    if (e.key === "?") { e.preventDefault(); showHelp(); return; }
    if (e.key === "d") { e.preventDefault(); cycleTheme(); return; }
    if (e.key === "f") { e.preventDefault(); document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen().catch(function () {}); return; }

    if (view === "library") {
      if (e.key === "/") { e.preventDefault(); $("#find").focus(); return; }
      if (e.key === "Enter") {
        var first = $("#nowlist .slip") || $(".card:not([hidden]) .card__link");
        if (first) { e.preventDefault(); goWork(first.closest("[data-id]") ? first.closest("[data-id]").dataset.id : decodeURIComponent(first.getAttribute("href").split("/w/")[1])); }
        return;
      }
      if (e.key >= "1" && e.key <= "4") {
        var b = $$(".ctl__sort button")[+e.key - 1];
        if (b) { e.preventDefault(); setLibView(b.dataset.sort); }
      }
      return;
    }

    /* reader */
    switch (e.key) {
      case " ": case "PageDown": e.preventDefault(); pageBy(e.shiftKey ? -1 : 1); return;
      case "PageUp": e.preventDefault(); pageBy(-1); return;
      case "ArrowDown": case "j": e.preventDefault(); scrollBy(0, 3 * S.fs * S.lh); flushSoon(); return;
      case "ArrowUp": case "k": e.preventDefault(); scrollBy(0, -3 * S.fs * S.lh); flushSoon(); return;
      case "ArrowRight": case "n": e.preventDefault(); chapterNav(1); revealHud(); return;
      case "ArrowLeft": case "p": e.preventDefault(); chapterNav(-1); revealHud(); return;
      case "]": e.preventDefault(); siblingWork(1); return;
      case "[": e.preventDefault(); siblingWork(-1); return;
      case "Home": e.preventDefault(); touched = true; pushUndo(); scrollTo({ top: 0 }); flushSoon(); return;
      case "End": e.preventDefault(); touched = true; pushUndo(); scrollTo({ top: document.body.scrollHeight }); flushSoon(); return;
      case "Enter": if (prog) { e.preventDefault(); restoreAnchor(prog); } return;
      case "t": e.preventDefault(); (document.body.classList.contains("drawer-on") && drawerTab === "toc") ? closeOverlays() : openDrawer("toc"); return;
      case "b": e.preventDefault(); toggleBookmark(); revealHud(); return;
      case "B": e.preventDefault(); openDrawer("bm"); return;
      case "Backspace": e.preventDefault(); goLibrary(); return;
      case "+": case "=": e.preventDefault(); bump("fs", 1, 15, 30); return;
      case "-": e.preventDefault(); bump("fs", -1, 15, 30); return;
      case "0": e.preventDefault(); withPin(function () { S.fs = DEFAULTS.fs; S.lh = DEFAULTS.lh; S.measure = DEFAULTS.measure; applySettings(); }); syncSettings(); saveSettingsSoon(); toast("기본값"); return;
      case ">": e.preventDefault(); bump("measure", 2, 45, 92); return;
      case "<": e.preventDefault(); bump("measure", -2, 45, 92); return;
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
  var groups = [
    ["서재", [["/", "찾기"], ["1"], ["Enter", "이어읽기"], ["클릭", "작품 열기"]]],
    ["이동", [["Space", "다음 화면"], ["Shift+Space", "이전 화면"], ["↓ / j", "조금 아래로"], ["↑ / k", "조금 위로"],
      ["→ / n", "다음 장"], ["← / p", "이전 장"], ["]", "같은 작가 다음 작품"], ["[", "같은 작가 이전 작품"],
      ["Home / End", "작품 처음 / 끝"], ["Enter", "저장된 위치로"], ["Ctrl+Z", "이동 취소"], ["Backspace", "서재로"]]],
    ["패널", [["t", "목차"], ["b", "책갈피 추가·삭제"], ["B", "책갈피 목록"], [",", "설정"], ["w", "작품 전환"],
      ["Esc", "닫기"], ["?", "단축키"]]],
    ["표시", [["+ / -", "글자 크게 / 작게"], ["0", "기본값"], ["> / <", "본문 넓게 / 좁게"], ["d", "테마 전환"],
      ["f", "전체화면"], ["u", "상태 표시줄 고정"]]]
  ];
  groups[0][1] = [["/", "찾기"], ["1–4", "정렬 방식"], ["Enter", "이어읽기"]];
  var h = '<div class="hp-box"><div class="hp-hd">단축키<button class="hp-x">✕</button></div><div class="hp-cols">';
  groups.forEach(function (g) {
    h += '<div class="hp-g"><h4>' + g[0] + "</h4>" + g[1].map(function (r) {
      return '<div class="hp-r"><kbd>' + esc(r[0]) + "</kbd><span>" + (r[1] || "") + "</span></div>";
    }).join("") + "</div>";
  });
  h += "</div></div>";
  var d = document.createElement("div"); d.id = "help"; d.innerHTML = h;
  document.body.appendChild(d);
  d.addEventListener("click", function (e) { if (e.target === d || e.target.closest(".hp-x")) d.remove(); });
}

/* ============================================================
   Pointer, scroll, routing, boot
   ============================================================ */
function bindPointer() {
  var curT = null;
  addEventListener("mousemove", function (e) {
    lastActive = Date.now();
    if (view === "reader") {
      document.documentElement.style.cursor = "";
      clearTimeout(curT); curT = setTimeout(function () { if (view === "reader") document.documentElement.style.cursor = "none"; }, 3000);
      if (Date.now() < escMute) return;
      if (e.clientY < 72 || e.clientY > innerHeight - 72) revealHud();
    } else document.documentElement.style.cursor = "";
  }, { passive: true });
  addEventListener("touchstart", function (e) {
    lastActive = Date.now();
    if (view !== "reader" || anyOverlay()) return;
    var x = e.touches[0].clientX / innerWidth, y = e.touches[0].clientY / innerHeight;
    if (x > 0.2 && x < 0.8 && y > 0.2 && y < 0.8) { hudOn ? hideHud() : revealHud(); }
    else if (x <= 0.18) pageBy(-1);
    else if (x >= 0.82) pageBy(1);
  }, { passive: true });
}
var lastY = 0;
addEventListener("scroll", function () {
  if (view !== "reader") return;
  lastActive = Date.now();
  if (!restoring) touched = true;
  flushSoon(); updateHud();
  var d = scrollY - lastY; lastY = scrollY;
  if (d > 0) hideHud();
}, { passive: true });
addEventListener("resize", throttle(function () { if (view === "reader") { var a = captureAnchor(); if (a) restoreAnchor(a); } }, 200));
addEventListener("pagehide", function () { flush(); });
addEventListener("beforeunload", function () { flush(); });

function route(replace) {
  var h = location.hash || "";
  var m = h.match(/^#\/w\/(.+)$/);
  if (m) {
    var id = decodeURIComponent(m[1]);
    if (byId[id]) { if (!WORK || WORK.id !== id) openWork(id, {}); return; }
  }
  if (view === "reader" || !document.body.dataset.view) goLibrary(replace !== false);
}
addEventListener("hashchange", function () { route(false); });

document.addEventListener("click", function (e) {
  var a = e.target.closest('a[href^="#/"]');
  if (!a) return;
  e.preventDefault();
  var href = a.getAttribute("href");
  var m = href.match(/^#\/w\/(.+)$/);
  if (m) goWork(decodeURIComponent(m[1]));
  else goLibrary();
});

/* ---------- go ---------- */
buildHud(); buildDrawer(); buildSettings(); buildPalette(); bindKeys(); bindPointer();
$("#theme").addEventListener("change", function () { S.theme = this.value; applySettings(); saveSettingsSoon(); });
$$(".ctl__sort button").forEach(function (b) { b.addEventListener("click", function () { setLibView(b.dataset.sort); }); });
$("#find").addEventListener("input", applyFilter);
if (EPHEMERAL) {
  var wsg = document.createElement("div"); wsg.id = "nostore";
  wsg.textContent = "저장할 수 없는 환경입니다. 읽은 위치가 기억되지 않습니다.";
  document.body.appendChild(wsg);
}
paintCards(); paintShelf(); paintMine();
route(true);
})();
