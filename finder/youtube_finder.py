#!/usr/bin/env python3
"""
LeadTube: YouTube channel finder

1. Searches YouTube for every phrase in ICP.md (as channels and as
   recent videos) using the official YouTube Data API v3.
2. Keeps channels from your chosen countries that uploaded recently and talk
   about your niche.
3. Finds contact emails from:
     - the channel description,
     - the coach's own website (homepage + contact / about pages), found via
       the links on the channel's About section or in the description.
4. Saves this run's channels to a dated CSV and merges them into
   all_channels.csv, a master list that grows across runs without duplicates.

Searches already done in the last 7 days are skipped, so running it again
tomorrow continues with the phrases that ran out of quota today.

Run (from the project folder):
    .venv/bin/python finder/youtube_finder.py
Usually started from the dashboard. Keys are read from .env.
"""

import argparse
import atexit
import csv
import math
import html
import json
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

# Optional extras, installed automatically by start.command into .venv.
# The tool still works without them, just with fewer features.
try:
    import dns.resolver          # dnspython: checks an email's domain can receive mail
    import dns.exception
except ImportError:
    dns = None
try:
    import tldextract            # correct domain matching for .co.uk, .com.au ...
    _TLD = tldextract.TLDExtract(suffix_list_urls=())   # bundled list, no network needed
except ImportError:
    _TLD = None
try:
    from playwright.async_api import async_playwright  # real browser for JavaScript websites
except ImportError:
    async_playwright = None

API_BASE = "https://www.googleapis.com/youtube/v3/"
from settings import ROOT, DATA_DIR, RESULTS_DIR, ENV_FILE, env, set_env  # noqa: E402
import icp  # noqa: E402  (ICP.md: the one file that describes who you're looking for)
import learning  # noqa: E402  (learns from your Good / Medium / Low ratings)
import semantic  # noqa: E402  (meaning fingerprints; optional, needs fastembed)
import variations  # noqa: E402  (extra search phrases with the same meaning)

ICP_SKIP_BELOW = 0.55     # during searches, skip channels whose meaning is this far from your ideal lead (ICP.md)
# "How many" counts leads at this fit level or better (Find new leads -> Count).
FIT_GOALS = {"top": 75, "good": 55, "possible": 35}
FIT_GOAL_NAMES = {"top": "Top fit", "good": "Good fit or better", "possible": "Possible or better"}
# During the search emails aren't looked up yet; email, website and LinkedIn add up to ~20
# fit points later. This allowance stops good leads from being judged too harshly too early.
PRE_EMAIL_ALLOWANCE = 10
ICP_TYPICAL = 0.66        # a typical real lead; closer gets up to +8 fit points, further down to -8

SCRIPT_DIR = Path(__file__).resolve().parent  # finder/
RUN_PREFIX = "Search"                    # runs are named "Search 01", "Search 02", ...
SEARCH_LOG = DATA_DIR / "search_log.json"
MASTER_CSV = RESULTS_DIR / "all_channels.csv"
EXCLUDED_CSV = RESULTS_DIR / "excluded_channels.csv"   # removed as inactive / off-niche; never found again
RUN_HISTORY = RESULTS_DIR / "run_history.csv"

DEFAULT_COUNTRIES = "US, UK, Canada, Norway, Netherlands"
DEFAULT_DAYS = 45
DEFAULT_BUDGET = 9000          # of the 10,000 free daily units
DEFAULT_TARGET = 0             # new channels per run; 0 = as many as the quota budget allows
SEARCH_REPEAT_DAYS = 7         # a fully used-up search starts again from page 1 after this many days
MAX_PAGES_PER_SEARCH = 10      # YouTube rarely returns useful results past ~500
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# A channel is kept only if its name, description or recent video titles
# contain at least one of these (case-insensitive, matches word starts).
DEFAULT_MATCH_WORDS = icp.prefix_words("keep a channel only if it mentions")
# Channels mentioning one of these are marked "strong" in the niche_match column;
# the rest (e.g. sports or life coaches) are marked "weak" and listed after them.
STRONG_MATCH_RE = icp.word_re("strong-match words")

COUNTRY_NAMES = {
    "us": "US", "usa": "US", "united states": "US", "america": "US",
    "uk": "GB", "gb": "GB", "united kingdom": "GB", "britain": "GB", "england": "GB",
    "canada": "CA", "ca": "CA",
    "australia": "AU", "au": "AU",
    "new zealand": "NZ", "nz": "NZ",
    "ireland": "IE", "ie": "IE",
    "india": "IN", "in": "IN",
    "germany": "DE", "de": "DE",
    "france": "FR", "fr": "FR",
    "netherlands": "NL", "nl": "NL", "holland": "NL", "the netherlands": "NL",
    "norway": "NO", "no": "NO", "norge": "NO",
    "singapore": "SG", "sg": "SG",
    "uae": "AE", "united arab emirates": "AE", "ae": "AE",
    "south africa": "ZA", "za": "ZA",
}

# Bounded lengths (emails are short) keep matching fast even on pages with
# megabytes of embedded data; unbounded patterns can take hours on such text.
EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@"
                      r"[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,4}\.[A-Za-z]{2,12}(?![A-Za-z])")
OBFUSCATED_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]{1,64})\s{0,3}[\[\(]\s{0,3}at\s{0,3}[\]\)]\s{0,3}"
    r"([A-Za-z0-9-]{1,63})\s{0,3}[\[\(]\s{0,3}dot\s{0,3}[\]\)]\s{0,3}([A-Za-z]{2,12})",
    re.IGNORECASE,
)
MAX_TEXT_FOR_EMAILS = 1_500_000   # characters of a page that are scanned for emails
JUNK_EMAIL_PARTS = (
    "example.", "example@", "sample@", "johndoe@", "janedoe@", "domain.com",
    "flast@", "first.last", "firstlast@", "first_last", "firstname", "lastname", "f.last@",
    "jdoe@", "jsmith@", "first@", "last@", "john.doe", "jane.doe", "jane.d@", "john.d@",
    "@company.com", "@yourcompany", "@yourdomain", "@domain.", "@mysite", "@website.com", "you@", "your@",
    "your.name", "yourname@", "name@company", "jane@", "john@example",
    "johnsmith@", "john.smith@", "email.com", "yourname", "youremail", "name@", "user@",
    "sentry", "wixpress", "@wix", "godaddy", "squarespace", "noreply", "no-reply",
    "donotreply", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", "u003e",
)
# Addresses that belong to a platform/host, not the coach (podcast hosts, site builders...)
PLATFORM_EMAIL_DOMAINS = ("podchaser", "buzzsprout", "anchor.fm", "libsyn", "podbean", "captivate.fm",
                          "transistor.fm", "riverside.fm", "acast", "supportingcast", "megaphone",
                          "simplecast", "spreaker", "omny", "art19", "redcircle", "podcastics",
                          "wixpress", "squarespace.com", "kajabi.com", "linktr.ee", "beacons.ai",
                          "stan.store", "luma.com", "eventbrite", "zoom.us", "calendly.com",
                          "youtube.com", "google.com", "apple.com", "spotify.com", "amazon.com",
                          "metricool.com", "hootsuite.com", "buffer.com", "later.com", "canva.com",
                          "mailchimp.com", "hubspot.com", "convertkit.com", "kit.com", "substack.com",
                          "godaddy.com", "wordpress.com", "shopify.com", "sentry.io", "example.com",
                          "skool.com", "circle.so", "mn.co", "gumroad.com", "beehiiv.com", "teachable.com", "thinkific.com")
FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "hotmail.co.uk",
    "live.com", "live.ca", "msn.com", "yahoo.com", "yahoo.co.uk", "yahoo.ca",
    "icloud.com", "me.com", "mac.com", "aol.com", "protonmail.com", "proton.me",
    "zoho.com", "gmx.com", "btinternet.com", "rogers.com", "shaw.ca", "sympatico.ca",
}
# Shared inboxes worth contacting (kept, ranked after personal emails)
GOOD_ROLE_NAMES = {
    "info", "contact", "contactus", "hello", "hi", "hey", "team", "office",
    "enquiries", "enquiry", "inquiries", "inquiry", "connect", "booking", "bookings",
    "book", "coach", "coaching", "speaking", "media", "press", "partnerships",
    "partner", "business", "collab", "collabs", "work", "mail", "email",
}
# Generic inboxes kept only as a last resort, and only on the coach's own domain
# (small coaching businesses often publish just support@ or help@).
FALLBACK_ROLE_NAMES = {"support", "help", "service", "services", "customerservice", "admin", "office1"}
# Department / system inboxes that never reach the coach (dropped)
BAD_LOCAL_WORDS = (
    "career", "job", "hiring", "recruit", "hr", "giving", "give", "donat", "fraud",
    "abuse", "privacy", "legal", "compliance", "gdpr", "dpo", "billing", "account",
    "invoice", "payment", "payable", "receivable", "finance", "order", "return",
    "refund", "shipping", "unsubscribe", "webmaster", "postmaster", "hostmaster",
    "admin", "root", "test", "security", "support", "help", "service", "prayer",
    "volunteer", "student", "alumni", "admission", "registrar", "ticket", "store",
    "shop", "sales", "marketing", "ads", "advert", "newsletter", "news", "editor",
    "feedback", "complaint", "noreply", "bounce", "mailer", "notification",
)
# Links on a channel that are never the coach's own website
NOT_A_WEBSITE = (
    "youtube.com", "youtu.be", "google.com", "linkedin.com", "facebook.com",
    "instagram.com", "twitter.com", "x.com", "tiktok.com", "threads.net",
    "pinterest.", "spotify.com", "apple.com", "podcasts.apple", "amazon.",
    "amzn.", "audible.", "patreon.com", "buymeacoffee", "paypal.", "discord.",
    "reddit.com", "medium.com", "substack.com", "bit.ly", "linktr.ee", "lnk.to",
    "skool.com", "circle.so", "mn.co", "gumroad.com", "beehiiv.com",
    "podbean.com", "buzzsprout.com", "anchor.fm", "libsyn.com", "simplecast.com", "captivate.fm",
    "transistor.fm", "spreaker.com", "acast.com", "podchaser.com", "redcircle.com", "audioboom.com",
    "goo.gl", "t.co", "wa.me", "whatsapp.", "calendly.com", "eventbrite.",
    "zoom.us", "gofundme", "goodreads.", "soundcloud.", "twitch.tv", "vimeo.com",
)
CONTACT_HINTS = ("contact", "about", "connect", "work-with", "workwithme", "hire",
                 "book", "speaking", "media", "press", "get-in-touch", "reach")


def make_ssl_context():
    """python.org Python on macOS ships without root certificates; fall back
    to certifi or the system bundle when the default store is empty."""
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca", 0) > 0:
        return ctx
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for bundle in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if Path(bundle).exists():
            return ssl.create_default_context(cafile=bundle)
    return ctx


SSL_CONTEXT = make_ssl_context()


class QuotaExceeded(Exception):
    pass


class BudgetReached(Exception):
    pass


class ApiError(Exception):
    pass


# ---------------------------------------------------------------- YouTube API

DAILY_QUOTA = 10_000
KEY_USAGE_FILE = DATA_DIR / "key_usage.json"


