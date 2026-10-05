# 연기 대본 지침 — 서재 1895—1936 낭독

낭독이 대사를 읽을 때 **누가 말하는지(who)** 와 **어떻게 말하는지(how)** 를 알려 주는
대본입니다. 대본은 연출 메모이지 각색이 아닙니다. 본문을 고치지 않고, 원문이 말하지 않는
감정을 덧칠하지 않습니다.

## 1. 전체 흐름

```
tools/tr/notes/<책>.md ──(사람·에이전트)──> tools/act/cast/<책>.json      배역표
python act.py plan <책>                  ──> tools/act/jobs/<책>/NNN.json  작업 단위
actor 에이전트 (작업 하나씩, 병렬)       ──> tools/act/out/<책>/NNN.json   대본 조각
python act.py check <책>/NNN             ──  검사
python act.py build <책>                 ──> 서재/data/act/<책>.js         SEOJAE.receiveAct({...})
```

## 2. 대사를 세는 법 (q 순번의 기준)

대본은 글자 위치가 아니라 **문단 번호(data-p) + 문단 안 n번째 대사**에 겁니다. 그래서
같은 대본이 영어 원문·한국어판·일본어 원문에 그대로 맞습니다. 세는 규칙은 `tools/act.py`
의 `spans()` 와 `tools/act/spans.js` 의 `actSpans()` 가 **똑같이** 구현합니다(전 코퍼스에서 일치 확인). 낭독 런타임은 대본 순번을 셀 때 이것을 씁니다.

- 여는 따옴표는 책·언어마다 하나로 정합니다(대본 파일 `qs`): 영어·한국어 `“` 또는 `‘`
  (문단 머리에 더 많이 오는 쪽), 일본어 `「『`. 이 집합에 없는 따옴표는 안쪽 인용이라
  세지 않습니다. 예: `“… ‘Maw and Meggins.’”` 는 대사 하나.
- `‘` 는 앞 글자가 글자가 아닐 때만 열리고, `’` 는 뒤 글자가 글자가 아닐 때만 닫힙니다
  (`don’t` 의 `’` 는 아포스트로피).
- 문단 끝까지 안 닫힌 대사는 다음 문단으로 이어집니다. 다음 문단이 같은 따옴표로 다시
  시작하면(영어식) 그것이 0번 대사이고 `cont`(이어짐) 표시가 붙습니다. 따옴표 없이
  이어지다 닫히면(일본어식) 문단 머리~닫는 따옴표가 0번 대사입니다.
- 작업 파일의 `q` 가 그 문단 대사 수, `quotes` 가 대사 앞부분입니다. **센 것을 믿고**
  거기에 맞춰 씁니다. 스스로 다시 세지 않습니다.

따옴표 안이 말이 아닐 때(간판, 책 제목, 비꼬는 인용 “Wee Kirk”, 머릿속 생각을 서술자가
옮긴 것)도 순번은 차지합니다. 그런 것은 `who` 를 **서술자 id** 로 둡니다.

## 3. 배역표 `tools/act/cast/<책>.json`

```json
{"id": "jacobs-the-monkey-s-paw", "narrator": "narrator",
 "src": "근거: 번역 노트·본문",
 "cast": [
  {"id": "narrator", "role": "narrator", "names": {"en": "Narrator", "ko": "서술자", "aliases": []},
   "gender": "x", "age": "adult", "traits": "3인칭, 절제된 가정극", "voice": {"base": "M1"}},
  {"id": "mrs-white", "role": "lead",
   "names": {"en": "Mrs. White", "ko": "화이트 부인", "ja": "", "aliases": ["the old lady", "his wife"]},
   "gender": "f", "age": "old", "traits": "조용한 늙은 어머니, 뒤에 광기 어린 바람",
   "voice": {"base": "F4", "speed": 0.96}}
 ]}
```

| 필드 | 값 |
|---|---|
| `id` | 영문 소문자·숫자·`-`. 대본의 `who`/`nar` 가 이것을 가리킴 |
| `role` | `narrator` · `lead`(주역) · `support`(조연) · `minor`(단역) |
| `names` | `en`/`ja`(원어), `ko`(번역 노트 표기 그대로), `aliases`(지문이 부르는 다른 이름: the old man, his wife …) |
| `gender` | `f` · `m` · `x`(서술자·무리) |
| `age` | `child` · `young` · `adult` · `old` |
| `traits` | 한 줄. 말투·성격 — 연기 판단의 근거 |
| `voice.base` | `F1`–`F5`, `M1`–`M5` (Supertonic 3 목소리) |
| `voice.mix` | 선택. `{"F5": 0.3}` = 그 목소리 스타일 벡터를 30% 섞음(합 < 1). 목소리가 모자랄 때 단역 구분용 |
| `voice.speed` | 선택. 0.8–1.2 배율(노인 0.95 안팎) |
| `narrator` | 서술 목소리의 id. 1인칭 화자면 그 인물 id (타임머신: `guest`) |

만드는 법:

