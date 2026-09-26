#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bookparse.py -- plain-text book -> structured HTML.

Public API
----------
    parse(path) -> {"title","author","year","toc","html","stats"}

Emitted vocabulary (and nothing else):
    <h1 class="worktitle"> <h2 class="part"> <h2 class="chapter"> <h3 class="subhead">
    <p> <p class="noindent"> <blockquote> <p class="verse"> <hr class="scene">
    <em> <span class="smallcaps"> <div class="letter">

Python 3, stdlib only.
"""

from __future__ import annotations

import html as _html
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

PARSER_VERSION = "1.0.0"

# --------------------------------------------------------------------------
# 0. character-level constants
# --------------------------------------------------------------------------

WJ = "⁠"          # WORD JOINER      (Standard Ebooks; must survive verbatim)
HAIRSP = " "      # HAIR SPACE       (Standard Ebooks; must survive verbatim)
NBSP = " "
INVISIBLES = WJ + HAIRSP + NBSP + "​‌‍﻿"

ROMAN = r"(?=[MDCLXVI])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"

ORDINAL_WORDS = """first second third fourth fifth sixth seventh eighth ninth tenth
eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth
nineteenth twentieth twenty-first twenty-second twenty-third twenty-fourth
twenty-fifth twenty-sixth twenty-seventh twenty-eighth twenty-ninth thirtieth
thirty-first thirty-second thirty-third thirty-fourth thirty-fifth last""".split()

CARDINAL_WORDS = """one two three four five six seven eight nine ten eleven twelve
thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty
forty fifty""".split()

NUMWORD = "(?:%s)" % "|".join(
    sorted(ORDINAL_WORDS + CARDINAL_WORDS, key=len, reverse=True)
)

NAMED_DIVISIONS = {
    "preface", "prologue", "epilogue", "introduction", "interlude", "foreword",
    "afterword", "envoy", "envoi", "postscript", "appendix", "conclusion",
    "the epilogue", "the end of the story", "proem", "dedication",
}

# --------------------------------------------------------------------------
# 1. junk / boilerplate recognisers
# --------------------------------------------------------------------------

DROP_LINE_RX = [
    re.compile(r"^\s*</?pre\b[^>]*>\s*$", re.I),   # incl. <pre id="pg-footer">
    re.compile(r"^\s*/\s*$"),
    re.compile(r"^\s*\[?Illustration\b", re.I),
    re.compile(r"^\s*\[?Device\]?\s*$", re.I),
    re.compile(r"^\s*Produced by\b", re.I),
    re.compile(r"^\s*(?:\[)?Transcriber.?s?\s+note", re.I),
    re.compile(r"^\s*End of (?:the )?Project Gutenberg", re.I),
    re.compile(r"^\s*\*\*\*\s*(?:START|END) OF TH", re.I),
    re.compile(r"^\s*\+[-+]{5,}\+\s*$"),                      # ascii box rule
    re.compile(r"^\s*\|.{0,80}\|\s*$"),                        # ascii box row
    re.compile(r"^\s*\|=+\|\s*$"),
]

# blocks that are front-matter apparatus and get dropped outright
FRONT_DROP_RX = [
    re.compile(r"^\s*(?:A\s+)?(?:TABLE\s+OF\s+)?CONTENTS?\.?\s*$", re.I),
    re.compile(r"^\s*LIST OF ILLUSTRATIONS\.?\s*$", re.I),
    re.compile(r"^\s*(?:BY THE SAME AUTHOR|By the Same Author)\b", re.I),
    re.compile(r"^\s*(?:Mr\.?\s+)?WELLS has also written\b", re.I),
    re.compile(r"^\s*Mr\.? Wells has also written\b", re.I),
    re.compile(r"^\s*Books by\b", re.I),
    re.compile(r"^\s*(?:The )?following (?:fantastic|novels|books)\b", re.I),
    re.compile(r"^\s*Numerous short stories collected\b", re.I),
    re.compile(r"^\s*A [Ss]eries of [Bb]ooks\b"),
    re.compile(r"^\s*COPYRIGHT[,.]?\s", re.I),
    re.compile(r"^\s*Copyright\s+(?:19|18)\d\d\b"),
    re.compile(r"^\s*_?All rights reserved_?\.?\s*$", re.I),
    re.compile(r"^\s*Printed in the United States", re.I),
    re.compile(r"^\s*Published\s+[A-Z][a-z]+,?\s*(?:19|18)\d\d", re.I),
    re.compile(r"^\s*_?Published\s+[A-Z][a-z]+,?\s*(?:19|18)\d\d_?", re.I),
    re.compile(r"^\s*_?Colonial Library_?\s*$", re.I),
    re.compile(r"^\s*_?ILLUSTRATED_?\s*$", re.I),
    re.compile(r"^\s*WITH FRONTISPIECE\s*$", re.I),
    re.compile(r"^\s*(?:CHAPTER|STORY|PAGE|CHAP\.)\s+PAGE\s*$", re.I),
]

# a block starting with one of these ends the body: everything after is dropped
BACK_MATTER_RX = [
    re.compile(r"^\s*_?PRINTED BY(?:\b|_)", re.I),     # "_Printed by_" too
    re.compile(r"^\s*A LIST OF NEW BOOKS\b", re.I),
    re.compile(r"^\s*MESSRS?\.?\s+\w+.{0,40}ANNOUNCEMENTS\b", re.I),
    re.compile(r"^\s*BOOKS FOR BOYS AND GIRLS\s*$"),
    re.compile(r"^\s*THE PEACOCK LIBRARY\s*$"),
    re.compile(r"^\s*UNIVERSITY EXTENSION SERIES\s*$"),
    re.compile(r"^\s*SOCIAL QUESTIONS OF TO-DAY\s*$"),
    re.compile(r"^\s*LEADERS OF RELIGION\s*$"),
    re.compile(r"^\s*End of (?:the )?Project Gutenberg", re.I),
    re.compile(r"^\s*\*\*\* END OF TH", re.I),
    re.compile(r"^\s*ADVERTISEMENTS?\s*$"),
    re.compile(r"^\s*MURRAY[’']S\s*$"),          # John Murray's list after Blackwood
]

END_MARK_RX = re.compile(r"^\s*THE END\.?\s*$", re.I)

# Production apparatus that can appear on ANY line of a multi-line front block.
PRODUCER_RX = re.compile(
    r"(?:Produced by\b|Distributed Proofread|Online Distributed"
    r"|This (?:file|etext) was produced from|Internet Archive/Canadian"
    r"|pgdp\.net|www\.gutenberg)", re.I)

# Bracketed production notes that sit INSIDE a paragraph, so no block-level
# rule can reach them ("The Star", "The Beautiful and Damned").
INLINE_NOTE_RX = re.compile(
    r"\s*\[\s*(?:Transcriber|Transcribers|Transcriber's|Illustration|Editor's)"
    r"[^\]]*\]", re.I)

AD_HEADER_RX = re.compile(
    r"^(?:Books by\b|BOOKS BY\b|By the Same Author|BY THE SAME AUTHOR"
    r"|(?:Mr\.?\s+)?\w+ has also written\b|Works by\b|WORKS BY\b)", re.I)


IMPRINT_RX = re.compile(
    r"^(?:New York|London|Boston|Chicago|Philadelphia|Toronto|Edinburgh"
    r"|Garden City|CHARLES SCRIBNER|SCRIBNER|MACMILLAN|HARPER|DUFFIELD"
    r"|METHUEN|CHAPMAN|CASSELL|COLLINS|NELSON|DOUBLEDAY|GROSSET|ACE BOOKS"
    r"|Printed|First published|Reprinted|MCM[IVXLC]*"
    r"|Set up and electrotyped|Copyright|All rights)\b", re.I)


def _front_worth_keeping(b):
    """True for an epigraph, verse, or a real prose passage; False for an
    imprint page or an advertisement list."""
    ls = [l.strip() for l in b.lines if l.strip()]
    if not ls:
        return False
    if any(IMPRINT_RX.match(l) for l in ls):
        return False
    if len(ls) == 1 and len(ls[0]) < 40:
        return False
    joined = " ".join(ls)
    # a year on its own line, or a block that is mostly bare capitalised
    # titles, is publisher furniture rather than text
    if sum(1 for l in ls if re.fullmatch(r"(?:19|18)\d\d\.?", l)):
        return False
    # a stack of unpunctuated ALL-CAPS lines is a list of other titles
    # ("SIX TALES OF THE JAZZ AGE AND OTHER STORIES"), never an epigraph
    caps = [l for l in ls if _is_allcaps(l) and l[-1] not in ".!?"]
    if len(ls) >= 2 and len(caps) >= 0.8 * len(ls):
        return False
    ends_like_prose = any(l[-1] in ".!?”’\"'" for l in ls)
    mean_len = sum(len(l) for l in ls) / float(len(ls))
    return ends_like_prose or mean_len >= 34 or len(joined) > 220


def _list_shaped(b):
    """A run of short, unpunctuated, title-ish lines — an advertisement list."""
    ls = [l.strip() for l in b.lines if l.strip()]
    if not ls or len(ls) > 30:
        return False
    for l in ls:
        if len(l) > 60 or l[-1] in ".!?,;:":
            return False
    return True

# things we keep but tag rather than treat as prose
TRANSLATOR_RX = re.compile(
    r"^\s*(?:Translation\s+Copyright|Translated by|Translator\b|\(translation:)",
    re.I)
DEDICATION_RX = re.compile(
    r"^\s*(?:TO\b|To\b|_?Dedicated\b|QUITE INAPPROPRIATELY)", re.I)

SCENE_STARS_RX = re.compile(r"^\s*(?:[*•]\s*){3,}\s*$")
HRULE_RX = re.compile(r"^\s*-{20,}\s*$")

LETTER_INTRO_RX = re.compile(
    r"(?:as follows|ran thus|read as follows|which ran|it read|wrote"
    r"|the letter|this note|the note|the telegram|inscription)\s*[:—-]?\s*$", re.I)
SALUTATION_RX = re.compile(
    r"^[“\"]?\s*(?:My dear|Dear|DEAR|MY DEAR|Sir|SIR|Madam|Gentlemen|To the)\b")
SIGNOFF_RX = re.compile(
    r"^\s*[“\"]?(?:Yours(?: \w+)*|Sincerely|Faithfully|Affectionately|Ever yours"
    r"|Your (?:loving|affectionate)\b).{0,40}$", re.I)


# --------------------------------------------------------------------------
# 2. small helpers
# --------------------------------------------------------------------------

ABBREVS = {"MR", "MRS", "MISS", "MS", "DR", "ST", "MME", "MLLE", "JR", "SR",
           "PROF", "CAPT", "LT", "COL", "GEN", "HON", "REV", "MT", "NO",
           "VS", "ETC", "INC", "CO", "LTD"}
_SENT_RX = re.compile(r"([A-Za-z']+|\d+)([.!?])\s+(\S)")


def _has_sentence_break(s):
    """True for real sentence breaks; abbreviations such as `MR.` do not count."""
    for m in _SENT_RX.finditer(s):
        word, punct, nxt = m.groups()
        if punct == "." and word.upper().strip("'") in ABBREVS:
            continue
        if punct == "." and len(word) <= 2:
            continue                       # initials: "H. G. WELLS"
        return True
    return False


def _norm_key(s: str) -> str:
    """Normalise a heading/TOC title for matching."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = re.sub(r"[_—–-]+", " ", s)
    s = re.sub(r"[^A-Za-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip().upper()
    return s


def _slug(s: str, maxlen: int = 48) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen].strip("-") or "x"