def quota_day():
    """YouTube quota resets at midnight US Pacific time."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    except Exception:
        return (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%d")


class YouTube:
    """YouTube Data API client. Each run uses ONE key: the one with the most
    quota left today. Only if that key runs out mid-run does it switch to the
    backup key for the rest of the run."""

    def __init__(self, keys, budget):
        self.keys = keys
        self.budget = budget
        self.units_used = 0
        self.day = quota_day()
        try:
            usage = json.loads(KEY_USAGE_FILE.read_text())
        except Exception:
            usage = {}
        self.usage = usage.get(self.day, {})
        self.idx = max(range(len(keys)), key=lambda i: (self.left(i), -i))
        self.switched = False
        self._lock = threading.Lock()   # several channels are checked at once
        self._tries = threading.local()  # network retries, per thread

    @staticmethod
    def label(key):
        return "key ..." + key[-4:]

    def left(self, i):
        return DAILY_QUOTA - self.usage.get(self.label(self.keys[i]), 0)

    @property
    def key(self):
        return self.keys[self.idx]

    def describe(self):
        main = "main" if self.idx == 0 else "backup"
        return f"{main} API key ({self.label(self.key)}, ~{max(0, self.left(self.idx))} units left today)"

    def save_usage(self):
        try:
            data = json.loads(KEY_USAGE_FILE.read_text())
        except Exception:
            data = {}
        data = {d: v for d, v in data.items() if d >= (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")}
        data[self.day] = self.usage
        KEY_USAGE_FILE.parent.mkdir(exist_ok=True)
        KEY_USAGE_FILE.write_text(json.dumps(data, indent=1, sort_keys=True))

    def _switch_key(self):
        others = [i for i in range(len(self.keys)) if i != self.idx and self.left(i) > 200]
        if not others:
            return False
        self.idx = max(others, key=self.left)
        self.switched = True
        print(f"  (API key ran out of today's quota; switching to the {self.describe()})")
        return True

    def get(self, endpoint, cost, **params):
        with self._lock:
            if self.units_used + cost > self.budget:
                raise BudgetReached()
            self.units_used += cost          # reserved now so parallel requests can't overshoot
        while True:
            with self._lock:
                key = self.key
            query = dict(params, key=key)
            url = API_BASE + endpoint + "?" + urllib.parse.urlencode(query)
            try:
                with urllib.request.urlopen(url, timeout=30, context=SSL_CONTEXT) as resp:
                    data = json.load(resp)
                self._tries.n = 0
                with self._lock:
                    name = self.label(key)
                    self.usage[name] = self.usage.get(name, 0) + cost
                return data
            except urllib.error.HTTPError as e:
                try:
                    err = json.load(e)["error"]
                    reason = (err.get("errors") or [{}])[0].get("reason", "")
                    message = err.get("message", "")
                except Exception:
                    reason, message = "", str(e)
                if reason in ("quotaExceeded", "dailyLimitExceeded"):
                    with self._lock:
                        self.usage[self.label(key)] = DAILY_QUOTA
                        switched = key != self.key or self._switch_key()   # another thread may have switched already
                    if switched:
                        continue
                    raise QuotaExceeded(message)
                if reason == "rateLimitExceeded":
                    raise QuotaExceeded(message)
                if e.code == 404:
                    return {"items": []}
                raise ApiError(f"{e.code} {reason}: {message}")
            except (urllib.error.URLError, ssl.SSLError, ConnectionError, TimeoutError) as e:
                # A dropped connection shouldn't end the whole run: retry a few times first.
                attempt = getattr(self._tries, "n", 0)
                if attempt < 3:
                    self._tries.n = attempt + 1
                    time.sleep(2 * (attempt + 1))
                    continue
                self._tries.n = 0
                raise ApiError(f"Network problem: {getattr(e, 'reason', e)}")


def page_token(page_index, per_page=50):
    """YouTube's page tokens only encode the starting position, e.g. 'CDIQAA'
    = result 50 (page 2), 'CGQQAA' = result 100 (page 3). Building them lets
    every search jump straight to the page it hasn't read yet, so page 1 is
    never re-read (and never paid for) twice."""
    import base64
    offset = page_index * per_page
    if offset <= 0:
        return ""
    varint = bytearray()
    while True:
        byte = offset & 0x7F
        offset >>= 7
        varint.append(byte | (0x80 if offset else 0))
        if not offset:
            break
    raw = bytes([0x08]) + bytes(varint) + bytes([0x10, 0x00])
    return base64.b64encode(raw).decode().rstrip("=")


def search_one_page(yt, term, country, search_type, published_after, token="", order="relevance"):
    """One page (up to 50 results). Returns (channel ids, next page token).
    `order` changes which channels YouTube returns for the same phrase:
    relevance, videoCount (most active channels), date (newest), viewCount."""
    params = dict(part="snippet", q=term, type=search_type, maxResults=50,
                  regionCode=country, relevanceLanguage="en", order=order)
    if search_type == "video":
        params["publishedAfter"] = published_after
    if token:
        params["pageToken"] = token
    data = yt.get("search", 100, **params)
    ids = [item.get("snippet", {}).get("channelId") for item in data.get("items", [])]
    return [i for i in ids if i], data.get("nextPageToken", "")


def search_channel_ids(yt, term, country, search_type, published_after, pages):
    ids = []
    token = None
    for _ in range(pages):
        params = dict(part="snippet", q=term, type=search_type, maxResults=50,
                      regionCode=country, relevanceLanguage="en")
        if search_type == "video":
            params["publishedAfter"] = published_after
        if token:
            params["pageToken"] = token
        data = yt.get("search", 100, **params)
        for item in data.get("items", []):
            cid = item.get("snippet", {}).get("channelId")
            if cid:
                ids.append(cid)
        token = data.get("nextPageToken")
        if not token:
            break
    return ids


def fetch_channels(yt, ids):
    channels = []
    for i in range(0, len(ids), 50):
        data = yt.get("channels", 1, part="snippet,statistics,contentDetails",
                      id=",".join(ids[i:i + 50]), maxResults=50)
        channels.extend(data.get("items", []))
    return channels


RECENT_VIDEO_DAYS = 30      # titles of videos posted in this window are saved and read
CHANNEL_WORKERS = 6         # channels checked at the same time during a search


def recent_uploads(yt, playlist_id):
    """Reads the channel's newest uploads (one request, 1 quota unit).
    Returns (latest upload datetime or None, newest 5 titles, [(datetime, video_id)],
             titles of videos posted in the last 30 days)."""
    data = yt.get("playlistItems", 1, part="snippet,contentDetails",
                  playlistId=playlist_id, maxResults=25)
    latest, titles, uploads, last_month = None, [], [], []
    since = datetime.now(timezone.utc) - timedelta(days=RECENT_VIDEO_DAYS)
    for item in data.get("items", []):
        title = item.get("snippet", {}).get("title", "")
        titles.append(title)
        stamp = item.get("contentDetails", {}).get("videoPublishedAt")
        if stamp:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            uploads.append((when, item.get("contentDetails", {}).get("videoId", "")))
            if when >= since and title and title not in ("Private video", "Deleted video"):
                last_month.append(title)
            if latest is None or when > latest:
                latest = when
    return latest, titles[:5], uploads, last_month


def join_titles(titles, limit=20):
    """Titles saved in one CSV cell, separated by ' | ' (pipes inside a title become '/')."""
    return " | ".join(" ".join(t.replace("|", "/").split()) for t in titles[:limit])


def iso_duration_seconds(text):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


REAL_VIDEO_SECONDS = 180   # Shorts and short clips don't count as activity


def video_durations(yt, video_ids):
    """{video_id: seconds} for up to any number of ids (1 unit per 50)."""
    ids, out = [v for v in dict.fromkeys(video_ids) if v], {}
    for i in range(0, len(ids), 50):
        data = yt.get("videos", 1, part="contentDetails", id=",".join(ids[i:i + 50]))
        for item in data.get("items", []):
            out[item["id"]] = iso_duration_seconds(item.get("contentDetails", {}).get("duration"))
    return out


MIN_SHORTS_FOR_ACTIVE = 3  # a Shorts-only channel needs this many in the window


def activity_check(yt, uploads, cutoff, durations=None):
    """(date, kind) of the channel's activity since cutoff, or (None, "").
    kind "Videos": at least one real video (over 3 minutes); date is the newest one.
    kind "Shorts": no real video, but 3+ Shorts / clips, so the channel posts
    regularly (its Videos tab may still look old). One or two stray clips on an
    otherwise dead channel don't count."""
    recent = [(when, vid) for when, vid in uploads if when >= cutoff and vid]
    if not recent:
        return None, ""
    if durations is None:
        durations = video_durations(yt, [vid for _, vid in recent])
    real = [when for when, vid in recent if durations.get(vid, 0) > REAL_VIDEO_SECONDS]
    if real:
        return max(real), "Videos"
    if len(recent) >= MIN_SHORTS_FOR_ACTIVE:
        return max(when for when, _ in recent), "Shorts"
    return None, ""


# ---------------------------------------------------------------- niche check

# Used to throw out channels that only matched because one word like "CEO" or
# "leader" appeared somewhere (news, magazines, gaming, churches, schools...).
NICHE_LEAD_RE = icp.word_re("core topic words")
# "a global leader in business journalism", "the leading provider of..." are company
# boasts, not leadership content.
NICHE_LEADER_BOAST_RE = re.compile(
    r"\b(?:global|world|world's|industry|market|thought|category|a|the|recognized|trusted|national|international)\s+"
    r"leaders?\s+(?:in|of|for|on)\b|\b(?:industry|local|world|community)\s+leaders\b"
    r"|\bleading\s+(?:provider|company|companies|brand|source|firm|platform|publisher|voice|expert|experts|organi[sz]ation|"
    r"manufacturer|supplier|distributor|agency|network|news|business|trade|edge)\b")
NICHE_CHURCH_RE = icp.word_re("not my icp: churches and ministries")
NICHE_MEDIA_RE = icp.word_re("not my icp: media, schools and companies")
NICHE_AUDIENCE_RE = icp.word_re("who they work with (any business setting)")
NICHE_SKILL_RE = icp.word_re("skills they teach")
NICHE_CRED_RE = icp.word_re("credentials")
BIG_MEDIA_SUBS = 1_000_000


def niche_check(name, description, titles="", subscribers=0):
    """(keep, reason). Looks at the channel's own name and description (not
    random video titles) for leadership / coaching / training / speaking for
    businesses."""
    own = f"{name} {description}".lower()
    strong = bool(FIT_ROLE_STRONG.search(f"{own} {titles}".lower()))
    lead = bool(NICHE_LEAD_RE.search(NICHE_LEADER_BOAST_RE.sub(" ", own)))
    role = bool(FIT_ROLE.search(own)) or bool(NICHE_CRED_RE.search(own))
    org, aud = bool(FIT_ORG_TOPICS.search(own)), bool(NICHE_AUDIENCE_RE.search(own))
    skill = bool(NICHE_SKILL_RE.search(own))
    if int(subscribers or 0) > BIG_MEDIA_SUBS and not strong:
        return False, "1M+ media brand"
    if NICHE_CHURCH_RE.search(own) and not (strong or (lead and aud)):
        return False, "church / ministry"
    # News, companies and off-niche topics need real leadership content, not a stray "leader".
    leadership = bool(re.search(r"\bleadership\b", NICHE_LEADER_BOAST_RE.sub(" ", own))) and \
        not re.search(r"\bleadership role\b", own)
    # A coach / consultant who works with executives or companies, or "leader" in the channel's own name.
    leadership = leadership or (role and aud) or bool(NICHE_LEAD_RE.search(name.lower()))
    if NICHE_MEDIA_RE.search(own) and not (strong or leadership):
        return False, "media, school or company"
    if FIT_OFF_NICHE.search(own) and not (strong or leadership):
        return False, "off-niche topic"
    if strong or lead or (role and (org or aud or skill)) or (org and aud) or (skill and aud):
        return True, ""
    return False, "no leadership / coaching signal"


# ---------------------------------------------------------------- web helpers

def fetch_page(url, timeout=15, max_bytes=2_000_000, attempts=3):
    """Returns (final_url, text) or (None, '') on failure. Network hiccups
    (DNS lookups failing, connections reset, timeouts) are retried, because
    home routers often drop lookups when many sites are checked at once.
    Sites that refuse automated visitors (403) are left alone."""
    req = urllib.request.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    })
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
                ctype = resp.headers.get("Content-Type", "")
                if "html" not in ctype and "text" not in ctype:
                    return None, ""
                raw = resp.read(max_bytes)
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.geturl(), raw.decode(charset, "ignore")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                time.sleep(2 + 2 * attempt)
                continue
            return None, ""
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt < attempts - 1:
                time.sleep(1.5 + 1.5 * attempt)
                continue
            return None, ""
        except Exception:
            return None, ""
    return None, ""


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []   # (href, link text)
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip().lower()))
            self._href = None


def email_kind(email):
    """'personal', 'role' (info@, contact@ ...) or '' for emails to drop."""
    local = email.split("@")[0]
    plain = re.sub(r"[^a-z]", "", local)
    if plain in GOOD_ROLE_NAMES or local in GOOD_ROLE_NAMES:
        return "role"
    if plain in FALLBACK_ROLE_NAMES:
        return "fallback"
    # whole-word check so names like chris@ or bishop@ aren't mistaken for hr@ / shop@
    tokens = [t for t in re.split(r"[._\-+\d]+", local) if t]
    if any(t.startswith(w) or (len(w) >= 5 and w in t) for t in tokens for w in BAD_LOCAL_WORDS):
        return ""
    # looks like a person: letters with optional . _ - separators and a few digits
    if re.fullmatch(r"[a-z]+(?:[._-]?[a-z]+){0,2}\d{0,4}", local) and len(plain) >= 2:
        return "personal"
    return ""


def same_brand(domain, site_domain):
    """True for two domains of the same business, e.g. milewalk.com and
    milewalkacademy.com (one name starts with the other, 6+ letters)."""
    if not domain or not site_domain:
        return False
    a = registered_domain(domain).split(".")[0]
    b = registered_domain(site_domain).split(".")[0]
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 6 and long_.startswith(short)


def registered_domain(host):
    """'mail.coach.co.uk' -> 'coach.co.uk' (falls back to the host itself)."""
    host = (host or "").lower().strip(".")
    if _TLD:
        try:
            ext = _TLD(host)
            if ext.domain and ext.suffix:
                return f"{ext.domain}.{ext.suffix}"
        except Exception:
            pass
    return host[4:] if host.startswith("www.") else host


def domain_matches(email_domain, site_domain):
    if site_domain and registered_domain(email_domain) == registered_domain(site_domain):
        return True
    return bool(site_domain) and (email_domain == site_domain or
                                  email_domain.endswith("." + site_domain) or
                                  site_domain.endswith("." + email_domain))


def clean_emails(candidates, site_domain="", name_tokens=()):
    """Keeps only contactable emails, best first: personal, then info@/contact@.

    site_domain: emails must be on this domain or a free provider (gmail...).
    name_tokens: for emails found in web search snippets, the address must
                 share a word with the channel/person name or be on site_domain.
    """
    seen, scored = set(), []
    for email in candidates:
        email = urllib.parse.unquote(email).strip().strip(".,;:'\"<>()[]").lower()
        if email.startswith("mailto:"):
            email = email[7:]
        email = email.split("?")[0]
        if not EMAIL_RE.fullmatch(email) or email in seen:
            continue
        if any(part in email for part in JUNK_EMAIL_PARTS):
            continue
        if any(p in email.split("@")[1] for p in PLATFORM_EMAIL_DOMAINS):
            continue
        seen.add(email)
        kind = email_kind(email)
        if not kind:
            continue
        local, domain = email.split("@", 1)
        free = domain in FREE_MAIL_DOMAINS
        on_site = domain_matches(domain, site_domain) or same_brand(domain, site_domain)
        if kind == "fallback" and not on_site:
            continue      # support@ / help@ only count on the coach's own domain
        if site_domain and not (on_site or free):
            continue
        if name_tokens and not on_site:
            # web-search emails: a personal mailbox must carry the name, and a
            # company address must be on a domain that carries the name
            # (stops e.g. a same-named politician's @state.gov address)
            if domain.endswith((".gov", ".edu", ".mil")) or ".gov." in domain:
                continue
            where = local if free else domain
            if not any(t in where for t in name_tokens):
                continue
        if kind == "role" and free:
            continue  # e.g. info1234@gmail.com style catch-alls are rarely the coach
        scored.append(({"personal": 0, "role": 1}.get(kind, 2), 0 if on_site else 1, email))
    scored.sort()
    return [e for _, _, e in scored]