1. `tools/tr/notes/<책>.md` 의 인물·호칭·말투표에서 시작합니다. `ko` 는 노트 표기를 그대로.
2. 본문에서 `said the …`, `cried …` 를 훑어 말하는 사람을 빠짐없이 모읍니다.
   말하는 사람만 배역입니다(말 없는 인물은 넣지 않음).
3. 목소리: **서술자 + lead + support 는 서로 겹치지 않게**(`act.py cast` 가 검사 —
   lead/서술자 겹침은 오류, support 겹침은 경고). 성별에 맞는 계열(F/M), 한 장면에 함께
   나오는 사람끼리 대비가 크게. 서술자는 주요 인물과 다른 목소리.
   목소리 10개로 모자라면 minor 는 겹치거나 `mix` 로 살짝 바꿉니다.
4. 서술자가 없는 작품(『덤불 속』처럼 진술만 이어지는 것)은 중립 `narrator` 를 두고
   각 장 첫 문단에 `nar` 로 그 장의 화자를 겁니다(4절).
5. `python act.py cast <책>` 이 `ok` 여야 `plan` 할 수 있습니다.

목소리별 음색(나이·높이)은 아직 **미측정**입니다(에이전트 A 의 결과로 보완). 지금 배정은
성별 계열과 CALIB.md 의 스펙트럼 특성(M4 저역, M3 밝음, M5 저역 웅웅, F5 밝음)만 근거입니다.

## 4. 대본 조각 `tools/act/out/<책>/NNN.json`

입력 작업 파일(`plan` 이 만듦):

```json
{"book": "...", "chunk": 1, "of": 3, "orig": "en", "opens": "“", "narrator": "narrator",
 "cast": [{"id": "mr-white", "name": "화이트 씨", "en": "Mr. White", "role": "lead", "traits": "…"}],
 "prev": [{"k": "63", "t": "앞 문단 꼬리(문맥용)", "q": 0}],
 "items": [
  {"k": "h", "t": "ch001"},
  {"k": "0", "q": 0, "t": "서술 문단(길면 앞뒤만)", "ko": "…"},
  {"k": "5", "q": 2, "t": "원문 전체", "quotes": ["“That’s the worst…", "“of all the beastly…"],
   "ko": "한국어판", "koq": 1, "cont": true}]}
```

`koq` 는 한국어판 대사 수가 다를 때만 붙습니다(참고용 — 대본은 언제나 **원문 순번**대로).

출력 — 문단 번호를 키로 한 평평한 객체:

```json
{"0":  {"mood": "warm"},
 "5":  {"q": [{"who": "mr-white", "how": "shout", "n": "느닷없이 버럭"},
              {"who": "mr-white", "how": "angry"}]},
 "14": {"q": [{"who": "mrs-white"}]},
 "40": {"nar": "tajomaru"}}
```

- `q > 0` 인 문단은 **모두** 넣고, `q` 목록 길이 = 그 문단 대사 수.
- `who` (필수): 배역 id. 정말 알 수 없으면 `null`(런타임이 규칙 기반으로 읽음).
- `how` (선택): `config.json` 의 어휘 하나. 없으면 생략 = 보통 말투.
- `n` (선택): 40자 이하 연출 메모(한국어). 지금 낭독은 쓰지 않지만 사람이 검토할 때와
  다음 모델에 씀. 근거가 된 지문 낱말을 짧게.
- `mood` (선택, 어느 문단에나): 장면 분위기. **이 문단부터 다음 mood 까지** 이어집니다.
  장면이 바뀌는 곳에만, 한 장에 서너 번 이하.
- `nar` (선택, 어느 문단에나): 서술 목소리를 이 문단부터 바꿈(진술 형식의 작품).
- `q == 0` 인 문단에는 `mood`/`nar` 만 넣을 수 있고 넣지 않아도 됩니다.
- 다른 필드·다른 키 금지. `prev` 문단은 앞 작업 몫이라 넣지 않습니다.

## 5. 연기 판단 기준

**기본은 `how` 없음(null).** 낭독은 중립 낭독이 기본이고, 표시는 과장되기 쉽습니다.
근거가 **본문에 적혀 있을 때만** 겁니다.

근거 순서:

1. **말하기 동사와 부사** — 가장 강한 근거.
   `whispered`, `murmured`, `in a low voice`, `hoarsely` → `whisper` ·
   `cried`(외침의 뜻일 때), `shouted`, `screamed`, `bawled`, `in a strong voice` → `shout` ·
   `sobbed`, `wept`, `brokenly` → `sad` · `angrily`, `fiercely`, `snapped` → `angry` ·
   `faltered`, `stammered`, `trembling`, `in shaking tones`, `his voice shook` → `fear` ·
   `laughed`, `chuckled`, `with pretended horror` → `laugh` ·
   `breathlessly`, `hastily`, `rapidly`, `feverishly`, `anxiously` → `tense` ·
   `soothingly`, `gently`(달래는 장면) → `calm`.
   일본어 `囁く`·`叫ぶ`·`泣きながら`, 괄호 지문 `（突然烈しき歔欷）` 도 같습니다.
