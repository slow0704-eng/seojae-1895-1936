/* tools/act.py spans()·align() 의 JS 짝 (참조 구현 — 낭독 런타임 tools/tts/act.js 가 대본 순번을 셀 때 이것을 그대로 씀).
   전 코퍼스(원문 79권 + 한국어판 63권 = 142 책·언어, 184,150 문단)에서 파이썬과 대사 수·cont 가 100% 같음.
   대본 q 순번 = 이 함수가 돌려주는 구간 순번. 파이썬과 한 글자도 다르게 세면 안 됨. */
var ACT_PAIR = { "“": "”", "‘": "’", "「": "」", "『": "』" };
var ACT_NEST = { "「": 1, "『": 1 };
var ACT_LET = /[\p{L}\p{N}_]/u;   /* 파이썬 re \w (유니코드) 와 같게 */
function actIsOpen(t, i) { return t[i] !== "‘" || i === 0 || !ACT_LET.test(t[i - 1]); }
function actIsClose(t, i) { return t[i] !== "’" || i + 1 >= t.length || !ACT_LET.test(t[i + 1]); }
/* t: 문단 텍스트(<rt>/<rp> 내용·태그 지우고 문자 참조 푼 것), opens: "“" | "‘" | "「『",
   carry: 앞 문단에서 열린 채 넘어온 여는 따옴표 또는 null.
   돌려줌 {spans: [[시작, 끝, cont]], carry} — 위치는 UTF-16 단위(파이썬은 코드포인트; 보충 평면
   글자가 없으면 같음. 순번만 쓰므로 수에는 영향 없음). */
function actSpans(t, opens, carry) {
  var out = [], i = 0, n = t.length, cur = null, depth = 0, start = 0, cont = false, k;
  if (carry) {
    var lead = t.length - t.replace(/^\s+/, "").length;
    if (t.charAt(lead) === carry) cont = true;
    else {
      var cl = ACT_PAIR[carry], j = -1, o = -1;
      for (k = 0; k < n; k++) if (t[k] === cl && actIsClose(t, k)) { j = k; break; }
      for (k = 0; k < n; k++) if (opens.indexOf(t[k]) >= 0 && actIsOpen(t, k)) { o = k; break; }
      if (j >= 0 && (o < 0 || j < o)) { out.push([0, j + 1, true]); i = j + 1; }
    }
  }
  for (; i < n; i++) {
    var c = t[i];
    if (cur === null) {
      if (opens.indexOf(c) >= 0 && actIsOpen(t, i)) { cur = c; depth = 1; start = i; }
    } else if (c === cur && actIsOpen(t, i)) {
      if (ACT_NEST[c]) depth++;
      else { out.push([start, i, cont]); cont = false; start = i; }
    } else if (c === ACT_PAIR[cur] && actIsClose(t, i)) {
      if (--depth === 0) { out.push([start, i + 1, cont]); cont = false; cur = null; }
    }
  }
  if (cur !== null) out.push([start, n, cont]);
  return { spans: out, carry: cur };
}
/* 런타임 정렬: q = 대본의 그 문단 q 목록, nspans = 읽는 언어에서 센 수. */
function actAlign(q, nspans, narrator) {
  var i, r = [];
  if (nspans === q.length) return { by: q.slice(), how: "exact" };
  if (!q.length) { for (i = 0; i < nspans; i++) r.push(null); return { by: r, how: "fallback" }; }
  var w = q[0].who, same = q.every(function (x) { return x.who === w; });
  if (nspans === 0) return { by: [], how: same && w === narrator ? "same" : "fallback" };
  if (same && w != null) {
    var h = q[0].how || null, hs = q.every(function (x) { return (x.how || null) === h; });
    for (i = 0; i < nspans; i++) r.push({ who: w, how: hs ? h : null });
    return { by: r, how: "same" };
  }
  for (i = 0; i < nspans; i++) r.push(null);
  return { by: r, how: "fallback" };
}
if (typeof module !== "undefined") module.exports = { actSpans: actSpans, actAlign: actAlign };
