# -*- coding: utf-8 -*-
import os, re, json, time, urllib.request, urllib.parse

ROOT = "C:/Users/user/" + chr(49548) + chr(49444)
DEST = os.path.join(ROOT, chr(52852) + chr(54532) + chr(52852))   # 카프카
API = "https://en.wikisource.org/w/api.php"

# (wikisource page title, first-publication year, output title)
WORKS = [
    ("The Castle (Kafka)", 1926, "The Castle"),
    ("Amerika", 1927, "Amerika (The Man Who Disappeared)"),

    # Betrachtung / Contemplation (1912)
    ("Children on a Country Road", 1912, "Children on a Country Road"),
    ("Unmasking a Confidence Trickster", 1912, "Unmasking a Confidence Trickster"),
    ("The Sudden Walk", 1912, "The Sudden Walk"),
    ("Resolutions", 1912, "Resolutions"),
    ("Excursion into the Mountains", 1912, "Excursion into the Mountains"),
    ("Bachelor's Ill Luck", 1912, "Bachelors Ill Luck"),
    ("The Tradesman", 1912, "The Tradesman"),
    ("Absent-minded Window-gazing", 1912, "Absent-minded Window-gazing"),
    ("Home-Coming (Kafka)", 1912, "Home-Coming"),
    ("Passers-by (Kafka)", 1912, "Passers-by"),
    ("On the Tram", 1912, "On the Tram"),
    ("Clothes", 1912, "Clothes"),
    ("Rejection", 1912, "Rejection"),
    ("Reflections for Gentlemen-Jockeys", 1912, "Reflections for Gentlemen-Jockeys"),
    ("The Street Window", 1912, "The Street Window"),
    ("The Trees", 1912, "The Trees"),
    ("Translation:Unhappiness", 1912, "Unhappiness"),

    ("The Judgement", 1913, "The Judgement"),
    ("In the Penal Colony", 1919, "In the Penal Colony"),

    # Ein Landarzt / A Country Doctor (1919)
    ("The New Advocate", 1919, "The New Advocate"),
    ("A Country Doctor", 1919, "A Country Doctor"),
    ("Up in the Gallery", 1919, "Up in the Gallery"),
    ("An Old Manuscript", 1919, "An Old Manuscript"),
    ("Before the Law", 1919, "Before the Law"),
    ("Jackals and Arabs", 1919, "Jackals and Arabs"),
    ("A Visit to a Mine", 1919, "A Visit to a Mine"),
    ("The Next Village", 1919, "The Next Village"),
    ("An Imperial Message", 1919, "An Imperial Message"),
    ("The Cares of a Family Man", 1919, "The Cares of a Family Man"),
    ("Eleven Sons", 1919, "Eleven Sons"),
    ("A Fratricide", 1919, "A Fratricide"),
    ("A Dream (Kafka)", 1919, "A Dream"),
    ("A Report to an Academy", 1919, "A Report to an Academy"),

    # Ein Hungerkuenstler / A Hunger Artist (1924)
    ("First Sorrow", 1924, "First Sorrow"),
    ("A Little Woman", 1924, "A Little Woman"),
    ("A Hunger Artist", 1924, "A Hunger Artist"),
    ("Josephine the Singer, or the Mouse Folk", 1924, "Josephine the Singer or the Mouse Folk"),

    # posthumous (Beim Bau der Chinesischen Mauer, 1931 and later)
    ("Description of a Struggle", 1936, "Description of a Struggle"),
    ("The Great Wall of China", 1931, "The Great Wall of China"),
    ("Blumfeld, an Elderly Bachelor", 1936, "Blumfeld an Elderly Bachelor"),
    ("The Burrow", 1931, "The Burrow"),
    ("Investigations of a Dog", 1931, "Investigations of a Dog"),
    ("The Hunter Gracchus", 1931, "The Hunter Gracchus"),
    ("The Village Schoolmaster", 1931, "The Village Schoolmaster"),
    ("The Warden of the Tomb", 1936, "The Warden of the Tomb"),
    ("The Married Couple", 1931, "The Married Couple"),
    ("A Little Fable", 1931, "A Little Fable"),
    ("Advocates", 1936, "Advocates"),
    ("At Night (Kafka)", 1931, "At Night"),
    ("The Bridge (Kafka)", 1931, "The Bridge"),
    ("The Bucket Rider", 1931, "The Bucket Rider"),
    ("The City Coat of Arms", 1931, "The City Coat of Arms"),
    ("A Common Confusion", 1931, "A Common Confusion"),
    ("The Conscription of Troops", 1936, "The Conscription of Troops"),
    ("A Crossbreed", 1931, "A Crossbreed"),
    ("The Departure (Kafka)", 1936, "The Departure"),
    ("Fellowship", 1931, "Fellowship"),
    ("Translation:Give It Up!", 1936, "Give It Up"),
    ("Translation:The Helmsman", 1936, "The Helmsman"),
    ("Translation:The Knock at the Manor Gate", 1931, "The Knock at the Manor Gate"),
    ("My Neighbor", 1931, "My Neighbor"),
    ("On Parables", 1931, "On Parables"),
    ("Translation:Poseidon (Kafka)", 1936, "Poseidon"),
    ("The Problem of Our Laws", 1931, "The Problem of Our Laws"),
    ("Prometheus (Kafka)", 1931, "Prometheus"),
    ("The Refusal", 1936, "The Refusal"),
    ("The Silence of the Sirens", 1931, "The Silence of the Sirens"),
    ("The Test (Kafka)", 1936, "The Test"),
    ("The Top", 1936, "The Top"),
    ("The Truth About Sancho Panza", 1931, "The Truth About Sancho Panza"),
    ("The Vulture (Kafka)", 1936, "The Vulture"),
]


