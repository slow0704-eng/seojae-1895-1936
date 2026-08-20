# -*- coding: utf-8 -*-
import os, re, io, json, zipfile, time, urllib.request, urllib.parse

DEST = "C:/Users/user/" + chr(49548) + chr(49444) + "/" + chr(52852) + chr(54532) + chr(52852)
UA = {"User-Agent": "KafkaTextArchive/1.0 (personal offline reading)"}


def get(url, tries=4):
    last = None
    for _ in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        except Exception as e:
            last = e
            time.sleep(5)
    raise last


TAGSTRIP = re.compile(r"<[^>]+>")
BLOCK = re.compile(r"</(p|div|h[1-6]|li|blockquote|section)\s*>", re.I)
BR = re.compile(r"<br\s*/?>", re.I)
SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)


def html2text(h):
    h = SCRIPT.sub("", h)
    h = BR.sub("\n", h)
    h = BLOCK.sub("\n\n", h)
    t = TAGSTRIP.sub("", h)
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&mdash;", "\u2014"), ("&hellip;", "\u2026")]:
        t = t.replace(a, b)
    t = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def write(year, title, body, note):
    path = os.path.join(DEST, "%d_%s.txt" % (year, re.sub(r'[<>:"/\\|?*]', "", title)))
    header = title + "\nFranz Kafka\n\n\n"
    with open(path, "wb") as f:
        f.write((header + body + "\n").encode("utf-8"))
    print("ok   %-40s %8d  %s" % (title, len(body), note))


# ---- 1. The Castle, from Standard Ebooks (Muir translation) ----
try:
    url = ("https://standardebooks.org/ebooks/franz-kafka/the-castle/willa-muir_edwin-muir"
           "/downloads/franz-kafka_the-castle_willa-muir-edwin-muir.epub")
    z = zipfile.ZipFile(io.BytesIO(get(url)))
    opf = [n for n in z.namelist() if n.endswith(".opf")][0]
    opf_txt = z.read(opf).decode("utf-8")
    base = os.path.dirname(opf)
    ids = dict(re.findall(r'<item\b[^>]*id="([^"]+)"[^>]*href="([^"]+)"', opf_txt))
    ids.update({i: h for h, i in re.findall(r'<item\b[^>]*href="([^"]+)"[^>]*id="([^"]+)"', opf_txt)})
    order = re.findall(r'<itemref[^>]*idref="([^"]+)"', opf_txt)
    parts = []
    for ref in order:
        href = ids.get(ref)
        if not href:
            continue
        name = (base + "/" + href) if base else href
        name = os.path.normpath(name).replace("\\", "/")
        if name not in z.namelist():
            continue
        low = href.lower()
        if any(k in low for k in ("titlepage", "imprint", "colophon", "uncopyright", "halftitle", "loi.")):
            continue
        parts.append(html2text(z.read(name).decode("utf-8", "replace")))
    body = ("\n\n\n" + "-" * 60 + "\n\n\n").join(p for p in parts if len(p) > 200)
    if len(body) < 50000:
        raise ValueError("too short %d" % len(body))
    write(1926, "The Castle", body, "%d sections (Muir trans., Standard Ebooks)" % len(parts))
except Exception as e:
    print("FAIL The Castle", repr(e)[:150])

# ---- 2. remaining Wikisource original translations ----
API = "https://en.wikisource.org/w/api.php"
WS = [("Translation:Poseidon (Kafka)", 1936, "Poseidon")]
for page, year, title in WS:
    try:
        u = API + "?" + urllib.parse.urlencode({"action": "parse", "page": page,
                                                "prop": "text", "format": "json", "formatversion": "2"})
        d = json.loads(get(u).decode("utf-8"))
        if "error" in d:
            raise ValueError(d["error"]["code"])
        body = html2text(d["parse"]["text"])
        body = re.split(r"\nThis work is|\nRetrieved from", body)[0].strip()
        if len(body) < 200:
            raise ValueError("short %d" % len(body))
        write(year, title, body, "Wikisource translation")
        time.sleep(3)
    except Exception as e:
        print("FAIL", title, repr(e)[:120])
