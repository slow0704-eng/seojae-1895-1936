/* 서재 낭독 — 글을 소리 낼 말로 바꾸는 정규화.
   Supertonic 은 글자 단위 모델이라 "1906년", "3펜스", "Mr." 를 스스로 읽지
   못합니다(숫자는 건너뛰거나 엉뚱한 소리를 냄). 여기서 읽는 그대로의 한글·영어
   단어로 풀어 넘깁니다. 워커(importScripts)와 node(테스트·캘리브레이션)가
   같은 파일을 씁니다. */
(function (root) {
"use strict";

/* ---------------- 한국어 ---------------- */
var SINO = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"];
var NATIVE1 = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"];
var NATIVE10 = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"];

function sino4(n) {             /* 0 < n < 10000 */
  var s = "", u = ["천", "백", "십", ""], d = [1000, 100, 10, 1];
  for (var i = 0; i < 4; i++) {
    var q = Math.floor(n / d[i]) % 10;
    if (!q) continue;
    s += (q === 1 && i < 3 ? "" : SINO[q]) + u[i];
  }
  return s;
}
function sino(n) {
  if (n === 0) return "영";
  var big = ["", "만", "억", "조"], s = "", k = 0;
  while (n > 0 && k < 4) {
    var part = n % 10000;
    if (part) s = (part === 1 && k === 1 ? "" : sino4(part)) + big[k] + s;
    n = Math.floor(n / 10000); k++;
  }
  return s;
}
function native(n) {            /* 관형형: 한·두·세·스무 — 1..99, 그 위는 한자어 */
  if (n <= 0 || n >= 100) return sino(n);
  var t = Math.floor(n / 10), o = n % 10;
  if (t === 2 && o === 0) return "스무";
  return NATIVE10[t] + NATIVE1[o];
}
/* 고유어 수사와 어울리는 단위. "시"는 시각(세 시), "시간"도 고유어(세 시간).
   "장"은 '제1장'이면 한자어라 앞에서 따로 거릅니다. */
var NATIVE_UNITS = "시간|시|개|명|살|마리|권|잔|사람|달|척|채|군데|가지|벌|켤레|송이|그루|자루|통|쌍|줄|걸음|바퀴|판|모금|방울|발짝|발|차례|배|끼|해|곳|분들|놈|병|접시|숟가락|번째|번|장|대|살배기";
var RX_KO_NUM = new RegExp("(제\\s?)?(\\d{1,3}(?:,\\d{3})+|\\d+)(?:\\.(\\d+))?(\\s?)(" + NATIVE_UNITS + ")?", "g");

function koNumber(m, je, intPart, frac, sp, unit, off, str) {
  var n = parseInt(intPart.replace(/,/g, ""), 10);
  var after = str.slice(off + m.length, off + m.length + 2);
  if (frac != null) return (je ? "제" : "") + sino(n) + " 점 " + frac.split("").map(function (d) { return d === "0" ? "영" : SINO[+d]; }).join("") + sp + (unit || "");
  if (unit && !je) {
    /* 번가·번지·번호는 한자어, 시각 '시'는 고유어지만 '시대·시절'은 단위가 아님 */
    if (unit === "번" && /^[가지호]/.test(after)) return sino(n) + sp + unit;
    if (unit === "시" && /^[대절]/.test(after)) return sino(n) + sp + unit;
    if (unit === "장" && /^[면]/.test(after)) return sino(n) + sp + unit;
    if (unit === "번째") return (n === 1 ? "첫" : native(n)) + sp + unit;
    if (n < 100) return native(n) + " " + unit;
  }
  /* 연도는 붙여 읽되 '천구백육' 처럼 */
  return (je ? "제" : "") + sino(n) + sp + (unit || "");
}

/* "2천1백50만" 처럼 숫자와 단위가 섞인 표기: 1천→천, 1백→백 */
function koMixed(s) {
  return s.replace(/(\d+)(?=\s?[천백십만억조])/g, function (d) {
    var n = parseInt(d, 10);
    return n === 1 ? "" : sino(n);
  });
}

var LETTER_KO = { A: "에이", B: "비", C: "시", D: "디", E: "이", F: "에프", G: "지", H: "에이치", I: "아이", J: "제이", K: "케이", L: "엘", M: "엠", N: "엔", O: "오", P: "피", Q: "큐", R: "아르", S: "에스", T: "티", U: "유", V: "브이", W: "더블유", X: "엑스", Y: "와이", Z: "제트" };
var ROMAN = { I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000 };
function roman(s) {
  var n = 0;
  for (var i = 0; i < s.length; i++) {
    var a = ROMAN[s[i]], b = ROMAN[s[i + 1]] || 0;
    n += a < b ? -a : a;
  }
  return n;
}

function normKo(t) {
  t = t.replace(/[\u200b\u00ad]/g, "");
  /* 머리말 숫자: "3. 시간 여행자" → "삼. 시간 여행자" 는 어색 — "3장" 처럼 읽힙니다 */
  t = koMixed(t);
  t = t.replace(/(\d+)\s?%/g, function (m, d) { return sino(+d) + " 퍼센트"; });
  t = t.replace(/(\d{1,2}):(\d{2})/g, function (m, h, mi) { return native(+h) + " 시 " + (+mi ? sino(+mi) + " 분" : ""); });
  t = t.replace(RX_KO_NUM, koNumber);
  /* 영문 머리글자: "H. G. 웰스" → "에이치 지 웰스" */
  t = t.replace(/\b([A-Z])\.(?=\s?[A-Z가-힣])/g, function (m, c) { return LETTER_KO[c] + " "; });
  t = t.replace(/\b(I{1,3}|IV|VI{0,3}|IX|XI{0,3}|XIV|XV|XVI{0,3}|XIX|XX)\b(?=[.\s])/g, function (m) { return sino(roman(m)); });
  t = t.replace(/\b([A-Z])\b/g, function (m, c) { return LETTER_KO[c]; });
  t = t.replace(/&/g, " 앤드 ");
  return tidy(t);
}

/* ---------------- English ---------------- */
var ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
var TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
function en99(n) { return n < 20 ? ONES[n] : TENS[Math.floor(n / 10)] + (n % 10 ? "-" + ONES[n % 10] : ""); }
function en999(n) {
  var h = Math.floor(n / 100), r = n % 100;
  return (h ? ONES[h] + " hundred" + (r ? " and " : "") : "") + (r || !h ? en99(r) : "");
}
function enNum(n) {
  if (n < 1000) return en999(n);
  var parts = [], names = ["", " thousand", " million", " billion"], k = 0;
  while (n > 0) {
    var p = n % 1000;
    if (p) parts.unshift(en999(p) + names[k]);
    n = Math.floor(n / 1000); k++;
  }
  return parts.join(" ");
}
function enYear(n) {
  if (n >= 2000 && n < 2010) return enNum(n);
  var a = Math.floor(n / 100), b = n % 100;
  return en99(a) + " " + (b === 0 ? "hundred" : b < 10 ? "oh " + ONES[b] : en99(b));
}
var ORD = { one: "first", two: "second", three: "third", five: "fifth", eight: "eighth", nine: "ninth", twelve: "twelfth" };
function enOrd(n) {
  var w = enNum(n), m = /(\w+)$/.exec(w)[1];
  var o = ORD[m] || (/y$/.test(m) ? m.replace(/y$/, "ieth") : m + "th");
  return w.replace(/\w+$/, o);
}
var ABBR = [
  [/\bMr\./g, "Mister"], [/\bMrs\./g, "Missus"], [/\bMessrs\./g, "Messieurs"], [/\bDr\./g, "Doctor"],
  [/\b([A-Z][a-z]+) St\.(?=\s+[A-Z])/g, "$1 Street."], [/\b([A-Z][a-z]+) St\./g, "$1 Street"], [/\bSt\.(?=\s[A-Z])/g, "Saint"], [/\bCapt\./g, "Captain"], [/\bCol\./g, "Colonel"], [/\bGen\./g, "General"],
  [/\bProf\./g, "Professor"], [/\bRev\./g, "Reverend"], [/\bLt\./g, "Lieutenant"], [/\bSgt\./g, "Sergeant"],
  [/\bNo\.(?=\s?\d)/g, "number"], [/&c\./g, "et cetera"], [/\betc\./g, "et cetera"], [/\bi\.e\./g, "that is"],
  [/\be\.g\./g, "for example"], [/\bvs\./g, "versus"], [/&/g, " and "]
];
function normEn(t) {
  t = t.replace(/[\u200b\u00ad]/g, "");
  ABBR.forEach(function (a) { t = t.replace(a[0], a[1]); });
  t = t.replace(/£\s?(\d+)/g, function (m, d) { return enNum(+d) + (+d === 1 ? " pound" : " pounds"); });
  t = t.replace(/\$\s?(\d+)/g, function (m, d) { return enNum(+d) + (+d === 1 ? " dollar" : " dollars"); });
  t = t.replace(/\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})\b/g, function (m, mo, d) { return mo + " " + enOrd(+d); });
  t = t.replace(/\b(\d+)(st|nd|rd|th)\b/g, function (m, d) { return enOrd(+d); });
  t = t.replace(/\b(1[0-9]{3})\b(?!,\d)/g, function (m, d) { return enYear(+d); });
  t = t.replace(/\b(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\b/g, function (m, i, f) {
    var s = enNum(parseInt(i.replace(/,/g, ""), 10));
    return f ? s + " point " + f.split("").map(function (d) { return ONES[+d]; }).join(" ") : s;
  });
  t = t.replace(/\b(CHAPTER|Chapter|BOOK|Book|PART|Part|BOOK|Section|SECTION)\s+([IVXLC]+)\b/g, function (m, w, r) { return w + " " + enNum(roman(r)); });
  t = t.replace(/^([IVXLC]+)\.(?=\s|$)/, function (m, r) { return enNum(roman(r)) + "."; });
  return tidy(t);
}

/* ---------------- 日本語 ---------------- */
function normJa(t) {
  t = t.replace(/[\u200b\u00ad]/g, "");
  t = t.replace(/―+|─+/g, "、");   /* 二倍ダッシュ: 間 */
  t = t.replace(/[〔〕［］]/g, "");
  return tidy(t);
}

/* 모델 앞 공통 정리: 줄표는 쉼, 말줄임은 마침, 겹공백 하나로 */
function tidy(t) {
  return t.replace(/\s*—+\s*/g, ", ").replace(/…+|\.{3,}/g, "…").replace(/\s+/g, " ")
          .replace(/([,、])\s*[,、]+/g, "$1").replace(/,\s*([.!?…])/g, "$1").replace(/^[,\s]+/, "").trim();
}

function normalize(text, lang) {
  return lang === "ko" ? normKo(text) : lang === "ja" ? normJa(text) : normEn(text);
}

/* ---------------- 문장 나누기 ----------------
   [시작, 끝) 문자 위치 목록을 돌려줍니다 — 리더가 같은 위치로 강조를 겁니다.
   따옴표 안의 마침표에서는 끊되, 닫는 따옴표까지 앞 문장에 붙입니다.
   너무 짧은 조각("예.")은 다음 문장에 붙이고, 너무 긴 문장은 쉼표에서 나눕니다. */
var ABBR_END = /(?:\b(?:Mr|Mrs|Ms|Dr|St|Mt|Messrs|Capt|Col|Gen|Prof|Rev|Lt|Sgt|No|vs|etc|Jr|Sr|Co)|\b[A-Z])\.$/;
function sentences(text, lang) {
  var out = [], start = 0, i, n = text.length;
  var END = lang === "ja" ? /[。！？!?]/ : /[.!?…。！？]/;
  var CLOSE = /[”’"'」』）)\]]/;
  var maxLen = lang === "en" ? 260 : 110, minLen = lang === "en" ? 18 : 8;
  for (i = 0; i < n; i++) {
    if (!END.test(text[i])) continue;
    var j = i + 1;
    while (j < n && (END.test(text[j]) || CLOSE.test(text[j]))) j++;
    if (text[i] === "." && (lang === "en" ? ABBR_END : /\b[A-Z]\.$/).test(text.slice(Math.max(0, i - 8), i + 1))) continue;
    if (j < n && lang !== "ja" && !/\s/.test(text[j])) continue;   /* 3.5 · U.S.A 같은 경우 */
    out.push([start, j]); start = j; i = j - 1;
  }
  if (start < n) out.push([start, n]);
  /* 앞 공백 걷기 */
  out = out.map(function (r) { while (r[0] < r[1] && /\s/.test(text[r[0]])) r[0]++; return r; })
           .filter(function (r) { return r[1] > r[0]; });
  /* 짧은 조각 합치기 */
  var merged = [];
  out.forEach(function (r) {
    var last = merged[merged.length - 1];
    if (last && (last[1] - last[0] < minLen) && (r[1] - last[0] <= maxLen)) last[1] = r[1];
    else merged.push(r);
  });
  /* 구두점뿐인 꼬리("………")는 앞 문장에 */
  for (var q = merged.length - 1; q > 0; q--)
    if (!/[\w가-힣ぁ-んァ-ン一-龯]/.test(text.slice(merged[q][0], merged[q][1]))) { merged[q - 1][1] = merged[q][1]; merged.splice(q, 1); }
  /* 긴 문장 쉼표에서 나누기 */
  var res = [];
  merged.forEach(function (r) {
    while (r[1] - r[0] > maxLen) {
      var cut = -1, lo = r[0] + Math.floor(maxLen * 0.45), hi = r[0] + maxLen;
      for (var k = hi; k > lo; k--) if (/[,，、;:—]/.test(text[k - 1]) && /\s|[^\w]/.test(text[k] || " ")) { cut = k; break; }
      if (cut < 0) for (k = hi; k > lo; k--) if (/\s/.test(text[k])) { cut = k; break; }
      if (cut < 0) break;
      res.push([r[0], cut]);
      r = [cut, r[1]];
      while (r[0] < r[1] && /\s/.test(text[r[0]])) r[0]++;
    }
    res.push(r);
  });
  return res;
}

var api = { normalize: normalize, sentences: sentences, sino: sino, native: native, enNum: enNum, enYear: enYear };
if (typeof module !== "undefined" && module.exports) module.exports = api;
else root.TTSNorm = api;
})(typeof self !== "undefined" ? self : this);
