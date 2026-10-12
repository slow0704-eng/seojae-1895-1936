# -*- coding: utf-8 -*-
"""Ship a Korean serif with the library: 서재/fonts/*.woff2.

Stock Windows has exactly one 명조 — Batang, drawn and hinted for low-res
screens, so at reading sizes it steps and looks jagged. This subsets Noto
Serif KR (SIL OFL 1.1) down to what the Korean edition can need:

  * all 2,350 KS X 1001 syllables + compatibility jamo + CJK punctuation, so
    a fresh translation almost never meets a missing glyph, and
  * every character actually present in 서재/data/ko/*.js, for the rare rest.

The big source OTFs live in tools/fonts/src/ (git-ignored, ~7.6 MB each):
  https://github.com/notofonts/noto-cjk/tree/main/Serif/SubsetOTF/KR
Without them this step is skipped and the committed woff2 stay as they are;
verify.py tells you if a translation has outgrown them.
"""
from __future__ import annotations
import os as _os
import glob, io, shutil

HERE = _os.path.dirname(_os.path.abspath(__file__))
ROOT = _os.path.dirname(HERE)
SITE = _os.path.join(ROOT, chr(49436) + chr(51116))    # 서재
SRC = _os.path.join(HERE, "fonts", "src")
OUT = _os.path.join(SITE, "fonts")
FACES = {"Regular": "NotoSerifKR-Regular", "SemiBold": "NotoSerifKR-SemiBold"}


def ks_x_1001():
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes([hi, lo]).decode("euc-kr"))
            except UnicodeDecodeError:
                pass
    return "".join(out)


def used_chars():
    s = set()
    for p in glob.glob(_os.path.join(SITE, "data", "ko", "*.js")):
        s.update(io.open(p, encoding="utf-8").read())
    return s


def wanted():
    base = set(ks_x_1001())
    base.update(chr(c) for c in range(0x3131, 0x318F))    # compatibility jamo
    base.update(chr(c) for c in range(0x3000, 0x3040))    # CJK punctuation
    base.update(chr(c) for c in range(0x20, 0x7F))         # so spacing stays in-face
    base.update("·‘’“”…—–")
    return base | {c for c in used_chars() if ord(c) > 0x7F}


def build():
    if not all(_os.path.exists(_os.path.join(SRC, f + ".otf")) for f in FACES.values()):
        print("fonts: source OTFs not in tools/fonts/src — keeping committed woff2")
        return
    from fontTools import subset
    _os.makedirs(OUT, exist_ok=True)
    text = "".join(sorted(wanted()))
    for name in FACES.values():
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "palt", "vkrn", "locl"]
        opts.name_IDs = ["*"]           # keep the licence and copyright records
        opts.hinting = False            # outlines only: the renderer smooths them
        opts.desubroutinize = True
        font = subset.load_font(_os.path.join(SRC, name + ".otf"), opts)
        sub = subset.Subsetter(opts)
        sub.populate(text=text)
        sub.subset(font)
        dst = _os.path.join(OUT, name + ".woff2")
        subset.save_font(font, dst, opts)
        print("fonts: %-24s %s bytes" % (name + ".woff2", "{:,}".format(_os.path.getsize(dst))))
    lic = _os.path.join(SRC, "OFL.txt")
    if _os.path.exists(lic):
        shutil.copy(lic, _os.path.join(OUT, "OFL.txt"))


def missing():
    """Characters in the Korean edition that the shipped font cannot draw
    but the source family can — i.e. the subset needs rebuilding."""
    from fontTools.ttLib import TTFont
    p = _os.path.join(OUT, FACES["Regular"] + ".woff2")
    if not _os.path.exists(p):
        return None
    have = set(TTFont(p).getBestCmap())
    return sorted(c for c in used_chars()
                  if 0xAC00 <= ord(c) <= 0xD7A3 and ord(c) not in have)


def serif_advances():
    """Advance widths (em) of the shipped Source Serif 4 for the cover title
    settings — upper case, small caps, roman, italic — so jacket.py can size a
    title by its widest word without a browser. Writes tools/serif_adv.json;
    rerun only if the Source Serif woff2 change."""
    import json
    from fontTools.ttLib import TTFont
    chars = [chr(c) for c in range(0x20, 0x7F)] + list("ÀÁÂÄÇÈÉÊËÍÎÏÑÓÔÖÚÛÜàáâäçèéêëíîïñóôöúûüŌōŪū’‘“”—–")
    out = {}
    for face, key in (("Roman", "R"), ("Italic", "I")):
        f = TTFont(_os.path.join(OUT, "SourceSerif4-%s.woff2" % face))
        cmap, hm, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
        smcp = {}
        for fr in f["GSUB"].table.FeatureList.FeatureRecord:
            if fr.FeatureTag == "smcp":
                for li in fr.Feature.LookupListIndex:
                    for st in f["GSUB"].table.LookupList.Lookup[li].SubTable:
                        st = getattr(st, "ExtSubTable", st)
                        smcp.update(getattr(st, "mapping", {}) or {})
        def adv(c, sc=False):
            g = cmap.get(ord(c))
            if g is None:
                return None
            return round(hm[smcp.get(g, g) if sc else g][0] / upm, 3)
        out[key] = {c: adv(c) for c in chars if adv(c) is not None}
        if key == "R":
            out["SC"] = {c: adv(c, True) for c in chars if adv(c) is not None}
    with io.open(_os.path.join(HERE, "serif_adv.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


if __name__ == "__main__":
    import sys
    serif_advances() if sys.argv[1:] == ["adv"] else build()
