"""Learns from your own ratings (Good / Medium / Low) in the dashboard.

What it learns
  * Which words, phrases and kinds of channel your Good leads share, and which
    ones your Low leads share. It reads the channel description and the titles
    of videos posted in the last 30 days (full weight) and the channel name
    (low weight). Every lead's fit score gets a "your ratings"
    adjustment (up to +/-25) from that.
  * Which search phrases found your Good leads, so the next searches read those
    phrases deeper (and skip phrases that only bring Low leads).
  * New channels that look like your Low leads are skipped during searches.

Files
  data/ratings.json        your ratings: { channel_link: {"rating": "good"|"medium"|"low", "date": ...} }
  data/learned_model.json  what was learned (rebuilt after every rating change)

Run by the dashboard after you rate; by hand:
  .venv/bin/python finder/learning.py --rescore
"""

import json
import math
import os
import re
import sys
from datetime import datetime

from settings import DATA_DIR
import semantic

RATINGS_FILE = DATA_DIR / "ratings.json"
MODEL_FILE = DATA_DIR / "learned_model.json"
VALUE = {"good": 1.0, "medium": 0.5, "low": 0.0}
MIN_RATINGS = 8            # learning switches on after this many ratings ...
MIN_EACH_SIDE = 2          # ... with at least 2 Good and 2 Medium/Low
FULL_CONFIDENCE_AT = 40    # adjustments reach full strength after 40 ratings
MAX_ADJUST = 25
SKIP_BELOW = -15           # during searches, skip new channels this unlike your Good leads

STOP = set("""the and for with you your our are was were this that from have has had not but all can will just
into about their them they his her she him who what when where how why which been being more most some such
than then there these those its it's also out get got one two new now very via www com http https youtube
channel channels video videos subscribe subscribed welcome here help helps helping each every over under
make makes made like what's i'm we're you're let's don't dont own way ways time times day days week weekly""".split())


def load_ratings():
    try:
        return json.loads(RATINGS_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return {}


# How much each part of a channel counts when learning (and when scoring).
SOURCE_WEIGHT = {
    "description": 1.0,     # what the channel says it's about (read in full)
    "recent_videos": 1.0,   # titles of videos posted in the last 30 days
    "name": 0.3,            # the channel name matters least
    "facts": 0.6,           # podcast or not, size, country, Shorts-only, email/LinkedIn
}


def _words(text):
    words = [w.strip("'-") for w in re.findall(r"[a-z][a-z'-]{2,}", (text or "").lower())]
    words = [w for w in words if w and w not in STOP]
    return set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}


def features(row, extra_text=""):
    """What a lead looks like, as {pattern: weight}: words and two-word phrases
    from the description and the last 30 days of video titles (full weight), the
    channel name (low weight) and a few channel facts."""
    recent = row.get("recent_videos") or row.get("latest_video_title") or ""
    # Video titles are split so a phrase never runs from one title into the next.
    video_words = set()
    for title in (recent + " | " + (extra_text or "")).split("|"):
        video_words |= _words(title)
    subs = int(row.get("subscribers") or 0)
    bucket = "under 1K" if subs < 1000 else "1K-10K" if subs < 10000 else "10K-100K" if subs < 100000 else "100K+"
    facts = {
        f"[{(row.get('content_type') or 'Videos').lower()}]",
        f"[{subs and bucket or 'subs hidden'} subscribers]",
        f"[country {row.get('country') or 'unknown'}]",
        "[posts Shorts only]" if row.get("activity") == "Shorts" else "[posts long videos]",
        "[has email]" if row.get("best_email") else "[no email]",
        "[has LinkedIn]" if row.get("linkedin") else "[no LinkedIn]",
    }
    out = {}
    for source, items in (("name", _words(row.get("channel_name"))), ("facts", facts),
                          ("description", _words(row.get("description"))), ("recent_videos", video_words)):
        w = SOURCE_WEIGHT[source]
        for f in items:
            out[f] = max(out.get(f, 0.0), w)   # a word in several places counts once, at its strongest
    return out


