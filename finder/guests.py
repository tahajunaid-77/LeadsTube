"""Guest search: finds podcast channels through the guests of podcasts you already have.

How it works
  1. Seed podcasts: podcast channels already in your leads (the ones you rated
     Good first, then by fit score; ones you rated Low are never used).
  2. Their episodes are read (titles + descriptions, 1 YouTube unit per 50
     episodes) and each guest's name is picked out:
       "... With Tim Klabunde"          (title)
       "Guest: Tim Klabunde"            (description)
       "ft. / feat. / featuring Name", "Episode 12 | Name", "Name: Title" ...
  3. Each guest is searched on YouTube ("Tim Klabunde" podcast, 100 units, the
     same as one keyword page). The channels that come back are checked exactly
     like any other search result (countries, active in the last 45 days,
     niche, ICP match, your ratings), so only channels in your ICP are saved.
     The guest is never checked: only the channels found have to fit.
  4. A guest is searched once, ever. A seed podcast is worked through guest by
     guest until all its guests are done; its episodes are re-read every 30
     days for new guests.

Memory: data/guest_search.json
  {"seeds": {channel_id: {"name", "read": date, "guests": [...]}},
   "searched": {guest name (lower case): {"date", "from", "found"}}}
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from settings import DATA_DIR
import icp

GUEST_FILE = DATA_DIR / "guest_search.json"
EPISODE_PAGES_MAX = 20          # read up to 1,000 episodes per seed podcast (20 units)
SEED_REREAD_DAYS = 30           # look for new episodes / guests after this long
DICTIONARY_FILE = Path("/usr/share/dict/words")

NAME_WORD = r"(?:[A-Z][a-z]+(?:['’-][A-Z]?[a-z]+)?|(?:Mc|Mac|La|De|Di|Le|O['’])[A-Z][a-z]+)"
PERSON_NAME = rf"(?:Dr\.?[ \t]+)?{NAME_WORD}(?:[ \t]+[A-Z]\.)?(?:[ \t]+{NAME_WORD}){{1,2}}"   # on one line

# Where a guest's name appears in a title or description.
TITLE_PATTERNS = [
    re.compile(rf"\b(?:with|w/|ft\.?|feat\.?|featuring|guest)\s+({PERSON_NAME})", re.I),
    re.compile(rf"(?:^|[|–—:/~-]\s+)({PERSON_NAME})\s*(?=$|[|–—:/,(]|\s-\s)"),  # "Ep 12 | Tim Klabunde | Title", "... / Kasi Phillips, GTEC"
    re.compile(rf"\b(?i:meet)\s+({PERSON_NAME})\b"),                                     # "Meet Aidan Connolly of ..."
    re.compile(rf"^({PERSON_NAME})\s+(?:on|shares|explains|talks|reveals|discusses)\b"),
]
DESCRIPTION_PATTERNS = [
    re.compile(rf"(?im)^\W*(?:today'?s\s+|special\s+|my\s+|our\s+|featured\s+)?guests?\s*[:\-–—]\s*({PERSON_NAME})"),
    re.compile(rf"\b(?:sits down with|joined by|welcomes?|interview(?:s|ing)?|speaks with|talks with|"
               rf"chats with|conversation with)\s+(?:guest\s+|author\s+|CEO\s+|expert\s+)?({PERSON_NAME})"),
]

# Words that are never (part of) a guest's name.
STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "at", "by", "with", "from", "your", "you",
    "our", "my", "his", "her", "their", "this", "that", "how", "why", "what", "when", "who", "is", "are",
    "episode", "ep", "part", "season", "podcast", "show", "live", "interview", "special", "bonus", "replay",
    "leadership", "leader", "leaders", "coach", "coaching", "ceo", "founder", "author", "expert", "team",
    "business", "success", "growth", "culture", "career", "work", "life", "money", "sales", "marketing",
    "new", "best", "top", "real", "true", "great", "good", "big", "first", "last", "next", "more", "less",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february",
    "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
    "america", "american", "united", "states", "new york", "london", "canada", "australia", "youtube",
    "meet", "website", "book", "linkedin", "facebook", "instagram", "spotify", "apple", "google", "amazon", "chatgpt", "ai",
}
_dictionary = None


def _dictionary_words():
    """{"names": capitalised words (Tim, Sarah...), "everyday": lower-case words}
    from the macOS word list; empty when it isn't there."""
    global _dictionary
    if _dictionary is None:
        try:
            words = DICTIONARY_FILE.read_text().split()
        except OSError:
            words = []
        _dictionary = {"names": {w for w in words if w[:1].isupper()}, "everyday": {w for w in words if w.islower()}}
    return _dictionary


