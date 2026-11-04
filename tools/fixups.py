# -*- coding: utf-8 -*-
"""Source-text repairs applied right after a Gutenberg download (fetch_gutenberg.py).

Nothing here changes wording. Each function only mends what keeps bookparse.py
from reading the book's structure: a table-of-contents row that does not match
its heading, footnote markers, a transcriber's picture line, title lines set in
mixed case that the parser cannot tell from prose. Every change is listed in the
author folder's 00_목록.txt.
"""
import re


def _bracket_note(t, marker_heading, note_first_words):
    """Turn `TITLE[1]` + `[1] note…` into `TITLE` + `[note…]`."""
    t = t.replace(marker_heading + "\n", marker_heading.rsplit("[", 1)[0] + "\n", 1)
    i = t.find("[1] " + note_first_words)
    if i >= 0:
        j = t.find("\n\n", i)
        note = t[i + 4:j].rstrip()
        t = t[:i] + "[" + note + "]" + t[j:]
    return t


def midst_of_life(t):
    # the TOC spells one title differently from the body: no manifest match,
    # so the parser demoted the story to a subheading of the one before it
    t = t.replace("A LADY FROM RED HORSE    ", "A LADY FROM REDHORSE     ", 1)
    # the first part heading is not in the TOC; the second (CIVILIANS) is
    t = t.replace("\nCONTENTS\n\n\nA HORSEMAN IN THE SKY", "\nCONTENTS\n\n\nPREFACE TO THE FIRST EDITION\n\nSOLDIERS\n\nA HORSEMAN IN THE SKY", 1)
    # the preface stands before the TOC, where the parser takes it for the
    # title page and loses its heading: move it after the TOC, one-line title
    i, j = t.find("PREFACE\nTO THE FIRST EDITION"), t.find("CONTENTS")
    if 0 <= i < j:
        pref = "PREFACE TO THE FIRST EDITION\n\n" + t[i:j].strip("\n").split("\n\n", 1)[1]
        t = t[:i] + t[j:]
        t = t.replace("\nSOLDIERS\n\n\n\n\nA HORSEMAN IN THE SKY",
                      "\n" + pref + "\n\n\n\n\nSOLDIERS\n\n\n\n\nA HORSEMAN IN THE SKY", 1)
    # the one footnote (co-authorship of "Brownville"): marker off the title,
    # the note itself kept as a bracketed paragraph under it
    t = _bracket_note(t, "AN ADVENTURE AT BROWNVILLE[1]", "This story was written")
    return t


def can_such_things_be(t):
    t = re.sub(r"\n[ \t]*\[Picture:[^\]]*\]\n", "\n", t)
    # footnote {252} on a title: the note moves under the title in brackets,
    # and the FOOTNOTES block at the end (which also repeated the Gertrude
    # note that already stands in the body) goes
    t = t.replace("JOHN MORTONSON’S FUNERAL {252}\n",
                  "JOHN MORTONSON’S FUNERAL\n\n"
                  "[Rough notes of this tale were found among the papers of the late\n"
                  "Leigh Bierce.  It is printed here with such revision only as the author\n"
                  "might himself have made in transcription.]\n", 1)
    i = t.rfind("\nFOOTNOTES\n")
    if i > 0:
        t = t[:i].rstrip("\n") + "\n"
    t = t.replace("\nGertrude was the late Mrs. Manton, sister to Mr. Brewer.\n",
                  "\n[Gertrude was the late Mrs. Manton, sister to Mr. Brewer.]\n", 1)
    return t


def fantastic_fables(t):
    """David Price's transcription sets every fable title in mixed case and lists
    248 of them in a Contents whose length defeats the parser's TOC harvester.
    So: drop the front matter and the Contents, and set the title lines in
    capitals, which the parser reads as headings on its own."""
    L = t.split("\n")
    start = next(i for i, l in enumerate(L) if l.startswith("A Moral Principle met a Material Interest"))
    pre = [l.strip() for l in L[:start] if l.strip()]
    ents = pre[pre.index("Contents:") + 1:]

    def key(s):
        return re.sub(r"[^a-z]", "", s.lower().replace(". . .", ""))
    keys = {key(e) for e in ents} - {""}

    # the body begins at the first title (set with leader dots in the source)
    k = start - 1
    while not L[k].strip():
        k -= 1
    body = L[k:]
    out = []
    for i, l in enumerate(body):
        s = l.strip()
        alone = (s and (i == 0 or not body[i - 1].strip())
                 and (i + 1 >= len(body) or not body[i + 1].strip()))
        if alone and key(s) in keys:
            s = s.replace(" . . .", "").rstrip(".")
            out.append(s.upper())
        else:
            out.append(l)
    t = "\n".join(out)
    # a three-line section heading: keep the title as the heading, the
    # descriptive subtitle as a line of its own
    t = t.replace("OLD SAWS WITH NEW TEETH\nCERTAIN ANCIENT FABLES APPLIED TO\nTHE LIFE OF OUR TIMES\n",
                  "OLD SAWS WITH NEW TEETH\n\nCertain ancient fables applied to the life of our times.\n", 1)
    return "FANTASTIC FABLES\n\nby Ambrose Bierce\n\n(1899)\n\n\n" + t.strip("\n") + "\n"


def negligible_tales(t):
    # a two-letter exclamation in the dramatic-form tale reads as a heading
    # when set in capitals; one small letter keeps it a line of dialogue
    return t.replace("\nS.E.--O, O!\n", "\nS.E.--O, o!\n", 1)


FIX = {
    "In the Midst of Life": midst_of_life,
    "Can Such Things Be": can_such_things_be,
    "Fantastic Fables": fantastic_fables,
    "Negligible Tales": negligible_tales,
}


def apply(title, text):
    f = FIX.get(title)
    return f(text) if f else text


def extract_header(title, year, stories):
    """Front matter for a part of a volume saved as a book of its own: the
    Contents list is what lets the parser recognise the story titles."""
    return "%s\n\nby Ambrose Bierce\n\n(%d)\n\n\nContents\n\n%s\n\n\n\n" % (
        title, year, "\n".join(" " + s.upper() for s in stories))
