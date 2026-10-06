# -*- coding: utf-8 -*-
"""Build the catalogue metadata for the reading site."""
import os, io, json, re

import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

AUTHORS = {
    "\uce74\ud504\uce74": {
        "en": "Franz Kafka", "ko": "\ud504\ub780\uce20 \uce74\ud504\uce74",
        "life": "1883\u20131924", "slug": "kafka",
        "note": "\ud504\ub77c\ud558\uc758 \ubcf4\ud5d8\uad6d \uc9c1\uc6d0\uc774\uc790, 20\uc138\uae30 \ubb38\ud559\uc744 \ub2e4\uc2dc \uc4f4 \ubaa8\ub354\ub2c8\uc998\uc758 \uc911\uc2ec.",
    },
    "HG\uc6f0\uc2a4": {
        "en": "H. G. Wells", "ko": "H. G. \uc6f0\uc2a4",
        "life": "1866\u20131946", "slug": "wells",
        "note": "\uacfc\ud559\uc18c\uc124\uc758 \uc124\uacc4\uc790. \uc0ac\ud68c\uc18c\uc124\uacfc \ubbf8\ub798\uc0ac\ub97c \uac19\uc740 \uc190\uc73c\ub85c \uc36c \uc0ac\ub78c.",
    },
    "\ud53c\uce20\uc81c\ub7f4\ub4dc": {
        "en": "F. Scott Fitzgerald", "ko": "F. \uc2a4\ucf67 \ud53c\uce20\uc81c\ub7f4\ub4dc",
        "life": "1896\u20131940", "slug": "fitzgerald",
        "note": "\uc7ac\uc988 \uc2dc\ub300\uc758 \uae30\ub85d\uc790\uc774\uc790 \uadf8 \uc2dc\ub300\uc5d0 \uac00\uc7a5 \uae4a\uc774 \ubca0\uc778 \uc0ac\ub78c.",
    },
    "\ud14c\uc544\ud3f0\ud558\ub974\ubd80": {
        "en": "Thea von Harbou", "ko": "\ud14c\uc544 \ud3f0 \ud558\ub974\ubd80",
        "life": "1888\u20131954", "slug": "harbou",
        "note": "\u300e\uba54\ud2b8\ub85c\ud3f4\ub9ac\uc2a4\u300f\uc758 \uc18c\uc124\uac00\uc774\uc790 \uac01\ubcf8\uac00.",
    },
    "블랙우드": {
        "en": "Algernon Blackwood", "ko": "앨저넌 블랙우드",
        "life": "1869–1951", "slug": "blackwood",
        "note": "숲과 눈과 바람 속에서 사람보다 큰 것을 느낀 괴기소설가. 러브크래프트가 스승으로 꼽은 사람.",
    },
    "체임버스": {
        "en": "Robert W. Chambers", "ko": "로버트 W. 체임버스",
        "life": "1865–1933", "slug": "chambers",
        "note": "『노란 옷의 왕』으로 코즈믹 호러의 문을 연 뒤, 당대 가장 잘 팔리는 대중소설가가 된 사람.",
    },
    "마켄": {
        "en": "Arthur Machen", "ko": "아서 마켄",
        "life": "1863–1947", "slug": "machen",
        "note": "웨일스 언덕의 옛 신들을 불러낸 신비주의자. 괴기소설을 경이의 문학으로 쓴 사람.",
    },
    "안드레예프": {
        "en": "Leonid Andreyev", "ko": "레오니트 안드레예프",
        "life": "1871–1919", "slug": "andreyev",
        "note": "톨스토이 다음가는 재능이라 불린 러시아 작가. 죽음 앞의 인간을 끝까지 들여다본 사람.",
    },
    "제이컵스": {
        "en": "W. W. Jacobs", "ko": "W. W. 제이컵스",
        "life": "1863–1943", "slug": "jacobs",
        "note": "템스강 부두의 익살꾼. 단 한 편의 괴담으로 세 가지 소원의 공포를 영원히 남긴 사람.",
    },
    "유메노": {
        "en": "Yumeno Kyūsaku", "ko": "유메노 규사쿠", "orig": "ja",
        "life": "1889–1936", "slug": "yumeno",
        "note": "『도구라 마구라』의 작가. 편지와 독백으로 광기를 받아 적은 일본 환상문학의 괴물.",
    },
    "아쿠타가와": {
        "en": "Akutagawa Ryūnosuke", "ko": "아쿠타가와 류노스케", "orig": "ja",
        "life": "1892–1927", "slug": "akutagawa",
        "note": "옛이야기를 근대의 칼로 다시 벼린 단편의 명인. 서른다섯에 스스로 떠났다.",
    },
}

