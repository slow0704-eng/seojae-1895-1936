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
    "The Centaur": ("켄타우로스", ""),
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
}

WPM = 240   # words per minute, unhurried literary reading


def build():
    out = {"authors": [], "works": []}
    for folder in ["\uce74\ud504\uce74", "HG\uc6f0\uc2a4", "\ud53c\uce20\uc81c\ub7f4\ub4dc", "\ud14c\uc544\ud3f0\ud558\ub974\ubd80", "블랙우드"]:
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
            out["works"].append({
                "id": "%s-%s" % (a["slug"], re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")),
                "file": folder + "/" + f,
                "author": a["slug"], "authorKo": a["ko"], "authorEn": a["en"],
                "year": int(year), "title": title, "titleKo": ko, "titleOrig": orig,
                "chars": len(t), "words": words,
                "minutes": int(round(words / float(WPM))),
                "form": FORM.get(title, "novel"),
            })
    out["works"].sort(key=lambda w: (w["author"], w["year"], w["title"]))
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