2. **바로 붙은 행동 지문** — `clasping her hands`, `starting up`, `the glass tapped against his teeth`.
   감정이 분명히 읽힐 때만 how, 애매하면 `n` 에 적고 how 는 비웁니다.
3. **장면 분위기** — mood 로만 표현. 장면이 무섭다고 모든 대사에 `fear` 를 걸지 않습니다.

하지 말 것:

- `slowly`, `curiously`, `politely`, `quietly`(조용히 = 낮은 목소리가 아닐 때) 같은
  어휘에 없는 결을 억지로 가까운 how 에 밀어 넣기 → `n` 에만.
- 문장부호만 보고 판단(`!` 이 있다고 shout 아님. `cried` 도 '말했다' 뜻이면 null).
- 농담하는 인물이라고 모든 대사에 `laugh`. 그 대사에 웃음 근거가 있을 때만.
- 한 문단의 대사 둘이 한 발화(`“…,” he said, “…”`)면 같은 how 를 둘 다에 거는 것이
  기본. 지문이 앞 조각에만 걸리면(`“Get it,” she panted; “get it…—Oh, my boy!”`)
  뒤 조각은 그 내용대로 따로 판단.

`check` 는 how 가 대사의 40%를 넘으면 경고합니다. 절정 장(원숭이 손 3장: 76%)처럼
지문이 실제로 다 감정 동사면 그대로 두어도 됩니다 — 경고는 다시 보라는 뜻입니다.

**화자 판단**: 지문의 `said X` 가 먼저, 없으면 대화의 주고받음(번갈아 말하기), 호칭
(“father” 라고 부르면 말하는 이는 자식), 앞뒤 문단. 화자 없는 연속 대사는 앞 문단의
반대편 사람인 경우가 많지만, 세 사람 이상 장면에서는 내용으로 확인합니다.
`cont` 가 붙은 0번 대사는 앞 문단 마지막 대사의 화자와 같습니다.

## 6. 런타임 정렬 규칙 (번역본·다른 판에 대본을 쓸 때)

낭독 런타임은 읽는 언어의 문단에서 2절 규칙으로 대사를 세고(`qs[lang]` 의 여는 따옴표),
대본 `q` 와 비교합니다(`act.py align()` 이 같은 규칙):

1. 대사 수가 같으면 → 순번대로 who/how.
2. 다르지만 그 문단 `q` 의 who 가 모두 같으면 → 모든 대사를 그 사람으로, how 는 모두 같을 때만.
   그 언어에서 대사가 0개면(따옴표가 사라짐) q 가 모두 서술자 몫이면 잃은 것 없음.
3. 그 밖 → 그 문단 대사는 서술 목소리로(대본 없을 때와 같음) 물러납니다. `mood`·`nar` 는 그대로.

대본에 없는 문단의 대사, `who: null` 도 서술 목소리. `qs` 에 없는 언어는 일본어 `「『`,
나머지 `“` 로 셉니다(build 는 원어와 한국어판의 qs 를 늘 싣습니다).

## 7. 낭독이 대본을 쓰는 법 (`tools/narrate.js` 연기 대본 절)

- **불러오기**: 낭독을 시작할 때 `data/act/index.js` 를 보고 대본이 있는 작품만
  `data/act/<id>.js` 를 받습니다. 설정 '목소리 연기'(`nrAct`, 기본 켬)로 끕니다.
- **자르기**: 문장(정규화기 `sentences`)을 대사 경계에서 다시 잘라, 조각마다 목소리를 정합니다.
  같은 목소리·말투가 이어지면 붙입니다(“Wee Kirk” 처럼 서술자 몫의 인용은 자르지 않음).
  문장 가운데서 자른 자리는 쉼표 쉼.
- **목소리**: 서술 목소리는 독자가 설정에서 고른 것. 배역표에서 그 목소리를 쓰던 배역은 배역표
  서술자 목소리와 맞바꿉니다. 성별 계열이 다르면 아무도 안 쓰는 같은 계열 목소리로, 그것도
  없으면 같은 계열 단역 목소리를 45% 섞습니다. `voice.mix` 는 워커가 스타일 벡터를 선형으로
  섞고, `voice.speed` 는 빠르기에 곱합니다. `nar` 가 걸린 구간의 지문은 그 배역의 목소리.
- **말투**: `how` 와 `mood` 는 `tools/tts/config.json` 의 `act` 표로 합성 매개변수가 됩니다 —
  빠르기·음높이(반음)·억양 폭(temp)·고역 기울기·크기·뒤 쉼. how 는 그 대사에만, mood 는 장면의
  모든 소리(지문 포함)에 곱해집니다. 값은 감정 음성의 대표 경향을 절반 세기로 잡은 것 —
  귀로 듣고 고칠 첫 후보.
- **기기 음성**(speechSynthesis)은 목소리를 바꿀 수 없어 빠르기·높이만 따릅니다.
- 점검: `?nrdebug` 로 열고 콘솔에서 `NR_DEBUG.act(() => console.table(NR_DEBUG.segs(블록번호)))`.