def train(rows, ratings=None):
    """Builds data/learned_model.json from your ratings and the leads they belong to."""
    ratings = load_ratings() if ratings is None else ratings
    by_link = {r.get("channel_link"): r for r in rows}
    rated = [(by_link[link], VALUE[v["rating"]]) for link, v in ratings.items()
             if link in by_link and v.get("rating") in VALUE]
    counts = {k: sum(1 for link, v in ratings.items() if link in by_link and v.get("rating") == k) for k in VALUE}
    active = len(rated) >= MIN_RATINGS and counts["good"] >= MIN_EACH_SIDE and \
        counts["medium"] + counts["low"] >= MIN_EACH_SIDE
    mean = sum(v for _, v in rated) / len(rated) if rated else 0.5

    total, seen, mass = {}, {}, {}
    for row, value in rated:
        for f, w in features(row).items():
            total[f] = total.get(f, 0.0) + (value - mean) * w
            mass[f] = mass.get(f, 0.0) + w
            seen[f] = seen.get(f, 0) + 1
    # A pattern needs to appear in 2+ rated leads; the +3 keeps rare ones gentle.
    weights = {f: total[f] / (mass[f] + 3) for f in total if seen[f] >= 2 and abs(total[f]) > 1e-9}
    weights = dict(sorted(weights.items(), key=lambda kv: -abs(kv[1]))[:600])

    # How good each search phrase's leads turned out (needs the 'found_by' column).
    phrase_stats = {}
    for row, value in rated:
        phrase = (row.get("found_by") or "").lower()
        if phrase:
            s = phrase_stats.setdefault(phrase, [0.0, 0])
            s[0] += value
            s[1] += 1
    phrases = {p: {"quality": round(t / n, 3), "rated": n} for p, (t, n) in phrase_stats.items()}

    # Calibrate: measure the signal across all leads so a typical lead moves ~±9
    # points and only clear look-alikes reach the ±25 limit.
    signal = sorted(abs(sum(weights.get(f, 0.0) * w for f, w in features(r).items())) for r in rows) if weights else []
    p80 = signal[int(0.8 * (len(signal) - 1))] if signal else 0
    scale = round(1 / p80, 4) if p80 > 1e-6 else 1.0

    # Meaning: the direction from your Low leads towards your Good leads, in the
    # model's "meaning space". Leads whose meaning points that way go up.
    meaning = None
    if active:
        vecs = semantic.lead_vectors([row for row, _ in rated])
        if vecs is not None:
            vals = [v for _, v in rated]
            direction = sum((val - mean) * vec for val, vec in zip(vals, vecs))
            norm = float((direction @ direction) ** 0.5)
            if norm > 1e-9:
                direction = direction / norm
                all_vecs = semantic.lead_vectors(rows)
                proj = sorted(abs(float(x)) for x in (all_vecs @ direction)) if all_vecs is not None else []
                p80m = proj[int(0.8 * (len(proj) - 1))] if proj else 0
                meaning = {"direction": [round(float(x), 5) for x in direction],
                           "scale": round(1 / p80m, 4) if p80m > 1e-6 else 1.0}
        semantic.save_cache()

    readable = lambda items: [f for f, _ in items][:12]
    model = {
        "active": active, "ratings": len(rated), "counts": counts, "mean": round(mean, 3),
        "needed": max(0, MIN_RATINGS - len(rated)),
        "scale": scale,
        "meaning": meaning,
        "weights": {f: round(w, 4) for f, w in weights.items()},
        "phrases": phrases,
        "likes": readable(sorted(((f, w) for f, w in weights.items() if w > 0), key=lambda kv: -kv[1])),
        "dislikes": readable(sorted(((f, w) for f, w in weights.items() if w < 0), key=lambda kv: kv[1])),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    MODEL_FILE.write_text(json.dumps(model, indent=1))
    _cache.update(model=model, mtime=MODEL_FILE.stat().st_mtime)
    return model


_cache = {"model": None, "mtime": None}


def load_model():
    try:
        mtime = MODEL_FILE.stat().st_mtime
    except FileNotFoundError:
        return None
    if _cache["mtime"] != mtime:
        try:
            _cache.update(model=json.loads(MODEL_FILE.read_text()), mtime=mtime)
        except ValueError:
            return None
    return _cache["model"]


def adjustment(row, extra_text="", model=None, vector=None):
    """Points to add to (or take off) a lead's fit score, from your ratings.
    Half from matching words, half from matching meaning (when the model is installed)."""
    model = model or load_model()
    if not model or not model.get("active"):
        return 0
    w = model["weights"]
    s = sum(w.get(f, 0.0) * weight for f, weight in features(row, extra_text).items())
    word_part = math.tanh(0.8 * s * model.get("scale", 1.0))
    total = word_part
    meaning = model.get("meaning")
    if meaning:
        vec = vector if vector is not None else semantic.lead_vector(row)
        if vec is not None:
            proj = sum(a * b for a, b in zip(vec, meaning["direction"]))
            total = 0.5 * word_part + 0.5 * math.tanh(0.8 * proj * meaning["scale"])
    confidence = min(1.0, model["ratings"] / FULL_CONFIDENCE_AT)
    return int(round(MAX_ADJUST * total * (0.5 + 0.5 * confidence)))


def phrase_factor(term, model=None):
    """How much to favour a search phrase (1.0 = neutral), from the ratings of the
    leads it found. Needs 2+ rated leads from that phrase."""
    model = model or load_model()
    if not model or not model.get("active"):
        return 1.0
    p = model.get("phrases", {}).get(term.lower())
    if not p or p["rated"] < 2:
        return 1.0
    return 0.4 + 1.2 * p["quality"]          # all-Low 0.4x ... all-Good 1.6x


def good_links():
    return {link for link, v in load_ratings().items() if v.get("rating") == "good"}


def _run_in_progress():
    lock = DATA_DIR / "run.lock"
    try:
        pid = int(lock.read_text().split()[0])
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import youtube_finder as yf
    rows = yf.load_master()
    model = train(rows)
    if "--rescore" in sys.argv and rows:
        if _run_in_progress():
            print("A search is running; it will use the new learning when it saves.")
        else:
            yf.rescore_master(rows)
    state = "on" if model["active"] else f"off (rate {model['needed']} more, with at least {MIN_EACH_SIDE} Good and {MIN_EACH_SIDE} Medium/Low)"
    print(json.dumps({"ok": True, "active": model["active"], "ratings": model["ratings"], "counts": model["counts"],
                      "message": f"Learning {state}."}))


if __name__ == "__main__":
    main()
