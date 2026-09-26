# -*- coding: utf-8 -*-
import os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ONLY = set(sys.argv[1:])   # folder names; empty = all

MANIFEST = {
u"\uce74\ud504\uce74": [
    (5200,  1915, "The Metamorphosis"),
    (7849,  1925, "The Trial"),
],
u"HG\uc6f0\uc2a4": [
    (35,   1895, "The Time Machine"),
    (33913,1895, "The Wonderful Visit"),
    (29472,1895, "Select Conversations with an Uncle"),
    (12750,1895, "The Stolen Bacillus and Other Incidents"),
    (159,  1896, "The Island of Doctor Moreau"),
    (1264, 1896, "The Wheels of Chance"),
    (23218,1896, "The Red Room"),
    (5230, 1897, "The Invisible Man"),
    (42989,1897, "The Plattner Story and Others"),
    (59774,1897, "Thirty Strange Stories"),
    (67071,1897, "The Star"),
    (36,   1898, "The War of the Worlds"),
    (775,  1899, "When the Sleeper Wakes"),
    (27365,1899, "Tales of Space and Time"),
    (11640,1900, "Love and Mr Lewisham"),
    (1013, 1901, "The First Men in the Moon"),
    (35920,1902, "The Sea Lady"),
    (1743, 1903, "Twelve Stories and a Dream"),
    (11696,1904, "The Food of the Gods"),
    (6424, 1905, "A Modern Utopia"),
    (39162,1905, "Kipps"),
    (3797, 1906, "In the Days of the Comet"),
    (780,  1908, "The War in the Air"),
    (718,  1909, "Tono-Bungay"),
    (524,  1909, "Ann Veronica"),
    (7308, 1910, "The History of Mr Polly"),
    (12163,1910, "The Sleeper Awakes"),
    (11870,1911, "The Country of the Blind and Other Stories"),
    (456,  1911, "The Door in the Wall and Other Stories"),
    (1047, 1911, "The New Machiavelli"),
    (35338,1912, "Marriage"),
    (30340,1913, "The Passionate Friends"),
    (1059, 1914, "The World Set Free"),
    (30855,1914, "The Wife of Sir Isaac Harman"),
    (59769,1915, "Bealby"),
    (34962,1915, "Boon"),
    (1138, 1915, "The Research Magnificent"),
    (14060,1916, "Mr Britling Sees It Through"),
    (1269, 1917, "The Soul of a Bishop"),
    (61426,1918, "Joan and Peter"),
    (61547,1919, "The Undying Fire"),
    (1734, 1922, "The Secret Places of the Heart"),
    (66409,1922, "Tales of the Unexpected"),
    (69394,1924, "The Dream"),
    (69410,1925, "Christina Albertas Father"),
],
u"\ud53c\uce20\uc81c\ub7f4\ub4dc": [
    (805,  1920, "This Side of Paradise"),
    (4368, 1920, "Flappers and Philosophers"),
    (9830, 1922, "The Beautiful and Damned"),
    (6695, 1922, "Tales of the Jazz Age"),
    (60962,1923, "The Vegetable"),
    (64317,1925, "The Great Gatsby"),
    (68229,1926, "All the Sad Young Men"),
],
u"\ud14c\uc544\ud3f0\ud558\ub974\ubd80": [
    (73727,1926, "Metropolis"),
],
u"블랙우드": [
    (14471,1906, "The Empty House and Other Ghost Stories"),
    (11438,1907, "The Willows"),
    (49222,1908, "John Silence, Physician Extraordinary"),
    (10897,1910, "The Wendigo"),
    (9964, 1911, "The Centaur"),
],
u"체임버스": [
    (8492, 1895, "The King in Yellow"),
    (46581,1897, "The Mystery of Choice"),
    (38958,1901, "Cardigan"),
    (18668,1904, "In Search of the Unknown"),
    (36281,1920, "The Slayer of Souls"),
],
u"안드레예프": [
    (6722, 1908, "The Seven Who Were Hanged"),
],
u"제이컵스": [
    (12122,1902, "The Monkey's Paw"),
],
}

START = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.I)
END   = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.I)

def fetch(bid):
    urls = ["https://www.gutenberg.org/cache/epub/%d/pg%d.txt" % (bid, bid),
            "https://www.gutenberg.org/ebooks/%d.txt.utf-8" % bid]
    last = None
    for u in urls:
        for attempt in range(3):
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                raw = urllib.request.urlopen(req, timeout=90).read()
                return raw.decode("utf-8", "replace")
            except Exception as e:
                last = e
                time.sleep(2)
    raise last

def strip(txt):
    m = START.search(txt)
    if m: txt = txt[m.end():]
    m = END.search(txt)
    if m: txt = txt[:m.start()]
    txt = re.sub(r"\r\n?", "\n", txt).strip("\n")
    # drop trailing produced-by / transcriber blocks left at head
    return txt + "\n"

fails = []
for folder, items in MANIFEST.items():
    if ONLY and folder not in ONLY: continue
    d = os.path.join(ROOT, folder)
    if not os.path.isdir(d): os.makedirs(d)
    for bid, year, title in items:
        safe = re.sub(r'[<>:"/\|?*]', "", title)
        path = os.path.join(d, "%d_%s.txt" % (year, safe))
        if os.path.exists(path) and os.path.getsize(path) > 3000:
            print("skip", folder, title); continue
        try:
            body = strip(fetch(bid))
            if len(body) < 2000: raise ValueError("too short: %d" % len(body))
            with open(path, "wb") as f:
                f.write(body.encode("utf-8"))
            print("ok  ", folder, year, title, len(body))
        except Exception as e:
            print("FAIL", folder, bid, title, repr(e)[:120])
            fails.append((folder, bid, title, repr(e)[:120]))
print("\nFAILURES:", len(fails))
for f in fails: print(f)