KO_TITLES = {
    # Kafka
    "The Metamorphosis": ("\ubcc0\uc2e0", "Die Verwandlung"),
    "The Trial": ("\uc18c\uc1a1", "Der Proze\u00df"),
    "The Castle": ("\uc131", "Das Schlo\u00df"),
    "The Knock at the Manor Gate": ("\uc800\ud0dd \ub300\ubb38\uc744 \ub450\ub4dc\ub9ac\ub2e4", "Der Schlag ans Hoftor"),
    "Give It Up": ("\ub2e8\ub150\ud574\ub77c!", "Gibs auf!"),
    "Poseidon": ("\ud3ec\uc138\uc774\ub3c8", "Poseidon"),
    "The Helmsman": ("\ud0a4\uc7a1\uc774", "Der Steuermann"),
    # Wells
    "The Time Machine": ("\ud0c0\uc784\uba38\uc2e0", ""),
    "The Wonderful Visit": ("\ub180\ub77c\uc6b4 \ubc29\ubb38", ""),
    "Select Conversations with an Uncle": ("\uc0bc\ucd0c\uacfc \ub098\ub208 \ub300\ud654 \uba87 \ud1a0\ub9c9", ""),
    "The Stolen Bacillus and Other Incidents": ("\ub3c4\ub09c\ub2f9\ud55c \uc138\uade0 \uc678", ""),
    "The Island of Doctor Moreau": ("\ubaa8\ub85c \ubc15\uc0ac\uc758 \uc12c", ""),
    "The Wheels of Chance": ("\uc6b0\uc5f0\uc758 \uc218\ub808\ubc14\ud034", ""),
    "The Red Room": ("\ubd89\uc740 \ubc29", ""),
    "The Invisible Man": ("\ud22c\uba85\uc778\uac04", ""),
    "The Plattner Story and Others": ("\ud50c\ub798\ud2b8\ub108 \uc774\uc57c\uae30 \uc678", ""),
    "Thirty Strange Stories": ("\uae30\ubb18\ud55c \uc774\uc57c\uae30 \uc11c\ub978 \ud3b8", ""),
    "The Star": ("\ubcc4", ""),
    "The War of the Worlds": ("\uc6b0\uc8fc \uc804\uc7c1", ""),
    "When the Sleeper Wakes": ("\uc7a0\uc790\ub294 \uc790\uac00 \uae68\uc5b4\ub0a0 \ub54c", ""),
    "Tales of Space and Time": ("\uacf5\uac04\uacfc \uc2dc\uac04\uc758 \uc774\uc57c\uae30", ""),
    "Love and Mr Lewisham": ("\uc0ac\ub791\uacfc \ub8e8\uc774\uc164 \uc528", ""),
    "The First Men in the Moon": ("\ub2ec \uc138\uacc4 \ucd5c\ucd08\uc758 \uc778\uac04", ""),
    "The Sea Lady": ("\ubc14\ub2e4 \uc544\uac00\uc528", ""),
    "Twelve Stories and a Dream": ("\uc5f4\ub450 \ud3b8\uc758 \uc774\uc57c\uae30\uc640 \uafc8 \ud558\ub098", ""),
    "The Food of the Gods": ("\uc2e0\ub4e4\uc758 \uc591\uc2dd", ""),
    "A Modern Utopia": ("\ud604\ub300\uc758 \uc720\ud1a0\ud53c\uc544", ""),
    "Kipps": ("\ud0b5\uc2a4", ""),
    "In the Days of the Comet": ("\ud61c\uc131\uc758 \ub0a0\ub4e4", ""),
    "The War in the Air": ("\uacf5\uc911\uc804", ""),
    "Tono-Bungay": ("\ud1a0\ub178\ubc88\uac8c\uc774", ""),
    "Ann Veronica": ("\uc564 \ubca0\ub85c\ub2c8\uce74", ""),
    "The History of Mr Polly": ("\ud3f4\ub9ac \uc528\uc758 \uc77c\ub300\uae30", ""),
    "The Sleeper Awakes": ("\uc7a0\ub4e0 \uc790 \uae68\uc5b4\ub098\ub2e4", ""),
    "The Country of the Blind and Other Stories": ("\ub208\uba3c \uc790\ub4e4\uc758 \ub098\ub77c \uc678", ""),
    "The Door in the Wall and Other Stories": ("\ub2f4\uc7a5 \uc18d\uc758 \ubb38 \uc678", ""),
    "The New Machiavelli": ("\uc0c8\ub85c\uc6b4 \ub9c8\ud0a4\uc544\ubca8\ub9ac", ""),
    "Marriage": ("\uacb0\ud63c", ""),
    "The Passionate Friends": ("\uc5f4\uc815\uc801\uc778 \uce5c\uad6c\ub4e4", ""),
    "The World Set Free": ("\ud574\ubc29\ub41c \uc138\uacc4", ""),
    "The Wife of Sir Isaac Harman": ("\uc544\uc774\uc791 \ud558\uba3c \uacbd\uc758 \uc544\ub0b4", ""),
    "Bealby": ("\ube4c\ube44", ""),
    "Boon": ("\ubd84", ""),
    "The Research Magnificent": ("\uc704\ub300\ud55c \ud0d0\uad6c", ""),
    "Mr Britling Sees It Through": ("\ube0c\ub9ac\ud2c0\ub9c1 \uc528, \ub05d\uae4c\uc9c0 \uc9c0\ucf1c\ubcf4\ub2e4", ""),
    "The Soul of a Bishop": ("\uc8fc\uad50\uc758 \uc601\ud63c", ""),
    "Joan and Peter": ("\uc870\uc564\uacfc \ud53c\ud130", ""),
    "The Undying Fire": ("\uaebc\uc9c0\uc9c0 \uc54a\ub294 \ubd88", ""),
    "The Secret Places of the Heart": ("\ub9c8\uc74c\uc758 \uc740\ubc00\ud55c \uacf3", ""),
    "Tales of the Unexpected": ("\ub73b\ubc16\uc758 \uc774\uc57c\uae30\ub4e4", ""),
    "The Dream": ("\uafc8", ""),
    "Christina Albertas Father": ("\ud06c\ub9ac\uc2a4\ud2f0\ub098 \uc568\ubc84\ud0c0\uc758 \uc544\ubc84\uc9c0", ""),
    # Fitzgerald
    "This Side of Paradise": ("\ub099\uc6d0\uc758 \uc774\ucabd", ""),
    "Flappers and Philosophers": ("\ub9d0\uad04\ub7c9\uc774\uc640 \ucca0\ud559\uc790\ub4e4", ""),
    "Tales of the Jazz Age": ("\uc7ac\uc988 \uc2dc\ub300\uc758 \uc774\uc57c\uae30\ub4e4", ""),
    "The Beautiful and Damned": ("\uc544\ub984\ub2f5\uace0 \uc800\uc8fc\ubc1b\uc740 \uc0ac\ub78c\ub4e4", ""),
    "The Vegetable": ("\ucc44\uc18c \u2014 \ub300\ud1b5\ub839\uc5d0\uc11c \uc9d1\ubc30\uc6d0\uc73c\ub85c", ""),
    "The Great Gatsby": ("\uc704\ub300\ud55c \uac1c\uce20\ube44", ""),
    "All the Sad Young Men": ("\ubaa8\ub4e0 \uc2ac\ud508 \uc80a\uc740\uc774\ub4e4", ""),
    # Harbou
    "Metropolis": ("\uba54\ud2b8\ub85c\ud3f4\ub9ac\uc2a4", "Metropolis"),
    # Blackwood
    "The Empty House and Other Ghost Stories": ("빈집 외 유령 이야기", ""),
    "The Willows": ("버드나무", ""),
    "John Silence, Physician Extraordinary": ("특별한 의사 존 사일런스", ""),
    "The Wendigo": ("웬디고", ""),
    # Chambers
    "The King in Yellow": ("노란 옷의 왕", ""),
    "The Mystery of Choice": ("선택의 수수께끼", ""),
    "Cardigan": ("카디건", ""),
    "In Search of the Unknown": ("미지를 찾아서", ""),
    "The Slayer of Souls": ("영혼을 죽이는 자", ""),
    # Machen
    "The White People": ("백색 사람들", ""),
    # Andreyev — Herman Bernstein's authorised translation, 1909
    "The Seven Who Were Hanged": ("사형수 7인", "Рассказ о семи повешенных"),
    # Jacobs
    "The Monkey's Paw": ("원숭이 손", ""),
    # Japanese originals (Aozora Bunko), keyed by the romanised file title
    "Shojo Jigoku": ("소녀 지옥", "少女地獄"),
    "Akuma Kitosho": ("악마 기도서", "悪魔祈祷書"),
    "Masayume": ("정몽", "正夢"),
    "Rashomon": ("라쇼몽", "羅生門"),
    "Jigokuhen": ("지옥변", "地獄変"),
    "Yabu no Naka": ("덤불 속", "藪の中"),
    "The Centaur": ("켄타우로스", ""),
}

