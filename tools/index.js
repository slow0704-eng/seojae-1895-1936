/* ============================================================
   서재 — library index behaviour
   Reads the same rdr/v1/* namespace the reader writes (shared file:// origin).
   ============================================================ */
(function () {
"use strict";
var R = window.RDR;                       /* exported by runtime.js */
if (!R) return;
var load = R.load, S = R.S, ago = R.ago, fmtMin = R.fmtMin;

function $(s){ return document.querySelector(s); }
function $$(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); }
function esc(s){ return String(s).replace(/[&<>"]/g,function(c){
  return ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[c]; }); }
function progOf(id){ return load("rdr/v1/prog/" + id, null); }
function marksOf(id){ var m = load("rdr/v1/marks/" + id, null); return (m && m.m) ? m.m.length : 0; }

var byId = {};
MANIFEST.forEach(function (w) { byId[w.id] = w; });

/* ---------- paint progress onto every jacket ---------- */
function paintCards() {
  $$(".card").forEach(function (c) {
    var p = progOf(c.dataset.id);
    var pct = c.querySelector(".cap__pct");
    c.removeAttribute("data-done");
    c.style.removeProperty("--progress");
    if (!p || !p.frac) { pct.textContent = ""; return; }
    c.style.setProperty("--progress", p.frac.toFixed(4));
    if (p.finished || p.maxFrac >= 0.98) { c.setAttribute("data-done", ""); pct.textContent = "완독"; }
    else pct.textContent = Math.floor(p.frac * 100) + "%";
    var n = marksOf(c.dataset.id);
    if (n && !c.querySelector(".cap__bm")) {
      var b = document.createElement("span");
      b.className = "cap__bm"; b.textContent = "· 책갈피 " + n;
      c.querySelector(".cap").appendChild(b);
    }
  });
}

/* ---------- 읽는 중 shelf ---------- */
function paintShelf() {
  var rows = MANIFEST.map(function (w) { return { w: w, p: progOf(w.id) }; })
    .filter(function (x) { return x.p && x.p.frac > 0.002 && !x.p.finished; })
    .sort(function (a, b) { return b.p.updated - a.p.updated; });
  var sec = $("#now"), list = $("#nowlist");
  if (!rows.length) { sec.hidden = true; return; }
  sec.hidden = false;
  var show = rows.slice(0, 3);
  list.innerHTML = show.map(function (x) {
    var w = x.w, p = x.p;
    var left = Math.round((w.chars - w.chars * p.frac) / 5.5 / (S.wpm || 200));
    return '<li><a class="slip" href="' + esc(w.href) + '" data-author="' + w.author +
      '" style="--progress:' + p.frac.toFixed(4) + '">' +
      '<span class="spine">' + (document.querySelector('.card[data-id="' + w.id + '"] .cover__mark') || {outerHTML:""}).outerHTML +
      '</span><span class="slip__body">' +
      '<span class="slip__title">' + esc(w.title) + '</span>' +
      '<span class="slip__meta">' + esc(w.authorKo) + ' · ' + w.year +
        ' · 남은 ' + fmtMin(left) + ' · ' + ago(p.updated) + '</span>' +
      '<span class="slip__bar"><i></i><b>' + Math.floor(p.frac * 100) + '%</b></span>' +
      '</span></a></li>';
  }).join("");
  if (rows.length > 3) {
    var li = document.createElement("li");
    li.innerHTML = '<span class="slip__meta">그 외 ' + (rows.length - 3) + '편</span>';
    list.appendChild(li);
  }
}

/* ---------- cumulative reading time ---------- */
function paintMine() {
  var sess = load("rdr/v1/session", null);
  var done = MANIFEST.filter(function (w) { var p = progOf(w.id); return p && p.finished; }).length;
  var reading = MANIFEST.filter(function (w) { var p = progOf(w.id); return p && p.frac > .002 && !p.finished; }).length;
  var bits = [];
  if (reading) bits.push("읽는 중 " + reading);
  if (done) bits.push("완독 " + done);
  if (sess && sess.totalMs > 60000) bits.push("누적 " + fmtMin(Math.round(sess.totalMs / 60000)));
  $("#mine").textContent = bits.length ? "  ·  " + bits.join(" · ") : "";
}

/* ---------- sort / filter ---------- */
var view = "era";
function setView(v) {
  view = v;
  $$(".ctl__sort button").forEach(function (b) {
    b.setAttribute("aria-selected", b.dataset.sort === v ? "true" : "false"); });
  $("#grid").hidden = (v === "author");
  $("#grid-author").hidden = (v !== "author");
  if (v === "era" || v === "author") { resort(null); }
  else resort(v);
  applyFilter();
}
function resort(mode) {
  if (!mode) return;
  var g = $("#grid");
  var cards = $$(".card", g).filter(function (c) { return c.parentNode === g; });
  $$(".era", g).forEach(function (e) { e.hidden = true; });
  cards.sort(function (a, b) {
    if (mode === "title") return a.dataset.title.localeCompare(b.dataset.title);
    if (mode === "len") return (+a.dataset.mins) - (+b.dataset.mins);
    return (+a.dataset.year) - (+b.dataset.year);
  });
  cards.forEach(function (c) { g.appendChild(c); });
}
function applyFilter() {
  var q = $("#find").value.trim().toLowerCase();
  var root = view === "author" ? $("#grid-author") : $("#grid");
  if (view === "era" && !q) $$(".era", root).forEach(function (e) { e.hidden = false; });
  var n = 0;
  $$(".card", root).forEach(function (c) {
    var w = byId[c.dataset.id];
    var hay = (c.dataset.title + " " + c.dataset.ko + " " + w.authorKo + " " +
               w.authorEn + " " + w.author + " " + w.year).toLowerCase();
    var hit = !q || hay.indexOf(q) >= 0;
    c.hidden = !hit; if (hit) n++;
  });
  if (q) { $$(".era", root).forEach(function (e) { e.hidden = true; });
           $$(".plate", root).forEach(function (e) { e.hidden = true; }); }
  else if (view === "author") $$(".plate", root).forEach(function (e) { e.hidden = false; });
  $("#count").textContent = q ? (MANIFEST.length + "편 중 " + n + "편") : "";
  var empty = $(".lib-empty");
  if (!n && q) { if (!empty) { var p = document.createElement("p");
      p.className = "lib-empty"; p.textContent = "일치하는 작품이 없습니다."; root.appendChild(p); } }
  else if (empty) empty.remove();
}

/* ---------- wiring ---------- */
$$(".ctl__sort button").forEach(function (b) {
  b.addEventListener("click", function () { setView(b.dataset.sort); });
});
$("#find").addEventListener("input", applyFilter);
$("#theme").value = S.theme;
$("#theme").addEventListener("change", function () {
  S.theme = this.value; R.applySettings(); R.saveSettingsSoon();
});
addEventListener("keydown", function (e) {
  var typing = /^(input|textarea|select)$/i.test(e.target.tagName);
  if (e.key === "Escape" && typing) { $("#find").value = ""; applyFilter(); $("#find").blur(); return; }
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "/") { e.preventDefault(); $("#find").focus(); return; }
  if (e.key === "Enter") {
    var first = $("#nowlist .slip") || $(".card:not([hidden]) .card__link");
    if (first) { e.preventDefault(); location.href = first.getAttribute("href"); }
    return;
  }
  if (e.key >= "1" && e.key <= "4") {
    var b = $$(".ctl__sort button")[+e.key - 1];
    if (b) { e.preventDefault(); setView(b.dataset.sort); }
  }
  if (e.key === "d") { e.preventDefault();
    var T = ["light","sepia","dark","night"];
    S.theme = T[(T.indexOf(S.theme) + 1) % 4];
    $("#theme").value = S.theme; R.applySettings(); R.saveSettingsSoon(); }
});

paintCards(); paintShelf(); paintMine();
addEventListener("pageshow", function () { paintCards(); paintShelf(); paintMine(); });
})();