# Generic words that can't identify a person/brand when matching emails to a name
COMMON_NAME_WORDS = {
    "coach", "coaches", "coaching", "leadership", "executive", "executives", "podcast",
    "official", "channel", "with", "group", "consulting", "academy", "media", "global",
    "leader", "leaders", "lead", "leading", "rise", "grow", "growth", "life", "team",
    "teams", "work", "business", "success", "mind", "mindset", "power", "high",
    "performance", "management", "manager", "managers", "career", "careers", "talk",
    "talks", "show", "world", "your", "from", "into", "that", "this", "best", "real",
    "inside", "partners", "partner", "solutions", "institute", "center", "centre",
    "network", "collective", "company", "corporate", "training", "development",
    "insights", "strategy", "purpose", "impact", "influence", "advantage", "human",
    "people", "culture", "online", "studio", "presents", "daily", "weekly", "club",
}


def name_tokens_for(*names):
    tokens = set()
    for name in names:
        for word in re.findall(r"[a-z]+", (name or "").lower()):
            if len(word) >= 4 and word not in COMMON_NAME_WORDS:
                tokens.add(word)
    return tuple(tokens)


def decode_cloudflare_email(hex_string):
    """Cloudflare 'email protection' writes emails as hex on the page; this
    turns them back into the address the page shows to every visitor."""
    try:
        data = bytes.fromhex(hex_string)
        return "".join(chr(b ^ data[0]) for b in data[1:])
    except Exception:
        return ""


def emails_in_text(text):
    text = html.unescape((text or "")[:MAX_TEXT_FOR_EMAILS])
    # long unbroken blobs (embedded images, fonts, data) can't contain a usable email
    text = re.sub(r"[A-Za-z0-9+/=]{400,}", " ", text)
    found = [decode_cloudflare_email(h) for h in
             re.findall(r'(?:data-cfemail="|/cdn-cgi/l/email-protection#)([0-9a-fA-F]{6,})', text)]
    text = text.replace("%40", "@").replace("&#64;", "@")
    found += EMAIL_RE.findall(text)
    found += [f"{a}@{b}.{c}" for a, b, c in OBFUSCATED_RE.findall(text)]
    return found


def bare_domain(url):
    host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _host_is(host, pattern):
    """'youtube.com' matches youtube.com and m.youtube.com, but 't.co' does NOT
    match 'resilientleadershipdevelopment.com'. Patterns ending in '.'
    (e.g. 'amazon.') match any country ending."""
    if pattern.endswith("."):
        return host.startswith(pattern) or ("." + pattern) in host
    return host == pattern or host.endswith("." + pattern)


def is_own_website(url):
    host = bare_domain(url)
    return bool(host) and "." in host and not any(_host_is(host, bad) for bad in NOT_A_WEBSITE)


def normalise_url(link):
    link = link.strip()
    if not link:
        return ""
    if not link.startswith(("http://", "https://")):
        link = "https://" + link
    return link


# ---------------------------------------------------------------- YouTube About page

_yt_lock = threading.Lock()
_yt_last = [0.0]


def channel_about_links(channel_url):
    """Links listed on the channel's public About section (no sign-in needed)."""
    with _yt_lock:  # be gentle with YouTube: at most ~2 page loads per second
        wait = 0.5 - (time.time() - _yt_last[0])
        if wait > 0:
            time.sleep(wait)
        _yt_last[0] = time.time()
    _, page = fetch_page(channel_url.rstrip("/") + "/about", timeout=20, max_bytes=3_000_000)
    if not page:
        return []
    links = re.findall(r'"link":\{"content":"([^"]+)"', page)
    for encoded in re.findall(r'redirect\?[^"]*?q=(https?%3A%2F%2F[^&"\\]+)', page):
        links.append(urllib.parse.unquote(encoded))
    out = []
    for link in links:
        link = normalise_url(link.encode().decode("unicode_escape", "ignore"))
        if link and link not in out:
            out.append(link)
    return out


# ---------------------------------------------------------------- website crawl

_robots_cache = {}
_robots_lock = threading.Lock()


def allowed_by_robots(url):
    parts = urllib.parse.urlparse(url)
    root = f"{parts.scheme}://{parts.netloc}"
    with _robots_lock:
        rp = _robots_cache.get(root)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        _, text = fetch_page(root + "/robots.txt", timeout=10, max_bytes=200_000)
        rp.parse(text.splitlines() if text else [])
        with _robots_lock:
            _robots_cache[root] = rp
    try:
        return rp.can_fetch(BROWSER_UA, url)
    except Exception:
        return True


class BrowserRenderer:
    """One headless Chromium shared by the whole run, rendering up to 4 pages
    at the same time. It runs in its own thread with an asyncio loop, and the
    email-lookup threads hand it URLs and wait for the HTML."""

    CONCURRENCY = 4

    def __init__(self):
        self._loop = None
        self._failed = async_playwright is None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._started = False
        self.pages_rendered = 0

    def available(self):
        return not self._failed

    def _thread(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._start())
            self._loop = loop
        except Exception:
            self._failed = True
            self._ready.set()
            return
        self._ready.set()
        loop.run_forever()

    async def _start(self):
        import asyncio
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(user_agent=BROWSER_UA, locale="en-US")

        async def block_heavy(route):
            if route.request.resource_type in ("image", "media", "font"):
                await route.abort()
            else:
                await route.continue_()
        await self._context.route("**/*", block_heavy)
        self._sem = asyncio.Semaphore(self.CONCURRENCY)

    async def _render(self, url):
        async with self._sem:
            page = await self._context.new_page()
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                if resp is not None and resp.status >= 400:
                    return None, ""
                try:
                    await page.wait_for_load_state("networkidle", timeout=2500)
                except Exception:
                    pass
                self.pages_rendered += 1
                return page.url, await page.content()
            except Exception:
                return None, ""
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

    def fetch(self, url, **_):
        import asyncio
        if self._failed:
            return None, ""
        with self._lock:
            if not self._started:
                self._started = True
                threading.Thread(target=self._thread, daemon=True).start()
        self._ready.wait(60)
        if self._failed or self._loop is None:
            return None, ""
        try:
            return asyncio.run_coroutine_threadsafe(self._render(url), self._loop).result(timeout=30)
        except Exception:
            return None, ""

    def close(self):
        import asyncio
        if self._loop is None or self._failed:
            return

        async def _shutdown():
            try:
                await self._browser.close()
                await self._pw.stop()
            except Exception:
                pass
        try:
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop).result(timeout=10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)


JS_SITE_MARKERS = ("wix.com", "wixstatic", "squarespace", "kajabi", "__next_data__", "data-reactroot",
                   "id=\"root\"", "id=\"app\"", "framerusercontent", "webflow", "showit", "gohighlevel",
                   "leadconnectorhq", "clickfunnels", "ng-version", "nuxt")


def looks_js_rendered(page_html):
    """True when a site probably fills in its content with JavaScript, so the
    quick read may have missed the contact details. Only these are re-opened
    in the browser, which keeps runs fast."""
    if not page_html:
        return False
    low = page_html[:600_000].lower()
    if any(m in low for m in JS_SITE_MARKERS):
        return True
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", low, flags=re.S)
    return len(text.split()) < 250


RENDERER = BrowserRenderer()

_mx_cache, _mx_lock = {}, threading.Lock()


def domain_accepts_mail(domain):
    """True if the domain has a mail server (MX record) or at least exists.
    Only a clear "this domain does not exist / has no mail setup" answer
    returns False; network hiccups count as True so good emails aren't lost."""
    if dns is None or domain in FREE_MAIL_DOMAINS:
        return True
    with _mx_lock:
        if domain in _mx_cache:
            return _mx_cache[domain]
    ok = True
    for attempt in range(2):
        try:
            dns.resolver.resolve(domain, "MX", lifetime=5)
            ok = True
            break
        except dns.resolver.NXDOMAIN:
            ok = False
            break
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            try:
                dns.resolver.resolve(domain, "A", lifetime=5)
                ok = True
            except dns.resolver.NXDOMAIN:
                ok = False
            except Exception:
                ok = True
            break
        except Exception:
            ok = True   # timeout etc.: don't punish the email for a flaky network
    with _mx_lock:
        _mx_cache[domain] = ok
    return ok


EMAIL_PLATFORM_DOMAINS = ("wix", "sentry", "squarespace", "godaddy", "shopify", "kajabi", "supportingcast",
                          "mailchimp", "hubspot", "wordpress", "wpengine", "cloudflare", "google",
                          "apple.com", "spotify", "amazon", "stripe", "paypal", "zoom.us", "calendly")
BIO_LINK_HOSTS = ("linktr.ee", "beacons.ai", "stan.store", "linkin.bio", "bio.link", "campsite.bio",
                  "tap.bio", "lnk.bio", "carrd.co", "hoo.be", "allmylinks.com", "solo.to", "msha.ke")


def is_bio_page(url):
    host = bare_domain(url)
    return any(host == h or host.endswith("." + h) for h in BIO_LINK_HOSTS)


def bio_page_details(url):
    """Link-in-bio pages (Linktree, Stan, Beacons...): emails shown there plus
    the outgoing links, which usually include the coach's real website."""
    final_url, page = fetch_page(url)
    if not page:
        return [], []
    parser = LinkParser()
    try:
        parser.feed(page)
    except Exception:
        pass
    emails = emails_in_text(page) + [h[7:] for h, _ in parser.links if h and h.lower().startswith("mailto:")]
    links = []
    for href, _ in parser.links:
        if href and href.startswith("http") and not is_bio_page(href) and href not in links:
            links.append(href)
    return clean_emails(emails), links


def find_website_emails(site_url, max_pages=5):
    """Visit the homepage plus up to 4 contact/about-style pages on the same
    site and return (emails, page_where_first_email_was_found)."""
    emails, source, _ = find_website_details(site_url, max_pages)
    return emails, source


def owner_tokens_for(row, description=""):
    """Words that identify the coach and their company: words from the channel
    name plus capitalised names in the description (e.g. 'Stephanie',
    'Wachman', 'Symetree'). Used to accept emails on a company domain that
    differs from the website, like stephanie@symetreestrat.com on
    stephaniewachman.com."""
    tokens = set(name_tokens_for(row.get("channel_name", "")))
    handle = row.get("channel_link", "").rsplit("@", 1)[-1] if "/@" in row.get("channel_link", "") else ""
    tokens |= set(t for t in name_tokens_for(re.sub(r"\d+", " ", handle)))
    for word in re.findall(r"\b[A-Z][a-zA-Z]{4,}\b", (description or "")[:600]):
        w = word.lower()
        if w not in COMMON_NAME_WORDS and w not in LEARN_STOP:
            tokens.add(w)
    return tuple(t for t in tokens if len(t) >= 4)


def _owner_email(email, owner_tokens):
    local, _, domain = email.partition("@")
    name_part = registered_domain(domain).split(".")[0]
    return any(t == local or local.startswith(t) or t in name_part for t in owner_tokens)


def _crawl_website(site_url, max_pages=5, fetch=None, owner_tokens=()):
    """Like find_website_emails, but also returns every outside link found on
    the pages it read (the footer usually links LinkedIn, Instagram...)."""
    fetch = fetch or fetch_page
    outside_links = []
    if not allowed_by_robots(site_url):
        return [], "", outside_links, False
    parts = urllib.parse.urlparse(site_url)
    if parts.path.strip("/"):
        # a deep link (e.g. /free-guide): start from the homepage instead
        site_url = f"{parts.scheme}://{parts.netloc}/"
    final_url, page = fetch(site_url)
    if not page:
        parts = urllib.parse.urlparse(site_url)
        if not parts.netloc.startswith("www."):  # some sites only answer on www.
            final_url, page = fetch(parts._replace(netloc="www." + parts.netloc).geturl())
    if not page:
        return [], "", outside_links, False
    domain = bare_domain(final_url)

    found, other_domain, any_other, source = [], [], [], ""

    def collect(text, url):
        nonlocal source
        parser = LinkParser()
        try:
            parser.feed(text)
        except Exception:
            pass
        mailtos = [urllib.parse.unquote(h[7:]).split("?")[0] for h, _ in parser.links
                   if h and h.lower().startswith("mailto:")]
        page_emails = emails_in_text(text)
        emails = clean_emails(page_emails + mailtos, domain)
        # Emails on another domain that clearly belong to this person or their
        # company (name or company name in the address) are trusted too.
        for e in clean_emails(page_emails + mailtos):
            if e in emails:
                continue
            if owner_tokens and _owner_email(e, owner_tokens):
                emails.append(e)            # clearly theirs (name / company in the address)
            elif e not in any_other:
                any_other.append(e)         # on their site, kept but ranked last
        if emails and not source:
            source = url
        for e in emails:
            if e not in found:
                found.append(e)
        # A clickable "email us" link on their own site is trusted even when the
        # address is on another domain (e.g. a company domain), unless it
        # belongs to a website platform.
        for e in clean_emails(mailtos):
            if e not in found and e not in other_domain and \
                    not any(p in e.split("@")[1] for p in EMAIL_PLATFORM_DOMAINS):
                other_domain.append(e)
                if not source:
                    source = url
        for href, _ in parser.links:
            if href and href.startswith("http") and bare_domain(href) != domain \
                    and href not in outside_links:
                outside_links.append(href)
        return parser.links

    links = collect(page, final_url)

    # pick contact-ish pages on the same site
    to_visit = []
    for href, text in links:
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = urllib.parse.urljoin(final_url, href).split("#")[0]
        if bare_domain(full) != domain:
            continue
        path = urllib.parse.urlparse(full).path.lower()
        if any(h in path or h in text for h in CONTACT_HINTS):
            if full not in to_visit and full.rstrip("/") != final_url.rstrip("/"):
                to_visit.append(full)
    # contact pages first, then about pages
    to_visit.sort(key=lambda u: 0 if "contact" in u.lower() else 1)

    for url in to_visit[: max_pages - 1]:
        if found or other_domain:
            break
        if not allowed_by_robots(url):
            continue
        _, text = fetch(url)
        if text:
            collect(text, url)
    # on-site emails first, then the coach's own other-domain emails, then
    # clickable "email us" links on another domain
    found.sort(key=lambda e: 0 if domain_matches(e.split("@")[1], domain) else 1)
    extra = [e for e in other_domain + any_other if e not in found]
    if not found and extra and not source:
        source = final_url
    return (found + list(dict.fromkeys(extra)), source, outside_links, looks_js_rendered(page))


