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


# ---- Melville --------------------------------------------------------------

def moby_dick(t):
    """Three rows of the table of contents defeat the harvester: chapter 50's
    title holds a second sentence, and the rows for 56 and 57 wrap onto a
    second line. The table is never shown (the reader builds its own from
    the headings), so those rows are shortened. The body headings of 56 and
    57 wrap as well; they are joined onto one line, every word kept."""
    j = t.find("\nEpilogue\n") + len("\nEpilogue\n")
    toc, rest = t[:j], t[j:]
    toc = toc.replace("CHAPTER 50. Ahab’s Boat and Crew. Fedallah.",
                      "CHAPTER 50. Ahab’s Boat and Crew", 1)
    toc = toc.replace("CHAPTER 56. Of the Less Erroneous Pictures of Whales, and the True\n"
                      "Pictures of Whaling Scenes.",
                      "CHAPTER 56. Of the Less Erroneous Pictures of Whales", 1)
    toc = toc.replace("CHAPTER 57. Of Whales in Paint; in Teeth; in Wood; in Sheet-Iron; in\n"
                      "Stone; in Mountains; in Stars.",
                      "CHAPTER 57. Of Whales in Paint", 1)
    toc = toc.replace("CHAPTER 73. Stubb and Flask kill a Right Whale; and Then Have a Talk\n"
                      "over Him.",
                      "CHAPTER 73. Stubb and Flask Kill a Right Whale", 1)
    rest = rest.replace("CHAPTER 56. Of the Less Erroneous Pictures of Whales, and the True\n"
                        "Pictures of Whaling Scenes.",
                        "CHAPTER 56. Of the Less Erroneous Pictures of Whales, and the True "
                        "Pictures of Whaling Scenes.", 1)
    rest = rest.replace("CHAPTER 57. Of Whales in Paint; in Teeth; in Wood; in Sheet-Iron; in\n"
                        "Stone; in Mountains; in Stars.",
                        "CHAPTER 57. Of Whales in Paint; in Teeth; in Wood; in Sheet-Iron; in "
                        "Stone; in Mountains; in Stars.", 1)
    # the transcribers' note on their sources, which stands between the
    # contents and the text
    rest = re.sub(r"\nThis text is a combination of etexts,.*?\n\n", "\n", rest, count=1, flags=re.S)
    return toc + rest


def piazza_tales(t):
    # the publisher's imprint on the title page
    i, j = t.find("\nAuthor of “Typee,”"), t.find("\nContents\n")
    if 0 < i < j:
        t = t[:i] + "\n" + t[j:]
    # the ten sketches of The Encantadas carry two-line headings ("SKETCH
    # FIRST." / "THE ISLES AT LARGE."): one line, joined with a dash, since
    # a full stop inside the line would read as a sentence
    t = re.sub(r"\n(SKETCH [A-Z]+)\.\n([A-Z][^\n]*\.)\n", r"\n\1—\2\n", t)
    # the two signatures that close the deposition in Benito Cereno: one of
    # them is the story's own title, which the parser reads as a heading
    # again (even set beside the other on one line). They close the
    # deposition's last paragraph instead, as its final line.
    t = t.replace("Hospital de Sacerdotes.\n\nBENITO CERENO.\n\n\nDOCTOR ROZAS.\n",
                  "Hospital de Sacerdotes.\nBENITO CERENO.          DOCTOR ROZAS.\n", 1)
    return t