def _visible(s: str) -> str:
    """Whitespace-normalised comparison form (used by the validator)."""
    s = s.replace(WJ, "").replace(HAIRSP, " ").replace(NBSP, " ")
    return re.sub(r"\s+", " ", s).strip()


def _roman_to_int(r: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    tot, prev = 0, 0
    for ch in reversed(r.upper()):
        v = vals.get(ch, 0)
        tot = tot - v if v < prev else tot + v
        prev = max(prev, v)
    return tot


def _is_allcaps(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


# --------------------------------------------------------------------------
# 3. Block model
# --------------------------------------------------------------------------

class Block:
    __slots__ = ("lines", "lineno", "indent", "kind", "meta")

    def __init__(self, lines, lineno):
        self.lines = lines                     # list[str], right-stripped, blank-free
        self.lineno = lineno                   # 1-based source line of first line
        self.indent = min((len(l) - len(l.lstrip(" ")) for l in lines), default=0)
        self.kind = None                       # set by the classifier
        self.meta = {}

    @property
    def text(self):
        return " ".join(l.strip() for l in self.lines)

    @property
    def raw(self):
        return "\n".join(self.lines)

    def __repr__(self):
        return "<Block L%d %s %r>" % (self.lineno, self.kind, self.text[:50])


def split_blocks(lines):
    """lines -> list[Block]; blocks are maximal runs of non-blank lines."""
    blocks, cur, start = [], [], 0
    for i, ln in enumerate(lines):
        if ln.strip():
            if not cur:
                start = i + 1
            cur.append(ln.rstrip())
        elif cur:
            blocks.append(Block(cur, start))
            cur = []
    if cur:
        blocks.append(Block(cur, start))
    return blocks


# --------------------------------------------------------------------------
# 4. Heading grammar
# --------------------------------------------------------------------------

_RX_BOOK = re.compile(
    r"^(BOOK|Book)\s+(?:THE\s+|the\s+)?(%s|\d{1,3}|%s|[A-Z]{2,12})\b\.?\s*(.*)$"
    % (ROMAN, NUMWORD), re.I)
_RX_PART = re.compile(
    r"^(PART|Part)\s+(?:THE\s+|the\s+)?(%s|\d{1,3}|%s)\b\.?\s*(.*)$"
    % (ROMAN, NUMWORD), re.I)
_RX_SECTWORD = re.compile(
    r"^(Section|SECTION)\s+(%s|\d{1,3}|%s)\b\.?\s*(.*)$" % (ROMAN, NUMWORD), re.I)
_RX_CHAPTER = re.compile(
    r"^(CHAPTER|Chapter|CHAP\.)\s*(?:THE\s+|the\s+)?(%s|\d{1,3}|%s)?\b\.?\s*"
    r"(?:[—–:.~-]+\s*)?(.*)$" % (ROMAN, NUMWORD), re.I)
# Blackwood's "John Silence": CASE I over the story's own title. Capitals and
# a numeral only, so a sentence that happens to open with "Case" never matches.
_RX_CASE = re.compile(r"^CASE\s+(%s)\.?$" % ROMAN)
_RX_ACT = re.compile(
    r"^(ACT|Act)\s+(%s|\d{1,3}|%s)\b\.?\s*(.*)$" % (ROMAN, NUMWORD), re.I)
_RX_SCENE = re.compile(
    r"^(SCENE|Scene)\s+(%s|\d{1,3}|%s)\b\.?\s*(.*)$" % (ROMAN, NUMWORD), re.I)
_RX_SECTSIGN = re.compile(r"^§\s*(\d{1,3})\.?\s*$")
_RX_BARE_ROMAN = re.compile(r"^(%s)\s*\.?\s*$" % ROMAN)
_RX_BARE_ARABIC = re.compile(r"^(\d{1,3})\s*\.?\s*$")
_RX_NUM_TITLE = re.compile(r"^(%s|\d{1,3})\s*[.—:-]{1,3}\s+(\S.*)$" % ROMAN)


def _numword_to_int(w):
    w = w.lower()
    if w in ORDINAL_WORDS:
        return ORDINAL_WORDS.index(w) + 1
    if w in CARDINAL_WORDS:
        return CARDINAL_WORDS.index(w) + 1
    return None


def _num_of(tok):
    if tok is None:
        return None
    tok = tok.strip().rstrip(".")
    if not tok:
        return None
    if tok.isdigit():
        return int(tok)
    if re.fullmatch(ROMAN, tok.upper()) and tok.upper():
        return _roman_to_int(tok)
    return _numword_to_int(tok)


def classify_heading_line(s):
    """Return (type, number, title) or None for a single candidate line."""
    t = s.strip()
    if len(t) > 2 and t[0] == "_" and t[-1] == "_":
        t = t[1:-1].strip()               # _BOOK THE SECOND_
    if not t:
        return None
    if len(t) > 90:
        return None

    m = _RX_BOOK.match(t)
    if m and _num_of(m.group(2)) is not None:
        return ("book", _num_of(m.group(2)), m.group(3).strip(" .—-"))
    m = _RX_PART.match(t)
    if m and _num_of(m.group(2)) is not None:
        return ("part", _num_of(m.group(2)), m.group(3).strip(" .—-"))
    m = _RX_ACT.match(t)
    if m and _num_of(m.group(2)) is not None:
        return ("act", _num_of(m.group(2)), m.group(3).strip(" .—-"))
    m = _RX_SCENE.match(t)
    if m and _num_of(m.group(2)) is not None:
        return ("scene", _num_of(m.group(2)), m.group(3).strip(" .—-"))
    m = _RX_SECTWORD.match(t)
    if m and _num_of(m.group(2)) is not None:
        return ("sectword", _num_of(m.group(2)), m.group(3).strip(" .—-"))
    m = _RX_CHAPTER.match(t)
    if m:
        n = _num_of(m.group(2))
        if n is not None or m.group(3):
            return ("chapter", n, m.group(3).strip(" .—-"))
    m = _RX_CASE.match(t)
    if m:
        return ("chapter", _roman_to_int(m.group(1)), "")
    m = _RX_SECTSIGN.match(t)
    if m:
        return ("sectsign", int(m.group(1)), "")
    m = _RX_BARE_ROMAN.match(t)
    if m and m.group(1):
        return ("numeric", _roman_to_int(m.group(1)), "")
    m = _RX_BARE_ARABIC.match(t)
    if m:
        return ("numeric", int(m.group(1)), "")
    if t.rstrip(".").lower() in NAMED_DIVISIONS:
        return ("named", None, t.rstrip("."))
    m = _RX_NUM_TITLE.match(t)
    if (m and _num_of(m.group(1)) is not None and _title_like(m.group(2))
            # "X. Y. Z." is a signature, not chapter X called "Y. Z."
            and not re.fullmatch(r"(?:[A-Z]\.\s*)+", m.group(2).strip())):
        # provisional: promoted to "numtitle" only if the TOC confirms it
        return ("numeric", _num_of(m.group(1)), m.group(2).strip(" ."))
    return None


# --------------------------------------------------------------------------
# 5. The parser
# --------------------------------------------------------------------------

AUTHOR_BY_FOLDER = {
    "카프카": "Franz Kafka",
    "HG웰스": "H. G. Wells",
    "피츠제럴드": "F. Scott Fitzgerald",
    "테아폰하르부": "Thea von Harbou",
    "블랙우드": "Algernon Blackwood",
}


class Doc:
    """Everything the parser learns about one file."""

    def __init__(self, path):
        self.path = path
        self.basename = os.path.basename(path)
        self.folder = os.path.basename(os.path.dirname(path))
        raw = open(path, "rb").read()
        text = raw.decode("utf-8-sig")
        text = text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(8)
        self.source = text
        self.lines = text.split("\n")
        self.blocks = split_blocks(self.lines)
        self.stats = Counter()
        self.notes = []
        self.dropped = []          # (reason, chars)

    # -- metadata ---------------------------------------------------------
    def meta(self):
        m = re.match(r"^((?:1[89]|20)\d\d)_(.+)\.txt$", self.basename)
        year = int(m.group(1)) if m else None
        title = m.group(2) if m else os.path.splitext(self.basename)[0]
        author = None
        for b in self.blocks[:40]:
            for ln in b.lines:
                s = ln.strip().strip("_")
                mm = re.match(r"^(?:by|BY|By)\s+(.{3,50})$", s)
                # "…made available by The Internet Archive/Canadian Libraries)"
                # is not a byline. A person's name has no slashes, brackets,
                # digits or production vocabulary in it.
                if (mm and not re.search(r"\d", mm.group(1))
                        and not re.search(r"[/()\[\]@]", mm.group(1))
                        and not PRODUCER_RX.search(mm.group(1))):
                    author = mm.group(1).strip(" .,_")
                    break
                if s in ("F. SCOTT FITZGERALD", "H. G. WELLS", "Franz Kafka",
                         "Thea von Harbou", "F. Scott Fitzgerald", "H.G. Wells"):
                    author = s
                    break
            if author:
                break
        if author:
            # normalise SHOUTED author names
            if _is_allcaps(author) and len(author) > 3:
                author = " ".join(w.capitalize() if len(w) > 2 or "." not in w
                                  else w for w in author.split())
                author = re.sub(r"\b([A-Za-z])\.", lambda x: x.group(1).upper() + ".",
                                author)
        return title, (author or AUTHOR_BY_FOLDER.get(self.folder)), year


# ---- 5a. profile detection ------------------------------------------------

def detect_profile(doc):
    nb = [len(l) for l in doc.lines if l.strip()]
    nb.sort()
    med = nb[len(nb) // 2] if nb else 0
    prof = {"reflowed": med > 120, "median_line": med}
    txt = doc.source
    prof["standard_ebooks"] = WJ in txt and re.search(r"^-{60}$", txt, re.M) is not None
    prof["wikisource"] = bool(re.match(
        r"^[^\n]{1,60}\n[^\n]{1,40}\n\(translation:", txt))
    prof["curly"] = txt.count("“") > txt.count('"')
    # play?
    acts = len(re.findall(r"^\s*ACT\s+[IVX0-9]", txt, re.M))
    speakers = len(re.findall(
        r"^[A-Z][A-Z' .’-]{1,28}(?:\s*\[[^\]]{0,60}\])?\.\s+\S", txt, re.M))
    prof["play"] = acts >= 2 and speakers >= 30
    prof["speaker_hits"] = speakers
    return prof


# ---- 5b. manifest (TOC) harvesting ---------------------------------------

TOC_HEAD_RX = re.compile(
    r"^\s*(?:A\s+)?(?:TABLE\s+OF\s+)?CONTENTS?\.?\s*$", re.I)


MAX_TOC_ENTRIES = 120


def harvest_manifest(doc):
    """Return (entries, toc_block_indices).  entries = list of dicts.

    A TOC block is a run of *unwrapped* short lines that follows a
    CONTENTS heading.  Consumption stops at the first block that reads
    like wrapped prose, which is what keeps the harvester out of the body.
    """
    entries, used = [], set()
    for bi, b in enumerate(doc.blocks[:80]):
        if len(b.lines) != 1 or not TOC_HEAD_RX.match(b.lines[0].strip()):
            continue
        used.add(bi)
        j, misses = bi + 1, 0
        prev_end = b.lineno
        seen_keys = set()
        while (j < len(doc.blocks) and misses < 2 and j < bi + 80
               and len(entries) < MAX_TOC_ENTRIES):
            blk = doc.blocks[j]
            # a big vertical gap means the table of contents is over
            if blk.lineno - prev_end - 1 >= 3:
                break
            # a wholly italic paragraph is an annotation between entries
            # (Fitzgerald's "A TABLE OF CONTENTS"), not the end of the list
            bt = blk.text.strip()
            if bt.startswith("_") and bt.endswith("_") and len(blk.lines) < 40:
                prev_end = blk.lineno + len(blk.lines) - 1
                j += 1
                continue
            # a wrapped-prose block ends the table of contents. Leader padding
            # does not count: "I. TITLE            1" set out to column 72 is
            # still an entry (Blackwood's "Ten Minute Stories").
            if (max(len(re.sub(r"\s{2,}", " ", l.strip())) for l in blk.lines) > 66
                    or len(blk.lines) > 60):
                break
            rows = [_toc_row(l) for l in blk.lines]
            ok = sum(1 for r in rows if r)
            # a repeated entry means we have walked back into the body
            if any(r and r["key"] in seen_keys for r in rows):
                break
            if ok and ok >= max(1, int(0.8 * len(blk.lines))):
                for r in rows:
                    if r:
                        entries.append(r)
                        seen_keys.add(r["key"])
                used.add(j)
                misses = 0
                prev_end = blk.lineno + len(blk.lines) - 1
            else:
                misses += 1
                prev_end = blk.lineno + len(blk.lines) - 1
            j += 1
        if entries:
            break
    seen, out = set(), []
    for e in entries:
        if e["key"] and e["key"] not in seen:
            seen.add(e["key"])
            out.append(e)
    return out, used


_TITLECASE_STOP = {"a", "an", "the", "of", "and", "or", "in", "on", "at", "to",
                   "for", "with", "by", "from", "de", "la", "as", "is", "it",
                   "his", "her", "who", "that", "into", "upon", "not", "but"}


def _strip_quotes(s):
    s = s.strip()
    while len(s) > 2 and s[0] in "“‘\"'" and s[-1] in "”’\"'":
        s = s[1:-1].strip()
    return s


def _title_like(s):
    """Heading-ish: ALL CAPS, or Title Case with few lowercase openers."""
    if s[:1] in "“‘\"'(":
        return False
    if _is_allcaps(s):
        return True
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", s)
    if not words:
        return False
    cap = sum(1 for w in words
              if w[0].isupper() or w.lower() in _TITLECASE_STOP)
    return cap == len(words) and words[0][0].isupper()


def _toc_row(line):
    s = line.strip()
    if not s or len(s) > 78:
        return None
    if re.fullmatch(r"(?:CHAPTER|CHAP\.|STORY|PAGE|BOOK|PART)\s+PAGE", s, re.I):
        return None
    if re.fullmatch(r"PAGE|FACING\s+PAGE|CONTENTS?\.?|CONTENTSCHAP\.", s, re.I):
        return None
    had_page = bool(re.search(r"(?:[\s.]{2,}|\s)\d{1,4}\s*$", s))
    s = re.sub(r"[\s.]{2,}\d{1,4}\s*$", "", s)
    s = re.sub(r"\s+\d{1,4}\s*$", "", s)
    s = re.sub(r"_Frontispiece_\s*$", "", s).strip()
    if not s:
        return None
    label = ""
    m = re.match(r"^((?:%s|\d{1,3})\.?)[\s.—:-]+(\S.*)$" % ROMAN, s)
    if m and _num_of(m.group(1)) is not None:
        label, s = m.group(1).rstrip("."), m.group(2)
    grp = bool(re.match(r"^(BOOK|PART|CHAPTER)\b", s, re.I))
    s = _strip_quotes(s).strip(" .—-")
    if not s or len(s) < 2 or len(s) > 70:
        return None
    if re.fullmatch(r"[\d\s.—-]+", s):
        return None
    if re.fullmatch(ROMAN + r"\.?", s) or re.fullmatch(r"\d{1,3}\.?", s):
        return None                       # a bare numeral carries no title
    if re.search(r"[,;]\s*$", s):
        return None
    if _has_sentence_break(s):                # a sentence, not an entry
        return None
    if not (had_page or label or _title_like(s)):
        return None
    return {"label": label, "title": s, "key": _norm_key(s), "group": grp}


# ---- 5c. front / back matter boundaries ----------------------------------

def find_body_start(doc, manifest, toc_used):
    """Index of the first block that belongs to the body."""
    n = len(doc.blocks)
    if not n:
        return 0
    # a file that opens on a heading has no front matter at all
    if len(doc.blocks[0].lines) <= 2 and classify_heading_line(doc.blocks[0].text):
        return 0

    limit = min(n, max(6, int(n * 0.30) + 40))
    keys = {e["key"] for e in manifest}
    first_key = manifest[0]["key"] if manifest else None
    last_toc = max(toc_used) if toc_used else -1

    cands = []
    for bi in range(last_toc + 1, limit):
        b = doc.blocks[bi]
        if bi in toc_used:
            continue
        h = classify_heading_line(b.text) if len(b.lines) <= 2 else None
        if h is None and len(b.lines) == 2:
            h = classify_heading_line(b.lines[0].strip())
        if first_key and len(b.lines) <= 2 and _norm_key(b.text) == first_key:
            cands.append((bi, 4))
        elif h and h[0] in ("book", "part", "chapter", "act", "numtitle"):
            cands.append((bi, 3))
        elif keys and len(b.lines) <= 2 and _norm_key(b.text) in keys:
            cands.append((bi, 2))
        elif h and h[0] == "named" and h[2].lower() in (
                "preface", "prologue", "introduction", "foreword", "proem"):
            cands.append((bi, 2))
        elif h and h[0] in ("numeric", "sectsign"):
            cands.append((bi, 1))
    cands = [c for c in cands if _followed_by_prose(doc, c[0])] or cands
    if cands:
        best = max(x[1] for x in cands)
        for bi, sc in cands:
            if sc == best:
                return _backup_over_heading(doc, bi, last_toc, toc_used)
    # no headings at all: skip leading title/attribution blocks
    for bi, b in enumerate(doc.blocks[:12]):
        if len(b.lines) >= 2 or len(b.text) > 200:
            return bi
    return 0


def _followed_by_prose(doc, bi, window=4):
    """True when real body text starts here (a contents list does not)."""
    for j in range(bi + 1, min(len(doc.blocks), bi + 1 + window)):
        b = doc.blocks[j]
        if len(b.lines) >= 3 and max(len(l.rstrip()) for l in b.lines) > 55:
            return True
    return False


def _backup_over_heading(doc, bi, last_toc, toc_used):
    """`BOOK I.` / `THE MAKING OF KIPPS` sit just above the matched title."""
    for _ in range(3):
        if bi - 1 <= last_toc or (bi - 1) in toc_used:
            break
        prev = doc.blocks[bi - 1]
        gap = doc.blocks[bi].lineno - (prev.lineno + len(prev.lines))
        if gap > 3 or len(prev.lines) > 2:
            break
        h = classify_heading_line(prev.text)
        caps = _is_allcaps(prev.text) and len(prev.text) <= 62
        if (h and h[0] in ("book", "part", "chapter", "act", "numeric")) or caps:
            bi -= 1
            continue
        break
    return bi


def find_body_end(doc, body_start):
    n = len(doc.blocks)
    floor = body_start + max(3, int((n - body_start) * 0.45))
    for bi in range(body_start, n):
        first = doc.blocks[bi].lines[0]
        for rx in BACK_MATTER_RX:
            if rx.match(first) and (bi >= floor or "Gutenberg" in first):
                return bi
    return n


# ---- 5d. block classification --------------------------------------------

def is_dropline(s):
    return any(rx.match(s) for rx in DROP_LINE_RX)


def block_is_junk(b):
    live = [l for l in b.lines if not is_dropline(l)]
    return not live


def looks_verse(b, body_indent):
    """Line-preserving block: verse, inscription, tabular scrap."""
    ls = [l for l in b.lines if l.strip()]
    if len(ls) < 2:
        # a lone bullet line is a list item, kept as its own line
        return bool(re.match(r"^\s*[*•—-]\s+\S", b.lines[0])
                    and not SCENE_STARS_RX.match(b.lines[0]))
    # column-aligned material (Gatsby's schedule): runs of inner spaces
    aligned = sum(1 for l in ls if re.search(r"\S {3,}\S", l))
    if aligned >= 2 and aligned >= 0.6 * len(ls) and max(
            len(l.rstrip()) for l in ls) <= 78:
        return True
    if all(re.match(r"^\s*[*•]\s+\S", l) for l in ls):
        return True
    lens = [len(l.rstrip()) for l in ls]
    inds = [len(l) - len(l.lstrip(" ")) for l in ls]
    if max(lens) > 68:
        return False
    # every line clearly short of the wrap column
    if max(lens) > 62:
        return False
    if min(inds) < body_indent + 2:
        return False
    # ragged indentation or short lines -> verse; uniform prose would fill the column
    avg = sum(lens) / len(lens)
    if avg > 58:
        return False
    if len(set(inds)) >= 2:
        return True
    # uniform indent: verse if most lines are well short of the column
    return sum(1 for x in lens if x < 52) >= max(2, int(0.7 * len(lens)))


def looks_smallblock_quote(b, body_indent):
    """Wrapped prose that is indented relative to the body -> blockquote."""
    ls = [l for l in b.lines if l.strip()]
    inds = [len(l) - len(l.lstrip(" ")) for l in ls]
    return min(inds) >= body_indent + 3 and max(
        len(l.rstrip()) for l in ls) > 55


def allcaps_head_candidate(b, prev_block, next_block, body_indent):
    """Is this block an ALL-CAPS heading rather than shouted prose?"""
    if len(b.lines) > 2:
        return None
    t = b.text.strip()
    if not (2 <= len(t) <= 62):
        return None
    if not _is_allcaps(t):
        return None
    if sum(c.isalpha() for c in t) < 2:
        return None
    if len(t.split()) > 10:
        return None
    if t[0] in "“‘\"'(" or t[-1] in "”’\"')":
        return None
    if t[-1] in ",;:":
        return None
    if _has_sentence_break(t):                # a sentence, not a title
        return None
    if re.search(r"\d\s*$", t) and re.search(r"\s{2,}\d", b.lines[0]):
        return None                           # TOC row with a page number
    if prev_block is not None and prev_block.kind not in ("head", "allcaps?"):
        pv = prev_block.text.rstrip()
        if pv and pv[-1] not in ".!?”’\"'—-*":
            return None                       # continues a sentence
    if (prev_block is not None and prev_block.kind not in ("head", "allcaps?")
            and _looks_like_signature(t)):
        return None
    return t


def _looks_like_signature(t):
    """`EDWARD PRENDICK.` closing a letter is not a heading."""
    if not t.endswith("."):
        return False
    words = [w for w in re.findall(r"[A-Z][A-Z.'’-]*", t)]
    if not (1 <= len(words) <= 4):
        return False
    if any(w.rstrip(".") in ("THE", "OF", "AND", "A", "IN", "ON", "TO",
                             "PART", "BOOK", "CHAPTER") for w in words):
        return False
    initials = sum(1 for w in words if len(w.rstrip(".")) <= 2)
    return initials > 0 or len(words) <= 3


def classify_blocks(doc, blocks, manifest, profile, body_indent):
    keys = {}
    for e in manifest:
        keys.setdefault(e["key"], e)
    mkeys = [k for k in keys if len(k) >= 4]

    def manifest_match(txt):
        t = _strip_quotes((txt or "").strip())
        k = _norm_key(t)
        if not k:
            return None
        if k in keys:
            return keys[k]
        # "JEMINA" in the TOC vs "JEMINA, THE MOUNTAIN GIRL" in the body:
        # only accept when the extra text is a subtitle and the line reads
        # like a title in the first place.
        if len(k) >= 8 and _title_like(t) and t[0] not in "“‘\"'":
            for mk in mkeys:
                if len(mk) < 8:
                    continue
                # the body title carries a subtitle the TOC omitted
                if k.startswith(mk + " ") and len(k) - len(mk) <= 41:
                    return keys[mk]
                # the TOC abbreviated the title
                if k.endswith(" " + mk) and len(k) - len(mk) <= 25:
                    return keys[mk]
        return None

    prev_live = None
    for i, b in enumerate(blocks):
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None

        if block_is_junk(b):
            b.kind = "drop"
            b.meta["why"] = "illustration/apparatus"
            continue
        if SCENE_STARS_RX.match(b.lines[0]) and len(b.lines) == 1:
            b.kind = "scenerule"
            continue
        if HRULE_RX.match(b.lines[0]) and len(b.lines) == 1:
            b.kind = "hrule"
            b.meta["len"] = len(b.lines[0].strip())
            continue
        if END_MARK_RX.match(b.lines[0]) and len(b.lines) == 1:
            b.kind = "drop"
            b.meta["why"] = "the-end marker"
            continue

        head = None
        if len(b.lines) <= 2:
            head = classify_heading_line(b.text)
            if head is None and len(b.lines) == 2:
                h0 = classify_heading_line(b.lines[0].strip())
                l1 = b.lines[1].strip()
                loose = (l1[:1].isupper() and l1[-1:] not in ".,;:!?"
                         and not _has_sentence_break(l1))
                if (h0 and h0[2] == "" and len(l1) <= 64
                        and not re.search(r"[,;:]$", l1)
                        and l1[:1] not in "“‘\"'0123456789"
                        and (_title_like(l1) or manifest_match(l1) or loose)):
                    head = (h0[0], h0[1], l1.strip(" ."))
        if head:
            htype, hnum, htitle = head
            # a bare number whose title is a TOC entry is a chapter, not a section
            mmh = manifest_match(htitle) if htitle else None
            if htype in ("numeric", "numtitle") and mmh:
                htype = "numtitle"
            b.kind = "head"
            b.meta["h"] = {"type": htype, "num": hnum, "title": htitle,
                           "mlabel": (mmh or {}).get("label", "")}
            prev_live = b
            continue

        mm = manifest_match(b.text) if len(b.lines) <= 2 else None
        if mm and not mm["group"]:
            b.kind = "head"
            b.meta["h"] = {"type": "manifest", "num": _num_of(mm["label"]),
                           "title": b.text.strip(), "mlabel": mm["label"]}
            prev_live = b
            continue

        # a quoted story title ("THE SENSIBLE THING") is a heading only when
        # the table of contents vouches for it
        if (len(b.lines) <= 2 and _is_allcaps(b.text)
                and b.text.strip()[:1] in "“‘\"'"):
            mq = manifest_match(b.text)
            if mq:
                b.kind = "head"
                b.meta["h"] = {"type": "manifest", "num": _num_of(mq["label"]),
                               "title": b.text.strip(), "mlabel": mq["label"]}
                prev_live = b
                continue

        ac = allcaps_head_candidate(b, prev_live, nxt, body_indent)
        if ac:
            b.kind = "allcaps?"
            b.meta["h"] = {"type": "allcaps", "num": None, "title": ac}
            prev_live = b
            continue

        if looks_verse(b, body_indent):
            b.kind = "verse"
        elif looks_smallblock_quote(b, body_indent):
            b.kind = "quote"
        else:
            b.kind = "para"
        prev_live = b


# ---- 5e. level inference --------------------------------------------------

SUBHEAD_TYPES = {"numeric", "sectsign", "allcaps", "scene"}
CHAPTER_TYPES = {"chapter", "manifest", "named", "numtitle", "act"}
PART_TYPES = {"book"}


def infer_levels(blocks):
    """Assign 'part' / 'chapter' / 'subhead' to each heading block."""
    counts = Counter(b.meta["h"]["type"] for b in blocks
                     if b.kind == "head" and "h" in b.meta)
    level = {}

    for t in counts:
        if t in PART_TYPES:
            level[t] = "part"
        elif t in CHAPTER_TYPES:
            level[t] = "chapter"
        elif t in SUBHEAD_TYPES:
            level[t] = "subhead"

    nchap = sum(counts[t] for t in counts if level.get(t) == "chapter")

    # PART / Section-N: outer division only when rarer than the chapter marker
    for t in ("part", "sectword"):
        if t in counts:
            if nchap and counts[t] < nchap:
                level[t] = "part"
            elif not nchap:
                level[t] = "chapter"
            else:
                level[t] = "subhead"

    nchap = sum(counts[t] for t in counts if level.get(t) == "chapter")
    if nchap == 0:
        # promote the most frequent low-level marker to chapter
        low = [(counts[t], t) for t in counts if level.get(t) == "subhead"]
        if low:
            low.sort(reverse=True)
            level[low[0][1]] = "chapter"
        else:
            for t in counts:
                if level.get(t) == "part":
                    level[t] = "chapter"

    # never leave two part-level marker types
    parts = [t for t in level if level[t] == "part"]
    if len(parts) > 1:
        parts.sort(key=lambda t: counts[t])
        for t in parts[1:]:
            level[t] = "chapter" if not nchap else "subhead"
    return level


def confirm_allcaps(blocks, level, manifest):
    """Accept/reject the provisional 'allcaps?' heads with file-level evidence."""
    cands = [b for b in blocks if b.kind == "allcaps?"]
    if not cands:
        return
    real_heads = [b for b in blocks
                  if b.kind == "head" and b.meta["h"]["type"] != "allcaps"]
    after_head = 0
    for i, b in enumerate(blocks):
        if b.kind == "allcaps?" and i and blocks[i - 1].kind == "head":
            after_head += 1
    accept = (len(cands) >= 4) or bool(manifest) or after_head >= 2
    if len(cands) <= 2 and not real_heads:
        accept = False
    for b in cands:
        b.kind = "head" if accept else "para"
        if b.kind == "para":
            b.meta.pop("h", None)
    # newspaper headlines &c: 3+ adjacent caps blocks are display text
    run = []
    for b in list(blocks) + [None]:
        if b is not None and b.kind == "head" and                 b.meta.get("h", {}).get("type") == "allcaps":
            run.append(b)
            continue
        if len(run) >= 3:
            for r in run:
                r.kind = "verse"
                r.meta.pop("h", None)
        run = []


def drop_repeated_heads(blocks, level):
    """PG half-titles and running heads repeat a chapter title."""
    heads = [b for b in blocks if b.kind == "head"]
    for a, b in zip(heads, heads[1:]):
        ka, kb = _norm_key(a.meta["h"]["title"]), _norm_key(b.meta["h"]["title"])
        if ka and ka == kb and not a.meta["h"].get("num"):
            a.kind = "drop"
            a.meta["why"] = "half-title"
    last_chap = None
    for b in heads:
        if b.kind != "head":
            continue
        h = b.meta["h"]
        lvl = h.get("forced_level") or level.get(h["type"], "subhead")
        if lvl != "chapter":
            continue
        k = _norm_key(h["title"])
        if k and k == last_chap:
            b.kind = "drop"
            b.meta["why"] = "running head"
        else:
            last_chap = k


def promote_group_heads(blocks, level):
    """A chapter head with no prose before the next chapter head is a part.

    This is how PG renders the section groups of a story collection
    (`MY LAST FLAPPERS`, `FANTASIES`, ...).
    """
    live = [b for b in blocks if b.kind in ("head", "para", "quote", "verse")]
    for i, b in enumerate(live):
        if b.kind != "head":
            continue
        h = b.meta["h"]
        if (h.get("forced_level") or level.get(h["type"], "subhead")) != "chapter":
            continue
        nxt = live[i + 1] if i + 1 < len(live) else None
        if nxt is not None and nxt.kind == "head":
            nh = nxt.meta["h"]
            if (nh.get("forced_level") or
                    level.get(nh["type"], "subhead")) == "chapter":
                h["forced_level"] = "part"


def merge_number_title(blocks, level):
    """`I.` + `THE EVE OF THE WAR.`  and  `CHAPTER I` + `ANTHONY PATCH`."""
    out, i = [], 0
    while i < len(blocks):
        b = blocks[i]
        nb = blocks[i + 1] if i + 1 < len(blocks) else None
        if (b.kind == "head" and nb is not None and nb.kind == "head"
                and not b.meta["h"]["title"]
                and nb.meta["h"]["type"] in ("allcaps", "manifest")
                and nb.meta["h"]["title"]
                and level.get(b.meta["h"]["type"]) in ("chapter", "subhead")
                and b.meta["h"]["type"] not in ("allcaps",)):
            promote = level.get(b.meta["h"]["type"])
            if nb.meta["h"]["type"] == "manifest":
                promote = "chapter"
            b.meta["h"]["title"] = nb.meta["h"]["title"]
            b.meta["h"]["merged"] = True
            b.meta["h"]["forced_level"] = promote
            nb.kind = "merged"
            out.append(b)
            i += 2
            continue
        out.append(b)
        i += 1
    return blocks


# ---- 5f. inline markup ----------------------------------------------------

_ITALIC_RX = re.compile(r"(?<![A-Za-z0-9_])_([^_]+?)_(?![A-Za-z0-9])")
_DBL_ITALIC_RX = re.compile(r"__([^_]+?)__")
# opening _ at a word boundary, closing _ mid-word: "_Di_sy", "_any_ways".
# Restricted to plain letters so price notation (6_s._ 6_d._) is untouched.
_PARTWORD_ITALIC_RX = re.compile(r"(?<![A-Za-z0-9_])_([^_\n]{1,22}?)_(?=[a-z])")
# sentinels: small caps are found before HTML escaping, wrapped afterwards
SC_OPEN, SC_CLOSE = "\x01", "\x02"
_ACRONYMS = {"I", "A", "OK", "PS", "NB", "MS", "AD", "BC", "AM", "PM", "US",
             "UK", "TV", "SOS", "III", "II", "IV", "VI", "IX", "XI", "XX"}


def normalise_punct(s, curly_source):
    # ellipses -- keep an existing U+2026, fold ASCII forms.
    # One rule covers "...", ". . .", "....", ". . . ." alike: a dot followed
    # by two or more further dots, each optionally preceded by one space.
    # (The old pair of rules only matched runs of *adjacent* dots, so the
    # spaced form ". . ." survived into the text in 8 files.)
    s = re.sub(r"\.(?:[  ]?\.){2,}", "…", s)
    s = re.sub(r"…[\s.]*\.", "…", s)
    # dashes: ---- (2-em), --- (2-em), -- (em)
    s = s.replace("----", "⸺").replace("---", "⸻")
    s = re.sub(r"(?<!-)--(?!-)", "—", s)
    s = s.replace("⸺", "——").replace("⸻", "——")
    if not curly_source:
        s = _curl_quotes(s)
    # spaced em dash -> tight em dash (typographic house style)
    s = re.sub(r"\s+—\s+", "—", s)
    s = re.sub(r"\s+([,;:!?])", r"\1", s)
    return s


def _curl_quotes(s):
    out, dq_open = [], False
    prev = ""
    for i, c in enumerate(s):
        if c == '"':
            out.append("“" if not dq_open else "”")
            dq_open = not dq_open
        elif c == "'":
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if prev.isalnum() and nxt.isalnum():
                out.append("’")                       # don't
            elif prev.isalnum() and not nxt.isalnum():
                out.append("’")                       # dogs'
            elif re.match(r"[a-z]", nxt) and not prev.isalnum():
                out.append("’")                       # 'em, 'tis
            else:
                out.append("‘")
        else:
            out.append(c)
        prev = c
    return "".join(out)


def _smallcaps(s):
    """ALL-CAPS runs -> small caps, skipping acronyms and shouted dialogue."""
    # mask quoted spans: shouting inside quotes stays as-is
    spans = [(m.start(), m.end()) for m in
             re.finditer(r"[“\"][^”\"]{0,400}[”\"]", s)]

    def inside(a, b):
        return any(x <= a and b <= y for x, y in spans)

    def rep(m):
        a, b = m.start(), m.end()
        run = m.group(0)
        if inside(a, b):
            return run
        words = re.findall(r"[A-Z][A-Z']*", run)
        letters = sum(len(w) for w in words)
        if len(words) < 2 or letters < 6:
            return run
        if all(w in _ACRONYMS for w in words):
            return run
        return SC_OPEN + run + SC_CLOSE

    return re.sub(r"\b[A-Z][A-Z']*(?:[  ](?:[A-Z][A-Z']*|&|OF|THE|AND)){1,8}\b",
                  rep, s)


def inline(s, curly_source, smallcaps=True, carry=None):
    """Escape + italics + small caps + punctuation.  Returns (html, carry)."""
    s = INLINE_NOTE_RX.sub("", s)          # [Transcriber's Note …], [Illustration …]
    s = normalise_punct(s, curly_source)
    # small caps are detected on the *unescaped* text and marked with
    # sentinels, so that escaping cannot cut an entity in half
    if smallcaps:
        s = _smallcaps(s)
    s = _html.escape(s, quote=False)
    opened = carry or False
    if opened:
        s = "_" + s
    n = s.count("_")
    trailing = False
    if n % 2:
        s = s + "_"
        trailing = True
    s = _DBL_ITALIC_RX.sub(lambda m: "<em>%s</em>" % m.group(1), s)
    s = _ITALIC_RX.sub(lambda m: "<em>%s</em>" % m.group(1), s)
    # part-word emphasis: _Di_sy, _any_ways, _Ran_dolph. The main rule refuses
    # these because its closing lookahead forbids a following letter.
    s = _PARTWORD_ITALIC_RX.sub(lambda m: "<em>%s</em>" % m.group(1), s)
    # Whatever underscores survive are unmatched italic delimiters, almost all
    # of them from emphasis that opens in one paragraph and closes in another.
    # Showing the reader a literal "_" is worse than losing the emphasis, so
    # drop any underscore not flanked by alphanumerics on both sides.
    s = re.sub(r"(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])", "", s)
    s = s.replace("_", "&#95;")
    s = s.replace(SC_OPEN, '<span class="smallcaps">').replace(SC_CLOSE, "</span>")
    return s, trailing


# ---- 5g. HTML emission ----------------------------------------------------

class Emitter:
    def __init__(self, curly, smallcaps=True):
        self.out = []
        self.toc = []
        self.pcount = 0
        self.curly = curly
        self.smallcaps = smallcaps
        self.carry = False
        self.text_kept = []          # body text, verbatim from the source
        self.head_src = []           # heading text, verbatim from the source
        self.synth = []              # text the parser synthesised (title page)
        self.synth_para = []         # synthesised text emitted inside a <p>
        self.counters = {"part": 0, "chapter": 0, "sub": 0}
        self._cur_chapter = None

    # text bookkeeping ---------------------------------------------------
    def _keep(self, s):
        self.text_kept.append(s)

    def p(self, text, cls=None, verse=False):
        self._keep(text)
        h, self.carry = inline(text, self.curly, self.smallcaps, self.carry)
        self.pcount += 1
        c = ' class="%s"' % cls if cls else ""
        self.out.append('<p%s data-p="%d">%s</p>' % (c, self.pcount, h))

    def raw_line(self, text, cls="verse"):
        self._keep(text)
        h, self.carry = inline(text, self.curly, self.smallcaps, self.carry)
        self.pcount += 1
        self.out.append('<p class="%s" data-p="%d">%s</p>' % (cls, self.pcount, h))

    def open(self, tag, coalesce=False):
        """coalesce=True continues the quotation block just closed."""
        if coalesce and self.out and self.out[-1] == "</%s>" % tag:
            self.out.pop()
            return
        self.out.append("<%s>" % tag)

    def close(self, tag):
        self.out.append("</%s>" % tag)

    def rule(self):
        self.out.append('<hr class="scene">')

    def h1(self, title, author):
        self.synth.append(title)
        h, _ = inline(title, self.curly, False, False)
        self.out.append('<h1 class="worktitle" id="work">%s</h1>' % h)
        if author:
            self.synth.append(author)
            self.synth_para.append(author)
            a, _ = inline(author, self.curly, False, False)
            self.pcount += 1
            self.out.append('<p class="noindent" data-p="%d">%s</p>'
                            % (self.pcount, a))

    def heading(self, level, label, title, srctext):
        self.head_src.append(srctext)
        if level == "part":
            self.counters["part"] += 1
            hid = "pt%02d" % self.counters["part"]
            tag, cls = "h2", "part"
        elif level == "chapter":
            self.counters["chapter"] += 1
            self.counters["sub"] = 0
            hid = "ch%03d" % self.counters["chapter"]
            tag, cls = "h2", "chapter"
        else:
            self.counters["sub"] += 1
            base = ("ch%03d" % self.counters["chapter"]
                    if self.counters["chapter"] else "front")
            hid = "%s-s%03d" % (base, self.counters["sub"])
            tag, cls = "h3", "subhead"

        title = (title or "").strip().strip("_").strip()
        disp = " ".join(x for x in (label, title) if x).strip()
        if label and title:
            disp = "%s. %s" % (label, title) if not label.endswith(".") \
                else "%s %s" % (label, title)
        h, _ = inline(disp, self.curly, False, False)
        self.out.append('<%s class="%s" id="%s" data-slug="%s">%s</%s>'
                        % (tag, cls, hid, _slug(disp), h, tag))

        node = {"id": hid, "level": {"part": 1, "chapter": 2, "subhead": 3}[level],
                "label": label, "title": title, "text": disp,
                "slug": _slug(disp), "children": []}
        if level == "part":
            self.toc.append(node)
            self._cur_chapter = None
        elif level == "chapter":
            if self.toc and self.toc[-1]["level"] == 1:
                self.toc[-1]["children"].append(node)
            else:
                self.toc.append(node)
            self._cur_chapter = node
        else:
            if self._cur_chapter is not None:
                self._cur_chapter["children"].append(node)
            elif self.toc:
                self.toc[-1]["children"].append(node)
            else:
                self.toc.append(node)
        return hid

    def html(self):
        return "\n".join(self.out)


# ---- 5h. play mode --------------------------------------------------------

SPEAKER_RX = re.compile(
    r"^([A-Z][A-Z0-9' .’-]{1,28}?)(\s*\[[^\]]{0,80}\])?\.\s+(\S.*)$", re.S)


def emit_play_block(em, b, body_indent):
    """The Vegetable: stage directions vs. speeches."""
    txt = join_lines(b.lines)
    stripped = txt.strip()
    if b.indent >= body_indent + 3:
        em.open("blockquote")
        em.p(stripped, cls="noindent")
        em.close("blockquote")
        return
    if re.fullmatch(r"CURTAIN\.?", stripped, re.I):
        em.p(stripped, cls="noindent")
        return
    m = SPEAKER_RX.match(stripped)
    if m and _is_allcaps(m.group(1)) and len(m.group(1)) >= 2:
        speaker = m.group(1) + (m.group(2) or "") + "."
        rest = m.group(3)
        em._keep(stripped)
        sp, _ = inline(speaker, em.curly, False, False)
        body, em.carry = inline(rest, em.curly, em.smallcaps, em.carry)
        em.pcount += 1
        em.out.append('<p class="noindent" data-p="%d">'
                      '<span class="smallcaps">%s</span> %s</p>'
                      % (em.pcount, sp, body))
        return
    em.p(stripped, cls="noindent")


# ---- 5i. reflow -----------------------------------------------------------

def join_lines(lines):
    """Unwrap a hard-wrapped paragraph.  Idempotent for single-line blocks."""
    out = ""
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not out:
            out = s
            continue
        if out.endswith("-") and not out.endswith("--"):
            out += s                     # soft hyphen join (none in this corpus)
        elif out.endswith("--") or out.endswith("—"):
            out += s
        else:
            out += " " + s
    return out


# ---- 5j. letters ----------------------------------------------------------

def is_letter_block(b, prev_block):
    t = b.text.strip()
    if len(t) < 20:
        return False
    if not SALUTATION_RX.match(t):
        return False
    if prev_block is None:
        return False
    if LETTER_INTRO_RX.search(prev_block.text.strip()):
        return True
    return bool(re.search(r"[:—-]\s*$", prev_block.text.strip()))


# --------------------------------------------------------------------------
# 6. top-level parse()
# --------------------------------------------------------------------------

def parse(path):
    doc = Doc(path)
    title, author, year = doc.meta()
    profile = detect_profile(doc)
    manifest, toc_used = harvest_manifest(doc)

    body_start = find_body_start(doc, manifest, toc_used)
    body_end = find_body_end(doc, body_start)

    # a Wikisource-style header block (title / author / translation credit)
    # belongs to the front matter even when the file has no headings at all
    if body_start < len(doc.blocks):
        b0 = doc.blocks[body_start]
        if _norm_key(b0.lines[0]) == _norm_key(title) and len(b0.lines) <= 4:
            body_start += 1

    front = doc.blocks[:body_start]
    body = doc.blocks[body_start:body_end]
    back = doc.blocks[body_end:]

    # body indent = modal indent of long (wrapped-prose) blocks
    inds = Counter(b.indent for b in body
                   if len(b.lines) >= 3 and max(len(l) for l in b.lines) > 55)
    body_indent = inds.most_common(1)[0][0] if inds else 0

    classify_blocks(doc, body, manifest, profile, body_indent)
    level = infer_levels(body)
    confirm_allcaps(body, level, manifest)
    level = infer_levels(body)
    merge_number_title(body, level)
    drop_repeated_heads(body, level)
    promote_group_heads(body, level)

    em = Emitter(profile["curly"], smallcaps=not profile["play"])
    em.h1(title, author)

    # ---- front matter -------------------------------------------------
    in_ad_list = False
    for bi, b in enumerate(front):
        if bi in toc_used or block_is_junk(b):
            doc.dropped.append(("front:apparatus", b.raw))
            continue
        # A Gutenberg producer credit runs several lines and only the FIRST one
        # says "Produced by"; testing just b.lines[0] let the whole block
        # through in Kipps and Boon. Test every line.
        if any(PRODUCER_RX.search(l) for l in b.lines):
            doc.dropped.append(("front:apparatus", b.raw))
            continue
        # "Books by H. G. Wells" heads an advertisement whose category headings
        # (SHORT STORIES / ROMANCES / NOVELS) and title lists are separate
        # blocks; keep dropping while the blocks still look like a list.
        if in_ad_list:
            if _list_shaped(b):
                doc.dropped.append(("front:boilerplate", b.raw))
                continue
            in_ad_list = False
        if AD_HEADER_RX.match(b.lines[0].strip()):
            in_ad_list = True
            doc.dropped.append(("front:boilerplate", b.raw))
            continue
        first = b.lines[0]
        if any(rx.match(first) for rx in FRONT_DROP_RX) or \
           any(rx.match(first) for rx in BACK_MATTER_RX):
            doc.dropped.append(("front:boilerplate", b.raw))
            continue
        if HRULE_RX.match(first) or SCENE_STARS_RX.match(first):
            doc.dropped.append(("front:rule", b.raw))
            continue
        if all(re.fullmatch(r"\s*(?:%s|\d{1,3})\.?\s*" % ROMAN, l)
               for l in b.lines):
            doc.dropped.append(("front:numeral-toc", b.raw))
            continue
        # drop title/author repetitions line by line (Wikisource headers)
        keep = [l for l in b.lines
                if _norm_key(l) not in ("", _norm_key(title),
                                        _norm_key(author or "\0"))]
        if len(keep) != len(b.lines):
            doc.dropped.append(
                ("front:titlepage",
                 "\n".join(l for l in b.lines if l not in keep)))
            if not keep:
                continue
            b = Block(keep, b.lineno)
            first = b.lines[0]
        t = b.text.strip()
        if _norm_key(t) == _norm_key(title) or (author and _norm_key(t) ==
                                                _norm_key(author)):
            doc.dropped.append(("front:titlepage", b.raw))
            continue
        if TRANSLATOR_RX.match(first):
            em.open("blockquote")
            for ln in b.lines:
                em.p(ln.strip(), cls="noindent")
            em.close("blockquote")
            continue
        if DEDICATION_RX.match(first) and len(b.text) < 200:
            em.open("blockquote")
            em.p(join_lines(b.lines), cls="noindent")
            em.close("blockquote")
            continue
        # Remaining front matter: keep only what a reader wants — an epigraph
        # or verse. Publisher imprints ("New York / THE MACMILLAN COMPANY /
        # 1924") and other-works advertisements have the same *shape* as an
        # epigraph, so shape alone was letting them through; discriminate on
        # whether the block reads as prose or verse rather than as a list.
        if not _front_worth_keeping(b):
            doc.dropped.append(("front:boilerplate", b.raw))
            continue
        if looks_verse(b, 0) or (len(b.lines) >= 2 and max(
                len(l.rstrip()) for l in b.lines) < 62):
            em.open("blockquote")
            for ln in b.lines:
                if ln.strip():
                    em.raw_line(ln.strip())
            em.close("blockquote")
        elif len(b.text) > 40:
            em.open("blockquote")
            em.p(join_lines(b.lines), cls="noindent")
            em.close("blockquote")
        else:
            doc.dropped.append(("front:stray", b.raw))

    # ---- body ----------------------------------------------------------
    open_quote = False
    after_break = True
    para_src = 0
    prev_live = None
    i = 0
    while i < len(body):
        b = body[i]
        k = b.kind

        if k in ("drop", "merged"):
            doc.dropped.append(("body:%s" % b.meta.get("why", k), b.raw))
            i += 1
            continue

        if k == "scenerule":
            em.rule()
            after_break = True
            i += 1
            continue

        if k == "hrule":
            nxt = body[i + 1] if i + 1 < len(body) else None
            if nxt is not None and nxt.kind == "head":
                doc.dropped.append(("body:chapter-rule", b.raw))
            else:
                em.rule()
                after_break = True
            i += 1
            continue

        if k == "head":
            h = b.meta["h"]
            lvl = h.get("forced_level") or level.get(h["type"], "subhead")
            label = ""
            if h["type"] in ("book",):
                label = "Book %s" % _roman_num(h["num"])
            elif h["type"] in ("part",):
                label = "Part %s" % _roman_num(h["num"])
            elif h["type"] == "act":
                label = "Act %s" % _roman_num(h["num"])
            elif h["type"] == "scene":
                label = "Scene %s" % _roman_num(h["num"])
            elif h["type"] == "chapter":
                word = "Case" if _RX_CASE.match(b.text.strip().split("\n")[0].strip()) else "Chapter"
                label = "%s %s" % (word, _roman_num(h["num"])) if h["num"] else word
            elif h["type"] == "sectword":
                label = "Section %s" % h["num"]
            elif h["type"] == "sectsign":
                label = "§ %d" % h["num"]
            elif h["type"] in ("numeric", "numtitle"):
                label = _roman_num(h["num"])
            elif h["type"] == "manifest":
                label = h.get("mlabel") or ""
            em.heading(lvl, label, h["title"], b.text)
            after_break = True
            prev_live = b
            i += 1
            continue

        if k == "verse":
            em.open("blockquote", coalesce=(prev_live is not None
                                            and prev_live.kind == "verse"))
            for ln in b.lines:
                if ln.strip():
                    em.raw_line(ln.strip())
            em.close("blockquote")
            after_break = False
            prev_live = b
            i += 1
            continue

        # prose paragraph -------------------------------------------------
        para_src += 1
        if profile["play"]:
            emit_play_block(em, b, body_indent)
            prev_live = b
            i += 1
            continue

        txt = join_lines(b.lines)
        if is_letter_block(b, prev_live):
            # gather the letter: this block plus following indented / sign-off ones
            group = [b]
            j = i + 1
            while j < len(body) and body[j].kind in ("para", "quote", "verse"):
                nb = body[j]
                if nb.indent >= b.indent and (
                        SIGNOFF_RX.match(nb.text.strip()) or nb.indent > body_indent
                        or len(nb.text) < 120):
                    group.append(nb)
                    j += 1
                    if SIGNOFF_RX.match(nb.text.strip()):
                        break
                else:
                    break
            em.out.append('<div class="letter">')
            for g in group:
                em.p(join_lines(g.lines), cls="noindent")
            em.out.append("</div>")
            para_src += len(group) - 1
            prev_live = group[-1]
            after_break = False
            i = j
            continue

        if k == "quote":
            em.open("blockquote")
            em.p(txt, cls="noindent")
            em.close("blockquote")
        else:
            cls = "noindent" if after_break else None
            em.p(txt, cls=cls)
        after_break = False
        prev_live = b
        i += 1

    # ---- back matter ----------------------------------------------------
    for b in back:
        doc.dropped.append(("back:matter", b.raw))

    kept = _visible(" ".join(em.text_kept))
    head_src = _visible(" ".join(em.head_src))
    stats = {
        "profile": profile,
        "blocks_total": len(doc.blocks),
        "blocks_front": len(front),
        "blocks_body": len(body),
        "blocks_back": len(back),
        "manifest_entries": len(manifest),
        "para_src": para_src,
        "para_html": em.pcount,
        "chapters": em.counters["chapter"],
        "parts": em.counters["part"],
        "kept_chars": len(kept),
        "head_chars": len(head_src),
        "dropped": [(r, len(_visible(t))) for r, t in doc.dropped],
        "dropped_text": doc.dropped,
        "level_map": level,
        "body_indent": body_indent,
    }
    return {"title": title, "author": author, "year": year,
            "toc": em.toc, "html": em.html(), "stats": stats,
            "_kept_text": kept, "_head_text": head_src,
            "_synth_para": _visible(" ".join(em.synth_para)),
            "_source": doc.source}


def _roman_num(n):
    if n is None:
        return ""
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
            (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
            (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


# --------------------------------------------------------------------------
# 7. CLI
# --------------------------------------------------------------------------

def _walk(root):
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f.endswith(".txt") and not f.startswith("00_"):
                yield os.path.join(dirpath, f)


def main(argv):
    """bookparse.py FILE_OR_DIR [--html DIR] [--json DIR]"""
    if len(argv) < 2:
        print(__doc__)
        return 1
    target = argv[1]
    outhtml = argv[argv.index("--html") + 1] if "--html" in argv else None
    outjson = argv[argv.index("--json") + 1] if "--json" in argv else None
    paths = list(_walk(target)) if os.path.isdir(target) else [target]
    for p in paths:
        r = parse(p)
        s = r["stats"]
        print("%-58s ch=%-4d pt=%-3d p=%-5d kept=%d"
              % (os.path.basename(p)[:58], s["chapters"], s["parts"],
                 s["para_html"], s["kept_chars"]))
        stem = _slug("%s %s" % (r["year"] or "", r["title"]), 80)
        if outhtml:
            os.path.isdir(outhtml) or os.makedirs(outhtml)
            with open(os.path.join(outhtml, stem + ".html"), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write("<!doctype html>\n<meta charset=\"utf-8\">\n"
                         "<title>%s</title>\n" % _html.escape(r["title"]))
                fh.write(r["html"])
        if outjson:
            import json
            os.path.isdir(outjson) or os.makedirs(outjson)
            with open(os.path.join(outjson, stem + ".json"), "w",
                      encoding="utf-8", newline="\n") as fh:
                json.dump({"title": r["title"], "author": r["author"],
                           "year": r["year"], "toc": r["toc"]}, fh,
                          ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
