/* 서재 낭독 — 대사·화자 분석기 (규칙 기반, 의존성 없음).
   오프라인 연기 대본이 없는 책에서도 기본 연기를 하도록, 문단 글자만 보고
   (1) 어디가 대사인지 (2) 누가 말하는지 (3) 어떻게 말하는지(속삭임·외침 …)를 짐작합니다.
   normalize.js 와 같은 UMD: 워커/브라우저는 self.TTSAct, node 는 module.exports.

   쓰는 법 (리더):
     var R = TTSAct.analyze(문단글자배열, "en"|"ko"|"ja");
     R[i].spans = [{a, z, kind, q, open, close, cont, who, del}]   ← 문단 i 의 조각
     TTSAct.segInfo(R[i], seg.a, seg.z)  → {kind, who, del}         ← 문장 하나의 연기 정보
   who = {name, key, pronoun, gender:"m"|"f"|null, conf, how, verb, adverb}
   del = {delivery, src, conf}  — delivery: whisper|shout|sad|laugh|fear|angry|tense|calm|null

   kind: "narr" 서술 · "dial" 대사 · "quote" 서술 속 인용구(“got done.” — 서술자 목소리로)
         · "thought" 한국어 홑따옴표 속말(‘…’) */
(function (root) {
"use strict";

/* ================= 1. 대사 경계 ================= */
var PAIRS = { "“": "”", "‘": "’", "「": "」", "『": "』", "\"": "\"" };

function isLetter(c) { return !!c && /[A-Za-z0-9À-ɏ]/.test(c); }

/* 문단 하나를 조각으로. prev = 앞 문단의 carry({open:"“"}) — 영어 관습에서
   여러 문단에 걸친 대사는 앞 문단이 닫히지 않고 다음 문단이 다시 “ 로 시작합니다.
   돌려주는 배열의 .carry 를 다음 문단 호출에 넘기면 됩니다. */
function spans(text, lang, prev) {
  lang = lang || "en";
  var out = [], stack = [], n = text.length, i, c;
  var dial = [];              /* 최상위 대사 [a, z, open, close] */
  var topA = -1;
  var ja = lang === "ja", ko = lang === "ko";
  for (i = 0; i < n; i++) {
    c = text[i];
    var top = stack.length ? stack[stack.length - 1] : null;
    /* 닫기 */
    if (top && c === PAIRS[top.m] && c !== "\"") {
      if (c === "’" && isLetter(text[i + 1])) continue;          /* don’t · I’m */
      stack.pop();
      if (!stack.length) dial.push([topA, i + 1, top.m, c]);
      continue;
    }
    if (c === "\"") {
      if (top && top.m === "\"") { stack.pop(); if (!stack.length) dial.push([topA, i + 1, "\"", "\""]); }
      else { if (!stack.length) topA = i; stack.push({ m: "\"", a: i }); }
      continue;
    }
    if (c === "”" && stack.length) {
      /* 짝 안 맞는 홑따옴표가 남았으면 겹따옴표까지 걷어냄 */
      var k = stack.length - 1;
      while (k >= 0 && stack[k].m !== "“") k--;
      if (k >= 0) { stack.length = k; if (!stack.length) dial.push([topA, i + 1, "“", "”"]); }
      continue;
    }
    /* 열기 */
    if (c === "“" || c === "「" || c === "『") {
      if (c === "“" && stack.length && stack[0].m === "“" && !stack.slice(1).some(function (s) { return s.m === "‘"; })) {
        /* 닫히지 않은 “ 뒤에 새 “ — 앞 대사를 여기서 끊음 */
        dial.push([topA, i, "“", ""]); stack = [];
      }
      if (!stack.length) topA = i;
      stack.push({ m: c, a: i });
      continue;
    }
    if (c === "‘") {
      /* 영어: 낱말 안(’tis 같은 경우)이 아니라 앞이 공백·구두점일 때만 여는 따옴표 */
      var pc = text[i - 1];
      if (!ko && isLetter(pc)) continue;
      if (!stack.length) topA = i;
      stack.push({ m: c, a: i });
      continue;
    }
  }
  var carry = null;
  if (stack.length) {
    dial.push([topA, n, stack[0].m, ""]);
    if (stack[0].m === "“" || stack[0].m === "\"") carry = { open: stack[0].m };
  }
  /* 조각 만들기 */
  var pos = 0, q = 0;
  dial.forEach(function (d, j) {
    if (d[0] > pos) out.push({ a: pos, z: d[0], kind: "narr" });
    var s = { a: d[0], z: d[1], kind: "dial", open: d[2], close: d[3] };
    s.kind = classify(text, s, lang);
    if (s.kind === "dial") s.q = q++;
    if (j === 0 && prev && prev.open && d[0] === firstNonSpace(text) && (d[2] === "“" || d[2] === "\"")) s.cont = true;
    out.push(s);
    pos = d[1];
  });
  if (pos < n) out.push({ a: pos, z: n, kind: "narr" });
  /* 공백뿐인 서술 조각 버림 */
  out = out.filter(function (s) { return s.kind !== "narr" || /\S/.test(text.slice(s.a, s.z)); });
  out.carry = carry;
  return out;
}
function firstNonSpace(t) { var m = /\S/.exec(t); return m ? m.index : 0; }

/* 대사냐, 서술 속 인용구냐 */
var EN_SAY_BEFORE = /(?:said|says|say|cried|called|shouted|whispered|murmured|added|answered|replied|asked|repeated|echoed|uttered|words|exclaimed|began|wrote|went)\s*$/i;
function classify(text, s, lang) {
  var inner = text.slice(s.a + 1, s.close ? s.z - 1 : s.z);
  var before = text.slice(Math.max(0, s.a - 40), s.a), after = text.slice(s.z, s.z + 12);
  if (lang === "ko") {
    if (s.open === "「" || s.open === "『") return "quote";               /* 한국어 「」『』는 책·글 제목 */
    if (s.open === "‘") {
      /* 홑따옴표: 따옴표 바로 뒤 조사면 강조·인용, 그 밖에 문장이면 속말 */
      if (/^(?:은|는|이|가|을|를|의|라는|이라는|란|이란|로|으로|와|과|도|만|에|처럼|같은)/.test(after) && inner.length < 30) return "quote";
      return /[.!?…。]/.test(inner) || inner.length > 15 ? "thought" : "quote";
    }
    /* “해낸다”는 · “농담”이라고(×) — 조사가 붙고 짧으면 인용구 */
    if (s.close && /^(?:은|는|을|를|의|라는|이라는|란|이란|로|으로|와|과|만|처럼|이니|이나)(?![가-힣]*고)/.test(after) && inner.length < 25 && !/[!?]/.test(inner)) return "quote";
    return "dial";
  }
  if (lang === "ja") {
    if (s.open === "『" && inner.length < 12 && !/[。！？!?]/.test(inner)) return "quote";   /* 書名 */
    if (s.close && /^(?:という|と云う|と言う|と申す|ように|やうに|の|を|が|は|も|に|など)/.test(after) && inner.length < 25 && !/[。！？!?]$/.test(inner)) return "quote";
    return "dial";
  }
  /* en */
  if (s.open === "‘") return inner.length < 30 && !/[.!?]\s*$/.test(inner) ? "quote" : "dial";
  if (s.open === "“" || s.open === "\"") {
    if (!s.close) return "dial";
    if (/[,:]\s*$/.test(before) || EN_SAY_BEFORE.test(before)) return "dial";
    if (/^\s*$/.test(before.slice(-3)) && /(?:^|[.!?”…—]\s*)$/.test(before.replace(/\s+$/, "") + " ") === false) {}
    var midSentence = /[a-z]\s+$/.test(before);
    if (midSentence && inner.length < 30 && !/[!?]/.test(inner)) return "quote";
    if (midSentence && /^[a-z]/.test(inner)) return "quote";
  }
  return "dial";
}

/* ================= 2. 낱말 사전 ================= */
var EN_VERBS = "said|says|say|asked|asks|replied|replies|answered|cried|cries|shouted|exclaimed|whispered|whispers|murmured|muttered|mumbled|called|continued|began|resumed|repeated|echoed|added|insisted|retorted|remarked|suggested|observed|demanded|inquired|enquired|questioned|interrupted|interposed|protested|objected|explained|admitted|agreed|declared|returned|rejoined|responded|stammered|stuttered|faltered|sobbed|wept|laughed|chuckled|giggled|sighed|groaned|moaned|wailed|hissed|snapped|growled|snarled|bawled|roared|yelled|screamed|shrieked|panted|gasped|breathed|urged|pleaded|begged|persisted|proceeded|complained|confessed|announced|thought|warned|yawned|smiled|grinned|sneered|scoffed|conceded|ventured|corrected|concluded|went on|broke out|broke in|cut in|put in|called out|cried out|told|tells|assured|argued|commented|pursued|reflected|grunted|drawled|called back|shouted back|whimpered|blurted|blurted out|announced|reported|chimed in|struck in";
var RX_EN_VERB = "(?:" + EN_VERBS + ")";
var EN_ADV = "[a-z]+ly|at last|at length|again|presently|aloud|softly|quietly|slowly|gently|suddenly";
var EN_TITLE = "Mr|Mrs|Miss|Ms|Dr|Sir|Lady|Lord|Captain|Capt|Colonel|Col|Major|General|Professor|Prof|Father|Mother|Aunt|Uncle|Madame|Madam|Monsieur|Mademoiselle|Signor|Herr|Frau|Sister|Brother|Saint|St|Count|Countess|Baron|Prince|Princess|King|Queen|Inspector|Sergeant|Rev|Reverend";
/* 이름: 대문자 낱말 1–3개(호칭 포함) */
var RX_EN_NAME = "(?!(?:The|A|An|His|Her|My|Our|Their|Your|This|That|It|Its)\\b)(?:(?:" + EN_TITLE + ")\\.?\\s+)?[A-Z][A-Za-z’'\\-]+(?:\\s+[A-Z][A-Za-z’'\\-]+){0,2}";
var RX_EN_DESC = "(?:[Tt]he|[Hh]is|[Hh]er|[Mm]y|[Oo]ur|[Tt]heir|[Yy]our|[Aa]|[Aa]n|[Tt]his|[Tt]hat|[Oo]ne of the)\\s+(?:[A-Za-z’'\\-]+\\s+){0,3}[A-Za-z’'\\-]+";
var RX_EN_PRON = "I|he|she|they|we";
var EN_NOT_NAME = /^(?:Our|His|Her|My|Their|Your|Its|One|Some|Every|All|Both|Each|None|Nobody|Everyone|Everybody|Someone|Somebody|Nothing|Something|Neither|Either|Most|Many|Few|Several|Such|These|Those|At|Behind|Beside|Across|Through|Above|Below|During|Without|Within|Toward|Towards|Upon|Under|Over|Into|From|By|To|Of|Or|Nor|Yet|Though|Although|Because|Since|Until|While|Whereupon|Instead|Once|Twice|Later|Soon|Long|Thus|Hence|Indeed|Evidently|Clearly|Possibly|Probably|Almost|Quite|Very|Too|Not|The|A|An|And|But|Then|Now|Well|Oh|Yes|No|So|He|She|It|I|We|They|You|This|That|There|Here|When|What|Why|How|Who|If|As|At|In|On|For|With|After|Before|Presently|Again|Still|Suddenly|Finally|Meanwhile|Afterwards|Just|Only|Even|Perhaps|Look|Listen|Come|Go|Good|Dear|Sir|Madam|Please|Thank|Hello|Hey|Why|Ah|Hush|Hark|Mate|Check|Never|Nothing|Certainly|Mother|Father|God|Lord|Heavens)$/;

var KO_SAY = "말했다|말하고|말하며|말을 이었다|말을 꺼냈다|말을 보탰다|입을 열었다|물었다|물으며|되물었다|캐물었다|대답했다|대답하며|대꾸했다|되받았다|받아쳤다|받았다|외쳤다|외치며|소리쳤다|소리를 질렀다|고함쳤다|고함을 질렀다|비명을 질렀다|속삭였다|속삭이며|중얼거렸다|웅얼거렸다|되뇌었다|되풀이했다|덧붙였다|끼어들었다|투덜거렸다|우겼다|고집했다|거들었다|털어놓았다|다그쳤다|더듬거렸다|더듬었다|헐떡였다|흐느꼈다|울부짖었다|웃었다|탄식했다|한숨지었다|중얼댔다|설명했다|항의했다|이의를 제기했다|선언했다|이르렀다|일렀다|타일렀다|불렀다|애원했다|간청했다|부르짖었다|말했습니다|물었습니다|대답했습니다|외쳤습니다|속으로 말했|했다|했습니다|못마땅해했다|생각했다|그런 생각을 했다";
var RX_KO_SAY = new RegExp("(?:" + KO_SAY + ")");
var JA_SAY = "言った|言う|言い|言って|云った|云う|云い|云って|申しました|申した|申す|申し上げ|答えた|答えました|答へ|叫んだ|叫び|叫ぶ|怒鳴った|怒鳴り|呟いた|呟く|囁いた|囁く|罵った|尋ねた|尋ねました|聞いた|聞きます|笑った|笑い|泣き|念を押した|仰有った|仰有る|仰った|仰しゃ|話した|話しました|喚いた|喚く|唸った|吐いた|返事をした|声をかけた|言い放った";
var RX_JA_SAY = new RegExp("(?:" + JA_SAY + ")");

/* 전달 단서 — [정규식, delivery, 세기] 앞쪽이 우선 */
var CUE = {
  en: [
    [/\b(?:whisper(?:ed|ing|s)?|murmur(?:ed|ing|s)?|mutter(?:ed|ing|s)?|mumbl(?:ed|ing)|breath(?:ed)|under (?:his|her|my) breath|in a (?:low|hushed|faint) (?:voice|tone)|in an undertone|hoarsely|below (?:his|her) breath)\b/i, "whisper", 0.8],
    [/\b(?:sobb(?:ed|ing)|wept|weeping|tearfully|mournfully|sadly|sorrowfully|wail(?:ed|ing)|moan(?:ed|ing)|sigh(?:ed|ing)|brokenly|piteously|miserably|with a sigh|despairingly|wretchedly|sadness|in tears)\b/i, "sad", 0.7],
    [/\b(?:laugh(?:ed|ing|s)?|chuckl(?:ed|ing)|giggl(?:ed|ing)|grinn(?:ed|ing)|merrily|gaily|gleefully|jokingly|with a laugh|hilariously|cheerfully|ecstatically|laughingly|teasingly|with a smile|smiling)\b/i, "laugh", 0.7],
    [/\b(?:stammer(?:ed|ing)|stutter(?:ed|ing)|falter(?:ed|ing)|trembl(?:ed|ing)|quaver(?:ed|ing)|in shaking tones|shakily|unsteadily|nervously|fearfully|timidly|breathlessly|in terror|aghast|with a shudder|his voice shook|her voice shook|tremulously|in alarm|with a look of alarm|panted|gasped|faintly)\b/i, "fear", 0.7],
    [/\b(?:snapp?(?:ed|ing)?|growl(?:ed|ing)|snarl(?:ed|ing)|hiss(?:ed|ing)|angrily|furiously|fiercely|crossly|savagely|irritably|indignantly|hotly|bitterly|contemptuously|scornfully|sharply|violently|violence|accusingly|impatiently|doggedly|gruffly|roughly|harshly|sneer(?:ed|ing)|scoff(?:ed))\b/i, "angry", 0.6],
    [/\b(?:shout(?:ed|ing|s)?|yell(?:ed|ing)|bawl(?:ed|ing)|roar(?:ed|ing)|scream(?:ed|ing)|shriek(?:ed|ing)|bellow(?:ed|ing)|exclaim(?:ed|ing)|cried out|called out|called|loudly|at the top of (?:his|her) voice|in a (?:loud|strong) voice|cried|cry|wildly)\b/i, "shout", 0.6],
    [/\b(?:hastily|hurriedly|urgently|feverishly|hysterically|excitedly|eagerly|anxiously|tense|tensely|quickly|rapidly|desperately|breathless)\b/i, "tense", 0.5],
    [/\b(?:quietly|calmly|gently|softly|soothingly|tenderly|kindly|slowly|solemnly|gravely|placidly|politely|evenly|mildly|thoughtfully|offhandedly|distinctly|reassuringly)\b/i, "calm", 0.5]
  ],
  ko: [
    [/속삭|소곤|중얼|웅얼|나직|낮은 목소리|낮게|쉰 목소리|숨죽여|들릴 듯 말 듯|목소리를 낮춰/, "whisper", 0.8],
    [/흐느|울먹|울며|울면서|울부짖|목 놓아|눈물|슬픈|슬픔이 어린|애처롭게|한숨|탄식|침울하게|비통/, "sad", 0.7],
    [/웃으며|웃었다|웃음|낄낄|킥킥|껄껄|깔깔|신이 나서|명랑하게|유쾌하게|황홀해|짐짓|농담/, "laugh", 0.7],
    [/더듬|떨리는|떨며|떨면서|떨렸|머뭇|겁에 질|두려|숨 가쁘|헐떡|벌벌|기어드는|아연실색|질겁|놀란 얼굴로|떨었다/, "fear", 0.7],
    [/사납게|화를 내|화가 나|버럭|성난|격하게|퉁명|쏘아|나무라|깔보듯|비웃|쏘아붙|노려|매섭게|발끈|완강하게/, "angry", 0.6],
    [/외쳤|외치|소리쳤|소리를 질렀|소리를 지르|고함|비명|크게|힘찬 목소리|부르짖|악을 쓰|목청/, "shout", 0.7],
    [/서둘러|급히|다급|허둥|열에 들뜬|발작하듯|정신없이|흥분|애타|조바심|빠르게|팽팽/, "tense", 0.5],
    [/조용히|차분|천천히|다정하게|부드럽게|달래듯|엄숙하게|담담|느긋|또렷하게|예의 바르게|무심히|대수롭지 않다는 듯|상냥하게/, "calm", 0.5]
  ],
  ja: [
    [/囁|ささや|呟|つぶや|小声|低い声|声を潜め|声をひそめ|蚊の鳴く/, "whisper", 0.8],
    [/泣き|泣い|泣く|涙|嘆|すすり|啜り|嗚咽|しおしお|悲しげ|悲しそう|ため息|溜息|うめく|呻/, "sad", 0.7],
    [/笑って|笑い|笑った|笑う|笑顔|にやり|にこにこ|からからと|嘲る|あざけ/, "laugh", 0.7],
    [/震え|ふるえ|わなわな|どもり|吃り|怯え|おびえ|恐る恐る|おずおず|声を顫/, "fear", 0.7],
    [/怒鳴|罵|憤|おこり|怒って|怒り|腹が立|プンプン|噛みつく|噛みつくよう|叱|睨/, "angry", 0.6],
    [/叫|喚|大きな声|大声|声を張|万歳/, "shout", 0.7],
    [/慌て|あわて|急いで|息を切ら|せき込|勢い込/, "tense", 0.5],
    [/静かに|しずかに|穏やか|おだやか|落ち着|ゆっくり|しんみり|やさしく|優しく/, "calm", 0.5]
  ]
};

/* ================= 3. 성별 ================= */
var G = {
  en: {
    m: /\b(?:Mr|Sir|Lord|Father|Uncle|Brother|Monsieur|Signor|Herr|King|Prince|Count|Baron|Rev|Reverend|Sergeant|Sergeant-Major|Colonel|Captain|Major|General)\b|\b(?:man|men|gentleman|fellow|boy|lad|father|son|husband|brother|uncle|nephew|king|prince|sir|lord|master|mister|chap|youth|sergeant|sergeant-major|soldier|old man|priest|monk|butler|footman|waiter|landlord|host|grandfather|bachelor|mayor|guy|he|him|his)\b/i,
    f: /\b(?:Mrs|Miss|Ms|Lady|Madame|Madam|Mademoiselle|Frau|Sister|Mother|Aunt|Queen|Princess|Countess|Duchess)\b|\b(?:woman|women|lady|girl|wife|mother|daughter|sister|aunt|niece|queen|princess|maid|maiden|widow|old woman|old lady|grandmother|hostess|landlady|she|her|hers|nurse|mistress|bride|actress)\b/i
  },
  ko: {
    m: /(?:^|[\s])(?:그|그는|그가)$|씨$|군$|경$|선생$|신사|남자|사내|아버지|아빠|남편|아들|오빠|형|삼촌|숙부|할아버지|노인|청년|소년|총각|군인|상사|대령|대위|장군|목사|신부|왕|왕자|주인장|집사|의사|시장|여행자|편집자|기자|심리학자|^그$/,
    f: /그녀|부인$|양$|여사|아가씨|여자|여인|아내|어머니|엄마|딸|누이|누나|언니|이모|고모|숙모|할머니|노부인|노파|하녀|소녀|처녀|왕비|공주|마님|과부|부인|신부님$/
  },
  ja: {
    m: /君$|殿$|氏$|旦那|男|父|親父|爺|翁|息子|兄|弟|夫|亭主|坊|紳士|下人|盗人|侍|僧|和尚|主人|若者|若い男|殿様|大殿|乞食|跛|医者|お医者|彼$|俺|おれ|己|僕|わし|放免|木樵|法師|師匠|弟子/,
    f: /夫人|奥様|奥さん|お嬢|嬢|娘|女|母|お母|婆|姥|妻|姉|妹|女房|お姫|姫|尼|彼女|あたし|女房|巫女/
  }
};
/* 흔한 영어 이름 몇 — 이름만으로 판단할 때 */
var EN_FIRST = {
  m: "Tom|Nick|Jay|George|Herbert|John|James|William|Henry|Charles|Edward|Robert|Richard|Arthur|Frank|Fred|Frederick|Harry|Jack|Joe|Joseph|Peter|Paul|Michael|David|Thomas|Walter|Albert|Alfred|Philip|Ralph|Hugh|Morris|Filby|Bert|Ben|Jim|Bill|Dick|Ted|Sam|Tony|Owl|Wolfsheim|Gatsby|Buchanan|Wilson|McKee|Klipspringer|Eckleburg|Cody|Gregor|Josef|Kipps|Polly|Lewisham|Griffin|Kemp|Bedford|Cavor|Prendick|Moreau|Montgomery|Graham|Ostrog|Trafford|Britling|Bealby",
  f: "Daisy|Jordan|Myrtle|Catherine|Pammy|Lucille|Ella|Mary|Anne|Ann|Elizabeth|Jane|Margaret|Alice|Edith|Ethel|Emily|Emma|Helen|Kate|Kitty|Lucy|Grace|Rose|Marion|Dora|Sylvia|Ruth|Martha|Sarah|Susan|Weena|Grete|Ann Veronica|Marjorie|Christina|Isabel|Isabella|Clara|Nora|Agnes|Hilda|Gloria|Rosalind|Eleanor|Isabelle|Ardita|Bernice|Marjorie"
};
var RX_EN_FIRST_M = new RegExp("\\b(?:" + EN_FIRST.m + ")\\b"), RX_EN_FIRST_F = new RegExp("\\b(?:" + EN_FIRST.f + ")\\b");

function gender(name, ctx, lang) {
  if (!name) return null;
  lang = lang || "en";
  var t = String(name);
  if (lang === "en") {
    if (/^(?:he|him|his)$/i.test(t)) return "m";
    if (/^(?:she|her)$/i.test(t)) return "f";
    /* 'his wife' 는 여자 — 한정사(his/her …)는 빼고 명사만 봄 */
    var head = t.replace(/^(?:the|his|her|my|our|their|a|an|this|that)\s+/i, "").replace(/\b(?:he|him|his|she|her|hers)\b/gi, " ");
    var hasF = G.en.f.test(head), hasM = G.en.m.test(head);
    if (hasF && !hasM) return "f";
    if (hasM && !hasF) return "m";
    if (RX_EN_FIRST_F.test(t)) return "f";
    if (RX_EN_FIRST_M.test(t)) return "m";
  } else {
    var g = G[lang];
    var f = g.f.test(t), m = g.m.test(t);
    if (f && !m) return "f";
    if (m && !f) return "m";
    if (f && m) {
      /* 머리 명사(끝)가 우선: '노부인'·'화이트 부인' */
      var tail = t.slice(-3);
      if (g.f.test(tail)) return "f";
      if (g.m.test(tail)) return "m";
    }
  }
  if (ctx && ctx.memo && ctx.memo[keyOf(name, lang)]) return ctx.memo[keyOf(name, lang)];
  return null;
}

/* ================= 4. 전달 단서 ================= */
/* quote: 대사 글자(따옴표 포함), tag: 말 동사·부사가 든 서술 조각 */
/* 대사 구두점 — 전달 종류로 단정하진 않고(‘Look!’ 은 외침이 아님) 운율 힌트로만 넘김 */
function punctOf(quote) {
  var inner = String(quote || "").replace(/^[“"‘「『\s]+|[”"’」』\s]+$/g, "");
  return {
    excl: (inner.match(/[!！]/g) || []).length,
    q: /[?？]\s*$/.test(inner),
    ellip: /(?:…|\.\.\.)\s*$/.test(inner) || /……/.test(inner),
    broken: /[—–―-]\s*$/.test(inner),
    stammer: /\b([A-Za-z])\s?[—-]\s?\1/i.test(inner) || /(?:^|\s)([A-Za-z]{1,3})-\1/i.test(inner) || /([가-힣])\s?[—-]\s?\1/.test(inner)
  };
}
function cues(quote, tag, lang) {
  var r = cues0(quote, tag, lang);
  r.punct = punctOf(quote);
  return r;
}
function cues0(quote, tag, lang) {
  lang = lang || "en";
  var L = CUE[lang] || CUE.en, i;
  var vm = tag && lang === "en" ? new RegExp("\\b(?:" + EN_VERBS + ")\\b", "i").exec(tag) : null;
  if (vm) for (i = 0; i < L.length; i++) {
    if (L[i][0].test(vm[0])) return { delivery: L[i][1], src: vm[0], conf: L[i][2] };
  }
  if (tag) for (i = 0; i < L.length; i++) {
    var m = L[i][0].exec(tag);
    if (m) return { delivery: L[i][1], src: m[0], conf: L[i][2] };
  }
  var inner = String(quote || "").replace(/^[“"‘「『\s]+|[”"’」』\s]+$/g, "");
  /* 대사 안 구두점 */
  if (/\b([A-Za-z])\s?[—-]\s?\1/i.test(inner) && lang === "en") return { delivery: "fear", src: "stammer", conf: 0.4 };
  if (/(?:^|\s)([A-Za-z]{1,3})-\1/i.test(inner)) return { delivery: "fear", src: "stammer", conf: 0.35 };
  if (/([가-힣])\s?[—-]\s?\1/.test(inner) || /^(?:저|나|그)\s?—/.test(inner)) return { delivery: "fear", src: "stammer", conf: 0.35 };
  var ex = (inner.match(/[!！]/g) || []).length;
  if (ex >= 2 && inner.length < 40) return { delivery: "shout", src: "!!", conf: 0.4 };
  if (/[A-Z]{4,}/.test(inner) && !/[a-z]/.test(inner)) return { delivery: "shout", src: "CAPS", conf: 0.5 };
  return { delivery: null, src: null, conf: 0 };
}

/* ================= 5. 화자 찾기 ================= */
function keyOf(name, lang) {
  if (!name) return null;
  var t = String(name).trim();
  if (lang === "en") {
    t = t.replace(/^(?:the|a|an|this|that)\s+/i, "").replace(/\s+/g, " ");
    if (/^I$/.test(t)) return "narrator";
    return t.toLowerCase();
  }
  if (lang === "ko") {
    if (/^(?:나|내|저|제)$/.test(t)) return "narrator";
    return t.replace(/\s+/g, " ");
  }
  if (lang === "ja") {
    if (/^(?:わたし|私|わたくし|おれ|俺|己|僕|わし|あたし|手前)$/.test(t)) return "narrator";
    return t.replace(/^(?:お|御)(?=医者|母様|父様)/, "");
  }
  return t;
}

/* --- 영어 --- */
var RX_EN_NP = "(" + RX_EN_PRON + "|" + RX_EN_NAME + "|" + RX_EN_DESC + ")";
var RX_EN_AFTER_INV = new RegExp("^[\\s,;:—–-]*(?:" + "(?:" + EN_ADV + ")\\s+)?(" + RX_EN_VERB + ")\\s+(?:(" + EN_ADV + ")\\s+)?" + RX_EN_NP);
var RX_EN_AFTER_NORM = new RegExp("^[\\s,;:—–-]*(?:and\\s+|then\\s+)?" + RX_EN_NP + "(?:,\\s*)?\\s+(?:(" + EN_ADV + ")\\s+)?(" + RX_EN_VERB + ")\\b");
var RX_EN_WAS_REPLY = /^[\s,;—]*was the (reply|answer|response|retort)/i;
var RX_EN_BEFORE = new RegExp(RX_EN_NP + "\\s+(?:(" + EN_ADV + ")\\s+)?(?:and\\s+)?(?:\\w+\\s+){0,4}?(" + RX_EN_VERB + ")(?:\\s+(?:to\\s+\\w+(?:\\s+\\w+)?|(" + EN_ADV + ")|in\\s+a\\s+\\w+\\s+voice|aloud))?\\s*[:,]?\\s*$");
var RX_EN_BEFORE_A = new RegExp("^" + RX_EN_NP + "\\s+(?:(?:" + EN_ADV + ")\\s+)?(?:(?:[a-z]+\\s+){1,4}and\\s+)?(?:(?:" + EN_ADV + ")\\s+)?(" + RX_EN_VERB + ")(?:\\s+(?:to\\s+\\w+(?:\\s+\\w+)?|(?:" + EN_ADV + ")|in\\s+a\\s+\\w+\\s+voice|aloud))*\\s*[:,]?\\s*$");
var NP_STOP = /\s+(?:who|which|with|as|and|in|at|to|of|from|for|by|on|after|before|while|without|when|that|whose|into|over|upon|making|looking|turning|still|again|softly|presently|then|but)\b.*$/;

function cleanEnNP(np) {
  if (!np) return null;
  np = np.replace(NP_STOP, "").replace(/[,.;:!?”’"]+$/, "").trim();
  for (var g = 0; g < 3; g++) np = np.replace(/\s+(?:[a-z]+ly|at|last|again|aloud|once|now|then)$/, "");
  /* 'the Time Traveller put forth' → 'the Time Traveller' (대문자 이름꼴은 대문자까지만) */
  var cap = /^((?:[Tt]he|[Aa]n?)\s+(?:[A-Z][A-Za-z’'\-]+\s*)+)(?:\s+[a-z].*)?$/.exec(np);
  if (cap && /^[A-Z]/.test(np.split(/\s+/)[1] || "")) np = cap[1].trim();
  else np = np.replace(/^((?:the|his|her|my|our|their|your|a|an|this|that)\s+(?:[a-z’'\-]+\s+)*?)(?:put|said|was|were|had|took|made|came|went|got|sat|stood|looked|turned|rose|shook|seemed|gave|held|kept|began|did|could|would|should|might|must|will|is|are|regarded|bowed|stared|smiled|laughed|nodded|leaned|walked|ran|cried)\b.*$/i, "$1").trim();
  if (/[’']s$/.test(np)) return null;
  var lw = np.split(/\s+/);
  if (lw.length > 2 && /^(?:the|his|her|my|our|their|your|a|an|this|that)$/i.test(lw[0]) && /^[a-z]/.test(lw[1]) && !lw.slice(1).some(function (x) { return /^[A-Z]/.test(x); })) {
    var cut = -1;
    for (var q = 1; q < lw.length; q++) if (/^(?:man|woman|lady|wife|husband|son|daughter|mother|father|boy|girl|visitor|stranger|soldier|sergeant-major|sergeant|gentleman|fellow|friend|guest|host|servant|maid|child|doctor|editor|journalist|cousin|uncle|aunt|brother|sister|people|men|women|girls|boys)$/i.test(lw[q])) { cut = q; break; }
    np = lw.slice(0, cut > 0 ? cut + 1 : 2).join(" ");
  }
  /* 'the frivolous Herbert' → Herbert, 'this point Miss Baker' → Miss Baker */
  var m = /^(?:[Tt]he|[Aa]n?|[Tt]his|[Tt]hat)\s+(?:[a-z\-]+\s+)+((?:(?:Mr|Mrs|Miss|Ms|Dr|Sir|Lady)\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)$/.exec(np);
  if (m && /^[a-z]/.test(np.split(/\s+/)[1] || "")) np = m[1];
  if (/^(?:the|his|her|my|our|their|your|a|an|this|that)$/i.test(np)) return null;
  if (/^(?:it|this|that|there)$/i.test(np)) return null;
  return np;
}
function pronounOf(np) {
  if (!np) return null;
  if (/^he$/i.test(np)) return "he";
  if (/^she$/i.test(np)) return "she";
  if (/^I$/.test(np)) return "I";
  if (/^(?:they|we)$/i.test(np)) return "they";
  return null;
}
function enVerbAdv(tagText) {
  var v = new RegExp("\\b(" + RX_EN_VERB + ")\\b").exec(tagText || "");
  var a = /\b([a-z]+ly)\b/.exec(tagText || "");
  return { verb: v ? v[1] : null, adverb: a && !/^(?:only|early|likely|really|nearly|merely|simply|hardly|scarcely|family|supply|reply|fly|holy|lily|ugly|silly|jolly|belly|rely|apply|ally|fully)$/.test(a[1]) ? a[1] : null };
}
/* 문장 첫머리 주어 */
var RX_EN_SUBJ = new RegExp("^(?:(?:Then|And|But|So|Now|At last|Presently|Suddenly|Again)\\s*,?\\s+)?" + RX_EN_NP + "(?:,\\s*([^,]{0,60}),)?\\s+(?!(?:of|and|or|in|on|at|to|with|from|for|by|as|who|whom|which|that|whose|the|a|an|is|are)\\b)[a-z]+\\b");
function enSubject(sent) {
  sent = sent.replace(/\([^)]*\)\s*/g, "").replace(/^[\s—–-]+/, "");
  var m = RX_EN_SUBJ.exec(sent);
  if (!m) return null;
  var np = cleanEnNP(m[1]);
  /* 'The other girl, Daisy, made …' — 동격 이름이 있으면 그 이름 */
  if (m[2] && new RegExp("^" + RX_EN_NAME + "$").test(m[2].trim()) && !EN_NOT_NAME.test(m[2].trim().split(/\s+/)[0])) np = m[2].trim();
  if (!np) return null;
  if (/^(?:The|A|An)\s+(?:thing|door|wind|fire|room|house|night|day|knock|talisman|paw|matches|candle|bed|sound|voice|words|idea|answer|last|first)\b/i.test(np) || /^(?:the|a)\s+(?:other|rest)$/i.test(np)) return null;
  if (/^[A-Z]/.test(np) && EN_NOT_NAME.test(np.split(/\s+/)[0]) && !/^(?:The|A|An|His|Her|My|Our|Their|This|That)\s/.test(np) && !/^(?:He|She|I|They|We)$/.test(np)) return null;
  if (/^(?:He|She|I)$/.test(np)) np = np === "I" ? "I" : np.toLowerCase();
  return np;
}
var RX_SENT_SPLIT = /(?<!\b(?:Mr|Mrs|Ms|Dr|St|Capt|Col|Gen|Prof|Rev|Lt|Sgt|[A-Z])\.)(?<=[.!?;])\s+/;
function lastSentence(t) {
  var ss = t.replace(/\s+$/, "").split(RX_SENT_SPLIT);
  return ss[ss.length - 1] || "";
}
function firstSentence(t) {
  return (t.replace(/^\s+/, "").split(RX_SENT_SPLIT)[0]) || "";
}

/* --- 한국어 --- */
var KO_ADV_STOP = /^(?:마침내|이윽고|그러자|그때|갑자기|다시|이내|잠시|곧|문득|결국|드디어|또|아까|한참|얼마|그러고는|그리고|그러나|하지만|그래서|그러다|그러더니|이번엔|이번에는|비로소|가만히|천천히|조용히|여전히|아직|벌써|이미|한동안|순간|한편|오히려|도리어|그제야|이때|그러면서|게다가|더구나|이어|뒤이어|금세|불쑥|느닷없이|대뜸|얼른|그만|도로|다들|모두|함께|같이|가까이|깊이|높이|멀리|많이|길이|곧이)$/;
var KO_PRON = /^(?:그|그녀|나|내|저|제|우리|그들|그이|당신)$/;
var KO_TITLE = /^(?:씨|부인|양|군|선생|선생님|여사|경|님|상사|박사|교수|대령|대위|목사|신부|부부)$/;
/* 사람 명사 — 은/는 주제어는 이 목록·알려진 이름·대명사일 때만 주어로 봄(‘젊은’·‘하는’ 같은 관형형 배제) */
var KO_PERSON = /(?:아버지|어머니|아빠|엄마|남편|아내|아들|딸|노인|노부인|노파|부인|남자|여자|사내|소년|소녀|청년|아가씨|손님|상대|상대방|친구|군인|상사|의사|박사|교수|학자|기자|편집자|여행자|시장|사람|주인|하인|하녀|집사|신사|숙녀|아이|애|형|오빠|누나|언니|동생|할아버지|할머니|삼촌|이모|고모|사촌|이웃|낯선 이|낯선 사람|씨|양|군|님|선생|여사|부부)$/;
var KO_GENERIC = /^(?:남자|여자|사람|사내|아이|애|누구|사람들|이들|모두|다들)$/;
var KO_NOT_SUBJ = /^(?:무언가|누군가|어딘가|언젠가|무언|누군|어딘|언젠|무엇인|아니|마치|모두|서로|이미|다시|함께|같이|가까이|깊이|높이|멀리|많이|길이|곧이|몹시|이따금|도리어|겨우|간신히|조용히|천천히|가만히|다행히|정말|사실|이것|그것|저것|무엇|아무것|누구|어디|여기|거기|저기|이곳|그곳|자기|스스로|그때|이때|순간|잠시|한참|대답|소리|목소리|말|생각|마음|눈|얼굴|손|문|바람|불|방|집|밤|날|두려움|침대|성냥|기계|물건|부적|종|벽|시간|빛|그림자|침묵|웃음|울음|비명|노크|발소리)$/;
var curKnown = null;                 /* analyze 중인 책에서 말 동사의 주어로 나온 이름들(한국어) */
function koSubject(sent, known) {
  known = known || curKnown;
  var toks = sent.replace(/[“”"‘’「」『』]/g, " ").split(/\s+/).filter(Boolean);
  for (var i = 0; i < toks.length && i < 14; i++) {
    var tk = toks[i].replace(/[,.!?…—–·]+$/, "");
    var m = /^([가-힣A-Za-z]+?)(께서|이|가|은|는)$/.exec(tk);
    if (!m) continue;
    var stem = m[1], p = m[2];
    if (KO_ADV_STOP.test(tk) || KO_ADV_STOP.test(stem) || KO_NOT_SUBJ.test(stem)) continue;
    if (stem === "그녀" || stem === "그" || stem === "나" || stem === "내" || stem === "저" || stem === "제" || stem === "우리" || stem === "그들") return { np: stem === "내" ? "나" : stem === "제" ? "저" : stem, i: i };
    if (stem.length < 2 && !(known && known[stem]) && !(KO_TITLE.test(stem) && i > 0)) continue;
    /* 이/가: 부사형 '-히' 나 명사형 '-기·-음' 은 주어 아님 */
    if ((p === "이" || p === "가") && /(?:기|음|함|됨|것|데|때|중|뿐|만큼)$/.test(stem)) continue;
    /* 은/는: 사람 명사·알려진 이름일 때만 */
    if ((p === "은" || p === "는") && !(KO_PERSON.test(stem) || (known && known[stem]))) continue;
    /* 앞 낱말 붙이기: '화이트 씨', '시간 여행자', '지방 시장' */
    var np = stem;
    if (i > 0) {
      var pv = toks[i - 1].replace(/[,.!?…]+$/, "");
      var pvOk = /^[가-힣A-Za-z]+$/.test(pv) && !KO_ADV_STOP.test(pv) && !/[은는을를이가의에도로며고서게듯히던운쁜한된진적럼와과랑]$/.test(pv) && !/(?:다|요|까|지|네|죠|야|어|아|나|자|고|면|서|며|니)$/.test(pv);
      if (KO_TITLE.test(stem) && pvOk) np = pv + " " + stem;
      else if (pvOk && pv.length >= 2 && !KO_PERSON.test(pv)) np = pv + " " + stem;
      else if (pvOk && pv.length === 1 && curKnown && curKnown[pv]) np = pv + " " + stem;   /* '톰 뷰캐넌' */
    }
    return { np: np, i: i };
  }
  return null;
}
/* 책 전체에서 'X가 … 말했다' 꼴의 X — 외국 이름(허버트·필비·데이지)을 사람으로 알아보는 근거 */
function koKnownNames(paras) {
  var k = {}, re = new RegExp("(?:^|[\\s”])([가-힣]{1,6})(이|가|은|는|께서)\\s+(?:[^.!?“”\\s]+\\s+){0,4}?(?:" + KO_SAY + ")", "g"), m;
  paras.forEach(function (t) {
    re.lastIndex = 0;
    while ((m = re.exec(t || ""))) {
      var w = m[1];
      if (KO_ADV_STOP.test(w) || KO_NOT_SUBJ.test(w) || KO_PRON.test(w)) continue;
      /* 한 글자 이름(톰·닉)은 받침 뒤 '이'로만, 흔한 한 글자 명사는 뺌 */
      if (w.length === 1 && (m[2] !== "이" || /[그내제네누뭐이저나날밤불문말눈손몸땅물돈빛일집방길곳것수때적줄체척넋숨잠꿈피칼총책편]/.test(w))) continue;
      k[w] = (k[w] || 0) + 1;
    }
  });
  Object.keys(k).forEach(function (w) { if (w.length === 1 && k[w] < 2) delete k[w]; });
  return k;
}
function koSentences(t) { return t.split(/(?<=[.!?…。])\s+/); }

/* --- 일본어 --- */
var JA_LEAD = /^(?:その時|そのとき|すると|けれども|けれど|しかし|そして|それから|そこで|やがて|間もなく|ところが|が、|で、|と、|今度は|やっと|また|まず|ただ|もっとも|しかも|ふと|急に|やがて|突然|そうして|さて)[、]?/;
var JA_PRON = /^(?:わたし|私|わたくし|おれ|俺|己|僕|わし|あたし|手前|彼|彼女|あなた|お前)$/;
/* 사람 같은 명사구: 사람 접미사·대명사·이 책에서 말 동사의 주어로 나온 이름 */
var JA_PERSON_SFX = /(?:人|者|様|殿|君|さん|婆|爺|娘|男|女|夫|妻|子|師|匠|弟子|乞食|紳士|医者|下人|盗人|侍|僧|法師|主|姥|母|父|兄|姉|妹|弟|房|翁|嫗|供|共|衆|彼|彼女)$/;
var JA_NOT_PERSON = /(?:事|物|声|音|風|雨|火|門|家|夜|日|手|目|眼|顔|心|光|時|所|中|話|語|言葉|御言|様子|容子|気色|色|姿|影|胸|口|唇|頭|体|命|夢|絵|画|屏風|猿|鴉|噂|評判|方|上|下|内|外|前|後|間|頃|度|程)$/;
var jaKnownCur = null;
function jaIsPerson(np) {
  if (!np) return false;
  if (JA_PRON.test(np)) return true;
  if (jaKnownCur && jaKnownCur[np]) return true;
  if (JA_NOT_PERSON.test(np) && !/(?:様|殿)$/.test(np)) return false;
  return JA_PERSON_SFX.test(np);
}
/* 문장 안 모든 'X は/が/も' — [명사구, 조사, 위치] */
var RX_JA_SUBJ = /((?:[一-龯々]+[いな])?(?:[一-龯々ァ-ヶー]+の)?[一-龯々ァ-ヶー]+|わたし|わたくし|おれ|あたし|あなた|お前)(は|が|も)(?![らなりれるろつっ])/g;
function jaSubjects(sent) {
  var t = String(sent || "").replace(/（[^）]*）|\([^)]*\)/g, ""), out = [], m;
  RX_JA_SUBJ.lastIndex = 0;
  while ((m = RX_JA_SUBJ.exec(t))) {
    var np = m[1].replace(/^(?:その|この|あの)(?=[一-龯])/, "").replace(/の方$/, "");
    var np2 = np.replace(/^(?:後|今|昔|又|唯|先刻|丁度|急|或日|或時|今度|当時|現に|殊に|尤も|別に|其|此)(?=[一-龯ァ-ヶ]{2,}|の)/, "").replace(/^の/, "");
    if (np2.length >= 2) np = np2;
    if (/^(?:それ|これ|あれ|どれ|何|誰|此|其|今|皆|私共)$/.test(np)) continue;
    out.push({ np: np, p: m[2], i: m.index });
  }
  return out;
}
/* 서술 문장의 주어(첫 사람 주어) */
function jaSubject(sent) {
  var c = jaSubjects(sent).filter(function (x) { return jaIsPerson(x.np); });
  return c.length ? c[0].np : null;
}
/* 대사 바로 앞(머리): 마지막 사람 주어 */
function jaLastSubject(t) {
  var c = jaSubjects(t).filter(function (x) { return jaIsPerson(x.np); });
  return c.length ? c[c.length - 1].np : null;
}
/* 대사 뒤 'こう叫んだ' 류(꼬리): 말 동사 앞의 마지막 が 주어, 없으면 첫 は 주어 */
function jaSpeakerOfVerb(sent) {
  var vm = RX_JA_SAY.exec(sent), cut = vm ? vm.index : sent.length;
  var c = jaSubjects(sent.slice(0, cut)).filter(function (x) { return jaIsPerson(x.np); });
  for (var i = c.length - 1; i >= 0; i--) if (c[i].p === "が") return c[i].np;
  return c.length ? c[0].np : null;
}
/* 책 전체에서 'X は/が … 言った' 꼴의 X */
function jaKnownNames(paras) {
  var k = {};
  paras.forEach(function (t) {
    jaSentences(t || "").forEach(function (sn) {
      if (!RX_JA_SAY.test(sn)) return;
      var vm = RX_JA_SAY.exec(sn);
      jaSubjects(sn.slice(0, vm.index)).forEach(function (x) { if (!JA_NOT_PERSON.test(x.np) && x.np.length <= 6) k[x.np] = (k[x.np] || 0) + 1; });
    });
  });
  Object.keys(k).forEach(function (w) { if (k[w] < 2) delete k[w]; });
  return k;
}
function jaHead(np) {
  if (!np) return np;
  if (JA_PRON.test(np)) return np;
  var m = /([一-龯々ァ-ヶー]+)$/.exec(np);
  return m ? m[1] : np;
}
function jaSentences(t) { return t.split(/(?<=[。！？])/); }

/* 호칭(vocative): “…, Nick?” — 다음 대사는 그 사람일 가능성 */
function vocative(inner, lang, known) {
  var m;
  if (lang === "en") {
    var re = /(?:^|,\s*|\.\s+)((?:(?:Mr|Mrs|Miss|Dr)\.?\s+)?[A-Z][a-z]+)(?=[,?!.;]|\s*$)/g, last = null;
    while ((m = re.exec(inner))) {
      var w = m[1];
      if (EN_NOT_NAME.test(w) || /^(?:sir|madam|dear|darling|mother|father)$/i.test(w)) continue;
      /* 문장 첫머리 대문자는 이름일 때만: 알려진 이름이어야 */
      if (known && !known[keyOf(w, lang)] && !/^(?:Mr|Mrs|Miss|Dr)/.test(w)) continue;
      last = w;
    }
    return last;
  }
  if (lang === "ko") {
    m = /(?:^|[,.\s])([가-힣]{2,6}(?: 씨| 양| 군| 부인)?)[,.?!](?:\s|$)/.exec(inner.replace(/^“/, ""));
    if (m && known && known[keyOf(m[1], lang)]) return m[1];
  }
  return null;
}

/* ================= 6. 전체 분석 ================= */
/* paras: 문단 글자 배열(장 하나나 책 하나).
   opts.cast  = {"Daisy": "f", …}  성별표(선택 — 오프라인 노트가 있으면)
   opts.alias = {"the old man": "Mr. White", …} 같은 인물 표(선택)
   opts.narrator = "m"|"f"  1인칭 서술자 성별(선택) */
function analyze(paras, lang, opts) {
  opts = opts || {};
  lang = lang || "en";
  var memo = {}, known = {}, alias = {};
  if (opts.alias) Object.keys(opts.alias).forEach(function (k) { alias[keyOf(k, lang)] = opts.alias[k]; });
  if (opts.cast) Object.keys(opts.cast).forEach(function (k) { memo[keyOf(k, lang)] = opts.cast[k]; known[keyOf(k, lang)] = k; });
  learnGender(paras, lang, memo, known);
  curKnown = lang === "ko" ? koKnownNames(paras) : null;
  jaKnownCur = lang === "ja" ? jaKnownNames(paras) : null;
  var ctx = { memo: memo };
  var res = [], carry = null;
  var hist = [];                       /* 장면 안 최근 대사 문단 [{p, who, voc}] */
  var narrRun = 0, pendingJa = null;
  var recent = { m: null, f: null };   /* 성별별 가장 최근 언급(주어 우선) */
  var lastSubj = null;                 /* 직전 서술 문단의 마지막 사람 주어 */
  var tailFlag = false, fpRef = false;
  var FP = lang === "en" ? /\b(?:me|I|my|myself)\b/ : lang === "ko" ? /(?:^|\s)(?:나에게|내게|나를|나는|내가|나도|나와|내 )/ : /(?:わたし|私|おれ|俺)(?:に|を|の|は|が)/;

  var SUBJ = lang === "en" ? enSubject : lang === "ko" ? function (s) { var r = koSubject(s); return r && r.np; } : jaLastSubject;
  var SENTS = lang === "en" ? function (t) { return t.replace(/\([^)]*\)/g, " ").split(RX_SENT_SPLIT); } : lang === "ko" ? koSentences : function (t) { return jaSentences(t).filter(function (x) { return x.trim(); }); };

  function prOf(np) {
    if (lang === "en") return pronounOf(np);
    if (lang === "ko") return np === "그" || np === "그이" ? "he" : np === "그녀" ? "she" : (np === "나" || np === "저") ? "I" : np === "우리" || np === "그들" ? "they" : null;
    return /^(?:わたし|私|おれ|俺|己|僕|わし|あたし|わたくし|手前)$/.test(np) ? "I" : np === "彼" ? "he" : np === "彼女" ? "she" : null;
  }
  function mkWho(np, how, conf, verb, adverb) {
    if (!np) return null;
    var pr = prOf(np);
    var w = { name: pr && pr !== "I" ? null : np, key: null, pronoun: pr, gender: null, conf: conf, how: how, verb: verb || null, adverb: adverb || null };
    if (pr === "he") w.gender = "m"; else if (pr === "she") w.gender = "f";
    if (pr === "they") { w.pronoun = "they"; return w; }
    if (w.name && /^(?:other|latter|former|other one|상대|상대방|相手|向う)$/i.test(keyOf(w.name, lang))) {
      /* 'the other'·'상대' — 이 대화에서 방금 말한 사람이 아닌 쪽 */
      var lastW = hist.length ? hist[hist.length - 1].who : null, pick = null;
      var cands = [expectAlt()];
      for (var h = hist.length - 2; h >= 0 && h >= hist.length - 6; h--) cands.push(hist[h].who);
      cands.push(recent.m, recent.f);
      for (var c = 0; c < cands.length && !pick; c++) { var x = cands[c]; if (x && x.name && (!lastW || x.key !== lastW.key)) pick = x; }
      if (pick) { w.name = pick.name; w.key = pick.key; w.gender = pick.gender; w.conf = Math.min(conf, 0.55); w.how = how + "+other"; return w; }
      w.name = null; w.conf = 0; return w;
    }
    if (w.name) {
      var k = keyOf(w.name, lang);
      if (alias[k]) { w.name = alias[k]; k = keyOf(w.name, lang); }
      w.key = k;
      w.gender = gender(w.name, ctx, lang) || memo[k] || null;
      if (k === "narrator") w.gender = opts.narrator || null;
    }
    return w;
  }
  function expectAlt() {
    if (hist.length < 2) return null;
    var a = hist[hist.length - 1].who, b = hist[hist.length - 2].who;
    if (a && b && a.key && b.key && a.key !== b.key) return b;
    return null;
  }
  var anyRecent = [];                  /* 성별 모르는 이름까지, 최근 언급 순 */
  function note(w) {
    if (!w || !w.name || (lang === "ko" && KO_GENERIC.test(w.name))) return;
    if (w.gender) recent[w.gender] = w;
    if (w.key !== "narrator") { anyRecent = anyRecent.filter(function (x) { return x.key !== w.key; }); anyRecent.push(w); if (anyRecent.length > 6) anyRecent.shift(); }
  }
  /* 대명사로 가리킨 사람의 성별을 배움 */
  function learn(w, g) { if (w && w.key && g && w.key !== "narrator" && !memo[w.key]) { memo[w.key] = g; w.gender = g; if (!recent[g] || recent[g].key === w.key) recent[g] = w; } }
  /* 대명사 → 이름. 서술이 끼었으면 최근 언급, 아니면 대화 교대가 우선 */
  function resolve(w, local, narrBetween) {
    if (!w || w.name || !w.gender) return w;
    var g = w.gender, cand = null, how = null, alt = expectAlt();
    if (local && local.name && local.gender === g) { cand = local; how = "beat"; }
    if (!cand && narrBetween && recent[g]) { cand = recent[g]; how = "recent"; }
    if (!cand && alt && alt.gender === g) { cand = alt; how = "alt"; }
    if (!cand && recent[g]) { cand = recent[g]; how = "recent"; }
    /* 같은 성별 후보가 없으면 성별 모르는 최근 인물(그리고 그 성별을 배움) */
    if (!cand) for (var i = anyRecent.length - 1; i >= 0; i--) { var x = anyRecent[i]; var xg = x.gender || memo[x.key]; if (!xg) { cand = x; how = "unk"; learn(x, g); break; } }
    if (cand) { w.name = cand.name; w.key = cand.key; w.conf = Math.min(w.conf, 0.6); w.how += "+" + how; }
    return w;
  }
  /* 서술 글을 문장마다 훑어 최근 언급을 갱신, 마지막 사람 주어를 돌려줌 */
  function readNarr(t) {
    var last = null;
    SENTS(t).forEach(function (s) {
      var np = SUBJ(s);
      if (np) {
        var w = mkWho(np, "narr", 0.5);
        if (w && !w.name && w.gender) resolve(w, null, true);
        if (w && (w.pronoun === "I" || (w.name && isPerson(w.name, w.gender, lang, curKnown)))) { note(w); last = w; }
      }
      if (lang === "en") enMentions(s).forEach(function (m) {
        if (np && m === np) return;
        var w2 = mkWho(m, "mention", 0.4);
        /* 문장 안 다른 언급은 같은 성별 최근 주어를 덮지 않음 — 주어가 없을 때만 */
        if (w2 && w2.name && w2.gender && (!recent[w2.gender] || !np)) recent[w2.gender] = w2;
      });
    });
    return last;
  }

  for (var p = 0; p < paras.length; p++) {
    var text = paras[p] || "";
    var sp = spans(text, lang, carry);
    carry = sp.carry;
    var dials = sp.filter(function (s) { return s.kind === "dial"; });
    res.push({ p: p, spans: sp });
    if (!dials.length) {
      narrRun++;
      if (!/[\p{L}]/u.test(text) || narrRun >= 3) hist = [];
      lastSubj = readNarr(text) || (narrRun > 1 ? lastSubj : null);
      fpRef = fpRef || FP.test(text.replace(/“[^”]*”/g, ""));
      tailFlag = false;
      if (lang === "ja") jaNarrPara(text, p, false);
      continue;
    }
    /* --- 대사 문단 --- */
    var narrBetween = narrRun > 0, prevW = null, firstTagged = null;
    var ws = [];
    for (var j = 0; j < sp.length; j++) {
      var s = sp[j];
      if (s.kind !== "dial") continue;
      var prevN = null, nextN = null, b, f;
      for (b = j - 1; b >= 0 && sp[b].kind !== "dial"; b--) if (sp[b].kind === "narr") { prevN = sp[b]; break; }
      for (f = j + 1; f < sp.length && sp[f].kind !== "dial"; f++) if (sp[f].kind === "narr") { nextN = sp[f]; break; }
      var after = nextN ? text.slice(nextN.a, nextN.z) : "";
      var before = prevN ? text.slice(prevN.a, prevN.z) : "";
      /* 대사 앞 서술: 언급 갱신 + 이 대사 바로 앞 주어(행동 꼬리) */
      /* 꼬리표 조각('he went on,')은 빼고 완결된 서술 문장만 읽음 */
      var full = before ? completeSents(before, lang) : "";
      var local = full ? readNarr(full) : null;
      if (full) narrBetween = true;
      var t = lang === "en" ? enTag(after, before) : lang === "ko" ? koTag(after, before) : jaTag(after, before, j === 0 ? pendingJa : null);
      var w = t && t.np ? mkWho(t.np, t.how, t.conf, t.verb, t.adverb) : null;
      if (w && w.pronoun === "they") w = null;
      if (w && !w.name && w.gender) {
        /* 대명사 꼬리표: 같은 문단 앞 대사와 성별이 같고 그 사이 새 주어가 없으면 같은 사람 */
        if (prevW && prevW.name && (prevW.gender === w.gender || !prevW.gender) && prevW.key !== "narrator" && !(local && local.name && local.key !== prevW.key)) { learn(prevW, w.gender); w.name = prevW.name; w.key = prevW.key; w.how += "+same"; }
        else resolve(w, local, narrBetween);
      }
      if (!w || (!w.name && w.pronoun !== "I")) {
        var w0 = w;
        if (prevW && !(local && local.name && local.key !== prevW.key)) w = Object.assign({}, prevW, { how: "para", conf: prevW.conf * 0.95 });
        else if (local && local.name) w = Object.assign({}, local, { how: "beat", conf: 0.55 });
        else w = null;
        if (w && w0) { w.verb = w0.verb; w.adverb = w0.adverb; }
        if (!w) w = w0;
      }
      s.who = w;
      s._tag = t && t.how === "before-para" && pendingJa ? pendingJa.tag : t && t.np && /^(?:after-inv|after-norm|after-subj|after|before|inline|before-para|after-next)$/.test(t.how) ? tagClause(/^after/.test(t.how) ? after : before, t.how, lang) : "";
      if (w && w.name && !firstTagged && /^(?:after|before|inline)/.test(w.how) && w.conf >= 0.7) firstTagged = w;
      if (w && (w.name || w.pronoun === "I")) prevW = w;
      ws.push(s);
    }
    pendingJa = null;
    /* 꼬리표 없는 앞 대사: 문단 뒤쪽 꼬리표(영어 관습: 한 문단 한 화자) */
    var paraWho = firstTagged || null;
    for (j = 0; j < ws.length && !paraWho; j++) if (ws[j].who && ws[j].who.name) paraWho = ws[j].who;
    ws.forEach(function (x) { if ((!x.who || (!x.who.name && x.who.pronoun !== "I")) && paraWho) x.who = Object.assign({}, paraWho, { how: "para", conf: (paraWho.conf || 0.5) * 0.9 }); });
    /* 문단 전체에 단서가 없으면: 이어지는 대사 → 호칭 → 앞 서술 주어 → 교대 */
    if (!ws.some(function (x) { return x.who && (x.who.name || x.who.pronoun === "I"); })) {
      var prevD = hist.length ? hist[hist.length - 1] : null, guess = null, pron = ws[0].who && ws[0].who.gender ? ws[0].who : null;
      if (dials[0].cont && prevD && prevD.who) guess = Object.assign({}, prevD.who, { how: "cont", conf: 0.8 });
      if (!guess && prevD && prevD.voc && !narrBetween && (!prevD.who || keyOf(prevD.voc, lang) !== prevD.who.key)) guess = mkWho(prevD.voc, "vocative", 0.55);
      if (!guess && (narrBetween || tailFlag) && lastSubj && (lastSubj.name || lastSubj.pronoun === "I")) guess = Object.assign({}, lastSubj, { how: "prev-narr", conf: 0.5 });
      if (!guess && expectAlt()) guess = Object.assign({}, expectAlt(), { how: "alt", conf: 0.45 });
      if (!guess && lang !== "en" && prevD && prevD.who && narrBetween) guess = Object.assign({}, prevD.who, { how: "same", conf: 0.3 });
      if (guess && pron && ((guess.gender && guess.gender !== pron.gender) || guess.key === "narrator")) guess = null;
      if (guess) ws.forEach(function (x) { x.who = Object.assign({}, guess, x.who ? { verb: x.who.verb, adverb: x.who.adverb } : {}); });
    }
    /* 전달 단서: 제 꼬리표 → 같은 화자의 이웃 대사 */
    ws.forEach(function (x) { x.del = cues(text.slice(x.a, x.z), x._tag, lang); x._own = !!x._tag; });
    ws.forEach(function (x, i) {
      if (x.del.delivery || x._own) return;
      for (var d = 1; d < ws.length; d++) {
        var y = ws[i - d] || ws[i + d];
        [ws[i - d], ws[i + d]].forEach(function (y) {
          if (!x.del.delivery && y && y._own && y.del.delivery && y.del.conf >= 0.5 && y.who && x.who && y.who.key === x.who.key) x.del = { delivery: y.del.delivery, src: y.del.src, conf: y.del.conf * 0.8 };
        });
        if (x.del.delivery) break;
      }
    });
    ws.forEach(function (x) { delete x._tag; delete x._own; });
    /* 장면 기록: 앞 서술의 주인공이 이번 화자와 다르면 한 차례로 끼워 넣음(대화 상대) */
    var main = ws[0].who;
    if ((narrBetween || tailFlag) && lastSubj && (lastSubj.name || lastSubj.pronoun === "I") && main && lastSubj.key !== main.key && (!hist.length || (hist[hist.length - 1].who || {}).key !== lastSubj.key)) hist.push({ p: p - 0.5, who: lastSubj });
    /* 1인칭 서술자가 말을 건네받는 자리("leaned towards me") — 서술자도 대화 상대로 */
    if (fpRef && narrBetween && main && main.key !== "narrator" && (!hist.length || (hist[hist.length - 1].who || {}).key !== "narrator")) hist.push({ p: p - 0.25, who: mkWho(lang === "en" ? "I" : lang === "ko" ? "나" : "わたし", "fp", 0.4) });
    fpRef = false;
    var mainK = null;
    for (j = 0; j < ws.length; j++) if (ws[j].who && ws[j].who.key) { mainK = ws[j].who; break; }
    if (mainK && mainK.key) { known[mainK.key] = mainK.name; if (mainK.gender && !memo[mainK.key]) memo[mainK.key] = mainK.gender; }
    var lastWho = ws[ws.length - 1].who;
    note(lastWho);
    var tailN = sp[sp.length - 1];
    if (tailN.kind === "narr") readNarr(text.slice(tailN.a, tailN.z));
    hist.push({ p: p, who: lastWho || mainK, voc: vocative(text.slice(ws[ws.length - 1].a, ws[ws.length - 1].z), lang, known) });
    narrRun = 0;
    /* 꼬리 서술에 새 인물이 끼어들면(began Miss Baker, but Tom interrupted her) 다음 대사 후보 */
    var ts = tailN.kind === "narr" ? tailSubject(text.slice(tailN.a, tailN.z), lang) : null;
    var tw = ts ? mkWho(ts, "tail", 0.45) : null;
    if (tw && tw.name && isPerson(tw.name, tw.gender, lang, curKnown) && (!lastWho || tw.key !== lastWho.key)) { lastSubj = tw; tailFlag = true; }
    else { lastSubj = null; tailFlag = false; }
    if (lang === "ja" && tailN.kind === "narr") jaNarrPara(text.slice(tailN.a, tailN.z), p, true);
  }
  return res;

  /* 일본어 서술 문단: 앞 대사의 꼬리(と…申しました) / 다음 대사의 머리(…申しました。 …、) */
  function jaNarrPara(t, p, inPara) {
    var ss = jaSentences(t).filter(function (x) { return x.trim(); });
    if (!ss.length) return;
    var first = ss[0];
    if (!inPara && hist.length && hist[hist.length - 1].p === p - 1 &&
        (/^と/.test(first) || (/(?:こう|かう|そう|さう|こんな|かやうな|かやう)/.test(first) && RX_JA_SAY.test(first)) || /(?:念を押した|罵った|答えました|答えた|仰有る|仰有つた)/.test(first))) {
      var subj = jaSpeakerOfVerb(first.replace(/^と[、]?/, ""));
      var prevEntry = res[p - 1];
      if (subj && prevEntry) {
        var w = mkWho(subj, "after-next", 0.75, (RX_JA_SAY.exec(first) || [])[0]);
        var dl = cues("", first, "ja");
        prevEntry.spans.forEach(function (x) {
          if (x.kind !== "dial") return;
          if (!x.who || x.who.conf < 0.75) x.who = w;
          if (!x.del || !x.del.delivery) x.del = dl;
        });
        hist[hist.length - 1].who = w;
        note(w);
      }
    }
    var last = ss[ss.length - 1].trim();
    if (/、$/.test(t.trim()) || new RegExp("(?:" + JA_SAY + ")[^。]{0,12}。?$").test(last)) {
      var sj = null;
      for (var i = ss.length - 1; i >= 0 && !sj; i--) sj = jaLastSubject(ss[i]);
      pendingJa = sj ? { np: sj, verb: (RX_JA_SAY.exec(last) || [])[0] || null } : null;
      if (pendingJa) pendingJa.tag = last;
    } else pendingJa = null;
  }
}

/* 꼬리 서술 속 새 주어: but Tom interrupted her */
function tailSubject(t, lang) {
  if (lang !== "en") return null;
  var re = new RegExp("\\b(?:but|and|while|when|until|whereupon|as)\\s+(" + RX_EN_NAME + "|" + RX_EN_DESC + ")\\s+(?!(?:of|and|or|in|on|at|to|with|from|for|by|as|who|which|that)\\b)[a-z]+", "g"), m, last = null;
  while ((m = re.exec(t))) { var np = cleanEnNP(m[1]); if (np) last = np; }
  return last;
}
/* 대사 앞 서술에서 완결된 문장만(끝의 꼬리표 조각 'he went on,' 은 뺌) */
function completeSents(t, lang) {
  var re = lang === "ja" ? /[。！？]/g : /[.!?。](?=\s|$)/g, m, end = -1;
  while ((m = re.exec(t))) {
    if (lang === "en" && /\b(?:Mr|Mrs|Ms|Dr|St|[A-Z])$/.test(t.slice(0, m.index))) continue;
    end = m.index + 1;
  }
  return end > 0 ? t.slice(0, end) : "";
}
/* 사람인가: 성별이 있거나, 대문자 이름이거나, 사람 명사 */
var RX_PERSON_EN = /\b(?:visitor|stranger|guest|friend|doctor|editor|journalist|servant|clerk|officer|child|speaker|newcomer|companion|traveller|traveler|psychologist|mayor|host|people|person|figure|other|latter|former|cousin|neighbour|neighbor|nurse|maid|butler)\b/i;
function isPerson(np, g, lang, known) {
  if (g) return true;
  if (known && known[keyOf(np, lang)]) return true;
  if (lang === "en") {
    var core = np.replace(/^(?:the|a|an|his|her|my|our|their)\s+/i, "");
    return /^[A-Z]/.test(core) || RX_PERSON_EN.test(core);
  }
  if (lang === "ko") return KO_PRON.test(np) || KO_PERSON.test(np);
  return jaIsPerson(np);
}

/* 영어: 문장 안 사람 언급(이름·호칭·성별 명사구) */
var RX_EN_MENTION = new RegExp("\\b(?:(?:" + EN_TITLE + ")\\.?\\s+[A-Z][a-z]+|(?:the|his|her|my|their)\\s+(?:old\\s+|young\\s+|little\\s+)?(?:man|woman|lady|wife|husband|son|daughter|mother|father|boy|girl|visitor|stranger|soldier|sergeant-major|sergeant|gentleman|fellow)|[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?)\\b", "g");
function enMentions(s) {
  var out = [], m;
  RX_EN_MENTION.lastIndex = 0;
  while ((m = RX_EN_MENTION.exec(s))) {
    var w = m[0];
    if (m.index === 0 && !/^(?:Mr|Mrs|Miss|Dr|Sir|Lady)/.test(w)) continue;      /* 문장 첫 대문자는 주어 처리에서 */
    if (EN_NOT_NAME.test(w.split(/\s+/)[0]) && !/^(?:the|his|her|my|their)\s/.test(w)) continue;
    out.push(w);
  }
  return out;
}

/* 꼬리표에서 전달 단서를 볼 범위: 대사에 붙은 절 하나 */
function tagClause(t, how, lang) {
  if (!t) return "";
  if (lang !== "en") return clauseOf(t, lang, how);
  var c = how.indexOf("after") === 0 ? firstSentence(t) : lastSentence(t);
  if (how.indexOf("after") === 0) c = c.split(/,\s*(?:as|while|who|which|when|whereupon|until|since|because|though|after|before)\b|;|—/)[0];
  return c;
}

/* 한국어·일본어: 꼬리표 조각에서 그 대사에 걸리는 문장만 */
function clauseOf(t, lang, how) {
  if (lang === "ko") { var ss = koSentences(t.trim()); return how && how.indexOf("before") === 0 ? ss[ss.length - 1] : ss[0]; }
  if (lang === "ja") { var js = jaSentences(t.trim()); return how && how.indexOf("before") === 0 ? js[js.length - 1] : js[0]; }
  return t;
}

function enTag(after, before) {
  var m, va;
  if (after) {
    var a1 = after.replace(/^\s*[—–-]+\s*/, " ");
    if ((m = RX_EN_WAS_REPLY.exec(a1))) return { np: null, how: "after-reply", conf: 0 };
    if ((m = RX_EN_AFTER_INV.exec(a1))) {
      var np = cleanEnNP(m[3]);
      if (np && !/^(?:to|that)$/i.test(np)) { va = enVerbAdv(firstSentence(a1)); return { np: np, how: "after-inv", conf: 0.9, verb: m[1], adverb: va.adverb }; }
    }
    if ((m = RX_EN_AFTER_NORM.exec(a1))) {
      var np2 = cleanEnNP(m[1]);
      if (np2 && !/^(?:it|this|that)$/i.test(np2)) { va = enVerbAdv(firstSentence(a1)); return { np: np2, how: "after-norm", conf: 0.9, verb: m[3], adverb: va.adverb || m[2] || null }; }
    }
  }
  if (before) {
    var tail = before.slice(-160);
    var cut = tail.search(/(?<!\b(?:Mr|Mrs|Ms|Dr|St|[A-Z]))[.!?;]\s+(?=(?:[^.!?;]|(?<=\b(?:Mr|Mrs|Ms|Dr|St))\.)*$)/);
    var cl = cut >= 0 ? tail.slice(cut + 1) : tail;
    if (/[:,]\s*$/.test(cl) || new RegExp("\\b" + RX_EN_VERB + "\\s*$").test(cl)) {
      /* 왼쪽부터 낱말 머리마다 'NP (…and) VERB:' 꼴을 맞춰 봄 — 'At this point Miss Baker said:' */
      var c2 = cl.replace(/^\s+/, ""), re = /(?:^|\s)(?=\S)/g, mm;
      while ((mm = re.exec(c2))) {
        var at = mm.index + mm[0].length;
        var m4 = RX_EN_BEFORE_A.exec(c2.slice(at));
        if (m4) {
          var np3 = cleanEnNP(m4[1]);
          if (np3 && !(EN_NOT_NAME.test(np3.split(/\s+/)[0]) && !/^(?:the|his|her|my|our|their|a|an|He|She|I|he|she)$/i.test(np3.split(/\s+/)[0]))) {
            va = enVerbAdv(cl); return { np: np3, how: "before", conf: 0.85, verb: m4[2], adverb: va.adverb };
          }
        }
        if (re.lastIndex === mm.index) re.lastIndex++;
      }
      /* 'Then she added irrelevantly:' 처럼 주어만 */
      var sj = enSubject(cl.replace(/^\s+/, ""));
      if (sj && new RegExp("\\b" + RX_EN_VERB + "\\b").test(cl)) { va = enVerbAdv(cl); return { np: sj, how: "before", conf: 0.75, verb: va.verb, adverb: va.adverb }; }
    }
  }
  /* 대사 바로 뒤 문장 주어(행동 꼬리): “Mate.” He turned … */
  if (after) {
    var fs = firstSentence(after);
    var sb = enSubject(fs);
    if (sb && new RegExp("\\b" + RX_EN_VERB + "\\b").test(fs)) { va = enVerbAdv(fs); return { np: sb, how: "after-subj", conf: 0.7, verb: va.verb, adverb: va.adverb }; }
    if (sb) return { np: sb, how: "after-beat", conf: 0.45 };
  }
  return null;
}

function koTag(after, before) {
  var m;
  /* 인라인: X가 “…” 하고 말했다 */
  if (before && after && /^\s*(?:하고|라고|하며|하는|하고는|했다|하더니|하자|하니|하면서)/.test(after)) {
    var bs = koSentences(before.trim()); var ls = bs[bs.length - 1] || "";
    var sj = koSubject(ls);
    if (sj) return { np: sj.np, how: "inline", conf: 0.8, verb: (RX_KO_SAY.exec(after) || [])[0] || null };
  }
  if (after && /^\s*[^\s“”]/.test(after)) {
    var fs = koSentences(after.trim())[0] || "";
    var s2 = koSubject(fs);
    var say = RX_KO_SAY.exec(fs);
    if (s2 && s2.i <= 3 && (say || isPerson(s2.np, null, "ko", curKnown))) {
      return { np: s2.np, how: "after", conf: say ? 0.9 : 0.65, verb: say ? say[0] : null };
    }
  }
  if (before) {
    var bss = koSentences(before.trim()), last = bss[bss.length - 1] || "";
    if (RX_KO_SAY.test(last) || /[:：]\s*$/.test(before.trim()) || /이렇게\s*(?:말했|덧붙|물었)/.test(last)) {
      var s3 = koSubject(last);
      if (s3) return { np: s3.np, how: "before", conf: 0.75, verb: (RX_KO_SAY.exec(last) || [])[0] || null };
    }
  }
  return null;
}

function jaTag(after, before, pending) {
  var fs = after ? (jaSentences(after)[0] || "") : "";
  /* 「…」と X は言った / 「…」と、横柄に御答へ申し上げました */
  if (after && /^\s*(?:と|って|とか)/.test(after)) {
    var rest = fs.replace(/^\s*(?:と|って)[、]?/, "");
    var sj = jaSpeakerOfVerb(rest);
    if (sj) return { np: sj, how: "after", conf: RX_JA_SAY.test(fs) ? 0.85 : 0.6, verb: (RX_JA_SAY.exec(fs) || [])[0] || null };
    /* 주어가 인용 앞에 있음: 夫はわたしを蔑んだまま、「殺せ。」と一言云った */
    if (before) {
      var bl = jaSentences(before).filter(function (x) { return x.trim(); });
      var sb = jaLastSubject(bl[bl.length - 1] || "");
      if (sb) return { np: sb, how: "inline", conf: 0.75, verb: (RX_JA_SAY.exec(fs) || [])[0] || null };
      /* 문단의 주제어(は) */
    }
    if (pending) return { np: pending.np, how: "before-para", conf: 0.75, verb: pending.verb };
    if (before) {
      for (var i = bl.length - 2; i >= 0; i--) { var tp = jaSubject(bl[i]); if (tp) return { np: tp, how: "inline-topic", conf: 0.55, verb: (RX_JA_SAY.exec(fs) || [])[0] || null }; }
    }
    return null;
  }
  /* 「…」――妻は気が狂ったように、何度もこう叫び立てた */
  if (after && /(?:こう|かう|そう|さう|こんな|かやうな|かう云ふ)/.test(fs) && RX_JA_SAY.test(fs)) {
    var sv = jaSpeakerOfVerb(fs.replace(/^[\s―—]+/, ""));
    if (sv) return { np: sv, how: "after", conf: 0.8, verb: (RX_JA_SAY.exec(fs) || [])[0] || null };
  }
  if (pending) return { np: pending.np, how: "before-para", conf: 0.75, verb: pending.verb };
  if (before) {
    var bs2 = jaSentences(before).filter(function (x) { return x.trim(); }), last = bs2[bs2.length - 1] || "";
    if (/[、―—]\s*$/.test(before.trim()) || RX_JA_SAY.test(last)) {
      var s3 = jaLastSubject(last);
      if (!s3) for (var j = bs2.length - 2; j >= 0 && !s3; j--) s3 = jaLastSubject(bs2[j]);
      if (s3) return { np: s3, how: "before", conf: 0.7, verb: (RX_JA_SAY.exec(last) || [])[0] || null };
    }
  }
  return null;
}

/* 책 전체에서 성별 배우기: 'X … his/her' 같은 문장, 꼬리표 'said X, … his' */
function learnGender(paras, lang, memo, known) {
  var votes = {};
  function vote(k, g) { if (!k) return; votes[k] = votes[k] || { m: 0, f: 0 }; votes[k][g]++; }
  paras.forEach(function (t) {
    if (!t) return;
    if (lang === "en") {
      var plain = t.replace(/“[^”]*”/g, " ");
      plain.split(/(?<=[.!?;])\s+/).forEach(function (s) {
        var subj = enSubject(s);
        if (!subj || pronounOf(subj) || !isPerson(subj, null, "en")) return;
        var rest = s.slice(subj.length);
        var m = /\b(his|him|himself|her|herself|hers)\b/.exec(rest);
        if (m) vote(keyOf(subj, lang), /^h(?:is|im)/.test(m[1]) ? "m" : "f");
      });
      /* 다음 문장이 He/She 로 시작 */
      var ss = plain.split(/(?<=[.!?])\s+/);
      for (var i = 0; i + 1 < ss.length; i++) {
        var s0 = enSubject(ss[i]);
        if (!s0 || pronounOf(s0) || !isPerson(s0, null, "en")) continue;
        if (/^He\b/.test(ss[i + 1])) vote(keyOf(s0, lang), "m");
        else if (/^She\b/.test(ss[i + 1])) vote(keyOf(s0, lang), "f");
      }
    } else if (lang === "ko") {
      t.replace(/[“][^”]*[”]/g, " ").split(/(?<=[.!?])\s+/).forEach(function (s, i, arr) {
        var sj = koSubject(s); if (!sj || KO_PRON.test(sj.np)) return;
        var nx = arr[i + 1] || "";
        if (/^그녀(?:는|가)/.test(nx)) vote(sj.np, "f");
        else if (/^그(?:는|가)\s/.test(nx)) vote(sj.np, "m");
      });
    }
  });
  Object.keys(votes).forEach(function (k) {
    var v = votes[k];
    if (memo[k]) return;
    if (v.m >= 2 * v.f + 1) memo[k] = "m"; else if (v.f >= 2 * v.m + 1) memo[k] = "f";
  });
}

/* ================= 7. 리더용 도우미 ================= */
/* 문장 [a,z) 하나의 연기 정보 — 대사와 겹치는 글자가 가장 많은 조각 기준 */
function segInfo(entry, a, z) {
  var best = null, bestN = 0, narrN = 0;
  (entry && entry.spans || []).forEach(function (s) {
    var o = Math.min(z, s.z) - Math.max(a, s.a);
    if (o <= 0) return;
    if (s.kind === "dial") { if (o > bestN) { bestN = o; best = s; } }
    else narrN += o;
  });
  if (!best || bestN < narrN * 0.5) return { kind: "narr", who: null, del: null };
  return { kind: "dial", who: best.who || null, del: best.del || null, mixed: narrN > 0 };
}

/* 원문 분석 결과를 번역 문단으로 옮김(같은 문단 번호, 대사 순서대로).
   한국어판은 원문(영어)의 꼬리표가 더 정확하므로, 화자는 원문에서 가져오는 편이 낫습니다. */
function project(src, dst) {
  dst.forEach(function (e, i) {
    var se = src[i]; if (!se) return;
    var sd = se.spans.filter(function (s) { return s.kind === "dial"; });
    var dd = e.spans.filter(function (s) { return s.kind === "dial"; });
    if (!sd.length) return;
    dd.forEach(function (s, j) {
      var from = sd.length === dd.length ? sd[j] : sd[0];
      if (from.who && (from.who.name || from.who.pronoun === "I" || !s.who || !s.who.name)) s.who = Object.assign({}, from.who, { how: "proj:" + from.who.how });
      if (from.del && from.del.delivery && (!s.del || !s.del.delivery || s.del.conf < from.del.conf)) s.del = from.del;
    });
  });
  return dst;
}

/* 제안 API 이름 그대로도: attribute(paras) → 대사마다 화자 후보 */
function attribute(paras, lang, opts) {
  var R = analyze(paras, lang, opts), out = [];
  R.forEach(function (e) {
    e.spans.forEach(function (s) {
      if (s.kind !== "dial") return;
      var w = s.who || {};
      out.push({ p: e.p, q: s.q, a: s.a, z: s.z, name: w.name || null, pronoun: w.pronoun || null, gender: w.gender || null, verb: w.verb || null, adverb: w.adverb || null, conf: w.conf || 0, how: w.how || null, delivery: s.del ? s.del.delivery : null });
    });
  });
  return out;
}

var api = { _: { enSubject: enSubject, enTag: enTag, koSubject: koSubject, koTag: koTag, jaSubject: jaSubject, jaTag: jaTag, enMentions: enMentions }, spans: spans, analyze: analyze, attribute: attribute, cues: cues, gender: gender, segInfo: segInfo, project: project, keyOf: keyOf };
if (typeof module !== "undefined" && module.exports) module.exports = api;
else root.TTSAct = api;
})(typeof self !== "undefined" ? self : this);