_TYPEE_ONES = ["ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
               "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN",
               "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
_TYPEE_TENS = {"TWENTY": 20, "THIRTY": 30, "FORTY": 40}


def _typee_number(word):
    if word in _TYPEE_ONES:
        return _TYPEE_ONES.index(word) + 1
    tens, _, ones = word.partition("-")
    return _TYPEE_TENS[tens] + (_TYPEE_ONES.index(ones) + 1 if ones else 0)


# words of the arguments that the body never prints in lower case, so the
# count below cannot judge them; and two names it never prints at all
_TYPEE_LOWER = {"attempting", "agrees", "oratory", "goose", "highway", "happens",
                "befalls", "displays", "unenlightened", "pond", "conceit", "monumental",
                "agile", "professor", "persecutions", "tabooing", "conferred", "feast",
                "subterfuge", "government", "warning", "inference", "equipages", "la"}
_TYPEE_UPPER = {"arva", "wai"}
_TYPEE_FIXED = [("feast of calabashes", "Feast of Calabashes"), ("South sea", "South Sea")]


def _sentence_case(arg, body):
    """A chapter argument set in capitals, re-set in sentence case: each
    dash-separated clause opens with a capital, and a word keeps its capital
    when the body of the book prints it with one inside a sentence (after a
    lower-case word) more often than it prints it in lower case anywhere."""
    def proper(low, cap):
        if low in _TYPEE_LOWER:
            return False
        if low in _TYPEE_UPPER:
            return True
        n_cap = len(re.findall(r"[a-z,;:]\s+%s\b" % re.escape(cap), body))
        n_low = len(re.findall(r"\b%s\b" % re.escape(low), body))
        if n_cap == 0 and n_low == 0:
            return len(low) > 2           # a name the book spells otherwise (Æsculapius)
        return n_cap > n_low

    def word(w, first):
        m = re.match(r"[A-Z’'-]+", w)
        if not m:
            return w
        core, parts = m.group(0), []
        for k, p in enumerate(core.split("-")):
            stem = re.split(r"[’']", p)[0]
            tail = p[len(stem):].lower()
            low = stem.lower()
            cap = low.capitalize()
            up = low == "i" or (first and k == 0) or proper(low, cap)
            parts.append((cap if up else low) + tail)
        return "-".join(parts) + w[len(core):]
    out = []
    for clause in arg.split("--"):
        ws = clause.split(" ")
        out.append(" ".join(word(w, k == 0) for k, w in enumerate(ws)))
    s = "--".join(out)
    for a, b in _TYPEE_FIXED:
        s = s.replace(a, b)
    return s


def typee(t):
    """Stedman's edition of 1892: his introduction goes (it is not Melville's)
    and the half-title with it. A contents list of two rows lets the parser
    read the preface and the sequel as chapters. The number-words of the
    chapter headings become numerals (the parser cannot read TWENTY-ONE).
    Each chapter's argument, set in capitals in the source, is re-set in
    sentence case and italics so that it reads as a paragraph and not as a
    heading; no word changes."""
    i, j = t.find("\nINTRODUCTION TO THE EDITION OF 1892\n"), t.find("\nCHAPTER ONE\n")
    pre, body = t[:i], t[j:]
    preface = pre[pre.find("\nPREFACE\n"):].strip("\n")
    body = re.sub(r"\nCHAPTER ([A-Z-]+)\n",
                  lambda m: "\nCHAPTER %d\n" % _typee_number(m.group(1)), body)
    body = re.sub(r"\nTHE STORY OF TOBY\n", "\n\n\n\nTHE STORY OF TOBY\n\n\n", body)

    def argument(m):
        arg = " ".join(l.strip() for l in m.group(2).strip("\n").split("\n"))
        return m.group(1) + "_" + _sentence_case(arg, body) + "_\n"
    body = re.sub(r"(\nCHAPTER \d+\n\n)((?:[A-Z][^\n]*\n)+)", argument, body)
    head = ("TYPEE\n\nby Herman Melville\n\n(1846)\n\n\nCONTENTS\n\n"
            "PREFACE\n\nTHE STORY OF TOBY\n\n\n\n\n")
    return head + preface + "\n\n\n\n" + body.strip("\n") + "\n"


_BILLY_CONTENTS = [
    "BILLY BUDD, FORETOPMAN", "OTHER PROSE PIECES", "DANIEL ORME", "COCK-A-DOODLE-DOO!", "THE TWO TEMPLES",
    "POOR MAN’S PUDDING AND RICH MAN’S CRUMBS", "THE HAPPY FAILURE, A STORY OF THE RIVER HUDSON",
    "THE FIDDLER", "THE PARADISE OF BACHELORS AND THE TARTARUS OF MAIDS", "JIMMY ROSE",
    "THE ’GEES", "I AND MY CHIMNEY", "THE APPLE-TREE TABLE, OR ORIGINAL SPIRITUAL MANIFESTATIONS",
    "UNDER THE ROSE", "THE MARQUIS DE GRANDVIN", "PORTRAIT OF A GENTLEMAN",
    "TO MAJOR JOHN GENTIAN, DEAN OF THE BURGUNDY CLUB", "JACK GENTIAN",
    "MAJOR GENTIAN AND COLONEL J. BUNKUM", "THE CINCINNATI", "FRAGMENT",
    "FRAGMENTS FROM A WRITING-DESK",
]


def billy_budd(t):
    """Weaver's Constable edition (1924), vol. XIII of the Standard Edition.
    The edition's title pages, the editor's note and the paged contents (whose
    rows carry magazine citations) are replaced by a plain contents list;
    the essay on Hawthorne goes (criticism, not fiction); two-line story
    titles are joined as the contents list itself prints them; the novel's
    title, printed twice, is kept once; the typographic rules go; and the
    editor's footnotes become bracketed paragraphs where they stand."""
    L = t.split("\n")
    start = next(i for i, l in enumerate(L) if l.strip() == "BILLY BUDD, FORETOPMAN")
    end = next(i for i, l in enumerate(L) if l.strip() == "Transcriber’s Notes")
    L = L[start:end]
    # the novel's own title block: title, then the sub-title as one line
    s1 = next(i for i, l in enumerate(L) if l.strip() == "WHAT BEFELL HIM IN THE YEAR OF")
    assert L[s1 + 1].strip() == "THE GREAT MUTINY, ETC."
    L[0:s1 + 2] = ["BILLY BUDD, FORETOPMAN", "", "WHAT BEFELL HIM IN THE YEAR OF THE GREAT MUTINY, ETC."]
    # the dedication, ten centred lines in the source, as three: the parser
    # takes a title followed only by short lines for a title page
    d0 = next(i for i, l in enumerate(L) if l.strip() == "DEDICATED")
    d1 = next(i for i, l in enumerate(L) if l.strip() == "‘UNITED STATES’")
    ded = [l.strip() for l in L[d0:d1 + 1] if l.strip()]
    assert len(ded) == 10
    L[d0:d1 + 1] = [" ".join(ded[0:4]), " ".join(ded[4:6]), " ".join(ded[6:10])]
    # the title printed a second time, where the narrative begins
    k = next(i for i, l in enumerate(L) if i > 3 and l.strip() == "BILLY BUDD, FORETOPMAN")
    del L[k]
    # the essay on Hawthorne
    a = next(i for i, l in enumerate(L) if l.strip() == "HAWTHORNE AND HIS MOSSES")
    b = next(i for i, l in enumerate(L) if l.strip() == "COCK-A-DOODLE-DOO!")
    del L[a:b]

    def after(i):
        """Index of the next non-blank line after i."""
        j = i + 1
        while j < len(L) and not L[j].strip():
            j += 1
        return j
    # two-line titles, as the contents list prints them
    out = []
    i = 0
    while i < len(L):
        s = L[i].strip()
        j = after(i)
        n = L[j].strip() if j < len(L) else ""
        if s == "THE HAPPY FAILURE" and n == "A STORY OF THE RIVER HUDSON":
            out.append("THE HAPPY FAILURE, A STORY OF THE RIVER HUDSON"); i = j + 1; continue
        if s == "THE APPLE-TREE TABLE" and n == "OR ORIGINAL SPIRITUAL MANIFESTATIONS":
            out.append("THE APPLE-TREE TABLE, OR ORIGINAL SPIRITUAL MANIFESTATIONS"); i = j + 1; continue
        if s == "END OF BOOK," and n.startswith("April 19, 1891"):
            out.append(" " * 40 + "END OF BOOK, " + n); i = j + 1; continue
        if re.fullmatch(r"-{5,}", s):
            i += 1; continue
        if re.fullmatch(r"Footnote \d+:", s):
            note = [s]
            i += 1
            while i < len(L) and (not L[i].strip() or L[i].startswith("  ")):
                if L[i].strip():
                    note.append(L[i].strip())
                elif i + 1 < len(L) and not L[i + 1].startswith("  "):
                    break
                i += 1
            out.append("[" + " ".join(note) + "]")
            continue
        out.append(L[i]); i += 1
    body = "\n".join(out).strip("\n")
    head = ("BILLY BUDD AND OTHER PROSE PIECES\n\nby Herman Melville\n\n(1924)\n\n\nCONTENTS\n\n"
            + "\n".join(" " + s for s in _BILLY_CONTENTS) + "\n\n\n\n\n")
    return head + body + "\n"


FIX = {
    "In the Midst of Life": midst_of_life,
    "Can Such Things Be": can_such_things_be,
    "Fantastic Fables": fantastic_fables,
    "Negligible Tales": negligible_tales,
    "Moby-Dick": moby_dick,
    "The Piazza Tales": piazza_tales,
    "Typee": typee,
    "Billy Budd and Other Prose Pieces": billy_budd,
}


def apply(title, text):
    f = FIX.get(title)
    return f(text) if f else text


def extract_header(title, year, stories):
    """Front matter for a part of a volume saved as a book of its own: the
    Contents list is what lets the parser recognise the story titles."""
    return "%s\n\nby Ambrose Bierce\n\n(%d)\n\n\nContents\n\n%s\n\n\n\n" % (
        title, year, "\n".join(" " + s.upper() for s in stories))