# ---- Website memory: a site read recently isn't read again (re-runs are much faster).
SITE_CACHE_FILE = DATA_DIR / "site_checks.json"
SITE_CACHE_VERSION = 3          # bump when the email rules change, so every site is re-read once
SITE_RECHECK_DAYS = {True: 30, False: 14}   # site had an email: 30 days; no email: 14 days
_site_cache = {"data": None, "dirty": False, "lock": threading.Lock()}


def _site_cache_data():
    if _site_cache["data"] is None:
        try:
            data = json.loads(SITE_CACHE_FILE.read_text())
        except Exception:
            data = {}
        if data.get("version") != SITE_CACHE_VERSION:
            data = {"version": SITE_CACHE_VERSION, "sites": {}}
        _site_cache["data"] = data
    return _site_cache["data"]


def save_site_cache():
    with _site_cache["lock"]:
        if _site_cache["dirty"] and _site_cache["data"] is not None:
            SITE_CACHE_FILE.write_text(json.dumps(_site_cache["data"], separators=(",", ":")))
            _site_cache["dirty"] = False


atexit.register(save_site_cache)
atexit.register(semantic.save_cache)


def find_website_details(site_url, max_pages=5, owner_tokens=()):
    """Emails and outside links (LinkedIn, Facebook...) from a coach's website.
    A site read recently is answered from memory (data/site_checks.json)."""
    key = f"{bare_domain(site_url)}|{max_pages}"
    today = datetime.now()
    with _site_cache["lock"]:
        hit = _site_cache_data()["sites"].get(key)
    if hit:
        age = (today - datetime.fromisoformat(hit["date"])).days
        if age < SITE_RECHECK_DAYS[bool(hit["emails"])]:
            return list(hit["emails"]), hit["source"], list(hit["links"])
    emails, source, links = _read_website(site_url, max_pages, owner_tokens)
    with _site_cache["lock"]:
        _site_cache_data()["sites"][key] = {"date": today.strftime("%Y-%m-%d"), "emails": emails,
                                            "source": source, "links": links[:200]}
        _site_cache["dirty"] = True
    return emails, source, links


def _read_website(site_url, max_pages=5, owner_tokens=()):
    """Like find_website_emails, but also returns every outside link found on
    the pages it read (the footer usually links LinkedIn, Instagram...).
    If the quick read finds no email, the site is opened in a real browser
    (Playwright), which sees contact details that load with JavaScript."""
    emails, source, links, js_site = _crawl_website(site_url, max_pages, owner_tokens=owner_tokens)
    # Only JavaScript-built sites that loaded normally are re-opened in the
    # browser; plain sites were read fully already, and sites that refused the
    # quick visit (e.g. bot protection) are left alone.
    have_profiles = any(any(n in u.lower() for n in ("linkedin.com/", "facebook.com/", "instagram.com/"))
                        for u in links)
    if (not emails or not have_profiles) and js_site and RENDERER.available():
        r_emails, r_source, r_links, _ = _crawl_website(site_url, 2, fetch=RENDERER.fetch,
                                                        owner_tokens=owner_tokens)
        if r_emails and not emails:
            emails, source = r_emails, r_source
        links += [u for u in r_links if u not in links]
    return emails, source, links


# ---------------------------------------------------------------- web search (Serper.dev)



