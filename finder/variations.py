"""Deeper search: more search phrases that mean the same as yours.

Sources (no YouTube quota is used here):
  1. YouTube's own search suggestions (what people really type after your phrases),
  2. word swaps inside your niche (coach -> mentor / advisor / consultant ...).
Every new phrase must pass the niche word rules AND be close in meaning to your
ICP (ICP.md), so the extra searches stay on your ideal leads. The word swaps,
useful words and phrases-that-are-not-leads lists are also in ICP.md.

Saved to data/variation_keywords.txt (refreshed once a week, at most 40 phrases).
Searches use them next to your search phrases (ICP.md) and the learned phrases.
"""

import json
import re
import ssl
import statistics
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from settings import DATA_DIR
import icp
import semantic

VARIATIONS_FILE = DATA_DIR / "variation_keywords.txt"
REFRESH_DAYS = 7
MAX_VARIATIONS = 40
MAX_SEEDS = 36

# Phrases that find people learning to coach, jobs, or courses: not your leads.
PODCAST_LIKE = re.compile(r"\b(podcast|show|interviews?|episodes?|conversations?)\b")
# Phrases that find people learning to coach, jobs or courses (ICP.md, section 24),
# plus anything with a year in it.
NOT_A_LEAD = re.compile(icp.word_re("phrases that are not leads").pattern + r"|\b\d{4}\b")

# Words a YouTube suggestion may add to your phrase (people, places and languages it
# might add, like "raj shamani" or "hindi", are not leads).
USEFUL_MODIFIERS = set(icp.items("useful words in youtube suggestions"))   # ICP.md, section 23

SWAPS = icp.swaps()   # ICP.md, section 22


def _ua_request(url):
    return urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                                                              "AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"})


def _ssl_context():
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


_SSL = _ssl_context()


def youtube_suggestions(phrase):
    """What YouTube suggests after a phrase (free, no API quota). Only suggestions
    that add useful words (e.g. "for women", "new managers") are returned."""
    url = ("https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&q="
           + urllib.parse.quote(phrase))
    try:
        with urllib.request.urlopen(_ua_request(url), timeout=8, context=_SSL) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception:
        return []
    base = set(phrase.lower().split())
    out = []
    for s in data[1] if len(data) > 1 else []:
        if not isinstance(s, str):
            continue
        s = s.strip().lower()
        extra = [w for w in s.split() if w not in base]
        if 1 <= len(extra) <= 3 and all(w in USEFUL_MODIFIERS for w in extra):
            out.append(s)
    return out


def word_swaps(phrase):
    out = set()
    words = phrase.lower().split()
    for word, alts in SWAPS:
        if word in words:
            for alt in alts:
                if any(a in words for a in alt.split()):
                    continue                           # avoids "executive executive coach"
                new = " ".join(alt if w == word else w for w in words)
                clumsy = ("leader " in new and "leadership" in new) or " in executive" in new or "program" in new
                if len(set(new.split())) == len(new.split()) and not clumsy:
                    out.add(new)
    return out


def build(seeds, signature, niche_re, off_niche_re, known_signatures):
    """New phrases close to your ICP, best first."""
    # Half podcast, half other phrases; a different slice each week so every keyword gets a turn.
    seeds = list(dict.fromkeys(s.lower() for s in seeds))
    week = datetime.now().isocalendar()[1]
    picked = []
    for group in ([x for x in seeds if PODCAST_LIKE.search(x)], [x for x in seeds if not PODCAST_LIKE.search(x)]):
        if group:
            start = (week * (MAX_SEEDS // 2)) % len(group)
            picked += (group[start:] + group[:start])[:MAX_SEEDS // 2]
    seeds = picked
    with ThreadPoolExecutor(max_workers=4) as pool:
        suggested = [p for group in pool.map(youtube_suggestions, seeds) for p in group]
    candidates, seen = [], set(known_signatures)
    for p in suggested + [v for s in seeds for v in word_swaps(s)]:
        p = " ".join(p.replace("#", " ").split())
        n = len(p.split())
        if not (2 <= n <= 6) or not niche_re.search(p) or off_niche_re.search(p) or NOT_A_LEAD.search(p):
            continue
        sig = signature(p)
        if sig in seen:
            continue
        seen.add(sig)
        candidates.append(p)
    if not candidates:
        return []
    # Keep only phrases about as close to your ICP as your own keywords are.
    sims = semantic.phrase_icp_similarity(candidates)
    seed_sims = semantic.phrase_icp_similarity(seeds)
    if sims is None or seed_sims is None:
        return candidates[:MAX_VARIATIONS // 2]          # no meaning model: fewer, word rules only
    # Podcast and other phrases are judged against their own kind, and the list is
    # split about half and half (like your keywords).
    out = []
    for is_pod in (True, False):
        kind_seeds = [x for x, sd in zip(seed_sims, seeds) if bool(PODCAST_LIKE.search(sd)) == is_pod]
        bar = (statistics.median(kind_seeds) if kind_seeds else statistics.median(seed_sims)) - 0.02
        ranked = sorted(((s, p) for s, p in zip(sims, candidates) if bool(PODCAST_LIKE.search(p)) == is_pod and s >= bar),
                        reverse=True)
        out.append([p for _, p in ranked])
    pods, gens = out
    half = MAX_VARIATIONS // 2
    take_p = min(len(pods), max(half, MAX_VARIATIONS - len(gens)))
    take_g = min(len(gens), MAX_VARIATIONS - take_p)
    return pods[:take_p] + gens[:take_g]


def load(max_age_days=REFRESH_DAYS):
    """(phrases, is_fresh) from data/variation_keywords.txt."""
    if not VARIATIONS_FILE.exists():
        return [], False
    lines = VARIATIONS_FILE.read_text().splitlines()
    date = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("# updated:")), "")
    fresh = False
    try:
        fresh = datetime.now() - datetime.fromisoformat(date) < timedelta(days=max_age_days)
    except ValueError:
        pass
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")], fresh


def save(phrases):
    VARIATIONS_FILE.write_text(
        "# Extra search phrases that mean the same as your keywords (YouTube suggestions + word swaps),\n"
        "# checked against your ICP. Refreshed weekly. Delete any line you don't want.\n"
        f"# updated: {datetime.now().isoformat(timespec='seconds')}\n" + "\n".join(phrases) + "\n")