def _everyday(word):
    """True for an ordinary English word, including plurals and -ing/-ed forms
    ("brands", "planning"); hyphenated words count when every part does."""
    everyday = _dictionary_words()["everyday"]
    for part in word.lower().split("-"):
        stems = {part}
        for ending, replacement in (("s", ""), ("es", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"),
                                    ("ers", ""), ("er", ""), ("ies", "y")):
            if part.endswith(ending) and len(part) > len(ending) + 2:
                stems.add(part[: -len(ending)] + replacement)
        if not stems & everyday:
            return False
    return True


def _clean_name(raw, host_words):
    """'Dr. Tim Klabunde' -> 'Tim Klabunde', or '' when it isn't a person's name
    (a topic like 'Strategic Planning', or the host themselves)."""
    words = re.sub(r"^Dr\.?\s+", "", raw.strip()).split()
    words = [w for w in words if not re.fullmatch(r"[A-Z]\.", w)]        # drop middle initials
    if not 2 <= len(words) <= 3:
        return ""
    generic = STOP_WORDS | set(icp.items("generic words (never someone's name)"))
    if any(w.lower() in generic for w in words):
        return ""
    first, last = words[0], words[-1]
    if last.lower() in host_words and first.lower() in host_words:
        return ""                                                          # the host, not a guest
    # A real name: a known first name (Tim, Sarah), or words that aren't ordinary
    # English ("Kasi Phillips", "Daniil Kurilov"); not "Strategic Planning".
    if first not in _dictionary_words()["names"] and (_everyday(first) or _everyday(last)):
        return ""
    return " ".join(words)


def guests_in(title, description, host_words=frozenset()):
    """Guest names in one episode's title and description, best evidence first."""
    found = []
    for pattern in TITLE_PATTERNS:
        found += [m.group(1) for m in pattern.finditer(title or "")]
    for pattern in DESCRIPTION_PATTERNS:
        found += [m.group(1) for m in pattern.finditer((description or "")[:3000])]
    out = []
    for raw in found:
        name = _clean_name(raw, host_words)
        if name and name.lower() not in (n.lower() for n in out):
            out.append(name)
    return out[:2]          # an episode rarely has more than two guests


def _host_words(seed):
    """Words naming the host/show (never treated as a guest)."""
    text = f"{seed.get('channel_name', '')} {seed.get('description', '')[:400]}"
    return frozenset(w.lower() for w in re.findall(r"[A-Za-z]{3,}", text))


def load_state():
    try:
        state = json.loads(GUEST_FILE.read_text())
    except (FileNotFoundError, ValueError):
        state = {}
    state.setdefault("seeds", {})
    state.setdefault("searched", {})
    return state


def save_state(state):
    GUEST_FILE.parent.mkdir(exist_ok=True)
    tmp = GUEST_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(GUEST_FILE)


def seed_podcasts(rows, ratings):
    """Podcast channels to read guests from: rated Good first, then by fit score.
    Channels you rated Low are left out."""
    def is_podcast(r):
        return r.get("content_type") == "Podcast" or bool(r.get("podcast"))
    seeds = [r for r in rows if is_podcast(r) and r.get("channel_id")
             and ratings.get(r.get("channel_link"), {}).get("rating") != "low"]
    rank = {"good": 0, "medium": 1}
    seeds.sort(key=lambda r: (rank.get(ratings.get(r.get("channel_link"), {}).get("rating"), 2),
                              -int(r.get("fit_score") or 0)))
    return seeds


class GuestPlanner:
    """Hands out the next guest to search, working through the seed podcasts in order."""

    def __init__(self, yt, seeds, state=None):
        self.yt = yt
        self.seeds = seeds
        self.state = state if state is not None else load_state()
        self.queue = []                 # [(guest, seed name, seed channel id)]
        self.seed_index = 0
        self.searches = 0
        self.kept = 0

    def _read_episodes(self, seed):
        """All episode titles + descriptions of one podcast (newest first)."""
        uploads = "UU" + seed["channel_id"][2:]
        episodes, token = [], ""
        for _ in range(EPISODE_PAGES_MAX):
            params = dict(part="snippet", playlistId=uploads, maxResults=50)
            if token:
                params["pageToken"] = token
            data = self.yt.get("playlistItems", 1, **params)
            for item in data.get("items", []):
                sn = item.get("snippet", {})
                episodes.append((sn.get("title", ""), sn.get("description", "")))
            token = data.get("nextPageToken", "")
            if not token:
                break
        return episodes

    def _guests_of(self, seed):
        """Guests of one seed podcast, reading its episodes when they're new or stale."""
        record = self.state["seeds"].get(seed["channel_id"])
        stale = not record or record.get("read", "") < (datetime.now() - timedelta(days=SEED_REREAD_DAYS)).strftime("%Y-%m-%d")
        if stale:
            host = _host_words(seed)
            names = []
            for title, description in self._read_episodes(seed):
                for name in guests_in(title, description, host):
                    if name.lower() not in (n.lower() for n in names):
                        names.append(name)
            record = {"name": seed.get("channel_name", ""), "read": datetime.now().strftime("%Y-%m-%d"), "guests": names}
            self.state["seeds"][seed["channel_id"]] = record
            save_state(self.state)
        return record["guests"]

    def next_guest(self):
        """(guest name, seed podcast name, seed channel id), or None when every
        seed podcast's guests have been searched."""
        while not self.queue and self.seed_index < len(self.seeds):
            seed = self.seeds[self.seed_index]
            self.seed_index += 1
            searched = self.state["searched"]
            self.queue = [(g, seed.get("channel_name", ""), seed["channel_id"])
                          for g in self._guests_of(seed) if g.lower() not in searched]
        return self.queue.pop(0) if self.queue else None

    def search(self, guest, seed_name, seed_id):
        """Channel ids of videos that mention the guest with a podcast (one search page)."""
        data = self.yt.get("search", 100, part="snippet", q=f'"{guest}" podcast', type="video",
                           maxResults=50, relevanceLanguage="en")
        ids = [it.get("snippet", {}).get("channelId") for it in data.get("items", [])]
        self.searches += 1
        return [i for i in dict.fromkeys(ids) if i and i != seed_id]

    def record(self, guest, seed_name, kept):
        self.kept += kept
        self.state["searched"][guest.lower()] = {"date": datetime.now().strftime("%Y-%m-%d"),
                                                 "from": seed_name, "found": kept}
        save_state(self.state)