class WebSearch:
    """Google results through the Serper.dev API (2,500 free searches at signup).
    The snippets often show emails from Facebook pages, LinkedIn, podcast
    directories and speaker bureaus, without visiting those sites."""

    def __init__(self, key, limit):
        self.key = key
        self.limit = limit
        self.used = 0
        self.lock = threading.Lock()
        self.disabled_reason = ""

    def search(self, query, country="US"):
        with self.lock:
            if self.disabled_reason or self.used >= self.limit:
                return []
            self.used += 1
        body = json.dumps({"q": query, "num": 10,
                           "gl": {"GB": "uk"}.get(country, country.lower())}).encode()
        req = urllib.request.Request("https://google.serper.dev/search", data=body, headers={
            "X-API-KEY": self.key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429):
                self.disabled_reason = ("Serper key rejected or out of credits"
                                        if e.code != 429 else "Serper rate limit reached")
            return []
        except Exception:
            return []
        results = []
        kg = data.get("knowledgeGraph") or {}
        if kg:
            results.append((kg.get("website", ""), kg.get("title", ""),
                            " ".join(str(v) for v in (kg.get("attributes") or {}).values())
                            + " " + kg.get("description", "")))
        for item in data.get("organic", []):
            results.append((item.get("link", ""), item.get("title", ""), item.get("snippet", "")))
        return results


def load_serper_key(cli_value):
    if cli_value:
        return cli_value.strip()
    return env("SERPER_API_KEY").strip()


def short_name(channel_name):
    """'Michael King | Executive Coach & Keynote' -> 'Michael King'"""
    return re.split(r"\s[|\-–—:•]\s|\s\|", channel_name)[0].strip() or channel_name


PROFESSION_RE = icp.prefix_re("words that show their line of work")


# People-search / lead-database sites show guessed email *patterns*, not real addresses.
DATA_BROKER_SITES = ("rocketreach", "leadiq", "signalhire", "contactout", "zoominfo", "apollo.io",
                     "lusha", "hunter.io", "snov.io", "seamless.ai", "adapt.io", "rocketreach",
                     "datanyze", "kickbox", "voilanorbert", "clearbit", "salesintel", "6sense",
                     "uplead", "getprospect", "anymail", "skrapp", "emailhunter", "contactsout")


def search_for_email(searcher, row, site_domain):
    """Returns (emails, source, website_found)."""
    name = short_name(row["channel_name"])
    handle = row["channel_link"].rsplit("@", 1)[-1] if "/@" in row["channel_link"] else ""
    tokens = name_tokens_for(name, handle)
    if not tokens:
        return [], "", ""
    country = row.get("country", "US")
    website_found = ""
    queries = [f'"{name}" email', f'"{name}" contact email facebook OR linkedin OR instagram']
    # Their Facebook page often lists an email in its intro, and Google shows it
    # in the result snippet (the page itself needs a login, so it isn't opened).
    fb = row.get("facebook", "")
    slug = urllib.parse.urlparse(fb).path.strip("/").split("/")[0] if fb else ""
    if slug and slug.lower() not in ("profile.php", "pages", "people"):
        queries.insert(1, f'site:facebook.com/{slug} email')
    for query in queries:
        results = searcher.search(query, country if country != "unknown" else "US")
        if not results:
            continue
        for link, title, snippet in results:
            if any(b in link.lower() for b in DATA_BROKER_SITES):
                continue
            # the result itself must be about this channel/person, and about
            # their line of work (so a same-named musician or politician is ignored)
            text = f"{title} {snippet}".lower()
            on_their_site = (bool(site_domain) and site_domain in link.lower()) or \
                (bool(slug) and f"facebook.com/{slug.lower()}" in link.lower())
            if not on_their_site and (name.lower() not in text or
                                      not PROFESSION_RE.search(text)):
                continue
            emails = clean_emails(emails_in_text(f"{title} {snippet}"), site_domain, tokens)
            if emails:
                return emails, f"web search: {link}", website_found
        if not site_domain and not website_found:
            for link, title, _ in results:
                if is_own_website(link) and any(t in bare_domain(link) for t in tokens):
                    website_found = link
                    emails, where = find_website_emails(link)
                    if emails:
                        return emails, where, website_found
                    break
    return [], "", website_found


# Words in channel names that say nothing about who the owner is.
GENERIC_OWNER_WORDS = set(icp.items("generic words (never someone's name)"))


def _facebook_target(fb_url):
    """The part of a Facebook link worth searching for, e.g. 'facebook.com/coachannagibbs'
    or 'facebook.com/profile.php?id=123'."""
    if not fb_url:
        return ""
    p = urllib.parse.urlparse(fb_url if "//" in fb_url else "https://" + fb_url)
    path = p.path.strip("/")
    if path.startswith("profile.php") and "id=" in p.query:
        return f"facebook.com/profile.php?{p.query.split('&')[0]}"
    if path.startswith("people/"):
        parts = path.split("/")
        return f"facebook.com/{'/'.join(parts[:3])}" if len(parts) >= 3 else ""
    slug = path.split("/")[0]
    return f"facebook.com/{slug}" if slug and slug.lower() not in ("pages", "groups", "sharer", "share") else ""


def facebook_email_search(searcher, row, site_domain, description=""):
    """Many coaches list their email on Facebook (page intro, posts) but not on
    their website. Facebook pages need a login, so they aren't opened; instead
    Google's results for their Facebook page and name are read, and only an
    email that clearly belongs to the coach is kept.
    Returns (emails, source, facebook_link_found)."""
    name = short_name(row["channel_name"])
    handle = row["channel_link"].rsplit("@", 1)[-1] if "/@" in row.get("channel_link", "") else ""
    # Who the coach is: words from their channel name and @handle, plus their website's name.
    owner = {t for t in name_tokens_for(row.get("channel_name", ""), re.sub(r"\d+", " ", handle))
             if len(t) >= 4 and t not in GENERIC_OWNER_WORDS}
    if site_domain:
        stem = registered_domain(site_domain).split(".")[0]
        if len(stem) >= 5:
            owner.add(stem)
    owner = sorted(owner)
    if not owner:
        return [], "", ""
    target = _facebook_target(row.get("facebook", ""))
    country = row.get("country", "US")
    country = "US" if country in ("", "unknown") else country
    queries = ([f'"{target}" email'] if target else []) + [f'"{name}" facebook email']
    fb_found = ""

    def belongs_to_owner(email, link):
        local, _, domain = email.partition("@")
        if site_domain and (domain_matches(domain, site_domain) or same_brand(domain, site_domain)):
            return True
        if target and target.lower() in link.lower():        # on their own Facebook page
            return True
        name_part = registered_domain(domain).split(".")[0]
        return any(len(t) >= 4 and (local.startswith(t) or (len(t) >= 5 and t in local) or t in name_part)
                   for t in owner)

    for query in queries:
        for link, title, snippet in searcher.search(query, country) or []:
            low = link.lower()
            if any(b in low for b in DATA_BROKER_SITES):
                continue
            # Remember their Facebook page if we didn't have it.
            if not target and not fb_found and "facebook.com/" in low and not is_share_link(link):
                slug = _facebook_target(link).split("/", 1)[-1].lower()
                if any(t in slug.replace("-", "").replace(".", "") for t in owner):
                    fb_found = link.split("?")[0]
            # Off their own page/site, the result must also be about their line of work
            # (so a realtor or musician with the same name is ignored).
            own_place = (target and target.lower() in low) or (site_domain and site_domain in low)
            if not own_place and not PROFESSION_RE.search(f"{title} {snippet}".lower()):
                continue
            found = [e for e in clean_emails(emails_in_text(f"{title} {snippet}"), site_domain, owner)
                     if belongs_to_owner(e, link)]
            if found:
                return found, f"web search (Facebook): {link}", fb_found
    return [], "", fb_found


SOCIAL_PATTERNS = [
    ("facebook", ("facebook.com/", "fb.com/", "fb.me/")),
    ("instagram", ("instagram.com/", "instagr.am/")),
    ("twitter", ("twitter.com/", "//x.com/", ".x.com/")),
    ("tiktok", ("tiktok.com/",)),
    ("podcast", ("podcasts.apple.com/", "open.spotify.com/show", "spotify.com/show",
                 "podbean.com", "buzzsprout.com", "anchor.fm", "libsyn.com", "simplecast.com")),
    ("booking", ("calendly.com/", "acuityscheduling.com", "tidycal.com", "cal.com/")),
]
SOCIAL_FIELDS = [name for name, _ in SOCIAL_PATTERNS] + ["other_links"]


SHARE_LINK_PARTS = ("sharer", "/share", "share?", "intent/", "sharearticle", "/dialog/", "shareoffsite",
                    "/plugins/", "/tr?", "pinterest.com/pin/create", "/hashtag/", "/explore/",
                    "facebook.com/wix", "instagram.com/wix", "facebook.com/metricool", "instagram.com/metricool", "twitter.com/wix", "linkedin.com/company/wix",
                    "facebook.com/squarespace", "instagram.com/squarespace", "twitter.com/squarespace",
                    "facebook.com/kajabi", "instagram.com/kajabi", "facebook.com/shopify",
                    "facebook.com/godaddy", "facebook.com/wordpress", "twitter.com/wordpress")


def is_share_link(url):
    low = url.lower()
    if any(p in low for p in SHARE_LINK_PARTS):
        return True
    path = urllib.parse.urlparse(low).path.strip("/")
    return path in ("", "home", "login", "signup")   # bare facebook.com/ etc.


def social_links(urls):
    """Sorts a channel's links into facebook / instagram / twitter / tiktok /
    podcast / booking, plus every other non-YouTube link in other_links."""
    out = {name: "" for name in SOCIAL_FIELDS}
    others, keys = [], set()
    for u in urls:
        low = u.lower()
        if "youtube.com" in low or "youtu.be" in low or is_share_link(low):
            continue
        parts = urllib.parse.urlparse(urllib.parse.unquote(u))
        key = bare_domain(u) + parts.path.rstrip("/").lower()
        if key in keys:
            continue
        keys.add(key)
        for name, needles in SOCIAL_PATTERNS:
            if any(n in low for n in needles):
                if not out[name]:
                    out[name] = u
                break
        others.append(u)
    out["other_links"] = " | ".join(others[:15])
    return out


def enrich_channel(row, description, check_websites, searcher=None, facebook_searcher="same"):
    """Adds website, linkedin, emails and email_source to a result row.
    facebook_searcher: used for the Facebook email search (defaults to searcher)."""
    if facebook_searcher == "same":
        facebook_searcher = searcher
    desc_urls = [normalise_url(u.rstrip(".,)")) for u in
                 re.findall(r"(?:https?://|www\.)[^\s<>\"']+", description)]
    about_urls = channel_about_links(row["channel_link"]) if check_websites else []
    all_urls = about_urls + [u for u in desc_urls if u not in about_urls]

    desc_emails = clean_emails(emails_in_text(description))
    emails, sources = list(desc_emails), (["YouTube description"] if desc_emails else [])

    # Link-in-bio pages (Linktree, Stan...) often list an email and the real website.
    if check_websites:
        for bio in [u for u in all_urls if is_bio_page(u)][:1]:
            bio_emails, bio_links = bio_page_details(bio)
            if bio_emails and not emails:
                emails, sources = bio_emails, [bio]
            all_urls = all_urls + [u for u in bio_links if u not in all_urls]

    websites = []
    for u in all_urls:
        if is_own_website(u) and not is_bio_page(u) and \
                bare_domain(u) not in [bare_domain(w) for w in websites]:
            websites.append(u)
    if row.get("website") and bare_domain(row["website"]) not in [bare_domain(w) for w in websites]:
        websites.append(row["website"])  # website saved by an earlier run
    linkedin = next((u for u in all_urls if "linkedin.com/" in u.lower() and not is_share_link(u)), "") \
        or row.get("linkedin", "")
    site_links = []
    read_sites = set()      # websites actually read (for emails AND social links)

    if check_websites:
        for site in websites[:3]:
            site_emails, where, links = find_website_details(site, owner_tokens=owner_tokens_for(row, description))
            read_sites.add(bare_domain(site))
            site_links += links
            new = [e for e in site_emails if e not in emails]
            if new:
                emails += new
                sources.append(where)
            if emails:
                break

    if not emails and searcher is not None:
        site_domain = bare_domain(websites[0]) if websites else ""
        found, where, site = search_for_email(searcher, row, site_domain)
        if found:
            emails, sources = found, [where]
        if site and not websites:
            # A website found by web search: keep its homepage, and read it for
            # LinkedIn / Facebook / Instagram links too (not only the email).
            parts = urllib.parse.urlparse(site)
            home = f"{parts.scheme or 'https'}://{parts.netloc}/" if parts.netloc else site
            websites.append(home)
            if check_websites:
                site_emails, where, links = find_website_details(home, owner_tokens=owner_tokens_for(row, description))
                read_sites.add(bare_domain(home))
                site_links += links
                if not emails and site_emails:
                    emails, sources = site_emails, [where]

    fb_found = ""
    if not emails and facebook_searcher is not None:
        site_domain = bare_domain(websites[0]) if websites else ""
        fb_row = dict(row, facebook=row.get("facebook") or social_links(all_urls + site_links).get("facebook", ""))
        found, where, fb_found = facebook_email_search(facebook_searcher, fb_row, site_domain, description)
        if found:
            emails, sources = found, [where]

    row["website"] = websites[0] if websites else ""
    # Safety rule: whatever website is saved, however it was found, its social
    # links are read too (so a new way of finding websites can't skip this step).
    if check_websites and row["website"] and bare_domain(row["website"]) not in read_sites:
        site_emails, where, links = find_website_details(row["website"], owner_tokens=owner_tokens_for(row, description))
        read_sites.add(bare_domain(row["website"]))
        site_links += links
        if not emails and site_emails:
            emails, sources = site_emails, [where]
    profiles = social_links(all_urls)
    if fb_found and not profiles.get("facebook"):
        profiles["facebook"] = fb_found
    # Profiles missing from the YouTube About section, taken from their website
    from_site = social_links(site_links)
    for key in SOCIAL_FIELDS[:-1]:
        if not profiles[key]:
            profiles[key] = from_site[key] or row.get(key, "")
    if not linkedin:
        linkedin = next((u for u in site_links if "linkedin.com/" in u.lower() and not is_share_link(u)), "")
    row["linkedin"] = linkedin
    row.update(profiles)
    emails = [e for e in emails if domain_accepts_mail(e.split("@")[1])]
    if not emails:
        sources = []
    row["best_email"] = emails[0] if emails else ""
    row["emails"] = "; ".join(emails[:4])
    row["email_source"] = "; ".join(sources)
    return row


# ---------------------------------------------------------------- fit score

# How close a channel is to the ideal lead: an individual executive / leadership
# coach or consultant, ideally with a podcast, who can actually be contacted.
FIT_ROLE_STRONG = icp.prefix_re("best-fit roles")
FIT_ROLE = icp.word_re("roles")
FIT_LEADERSHIP = icp.word_re("core topic words")
FIT_AUDIENCE = icp.word_re("who they work with (decision makers)")
FIT_SPEAKER = icp.word_re("speaker and author signs")
FIT_HOST = re.compile(r"\b(podcast host|host of|hosts? the|my podcast|our podcast|new episode|episode \d+|ep\.? ?\d+)\b")
FIT_AUTHOR = re.compile(r"\b(author of|my (new )?book|bestselling|best-selling|wrote the book|published)\b")
FIT_ORG_TOPICS = icp.word_re("topics they work on")
FIT_ORGANISATION = icp.word_re("organisations, not a person")
FIT_OFF_NICHE = icp.word_re("not my icp: topics")


def fit_score(row, extra_text=""):
    """Returns (score 0-100, label, short reason) for how well a channel matches
    the target: a leadership / executive coach or consultant with a podcast."""
    name = (row.get("channel_name") or "").lower()
    text = " ".join([name, row.get("description") or "", row.get("latest_video_title") or "",
                     row.get("recent_videos") or "", extra_text]).lower()
    score, reasons = 0, []

    if FIT_ROLE_STRONG.search(text):
        score += 35; reasons.append("executive/leadership coach")
    elif FIT_ROLE.search(text):
        score += 18; reasons.append("coach/consultant")
    if FIT_LEADERSHIP.search(text):
        score += 12
        if not reasons or reasons[-1] != "executive/leadership coach":
            reasons.append("leadership")
    if FIT_AUDIENCE.search(text):
        score += 8; reasons.append("works with executives")
    if FIT_SPEAKER.search(text):
        score += 4
    has_podcast = row.get("content_type") == "Podcast" or bool(row.get("podcast")) or bool(FIT_HOST.search(text))
    if has_podcast:
        score += 16; reasons.append("podcast host" if FIT_HOST.search(text) else "podcast")
        if FIT_LEADERSHIP.search(text) or FIT_ROLE_STRONG.search(text) or FIT_ORG_TOPICS.search(text):
            score += 10  # a leadership / workplace podcast is the best fit
    # "Speaker | Coach | Author | Podcast Host" style profiles: several roles at once
    roles = sum(bool(x.search(text)) for x in (FIT_ROLE, FIT_SPEAKER, FIT_AUTHOR, FIT_HOST))
    if roles >= 3:
        score += 8; reasons.append("coach + speaker + author")
    elif FIT_AUTHOR.search(text):
        score += 3
    if FIT_ORG_TOPICS.search(text) and FIT_ROLE.search(text):
        score += 5

    email_source = row.get("email_source") or ""
    if row.get("best_email"):
        score += 7 if email_source.startswith("web search") else 12
        reasons.append("email")
    if row.get("website"):
        score += 4
    if row.get("linkedin"):
        score += 5

    subs = int(row.get("subscribers") or 0)
    if 500 <= subs <= 150_000:
        score += 4          # established but still reachable
    elif subs > 1_000_000:
        score -= 8          # big media brands rarely answer cold email

    clearly_leadership = FIT_ROLE_STRONG.search(text) or (FIT_LEADERSHIP.search(text) and FIT_SPEAKER.search(text))
    if FIT_ORGANISATION.search(text):
        score -= 10 if clearly_leadership else 18; reasons.append("organisation, not a person")
    if FIT_OFF_NICHE.search(text) and not clearly_leadership:
        score -= 22; reasons.append("off-niche")
    if row.get("niche_match") == "weak":
        score -= 10

    # Meaning: how close the channel's description + recent videos are to your ideal lead (ICP.md, section 1).
    icp = semantic.icp_similarity(row) if row.get("channel_link") else None
    if icp is not None:
        icp_points = max(-8, min(8, round((icp - ICP_TYPICAL) * 100)))
        if icp_points:
            score += icp_points
            reasons.append(f"ICP match {icp_points:+d}")

    # Your own ratings: leads like the ones you rated Good go up, like your Low ones go down.
    learned = learning.adjustment(row, extra_text)
    if learned:
        score += learned
        reasons.insert(0, f"your ratings {learned:+d}")

    score = max(0, min(100, score))
    label = "Top fit" if score >= 75 else "Good fit" if score >= 55 else "Possible" if score >= 35 else "Low fit"
    return score, label, ", ".join(reasons[:4])


def apply_fit(row, extra_text=""):
    row["fit_score"], row["fit_label"], row["fit_reason"] = fit_score(row, extra_text)
    return row


# ---------------------------------------------------------------- bookkeeping

def ensure_folders():
    for folder in (RESULTS_DIR, DATA_DIR):
        folder.mkdir(exist_ok=True)


def load_api_keys():
    """YouTube keys from .env (YOUTUBE_API_KEYS=main,backup,...). Asks once if there are none."""
    keys = [k.strip() for k in env("YOUTUBE_API_KEYS").split(",") if k.strip()]
    if keys:
        return list(dict.fromkeys(keys))
    print("No YouTube API key saved yet. Paste your YouTube Data API key")
    print("(saved in .env, so you only do this once):")
    key = input("> ").strip()
    if not key:
        sys.exit("No key entered. Stopping.")
    set_env("YOUTUBE_API_KEYS", key)
    return [key]


LEARNED_KEYWORDS_FILE = DATA_DIR / "learned_keywords.txt"
MAX_KEYWORDS = 140   # your phrases first, then learned ones, then variations


def expand_spintax(text):
    """'{executive|leadership} {coach|coaching}' -> all 4 combinations.
    Nested braces work too: '{a|b {c|d}}'."""
    m = re.search(r"\{([^{}]*)\}", text)
    if not m:
        return [" ".join(text.split())]
    out = []
    for option in m.group(1).split("|"):
        out += expand_spintax(text[:m.start()] + option + text[m.end():])
    return out


_NORMALISE = {"coaching": "coach", "coaches": "coach", "leaders": "leader", "podcasts": "podcast",
              "consulting": "consultant", "consultants": "consultant", "executives": "executive",
              "managers": "manager", "founders": "founder", "ceos": "ceo", "mentoring": "mentor",
              "speakers": "speaker", "trainers": "trainer", "training": "trainer"}


def keyword_signature(phrase):
    """Phrases YouTube treats as the same search get the same signature, so
    'executive coaching' and 'executive coach' aren't both spent on."""
    words = [_NORMALISE.get(w, w) for w in re.findall(r"[a-z0-9-]+", phrase.lower())
             if w not in ("the", "a", "an", "for", "of", "and", "with", "to", "in")]
    return " ".join(sorted(words))


def load_keywords(cli_value):
    """Search phrases from ICP.md (spintax allowed) plus phrases the tool
    learned from your best-fit channels (data/learned_keywords.txt)."""
    if cli_value:
        lines = [k.strip() for k in cli_value.split(",")]
    else:
        lines = icp.lines("search phrases")                 # ICP.md, section 2
        if LEARNED_KEYWORDS_FILE.exists():
            lines += LEARNED_KEYWORDS_FILE.read_text().splitlines()
        lines += variations.load(max_age_days=3650)[0]     # deeper search: same-meaning phrases
    words, sigs = [], set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for phrase in expand_spintax(line):
            sig = keyword_signature(phrase)
            if phrase and sig not in sigs:
                sigs.add(sig)
                words.append(phrase)
    return words[:MAX_KEYWORDS] or ["executive leadership coach"]


# Words that mark a phrase as being about the niche (used when learning new keywords)
NICHE_WORDS = icp.word_re("niche words for new search phrases")
LEARN_STOP = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "your", "my", "our",
              "best", "top", "certified", "professional", "official", "free", "new", "life", "health",
              "i", "am", "is", "are", "be", "as", "by", "at", "from", "this", "that", "who", "we"}