# 장르 — 서재의 '장르' 필터. 한 작품에 하나. 이름은 GENRE_KO, 차례도 그 순서.
GENRE_KO = {
    "sf": "SF·과학 공상", "weird": "괴기·초자연", "fable": "환상·우화", "mystery": "추리·범죄",
    "society": "사회·풍속", "romance": "연애", "comic": "유머·풍자", "history": "역사·모험",
    "ideas": "사상·유토피아",
}
GENRE = {
    "akutagawa-rashomon": "history", "akutagawa-jigokuhen": "history",
    "akutagawa-yabu-no-naka": "mystery",
    "andreyev-the-seven-who-were-hanged": "society",
    "blackwood-the-empty-house-and-other-ghost-stories": "weird", "blackwood-the-willows": "weird",
    "blackwood-john-silence-physician-extraordinary": "weird", "blackwood-the-wendigo": "weird",
    "blackwood-the-centaur": "fable",
    "chambers-the-king-in-yellow": "weird", "chambers-the-mystery-of-choice": "romance",
    "chambers-cardigan": "history", "chambers-in-search-of-the-unknown": "comic",
    "chambers-the-slayer-of-souls": "weird",
    "fitzgerald-flappers-and-philosophers": "society",
    "fitzgerald-this-side-of-paradise": "society",
    "fitzgerald-tales-of-the-jazz-age": "society",
    "fitzgerald-the-beautiful-and-damned": "society", "fitzgerald-the-vegetable": "comic",
    "fitzgerald-the-great-gatsby": "society", "fitzgerald-all-the-sad-young-men": "society",
    "harbou-metropolis": "sf",
    "jacobs-the-monkey-s-paw": "weird",
    "kafka-the-metamorphosis": "fable", "kafka-the-trial": "fable", "kafka-the-castle": "fable",
    "kafka-the-knock-at-the-manor-gate": "fable", "kafka-give-it-up": "fable",
    "kafka-poseidon": "fable", "kafka-the-helmsman": "fable",
    "machen-the-white-people": "weird",
    "wells-select-conversations-with-an-uncle": "comic",
    "wells-the-stolen-bacillus-and-other-incidents": "sf",
    "wells-the-time-machine": "sf", "wells-the-wonderful-visit": "fable",
    "wells-the-island-of-doctor-moreau": "sf", "wells-the-red-room": "weird",
    "wells-the-wheels-of-chance": "comic", "wells-the-invisible-man": "sf",
    "wells-the-plattner-story-and-others": "sf", "wells-the-star": "sf",
    "wells-thirty-strange-stories": "sf", "wells-the-war-of-the-worlds": "sf",
    "wells-tales-of-space-and-time": "sf", "wells-when-the-sleeper-wakes": "sf",
    "wells-love-and-mr-lewisham": "romance", "wells-the-first-men-in-the-moon": "sf",
    "wells-the-sea-lady": "fable", "wells-twelve-stories-and-a-dream": "sf",
    "wells-the-food-of-the-gods": "sf", "wells-a-modern-utopia": "ideas",
    "wells-kipps": "comic", "wells-in-the-days-of-the-comet": "sf",
    "wells-the-war-in-the-air": "sf", "wells-ann-veronica": "society",
    "wells-tono-bungay": "society", "wells-the-history-of-mr-polly": "comic",
    "wells-the-sleeper-awakes": "sf", "wells-the-country-of-the-blind-and-other-stories": "sf",
    "wells-the-door-in-the-wall-and-other-stories": "fable",
    "wells-the-new-machiavelli": "society", "wells-marriage": "romance",
    "wells-the-passionate-friends": "romance",
    "wells-the-wife-of-sir-isaac-harman": "society", "wells-the-world-set-free": "sf",
    "wells-bealby": "comic", "wells-boon": "comic",
    "wells-the-research-magnificent": "ideas", "wells-mr-britling-sees-it-through": "society",
    "wells-the-soul-of-a-bishop": "ideas", "wells-joan-and-peter": "society",
    "wells-the-undying-fire": "ideas", "wells-tales-of-the-unexpected": "weird",
    "wells-the-secret-places-of-the-heart": "romance", "wells-the-dream": "society",
    "wells-christina-albertas-father": "society",
    "yumeno-masayume": "weird", "yumeno-shojo-jigoku": "mystery",
    "yumeno-akuma-kitosho": "weird",
}