def api(params):
    params["format"] = "json"
    params["formatversion"] = "2"
    url = API + "?" + urllib.parse.urlencode(params)
    for _ in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kafka-txt/1.0 (personal archive)"})
            return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
        except Exception:
            time.sleep(2)
    raise RuntimeError("api failed: " + url)


def extract(title):
    d = api({"action": "query", "prop": "extracts", "explaintext": "1",
             "exlimit": "1", "redirects": "1", "titles": title})
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    return pages[0].get("extract", "")


def subpages(title):
    ns = 114 if title.startswith("Translation:") else 0
    base = title.split(":", 1)[1] if ns == 114 else title
    out, cont = [], {}
    while True:
        p = {"action": "query", "list": "allpages", "apnamespace": str(ns),
             "apprefix": base + "/", "aplimit": "500"}
        p.update(cont)
        d = api(p)
        out += [x["title"] for x in d.get("query", {}).get("allpages", [])]
        if "continue" in d:
            cont = d["continue"]
        else:
            break
    return out


def natkey(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def clean(t):
    t = re.sub(r"\r\n?", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


if not os.path.isdir(DEST):
    os.makedirs(DEST)

fails = []
for src, year, out in WORKS:
    path = os.path.join(DEST, "%d_%s.txt" % (year, re.sub(r'[<>:"/\\|?*]', "", out)))
    try:
        subs = subpages(src)
        if subs:
            subs.sort(key=natkey)
            parts = []
            for s in subs:
                body = clean(extract(s) or "")
                if len(body) < 40:
                    continue
                label = s.split("/", 1)[1]
                parts.append(label + "\n\n" + body)
            text = ("\n\n\n" + "-" * 60 + "\n\n\n").join(parts)
            note = "%d chapters" % len(parts)
        else:
            text = clean(extract(src) or "")
            note = "single"
        if len(text) < 150:
            raise ValueError("empty/short (%d chars)" % len(text))
        header = out + "\nFranz Kafka\n\n\n"
        with open(path, "wb") as f:
            f.write((header + text + "\n").encode("utf-8"))
        print("ok   %-45s %8d  %s" % (out, len(text), note))
    except Exception as e:
        print("FAIL %-45s %s" % (out, repr(e)[:100]))
        fails.append((src, out, repr(e)[:100]))

print("\nFAILURES: %d" % len(fails))
for f in fails:
    print(f)