def refresh_variations(force=False):
    """Builds data/variation_keywords.txt from your keywords (weekly, or when forced)."""
    phrases, fresh = variations.load()
    if fresh and not force:
        return phrases
    base = []
    for line in icp.lines("search phrases"):
        base += expand_spintax(line)
    if LEARNED_KEYWORDS_FILE.exists():
        base += [l.strip() for l in LEARNED_KEYWORDS_FILE.read_text().splitlines() if l.strip() and not l.startswith("#")]
    known = {keyword_signature(k) for k in base}
    new = variations.build(base, keyword_signature, NICHE_WORDS, FIT_OFF_NICHE, known)
    if new:
        variations.save(new)
        semantic.save_cache()
    return new


LEARN_ENDINGS = "|".join(re.escape(w) for w in icp.items("endings for learned phrases"))


def learn_keywords(rows, known_keywords, max_new=8):
    """Reads the names and descriptions of Top-fit channels and finds phrases
    like 'executive presence coach' or 'servant leadership podcast' that several
    of them use but you don't search yet. Saves the best ones to
    data/learned_keywords.txt so the next runs search them too."""
    known = {keyword_signature(k) for k in known_keywords}
    counts = {}
    # Once you've rated 5+ leads Good, learn from those; until then, from Top-fit leads.
    good = learning.good_links()
    use_ratings = len(good) >= 5
    for r in rows:
        if (r.get("channel_link") not in good) if use_ratings else int(r.get("fit_score") or 0) < 70:
            continue
        text = " ".join([r.get("channel_name", ""), r.get("description", ""),
                         (r.get("recent_videos") or "").replace("|", ".")]).lower()
        found = set()
        for m in re.finditer(r"((?:[a-z][a-z-]+\s){1,2})(" + LEARN_ENDINGS + r")\b", text):
            words = [w for w in m.group(1).split() if w not in LEARN_STOP]
            if not words:
                continue
            phrase = " ".join(words + [_NORMALISE.get(m.group(2), m.group(2))])
            if NICHE_WORDS.search(phrase) and not FIT_OFF_NICHE.search(phrase):
                found.add(phrase)
        for phrase in found:
            counts[phrase] = counts.get(phrase, 0) + 1
    fresh = [(n, p) for p, n in counts.items() if n >= 2 and keyword_signature(p) not in known]
    fresh.sort(reverse=True)
    new = [p for _, p in fresh[:max_new]]
    if new:
        existing = LEARNED_KEYWORDS_FILE.read_text().splitlines() if LEARNED_KEYWORDS_FILE.exists() else \
            ["# Learned automatically from your best-fit channels. Delete any line you don't want."]
        LEARNED_KEYWORDS_FILE.write_text("\n".join(existing + new) + "\n")
    return new


def parse_countries(text):
    codes = []
    for part in text.split(","):
        name = part.strip().lower()
        if not name:
            continue
        code = COUNTRY_NAMES.get(name)
        if not code and len(name) == 2 and name.isalpha():
            code = name.upper()
        if not code:
            sys.exit(f"Don't recognise country '{part.strip()}'. Use a name like "
                     f"'Canada' or a 2-letter code like 'CA'.")
        if code not in codes:
            codes.append(code)
    return codes


def load_search_log():
    """{"term|country|type": {"pages": n, "next": token, "done": bool, "last": iso}}"""
    try:
        raw = json.loads(SEARCH_LOG.read_text())
    except Exception:
        return {}
    log = {}
    for key, value in raw.items():
        if isinstance(value, str):  # old format: "term|country|type|pages": "date"
            term, country, stype, pages = key.rsplit("|", 3)
            log[f"{term}|{country}|{stype}"] = {"pages": int(pages), "next": "",
                                                "done": False, "last": value}
        else:
            log[key] = value
    return log


def save_search_log(log):
    SEARCH_LOG.write_text(json.dumps(log, indent=1, sort_keys=True))


def next_run_number():
    numbers = [int(m.group(1)) for f in RESULTS_DIR.glob("*.csv")
               if (m := re.fullmatch(r"(?:Search |search_)(\d+)\.csv", f.name))]
    return max(numbers, default=0) + 1