FORM = {
    "Thirty Strange Stories": "collection",
    "Tales of Space and Time": "collection",
    "The Stolen Bacillus and Other Incidents": "collection",
    "The Plattner Story and Others": "collection",
    "The Country of the Blind and Other Stories": "collection",
    "The Door in the Wall and Other Stories": "collection",
    "Twelve Stories and a Dream": "collection",
    "Tales of the Unexpected": "collection",
    "Select Conversations with an Uncle": "collection",
    "Tales of the Jazz Age": "collection",
    "Flappers and Philosophers": "collection",
    "All the Sad Young Men": "collection",
    "The Vegetable": "play",
    "Boon": "miscellany",
    "A Modern Utopia": "essay-novel",
    "The Red Room": "story",
    "The Star": "story",
    "The Knock at the Manor Gate": "story",
    "Give It Up": "story",
    "Poseidon": "story",
    "The Helmsman": "story",
    "The Metamorphosis": "novella",
    "The Empty House and Other Ghost Stories": "collection",
    "John Silence, Physician Extraordinary": "collection",
    "The Willows": "novella",
    "The Wendigo": "novella",
    "The King in Yellow": "collection",
    "The Mystery of Choice": "collection",
    "The White People": "novella",
    "The Seven Who Were Hanged": "novella",
    "The Monkey's Paw": "story",
    "Shojo Jigoku": "collection",
    "Akuma Kitosho": "story",
    "Masayume": "story",
    "Rashomon": "story",
    "Jigokuhen": "story",
    "Yabu no Naka": "story",
}

