"""Reads ICP.md (project root): the one place that describes who you're looking for.

Every list LeadTube uses to search, score and filter channels comes from there, so
changing your ICP means editing that file only. See ICP.md for the format.
"""

import re

from settings import ROOT

ICP_FILE = ROOT / "ICP.md"


class ICPError(Exception):
    pass


_cache = {"mtime": None, "sections": None}


def _key(title):
    """'## 17. Not my ICP: topics' -> 'not my icp: topics'"""
    return re.sub(r"^\d+\.\s*", "", title.strip().lstrip("#").strip()).lower()


def _sections():
    try:
        mtime = ICP_FILE.stat().st_mtime
    except FileNotFoundError:
        raise ICPError(f"{ICP_FILE} is missing. It describes your ideal lead; restore it to search.")
    if _cache["mtime"] != mtime:
        sections, current = {}, None
        for line in ICP_FILE.read_text().splitlines():
            if line.startswith("## "):
                current = _key(line)
                sections[current] = []
            elif current is not None:
                sections[current].append(line)
        _cache.update(mtime=mtime, sections=sections)
    return _cache["sections"]


def _section(name):
    sections = _sections()
    key = name.lower()
    if key not in sections:
        raise ICPError(f'ICP.md has no section "{name}". Add it back (see the other sections for the format).')
    return [l for l in sections[key] if not l.strip().startswith(">")]


def _spintax(text):
    m = re.search(r"\{([^{}]*)\}", text)
    if not m:
        return [text]
    return [x for opt in m.group(1).split("|") for x in _spintax(text[:m.start()] + opt + text[m.end():])]


def text(name):
    """A free-text section (e.g. the ideal lead), as one paragraph."""
    return " ".join(l.strip() for l in _section(name) if l.strip() and not l.startswith("#"))


def lines(name):
    """A one-item-per-line section (e.g. search phrases), '###' headings skipped."""
    return [l.strip() for l in _section(name) if l.strip() and not l.strip().startswith("#") and l.strip() != "---"]


def items(name):
    """A list section: comma or line separated, {a|b} expanded, lower case."""
    out = []
    for line in _section(name):
        line = line.strip()
        if not line or line.startswith("#") or line == "---":
            continue
        # split on commas that are not inside {...}
        depth, part = 0, ""
        for ch in line:
            depth += ch == "{"
            depth -= ch == "}"
            if ch == "," and depth == 0:
                out += _spintax(part.strip())
                part = ""
            else:
                part += ch
        out += _spintax(part.strip())
    return list(dict.fromkeys(i.lower() for i in out if i.strip()))


def _alternation(words, prefix):
    pats = []
    for w in sorted(words, key=len, reverse=True):
        star = w.endswith("*")
        w = w.rstrip("*").strip()
        pat = r"\s+".join(re.escape(part) for part in w.split())
        if star and not prefix:
            pat += r"\w*"
        pats.append(pat)
    return "|".join(pats)


def word_re(name):
    """Whole-word match for a list section (`*` = any ending)."""
    return re.compile(r"\b(?:" + _alternation(items(name), prefix=False) + r")\b")


def prefix_re(name):
    """Match at the start of a word (e.g. 'consult' also matches 'consultant')."""
    return re.compile(r"\b(?:" + _alternation(items(name), prefix=True) + ")")


def prefix_words(name):
    return [w.rstrip("*").strip() for w in items(name)]


def swaps(name="word swaps for deeper search"):
    """[(word, [alternatives])] from 'word: alt, alt' lines."""
    out = []
    for line in _section(name):
        if ":" in line and not line.strip().startswith("#"):
            word, alts = line.split(":", 1)
            alts = [a.strip().lower() for a in alts.split(",") if a.strip()]
            if word.strip() and alts:
                out.append((word.strip().lower(), alts))
    return out