def load_master():
    if not MASTER_CSV.exists():
        return []
    with open(MASTER_CSV, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_excluded():
    if not EXCLUDED_CSV.exists():
        return []
    with open(EXCLUDED_CSV, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def clean_master(args):
    """Re-checks every saved channel: drops those whose newest real video
    (not a Short) is older than the activity window, and those that only
    matched on a stray word and aren't in the niche. Removed channels move to
    excluded_channels.csv (with the reason), so they are never found again."""
    master = load_master()
    if not master:
        sys.exit(f"{MASTER_CSV.name} not found. Run a normal search first.")
    days = args.days or DEFAULT_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    yt = YouTube(load_api_keys(), args.budget)
    print(f"Checking {len(master)} saved channels (real video in the last {days} days, in the niche)...")

    reasons = {}
    for r in master:
        ok, why = niche_check(r.get("channel_name", ""), r.get("description", ""),
                              r.get("latest_video_title", ""), r.get("subscribers", 0))
        if not ok:
            reasons[r["channel_link"]] = why

    # Activity: newest uploads per channel (1 unit each), then durations in batches of 50.
    to_check = [r for r in master if r["channel_link"] not in reasons and r.get("channel_id", "").startswith("UC")]
    uploads_by_link, all_ids = {}, []
    try:
        for i, r in enumerate(to_check, 1):
            _, _, uploads, last_month = recent_uploads(yt, "UU" + r["channel_id"][2:])
            r["recent_videos"] = join_titles(last_month)
            uploads_by_link[r["channel_link"]] = uploads
            all_ids += [vid for when, vid in uploads if when >= cutoff]
            if i % 100 == 0:
                print(f"  {i}/{len(to_check)} channels checked")
        durations = video_durations(yt, all_ids)
    except (BudgetReached, QuotaExceeded) as e:
        yt.save_usage()
        sys.exit(f"Stopped: not enough YouTube quota to finish the check ({e}). Nothing was changed.")
    yt.save_usage()
    for r in to_check:
        latest, kind = activity_check(yt, uploads_by_link.get(r["channel_link"], []), cutoff, durations)
        if latest is None:
            reasons[r["channel_link"]] = f"not active in {days} days (no real video, under 3 Shorts)"
        else:
            r["last_upload"], r["activity"] = latest.strftime("%Y-%m-%d"), kind

    keep = [r for r in master if r["channel_link"] not in reasons]
    gone = [dict(r, excluded_reason=reasons[r["channel_link"]],
                 excluded_on=datetime.now().strftime("%Y-%m-%d"))
            for r in master if r["channel_link"] in reasons]
    fields = list(master[0].keys())
    if "activity" not in fields:
        fields.insert(fields.index("last_upload") + 1 if "last_upload" in fields else len(fields), "activity")
    if "recent_videos" not in fields:
        fields.insert(fields.index("latest_video_title") + 1 if "latest_video_title" in fields else len(fields), "recent_videos")
    with open(MASTER_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(keep)
    old_gone = load_excluded()
    ex_fields = fields + ["excluded_reason", "excluded_on"]
    with open(EXCLUDED_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=ex_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(old_gone + gone)
    # Take them out of the Search XX.csv files too.
    gone_links = set(reasons)
    for path in sorted(RESULTS_DIR.glob(f"{RUN_PREFIX} *.csv")):
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            run_fields, rows = reader.fieldnames, list(reader)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=run_fields, extrasaction="ignore")
            w.writeheader()
            w.writerows([x for x in rows if x.get("channel_link") not in gone_links])
    sync_run_files(keep)

    print(f"\nKept {len(keep)} channels, moved {len(gone)} to {EXCLUDED_CSV.name}:")
    counts = {}
    for g in gone:
        counts[g["excluded_reason"]] = counts.get(g["excluded_reason"], 0) + 1
    for why, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {n:4d}  {why}")
    print(f"YouTube units used: {yt.units_used}")


def profile_self_check(rows):
    """Safety net: for every lead with a website, compares the saved LinkedIn /
    Facebook / Instagram / X / TikTok with what that website is known to link to
    (website memory, no internet needed) and fills anything missing.
    Returns how many profiles it added."""
    with _site_cache["lock"]:
        sites = dict(_site_cache_data()["sites"])
    by_domain = {}
    for key, hit in sites.items():
        by_domain.setdefault(key.split("|")[0], []).extend(hit.get("links", []))
    added = 0
    for r in rows:
        site = (r.get("website") or "").strip()
        links = by_domain.get(bare_domain(site), []) if site else []
        if not links:
            continue
        found = social_links(links)
        for k in ("facebook", "instagram", "twitter", "tiktok"):
            if not r.get(k) and found.get(k):
                r[k] = found[k]
                added += 1
        if not r.get("linkedin"):
            li = next((u for u in links if "linkedin.com/" in u.lower() and not is_share_link(u)), "")
            if li:
                r["linkedin"] = li
                added += 1
    return added


def self_check_master():
    """Runs profile_self_check on the master list and saves only if something was added."""
    rows = load_master()
    added = profile_self_check(rows) if rows else 0
    if added:
        fields = list(rows[0].keys())
        for r in rows:
            apply_fit(r)
        tmp = MASTER_CSV.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        tmp.replace(MASTER_CSV)
        sync_run_files(rows)
    print(f"Self-check: {added} missed social profile{'s' if added != 1 else ''} added from websites." if added
          else "Self-check: every lead's social profiles match its website.")
    return added


def rescore_master(rows=None):
    """Recomputes every lead's fit score (e.g. after you rate leads) and saves."""
    rows = load_master() if rows is None else rows
    if not rows:
        return
    fields = list(rows[0].keys())
    for r in rows:
        apply_fit(r)
    rows.sort(key=lambda r: (-int(r.get("fit_score") or 0), -int(r.get("subscribers") or 0)))
    tmp = MASTER_CSV.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(MASTER_CSV)
    sync_run_files(rows)
    semantic.save_cache()


def merge_into_master(rows, fields, run_name):
    existing = {r.get("channel_link", ""): r for r in load_master()}
    new_count = 0
    for r in rows:
        old = existing.get(r["channel_link"])
        if old is None:
            new_count += 1
            r = dict(r, first_found=datetime.now().strftime("%Y-%m-%d"), found_in=run_name)
        else:
            r = dict(r, first_found=old.get("first_found", ""), found_in=old.get("found_in", ""))
            if not r["emails"] and old.get("emails"):
                r["emails"], r["email_source"] = old["emails"], old.get("email_source", "")
                r["best_email"] = old.get("best_email") or old["emails"].split(";")[0].strip()
        existing[r["channel_link"]] = r
    master_fields = fields + ["first_found", "found_in"]
    merged = sorted(existing.values(), key=lambda r: (-int(r.get("fit_score") or 0),
                                                      -int(r.get("subscribers") or 0)))
    with open(MASTER_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=master_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    return new_count, len(merged)


def add_run_history(entry):
    fields = ["run", "date", "new_channels", "with_email", "strong_match", "searches_run",
              "youtube_units", "web_searches", "countries", "note"]
    first = not RUN_HISTORY.exists()
    with open(RUN_HISTORY, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if first:
            writer.writeheader()
        writer.writerow(entry)


def build_dashboard(open_browser=False):
    """The dashboard (Next.js app in dashboard/) reads the CSV files live, so
    there is nothing to rebuild. If it's running, open it."""
    url = "http://localhost:3030"
    try:
        urllib.request.urlopen(url + "/api/run", timeout=2)
        running = True
    except Exception:
        running = False
    if running:
        print(f"Dashboard: {url} (refresh the page to see the new results)")
        if open_browser:
            import webbrowser
            webbrowser.open(url)
    else:
        print(f"Dashboard: double-click 'Start LeadTube.command' and open {url}")


RUN_LOCK = DATA_DIR / "run.lock"


def acquire_run_lock():
    """Only one search / fill run at a time, so two runs never overwrite
    each other's results. A lock left by a crashed run is ignored."""
    import os
    if RUN_LOCK.exists():
        try:
            pid = int(RUN_LOCK.read_text().split()[0])
            os.kill(pid, 0)          # still running?
            sys.exit(f"Another run is already in progress (process {pid}). "
                     f"Wait for it to finish, then try again.")
        except (ValueError, ProcessLookupError, PermissionError, IndexError):
            pass                     # stale lock
    RUN_LOCK.write_text(f"{os.getpid()} {datetime.now().isoformat(timespec='seconds')}")


def release_run_lock():
    import os
    try:
        if RUN_LOCK.exists() and RUN_LOCK.read_text().split()[0] == str(os.getpid()):
            RUN_LOCK.unlink()
    except Exception:
        pass


def ask(prompt, default):
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def sync_run_files(master_rows):
    """Copies emails and profile links from the master list back into each
    "Search XX.csv" file, and refreshes the email counts in run_history.csv."""
    by_link = {r["channel_link"]: r for r in master_rows}
    copy_cols = ["fit_score", "fit_label", "fit_reason",
                 "best_email", "emails", "email_source", "website", "linkedin", *SOCIAL_FIELDS]
    counts = {}
    for path in sorted(RESULTS_DIR.glob(f"{RUN_PREFIX} *.csv")):
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames)
            rows = list(reader)
        for col in copy_cols:
            if col not in fields:
                if col.startswith("fit_"):
                    fields.insert(["fit_score", "fit_label", "fit_reason"].index(col), col)
                else:
                    fields.insert(fields.index("latest_video_title") if "latest_video_title" in fields
                                  else len(fields), col)
        for r in rows:
            m = by_link.get(r["channel_link"])
            if m:
                for col in copy_cols:
                    r[col] = m.get(col, r.get(col, ""))
        rows.sort(key=lambda r: (-int(r.get("fit_score") or 0), -int(r.get("subscribers") or 0)))
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        counts[path.stem] = sum(1 for r in rows if r.get("emails"))
    if RUN_HISTORY.exists():
        with open(RUN_HISTORY, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames)
            history = list(reader)
        for h in history:
            if h["run"] in counts:
                h["with_email"] = counts[h["run"]]
        with open(RUN_HISTORY, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(history)


# ---------------------------------------------------------------- fill-missing mode

EMAIL_CHECKS = DATA_DIR / "email_checks.json"
WEB_SEARCH_RECHECK_DAYS = 30
PROFILE_KEYS = ("linkedin", "facebook", "instagram", "twitter", "tiktok")


def fill_missing_emails(args):
    """For channels already in all_channels.csv (uses no YouTube quota):
      - channels with no email: website, link-in-bio page and web search again
        (web search is skipped if it was already tried in the last 30 days),
      - channels missing LinkedIn / Facebook / Instagram / X / TikTok: read
        their website for those links."""
    if not MASTER_CSV.exists():
        sys.exit(f"{MASTER_CSV.name} not found. Run a normal search first.")
    with open(MASTER_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        rows = list(reader)
    for col in ["linkedin", *SOCIAL_FIELDS]:
        if col not in fields:
            fields.insert(fields.index("latest_video_title"), col)
    try:
        checks = json.loads(EMAIL_CHECKS.read_text())
    except Exception:
        checks = {}
    recent = (datetime.now() - timedelta(days=WEB_SEARCH_RECHECK_DAYS)).strftime("%Y-%m-%d")

    need_email = [r for r in rows if not r.get("emails")]
    need_profiles = [r for r in rows if r.get("emails") and (r.get("website") or "").strip()
                     and any(not r.get(k) for k in PROFILE_KEYS)]
    serper_key = "" if args.no_web_search else load_serper_key(args.serper_key)
    searcher = WebSearch(serper_key, args.web_search_limit) if serper_key else None
    print(f"{len(need_email)} channels have no email; {len(need_profiles)} others are missing "
          f"some social profiles. Checking them (no YouTube quota)...")
    before_profiles = sum(1 for r in rows for k in ["linkedin", *PROFILE_KEYS[1:]] if r.get(k))

    def work_email(r):
        searched_recently = checks.get(r["channel_link"], "") >= recent
        fb_key = "facebook|" + r["channel_link"]           # the Facebook search has its own record
        fb_recently = checks.get(fb_key, "") >= recent
        found = enrich_channel(dict(r), r.get("description", ""), not args.no_websites,
                               None if searched_recently else searcher,
                               facebook_searcher=None if fb_recently else searcher)
        for k in ("best_email", "emails", "email_source", "website", "linkedin", *SOCIAL_FIELDS):
            if found.get(k):
                r[k] = found[k]
        today_str = datetime.now().strftime("%Y-%m-%d")
        if searcher and not searched_recently:
            checks[r["channel_link"]] = today_str
        if searcher and not fb_recently:
            checks[fb_key] = today_str

    def work_profiles(r):
        # same full read as everywhere else (and shared with the website memory)
        _, _, links = find_website_details(r["website"], owner_tokens=owner_tokens_for(r, r.get("description", "")))
        found = social_links(links)
        for k in SOCIAL_FIELDS[:-1]:
            if not r.get(k) and found.get(k):
                r[k] = found[k]
        if not r.get("linkedin"):
            r["linkedin"] = next((u for u in links if "linkedin.com/" in u.lower()
                                  and not is_share_link(u)), "")

    jobs = [(work_email, r) for r in need_email] + [(work_profiles, r) for r in need_profiles]
    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for fut in as_completed([pool.submit(fn, r) for fn, r in jobs]):
            try:
                fut.result()
            except Exception as e:
                print(f"  (skipped one channel: {e})")
            done += 1
            if done % 20 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)} checked, "
                      f"{sum(1 for r in need_email if r.get('emails'))} new emails")

    for col in ("fit_score", "fit_label", "fit_reason")[::-1]:
        if col not in fields:
            fields.insert(0, col)
    for r in rows:
        apply_fit(r)
    rows.sort(key=lambda r: (-int(r.get("fit_score") or 0), -int(r.get("subscribers") or 0)))
    with open(MASTER_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    EMAIL_CHECKS.write_text(json.dumps(checks, indent=1, sort_keys=True))
    save_site_cache()
    sync_run_files(rows)
    after_profiles = sum(1 for r in rows for k in ["linkedin", *PROFILE_KEYS[1:]] if r.get(k))
    print(f"\nNew emails found:        {sum(1 for r in need_email if r.get('emails'))}")
    print(f"New social profiles:     {after_profiles - before_profiles}")
    print(f"Channels with an email:  {sum(1 for r in rows if r.get('emails'))} of {len(rows)}")
    if searcher:
        print(f"Web searches used:       {searcher.used}"
              + (f"  (stopped: {searcher.disabled_reason})" if searcher.disabled_reason else ""))
    print(f"Saved to: {MASTER_CSV}")
    self_check_master()
    build_dashboard(open_browser=not args.no_open)


# ---------------------------------------------------------------- main

FIELDS = ["fit_score", "fit_label", "fit_reason", "channel_name", "channel_link", "country", "subscribers", "total_videos",
          "last_upload", "activity", "content_type", "niche_match", "best_email", "emails", "email_source",
          "website", "linkedin", "facebook", "instagram", "twitter", "tiktok", "podcast",
          "booking", "other_links", "latest_video_title", "recent_videos", "description", "channel_id", "found_by"]


def main():
    p = argparse.ArgumentParser(description="Find NEW active YouTube channels in a niche and their contact emails.")
    p.add_argument("--target", type=int, help="new good-fit leads to find this run "
                   "(default: no limit, keep going until the quota budget is used)")
    p.add_argument("--fit-goal", choices=sorted(FIT_GOALS), default="good",
                   help="with --target: which leads count toward it (top, good = Good or better, "
                        "possible = Possible or better). Lower-fit leads are still saved.")
    p.add_argument("--keywords", help="comma-separated phrases (default: the search phrases in ICP.md)")
    p.add_argument("--countries", help="comma-separated, e.g. 'US, UK, Canada'")
    p.add_argument("--days", type=int, help="only channels that uploaded in the last N days")
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                   help=f"max YouTube quota units this run (default {DEFAULT_BUDGET})")
    p.add_argument("--include-unknown-country", action="store_true",
                   help="also keep channels that have not set a country")
    p.add_argument("--match-words", help="comma-separated relevance words "
                   f"(default: {', '.join(DEFAULT_MATCH_WORDS)}); 'none' disables the filter")
    p.add_argument("--no-websites", action="store_true",
                   help="skip visiting About pages and websites (faster, fewer emails)")
    p.add_argument("--no-web-search", action="store_true",
                   help="don't use Serper web search for channels with no email")
    p.add_argument("--web-search-limit", type=int, default=400,
                   help="max Serper searches per run (2 per channel at most). Default 400")
    p.add_argument("--serper-key", help="Serper.dev API key (default: SERPER_API_KEY in .env)")
    p.add_argument("--include-known", action="store_true",
                   help="also return channels already in all_channels.csv")
    p.add_argument("--fill-missing", action="store_true",
                   help="re-check channels in all_channels.csv for missing emails and social "
                        "profiles (no YouTube quota used)")
    p.add_argument("--refresh-variations", action="store_true",
                   help="rebuild the same-meaning search phrases now (normally weekly)")
    p.add_argument("--clean", action="store_true",
                   help="re-check saved channels and move inactive / off-niche ones to "
                        "excluded_channels.csv (about 1 YouTube unit per channel)")
    p.add_argument("--dashboard", action="store_true",
                   help="open the dashboard if it's running (no searching)")
    p.add_argument("--no-open", action="store_true", help="don't open the dashboard after a run")
    p.add_argument("--yes", action="store_true", help="don't ask questions, use defaults/flags")
    args = p.parse_args()

    ensure_folders()
    print("=== YouTube Channel Finder ===\n")
    if args.dashboard:
        build_dashboard(open_browser=not args.no_open)
        return
    if args.fill_missing:
        acquire_run_lock()
        fill_missing_emails(args)
        return
    if args.clean:
        acquire_run_lock()
        clean_master(args)
        return

    if not args.keywords:
        try:
            fresh = refresh_variations(force=args.refresh_variations)
            if fresh:
                print(f"Deeper search: {len(fresh)} same-meaning phrases ready (data/variation_keywords.txt).")
        except Exception as e:                       # never let this stop a search
            print(f"  (couldn't refresh phrase variations: {e})")
    keywords = load_keywords(args.keywords)
    print(f"Search phrases ({len(keywords)}): " + ", ".join(keywords))
    print("(edit section 2 of ICP.md to change them)\n")
    if args.yes:
        countries = parse_countries(args.countries or DEFAULT_COUNTRIES)
        days = args.days or DEFAULT_DAYS
        target = args.target or DEFAULT_TARGET
    else:
        countries = parse_countries(args.countries or ask("Countries", DEFAULT_COUNTRIES))
        days = args.days or int(ask("Uploaded within the last how many days", DEFAULT_DAYS))
        answer = ask("How many NEW channels to find (Enter = as many as today's quota allows)", "all")
        target = args.target or (0 if answer.strip().lower() in ("all", "", "0") else int(answer))
    if not countries:
        sys.exit("No countries given. Stopping.")

    match_words = DEFAULT_MATCH_WORDS
    if args.match_words:
        match_words = [] if args.match_words.strip().lower() == "none" else \
            [w.strip().lower() for w in args.match_words.split(",") if w.strip()]
    match_re = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in match_words) + ")") if match_words else None

    acquire_run_lock()
    yt = YouTube(load_api_keys(), args.budget)
    print(f"Using the {yt.describe()}.")
    if yt.left(yt.idx) < 300:
        sys.exit("Today's YouTube quota is used up on every key. It resets at midnight US Pacific time.")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Channels already found in earlier runs are skipped.
    known_links, known_ids = set(), set()
    if not args.include_known:
        for r in load_master() + load_excluded():
            known_links.add(r.get("channel_link", "").lower())
            if r.get("channel_id"):
                known_ids.add(r["channel_id"])

    # Every (phrase, country, type) search is read one page of 50 at a time. The
    # tool remembers how far it got, so the next run continues on the next page
    # instead of returning the same channels again.
    log = load_search_log()
    restart_before = datetime.now() - timedelta(days=SEARCH_REPEAT_DAYS)
    order = {}
    # Each phrase is searched as several different result lists: YouTube returns
    # different channels for the same phrase depending on the sort order.
    LISTS = [("channel", "relevance"), ("video", "relevance"), ("channel", "videoCount"),
             ("channel", "date"), ("video", "date"), ("video", "viewCount")]
    sort_of = {}
    for ki, term in enumerate(keywords):
        for ci, country in enumerate(countries):
            for ti, (stype, sort_by) in enumerate(LISTS):
                key = f"{term.lower()}|{country}|{stype}" + ("" if sort_by == "relevance" else f"|{sort_by}")
                state = log.setdefault(key, {"pages": 0, "next": "", "done": False, "last": ""})
                if state["done"] and state["last"] and \
                        datetime.fromisoformat(state["last"]) < restart_before:
                    state.update(pages=0, next="", done=False)  # fresh videos since then
                order[key] = (ki, ci, ti, term, country, stype)
                sort_of[key] = sort_by

    # Smart scheduling (an "upper confidence bound" bandit): each search earns a
    # score from how many NEW, matching channels its pages have produced. Proven
    # keywords are read deeper, weak ones are dropped early, untried ones get a
    # fair first try, and what works in one country boosts it in the others.
    country_weight = {"US": 1.0, "GB": 0.85, "CA": 0.8, "AU": 0.75}
    type_weight = {"video": 1.0, "channel": 0.9}
    sort_weight = {"relevance": 1.0, "videoCount": 0.9, "date": 0.8, "viewCount": 0.7}

    def term_yield(term):
        pages = kept_sum = 0
        for k, (_, _, _, t, _, _) in order.items():
            if t == term:
                pages += log[k].get("pages", 0)
                kept_sum += log[k].get("kept", 0)
        # prior: ~3 new channels per page; phrases whose leads you rated Good count for more
        return (kept_sum + 3.0) / (pages + 1.0) * learning.phrase_factor(term)

    def search_score(k):
        """How promising one result list is (used to pick WHICH list of a phrase
        to read next): untried lists first, then lists that keep producing."""
        st = log[k]
        _, _, _, term, country, stype = order[k]
        weight = country_weight.get(country, 0.5) * type_weight[stype] * sort_weight[sort_of[k]]
        pages = st.get("pages", 0)
        if pages == 0:
            return 100 + weight
        own = st.get("kept", 0) / pages
        recent = st.get("last_kept", own)
        return (0.6 * own + 0.4 * recent) * (0.9 ** pages) * weight

    # ---- Planner ---------------------------------------------------------
    # 1. Mix: about 55% of search pages go to podcast phrases, 45% to the rest.
    # 2. Coverage: every phrase gets a page before any phrase gets a second one
    #    this run; phrases used least in earlier runs go first, so over a couple
    #    of runs every keyword is used, not just the top ones.
    # 3. Once all phrases had their turn, extra pages go to the phrases that
    #    produce the most new matching channels (proven winners go deeper).
    PODCAST_SHARE = 0.55
    is_podcast = {t: "podcast" in t.lower() for t in keywords}
    run_pages = {t: 0 for t in keywords}
    run_count = {"podcast": 0, "general": 0}
    # 4. Countries: pages are shared out by country size (US most, then UK,
    #    Canada...), so every country you picked gets searched each run.
    share = {c: country_weight.get(c, 0.45) for c in countries}
    share = {c: v / sum(share.values()) for c, v in share.items()}
    run_country = {c: 0 for c in countries}

    def lifetime_pages(term):
        return sum(log[k].get("pages", 0) for k in order if order[k][3] == term)

    lifetime = {t: lifetime_pages(t) for t in keywords}
    last_used = {t: max((log[k].get("last") or "" for k in order if order[k][3] == t), default="")
                 for t in keywords}

    def open_lists(term):
        return [k for k in order if order[k][3] == term and not log[k]["done"]]

    def next_search():
        open_terms = [t for t in keywords if open_lists(t)]
        if not open_terms:
            return None
        pods = [t for t in open_terms if is_podcast[t]]
        gens = [t for t in open_terms if not is_podcast[t]]
        total = run_count["podcast"] + run_count["general"]
        want_podcast = (run_count["podcast"] < PODCAST_SHARE * (total + 1))
        pool = (pods if want_podcast else gens) or pods or gens
        least = min(run_pages[t] for t in pool)
        candidates = [t for t in pool if run_pages[t] == least]
        if least == 0:
            # coverage pass: the phrase that has waited longest goes first
            # (never-used phrases first), so all phrases take turns across runs
            term = min(candidates, key=lambda t: (last_used[t], lifetime[t], keywords.index(t)))
        else:
            # every phrase had a turn: favour the ones that pay off
            term = max(candidates, key=lambda t: (term_yield(t), -lifetime[t]))
        done_pages = sum(run_country.values()) + 1
        return max(open_lists(term), key=lambda k: (
            round(share[order[k][4]] * done_pages - run_country[order[k][4]], 1), search_score(k)))

    def count_page(term, country):
        run_country[country] += 1
        run_pages[term] += 1
        lifetime[term] += 1
        run_count["podcast" if is_podcast[term] else "general"] += 1

    goal = FIT_GOALS[args.fit_goal]
    if target:
        print(f"\nLooking for {target} NEW leads that are {FIT_GOAL_NAMES[args.fit_goal]} "
              f"(lower-fit ones are saved too but don't count) "
              f"({len(known_links)} already in your master list are skipped)...")
    else:
        print(f"\nLooking for as many NEW channels as the quota budget ({args.budget} units) allows "
              f"({len(known_links)} already in your master list are skipped)...")
    kept, seen = [], set()
    on_goal = [0]          # kept channels that count toward "How many"
    skipped = {"known": 0, "country": 0, "inactive": 0, "off-topic": 0, "off-ICP meaning": 0, "unlike your ratings": 0}
    searches_run, stopped_early, interrupted = 0, None, False

    def evaluate(ch, term):
        """Checks one channel (country, niche, your ratings, recent activity).
        Returns (skip reason, None) or ("kept", (row, description)). Runs in parallel."""
        snippet, stats = ch.get("snippet", {}), ch.get("statistics", {})
        handle = snippet.get("customUrl", "")
        link = (f"https://www.youtube.com/{handle}" if handle.startswith("@")
                else f"https://www.youtube.com/channel/{ch['id']}")
        if link.lower() in known_links or \
                f"https://www.youtube.com/channel/{ch['id']}".lower() in known_links:
            return "known", None
        country = snippet.get("country", "")
        if country not in countries and not (country == "" and args.include_unknown_country):
            return "country", None
        uploads = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        latest, titles, upload_list, last_month = recent_uploads(yt, uploads) if uploads else (None, [], [], [])
        description = snippet.get("description", "")
        text = " ".join([snippet.get("title", ""), description] + titles).lower()
        if match_re and (not match_re.search(text) or not niche_check(
                snippet.get("title", ""), description, " ".join(titles),
                stats.get("subscriberCount", 0))[0]):
            return "off-topic", None
        candidate = {"channel_name": snippet.get("title", ""), "description": description,
                     "recent_videos": join_titles(last_month),
                     "latest_video_title": titles[0] if titles else "", "country": country,
                     "subscribers": stats.get("subscriberCount", 0)}
        # Meaning far from your ICP (e.g. a school, a service club, a video studio)? Skip it.
        vec = semantic.lead_vector(candidate, cache=False)
        icp = semantic.icp_similarity(candidate, vector=vec) if vec is not None else None
        if icp is not None and icp < ICP_SKIP_BELOW:
            return "off-ICP meaning", None
        # Looks like the leads you rated Low? Skip it (once learning is on).
        if learning.adjustment(candidate, vector=vec) <= learning.SKIP_BELOW:
            return "unlike your ratings", None
        latest, activity = activity_check(yt, upload_list, cutoff) if latest and latest >= cutoff else (None, "")
        if latest is None:
            return "inactive", None
        return "kept", ({
            "_titles": " ".join(titles),
            "channel_name": snippet.get("title", ""),
            "channel_link": link,
            "channel_id": ch["id"],
            "country": country or "unknown",
            "subscribers": "" if stats.get("hiddenSubscriberCount") else stats.get("subscriberCount", ""),
            "total_videos": stats.get("videoCount", ""),
            "last_upload": latest.strftime("%Y-%m-%d"),
            "activity": activity,
            "content_type": "Podcast" if ("podcast" in text or "episode" in text) else "Videos",
            "niche_match": "strong" if STRONG_MATCH_RE.search(text) else "weak",
            "best_email": "", "emails": "", "email_source": "", "website": "", "linkedin": "",
            **{name: "" for name in SOCIAL_FIELDS},
            "latest_video_title": titles[0] if titles else "",
            "recent_videos": join_titles(last_month),
            "description": " ".join(description.split())[:5000],
            "found_by": term,
        }, description)

    channel_pool = ThreadPoolExecutor(max_workers=CHANNEL_WORKERS)

    def check_channels(ids, term=""):
        """Checks a page of channels, several at once; results keep YouTube's order."""
        for status, item in channel_pool.map(lambda ch: evaluate(ch, term), fetch_channels(yt, ids)):
            if status == "kept":
                kept.append(item)
                row = item[0]
                early_fit = fit_score(dict(row), row.get("_titles", ""))[0]
                if early_fit + PRE_EMAIL_ALLOWANCE >= goal:
                    on_goal[0] += 1
            else:
                skipped[status] += 1

    try:
        while not target or on_goal[0] < target:
            key = next_search()
            if key is None:
                stopped_early = ("every search phrase is used up for now; add phrases to "
                                 "ICP.md or countries to find more")
                break
            _, _, _, term, country, stype = order[key]
            state = log[key]
            # Always continue from the first page this search hasn't read yet.
            state["next"] = page_token(state["pages"])
            try:
                ids, token = search_one_page(yt, term, country, stype, published_after, state["next"],
                                             order=sort_of[key])
            except ApiError as e:
                if "pageToken" in str(e) or "invalid" in str(e).lower():
                    state.update(done=True, last=datetime.now().isoformat(timespec="seconds"))
                    continue                        # past the last page YouTube offers
                raise
            searches_run += 1
            count_page(term, country)
            state["pages"] += 1
            state["next"] = page_token(state["pages"])
            state["last"] = datetime.now().isoformat(timespec="seconds")
            if not token or state["pages"] >= MAX_PAGES_PER_SEARCH:
                state["done"] = True
            new_ids = [i for i in dict.fromkeys(ids) if i not in seen and i not in known_ids]
            seen.update(new_ids)
            before = len(kept)
            if new_ids:
                check_channels(new_ids, term)
            gained = len(kept) - before
            state["kept"] = state.get("kept", 0) + gained
            state["last_kept"] = gained
            # Two pages in a row with nothing new: this search is drained for now.
            if state["pages"] >= 2 and gained == 0 and state.get("prev_kept", 1) == 0:
                state["done"] = True
            state["prev_kept"] = gained
            print(f"  {country} | {stype:7} {sort_of[key][:5]:5} | {term[:32]:32} | page {state['pages']:2} -> "
                  f"{len(kept) - before:2} new kept  ("
                  + (f"{on_goal[0]}/{target} {args.fit_goal}-fit, {len(kept)} kept" if target else f"{len(kept)}")
                  + 
                  f", ~{yt.units_used} units used)")
    except KeyboardInterrupt:
        interrupted = True
        stopped_early = "Stopped during the search; channels found so far are saved without emails " \
                        "(run 'Fill missing emails & profiles' later)."
        print("\nStopped. Saving the channels found so far...")
    except (QuotaExceeded, BudgetReached) as e:
        stopped_early = ("YouTube's daily quota ran out (resets at midnight US Pacific time)"
                         if isinstance(e, QuotaExceeded) else
                         f"used this run's quota budget ({args.budget} units)")
    except ApiError as e:
        if not kept:
            save_search_log(log)
            sys.exit(f"\nYouTube API error: {e}\nIf a key is wrong, fix YOUTUBE_API_KEYS in .env and run again.")
        stopped_early = f"YouTube API error: {e}"
    finally:
        save_search_log(log)
        yt.save_usage()

    # Emails: description + About links + website contact pages + web search.
    searcher = None
    serper_key = "" if args.no_web_search else load_serper_key(args.serper_key)
    if serper_key:
        searcher = WebSearch(serper_key, args.web_search_limit)
    if kept:
        how = "description only" if args.no_websites else "About links + websites"
        print(f"\nLooking for emails on {len(kept)} channels ({how}"
              + (" + web search" if searcher else "") + ")... this takes a few minutes.")
    rows, done = [], 0
    if interrupted:
        kept, rows = [], [row for row, _ in kept]
    pool = ThreadPoolExecutor(max_workers=6)
    futures = {pool.submit(enrich_channel, dict(row), desc, not args.no_websites, searcher): row
               for row, desc in kept}
    try:
        for fut in as_completed(futures):
            try:
                rows.append(fut.result())
            except Exception as e:
                rows.append(futures[fut])       # keep the channel even if its lookup failed
                print(f"  (email lookup failed for one channel: {e})")
            done += 1
            if done % 10 == 0 or done == len(futures):
                print(f"  {done}/{len(futures)} checked, {sum(1 for r in rows if r['emails'])} with an email")
    except KeyboardInterrupt:
        # Stopped while looking up emails: still save every channel found.
        finished = {r["channel_link"] for r in rows}
        rows += [r for r in futures.values() if r["channel_link"] not in finished]
        stopped_early = (stopped_early or "") + " Stopped during the email look-up; channels saved, " \
            "run 'Fill missing emails & profiles' to finish their emails."
        print("\nStopped. Saving the channels found so far...")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    for r in rows:
        apply_fit(r, r.pop("_titles", ""))
    rows.sort(key=lambda r: (-r["fit_score"], -int(r["subscribers"] or 0)))

    run_name = f"{RUN_PREFIX} {next_run_number():02d}"
    print("\n=== Done ===")
    if stopped_early:
        print(f"NOTE: {stopped_early}.")
    print(f"NEW channels this run:    {len(rows)}")
    print(f"  with an email:          {sum(1 for r in rows if r['emails'])}")
    print(f"  strong niche match:     {sum(1 for r in rows if r['niche_match'] == 'strong')}")
    print(f"Searches run:             {searches_run}")
    if target:
        print(f"Goal: {on_goal[0]} of {target} new leads looked {FIT_GOAL_NAMES[args.fit_goal]} during the search "
              f"({len(kept)} kept in total; final fit scores below include emails found).")
    print(f"Skipped: already found {skipped['known']}, other country {skipped['country']}, "
          f"no upload in {days} days {skipped['inactive']}, off-topic {skipped['off-topic']}, "
          f"off-ICP meaning {skipped['off-ICP meaning']}, unlike your ratings {skipped['unlike your ratings']}")
    print(f"YouTube quota used:       ~{yt.units_used} (of 10,000 per day)")
    if searcher:
        print(f"Web searches used:        {searcher.used}"
              + (f"  (stopped: {searcher.disabled_reason})" if searcher.disabled_reason else ""))

    if not rows:
        print("\nNo new channels, so no file was saved.")
        build_dashboard(open_browser=not args.no_open)
        return
    out_path = RESULTS_DIR / f"{run_name}.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    new_count, total = merge_into_master(rows, FIELDS, run_name)
    add_run_history({
        "run": run_name, "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "new_channels": len(rows), "with_email": sum(1 for r in rows if r["emails"]),
        "strong_match": sum(1 for r in rows if r["niche_match"] == "strong"),
        "searches_run": searches_run, "youtube_units": yt.units_used,
        "web_searches": searcher.used if searcher else 0,
        "countries": " ".join(countries), "note": stopped_early or "",
    })
    try:
        learned = learn_keywords(load_master(), keywords)
        if learned:
            print("\nLearned new search phrases from your best-fit channels (used from the next run):")
            for phrase in learned:
                print(f"  + {phrase}")
    except Exception as e:
        print(f"(Keyword learning skipped: {e})")
    print(f"\nSaved:  results/{out_path.name}")
    print(f"Master: results/{MASTER_CSV.name}  ({total} channels in total)")
    print(f"Log:    results/{RUN_HISTORY.name}\n")
    for r in rows[:15]:
        print(f"  {r['channel_name'][:34]:34}  {r['country']:3}  {r['channel_link'][:48]:48}  {r['best_email']}")
    if len(rows) > 15:
        print(f"  ... and {len(rows) - 15} more in the CSV")
    print()
    save_site_cache()
    self_check_master()
    build_dashboard(open_browser=not args.no_open)


if __name__ == "__main__":
    import signal

    def _stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGHUP, _stop)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled.")
    finally:
        RENDERER.close()
        release_run_lock()