WPM = 240   # words per minute, unhurried literary reading


def build():
    out = {"authors": [], "works": []}
    for folder in ["\uce74\ud504\uce74", "HG\uc6f0\uc2a4", "\ud53c\uce20\uc81c\ub7f4\ub4dc", "\ud14c\uc544\ud3f0\ud558\ub974\ubd80", "블랙우드", "체임버스", "마켄", "안드레예프", "제이컵스", "유메노", "아쿠타가와"]:
        d = os.path.join(ROOT, folder)
        a = dict(AUTHORS[folder])
        a["folder"] = folder
        out["authors"].append(a)
        for f in sorted(os.listdir(d)):
            if not f.endswith(".txt") or f.startswith("00_"):
                continue
            year, title = f[:-4].split("_", 1)
            t = io.open(os.path.join(d, f), encoding="utf-8").read()
            words = len(re.findall(r"[A-Za-z\u2019'\u2010-\u2015]+", t))
            ko, orig = KO_TITLES.get(title, (title, ""))
            ja = a.get("orig") == "ja"
            slug_src = title
            if ja:
                # Japanese: the shelf shows the Japanese title; the id stays romanised.
                # No words to count, so 2.5 characters stand in for an English word
                # and pages and reading time come out on the same scale.
                import aozora
                body = re.sub(r"<rt>.*?</rt>|<[^>]+>", "", aozora.parse(os.path.join(d, f))["html"])
                t, words = body, int(len(body) / 2.5)
                title, orig = orig or title, title
            out["works"].append({
                "id": "%s-%s" % (a["slug"], re.sub(r"[^a-z0-9]+", "-", slug_src.lower()).strip("-")),
                "file": folder + "/" + f,
                "author": a["slug"], "authorKo": a["ko"], "authorEn": a["en"],
                "year": int(year), "title": title, "titleKo": ko, "titleOrig": orig,
                "chars": len(t), "words": words,
                "minutes": int(round(words / float(WPM))),
                "form": FORM.get(slug_src, "novel"),
                "orig": a.get("orig", "en"),
            })
    out["works"].sort(key=lambda w: (w["author"], w["year"], w["title"]))
    for w in out["works"]:
        w["genre"] = GENRE.get(w["id"], "")
        if not w["genre"]:
            print("meta: 장르 없음 — GENRE 에 넣을 것:", w["id"])
    return out


if __name__ == "__main__":
    data = build()
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))
    print("works:", len(data["works"]))
    tw = sum(w["words"] for w in data["works"])
    print("total words: {:,}  ~{:,} hours at {} wpm".format(tw, tw // (WPM * 60), WPM))
    for w in data["works"]:
        print("  %-11s %d  %-46s %-24s %8s w  %4dm  %s" % (
            w["author"], w["year"], w["title"][:46], w["titleKo"][:22],
            "{:,}".format(w["words"]), w["minutes"], w["form"]))
