# LeadTube - cd /Users/tahamansuri/Documents/website/youtube_finder && npm run dev

Finds **new** active YouTube channels in your niche, in the countries you
choose, and looks for a contact email for each one. Every run saves a
numbered file (`Search 01.csv`, `Search 02.csv`, ...). A dashboard lets you
filter leads, write your email, and send them to Smartlead.

## Start it (one click)

Double-click **`Start LeadTube.command`** in this folder. The dashboard opens
at http://localhost:3030. Then click **Find new leads**.

- The first time, it sets itself up (a few minutes): a private Python
  environment in `.venv/` and the dashboard's packages. You only need Node.js
  and Python 3, which are already on this Mac.
- Keep the small Terminal window open while you use the dashboard; close it to stop.
- If macOS says the file can't be opened, right-click it, choose **Open**, then **Open** again (only needed once).

You can also run the finder from Terminal:

```bash
cd /Users/tahamansuri/Documents/website/youtube_finder && .venv/bin/python finder/youtube_finder.py
```

## API keys (.env)

All keys live in one private file, `.env` (`.env.example` shows the format):

| Key | What it is |
|---|---|
| `YOUTUBE_API_KEYS` | YouTube Data API keys, comma-separated. The first is used first; the others take over when one runs out of today's quota. |
| `SERPER_API_KEY` | Serper.dev, for finding emails by web search |
| `SMARTLEAD_API_KEY` | Smartlead (filled in from Settings → Smartlead) |
| `GMAIL_APP_PASSWORD` | Gmail app password (filled in from Settings → Gmail) |

Never share `.env` or put it online.

## Your ICP (one file: ICP.md)

Everything about **who you're looking for** lives in one file, `ICP.md`, in
plain sections. Change your ICP there, or in the dashboard: **Settings →
Ideal lead (ICP)** (with "Jump to section", Save ⌘S and Undo last save). Nothing
in the code needs changing.

| Sections | What they control |
|---|---|
| 1. Ideal lead | Your ideal lead in plain words: the meaning check ("ICP match", off-ICP skips) |
| 2. Search phrases | What is typed into YouTube search (spintax `{a\|b}` allowed) |
| 3–4 | Which found channels are kept, and "strong" vs "weak" match |
| 5–13 | Fit score: best-fit roles, roles, core topic, topics, audience, skills, credentials, speaker signs |
| 14 | Words that show a web result is about their line of work (email checks) |
| 15–16 | Rules for phrases learned from your best leads |
| 17–20 | Not your ICP: off-niche topics, churches, media/schools/companies, organisations |
| 21 | Generic words that are never a person's name |
| 22–24 | Deeper search: word swaps, useful suggestion words, phrases that are not leads |

Format: `*` = any ending (`facilitat*`), `{a|b}` = one item per option, lines
starting with `>` are explanations. Section titles must stay; the dashboard
refuses a save that removes one. The previous version is kept in
`data/ICP.previous.md` for Undo.

## API limits

The strip at the top of the dashboard shows, live:
- each YouTube key's units left today,
- when they reset,
- about how many search pages are left,
- your Serper credits.

## Dashboard (Next.js + React)

A Next.js app in `dashboard/` (React components, API routes in `dashboard/app/api`).
`Start LeadTube.command` installs its packages, builds it when the code
changed, and starts it on http://localhost:3030. By hand: `npm run dev` (live
reload; it keeps its files in `dashboard/.next-dev`, apart from the
production build in `dashboard/.next`) or `npm run build && npm start`. It reads the CSV files
live, so refreshing the page always shows the latest results.

- **Sidebar:** Leads, Email, Runs, Settings, plus today's API usage.
- **Find new leads:** pick countries, how recent the uploads must be, optional
  keywords, and **How many**:
  - **A number** (e.g. 50) = "find me 50 good leads". It keeps searching until
    that many new leads reach the fit level you pick in **Count only**: *Top fit
    only*, *Good fit or better* (default) or *Possible or better*. Lower-fit
    leads found on the way are still saved, they just don't count. Emails are
    looked up for every lead, whatever its fit.
  - **Empty** = "find as many as possible today": it searches until the run's
    quota budget (~9,000 units) is used, and saves everything it found.
  **Stop run** ends a run safely. **Fill missing emails** re-checks channels
  with no email (no YouTube quota).
- **Filters:** run, fit, country, email, status, and under **Filters** niche
  match, content type, size and profiles.
- **Select leads:** tick the checkbox on any rows (or the header box for every
  lead in the current view). A bar appears with:
  - **Export CSV**: only the selected leads, with Email, Channel name, About
    the channel and Last video.
  - **Mark contacted / Unmark**, **Send to Smartlead** (only the selected
    leads), and **✕** to clear the selection.
- **Open a row** to see the full description, other emails, why it got its fit
  score, and **Mark contacted**.
- **Export** (no selection): Smartlead CSV, full CSV, or copy all emails in view.
- **Email dot:** green = found on their website or YouTube; amber = found by
  web search, double-check it.
- Contacted marks are saved in `data/contacted.json`.

Code layout: `dashboard/components` (React components: `leads/`, `email/`,
`settings/`, `dialogs/`), `dashboard/lib/backend.js` (reads the tool's files,
reads `.env`, starts `finder/youtube_finder.py` / `finder/mailer.py`, talks to Smartlead),
`dashboard/lib/personalize.js` (personalization fields).

## Folders

```
youtube_finder/
├── Start LeadTube.command   double-click to start everything
├── .env                     your API keys (private)
├── .env.example             the format of .env
├── README.md
├── package.json             npm run dev / build / start (runs the dashboard)
├── ICP.md                   who you're looking for (the only file to change for a new ICP)
├── finder/                  the Python tool
│   ├── youtube_finder.py    searches YouTube, finds emails and profiles
│   ├── mailer.py            sends single emails from Gmail (optional)
│   ├── settings.py          shared folder paths + reads .env
│   ├── icp.py               reads ICP.md
│   ├── learning.py          learns from your Good / Medium / Low ratings
│   ├── semantic.py          meaning fingerprints (fastembed)
│   ├── variations.py        same-meaning search phrases
│   └── requirements.txt     extra Python libraries (installed automatically)
├── dashboard/               the Next.js + React dashboard
│   ├── app/                 page, layout, styles, API routes (app/api/…)
│   ├── components/          React components (leads/, email/, settings/, dialogs/)
│   ├── lib/                 backend.js (server), client.js, personalize.js
│   └── public/              favicon
├── results/                 everything you open
│   ├── Search 01.csv …      one file per run, only channels new in that run
│   ├── all_channels.csv     master list of every lead (no duplicates)
│   ├── excluded_channels.csv  removed as inactive / off-niche (never found again)
│   └── run_history.csv      one line per run: date, new channels, emails, quota used
├── data/                    the tool's memory and your settings
│   ├── search_log.json      which search pages have been read
│   ├── key_usage.json       YouTube quota used per key per day
│   ├── email_checks.json    when each channel was last web-searched for an email
│   ├── site_checks.json     websites already read (re-read after 14 days, or 30 if they had an email)
│   ├── learned_keywords.txt phrases learned from your best leads
│   ├── contacted.json       leads marked contacted
│   ├── settings.json        Gmail name/address/limits (no secrets)
│   ├── email_copy.json      your email copy (Email page)
│   ├── smartlead.json       leads already sent to Smartlead
│   ├── embeddings.json      meaning fingerprints of your leads (cache)
│   ├── variation_keywords.txt  same-meaning search phrases (weekly)
│   ├── ICP.previous.md      your ICP before the last save (for Undo)
│   ├── ratings.json         your Good / Medium / Low ratings
│   └── learned_model.json   what LeadTube learned from them
├── .models/                 the small meaning model (downloaded automatically)
└── .venv/                   private Python environment (created automatically)
```

## How a run works (smart search)

1. **Keywords:** The search phrases in `ICP.md` (section 2) use spintax: `{executive|leadership} {coach|consultant}`
   expands to every combination. Phrases YouTube treats as the same
   ("coach" / "coaching" / "coaches") are searched only once. Up to 80 phrases.
2. **Learned keywords:** after each run, the tool reads your Top-fit channels'
   names and descriptions, finds phrases several of them use (e.g.
   "executive presence coach") that you don't search yet, and adds them to
   `data/learned_keywords.txt`. Delete any line there you don't want.
3. **Every search is phrase × country × result list**, read one page of 50 at a
   time. `data/search_log.json` records how many pages each one has read, and
   the next run jumps **straight to the next unread page** (YouTube's page
   markers just encode the position, e.g. page 3 = result 100). Page 1 is never
   read or paid for twice.
4. **Planner (how the ~90 search pages a day are shared out):**
   - about **55% podcast phrases, 45% general** phrases,
   - **every phrase gets a page before any phrase gets a second one**; the
     phrase that has waited longest goes first, so over 1-2 runs every keyword
     is used, not just the top ones,
   - pages are spread over your countries by size (US most, then UK, Canada…),
   - each phrase is searched as 6 different result lists (channels by
     relevance / most videos / newest, videos by relevance / newest / most
     viewed), because YouTube returns different channels for each,
   - once every phrase has had its turn, extra pages go to the phrases that
     bring the most new matching channels,
   - two empty pages in a row rest a list for a week.
5. **Filtering:** channels already in `all_channels.csv` or
   `excluded_channels.csv` are skipped. Each new channel must:
   - be in your countries;
   - be active in the window (45 days): a real video over 3 minutes, or at
     least 3 Shorts / clips. Shorts-only channels get an orange **Shorts** tag
     in the dashboard, because their Videos tab can look old;
   - be in the niche, judged from the channel's own name and description
     (leadership, coaching, training, speaking for businesses). News, magazines,
     schools, churches, software companies, off-niche topics and 1M+ media
     brands are dropped.

   To re-check the saved list later (about 1 YouTube unit per channel):
   `.venv/bin/python finder/youtube_finder.py --clean`. Removed channels move to
   `results/excluded_channels.csv` with the reason, and are never found again.
6. **Stopping:** a run stops at your channel limit, or (default) when the run's
   quota budget is used.

## How emails are found, in order

1. **Channel description** on YouTube.
2. **The coach's website.** The tool follows the links on the channel's public
   About section and reads the homepage plus up to 4 contact or about pages.
   It also reads link-in-bio pages (Linktree, Stan, Beacons), decodes emails
   hidden with Cloudflare's protection, and retries sites that fail to load.
   If no email turns up, the site is opened in a real (headless) browser,
   which sees contact details that only appear with JavaScript.
   Emails whose domain can't receive mail are dropped (DNS check).
   Sites that block automated visitors (403) and contact-form-only sites
   have no email to find.
3. **Web search** (Serper), only for channels still without an email. It
   searches `"<name>" email` and `"<name>" contact email facebook OR linkedin
   OR instagram`, and reads emails shown in results that mention that name.

## Which emails are kept

- **Kept:** personal emails (`john@company.com`, `jane@gmail.com`) and shared
  inboxes (`info@`, `contact@`, `hello@`, `team@`, `bookings@`).
- **Dropped:**
  - department or system addresses (`support@`, `careers@`, `billing@`, `privacy@`, `noreply@` ...),
  - placeholders,
  - emails on unrelated domains.
- **`best_email`** is the one to use: personal first, then `info@`/`contact@`.

## Social profiles from websites

A coach's website can be found three ways: listed on their YouTube About
page, in their description, or by Google search. Whichever way, LeadTube reads
the **saved website for both emails and social profiles** (LinkedIn, Facebook,
Instagram, X, TikTok), and saves the homepage as the website.

**Self-check:** at the end of every search and every **Fill missing emails**,
LeadTube compares each lead's saved profiles with what its website is known to
link to (website memory, no internet needed) and fills anything missing. The
run log says "Self-check: N missed social profiles added" or "every lead's
social profiles match its website".

## Rate leads: LeadTube learns what you like

Every lead has three buttons in the **Your rating** column: 👍 **Good**,
○ **Medium**, 👎 **Low** (click again to clear). To rate many at once, select
them and use **Rate** in the selection bar. The tool never rates for you.

**What it reads** to learn what your Good and Low leads have in common:

| Part of the channel | Weight |
|---|---|
| Description (about the channel, in full) | full |
| Titles of videos posted in the last 30 days | full |
| Channel facts (podcast or not, size, country, Shorts-only, email, LinkedIn) | medium |
| Channel name | low |

Opening a lead shows its last-30-day video titles under **Videos in the last
30 days**. They are saved for every new lead (column `recent_videos`) and
refreshed by `--clean`.

After **8 ratings** (with at least 2 Good and 2 Medium/Low) learning switches
on, and a few seconds after each rating:
- **Fit scores** change: leads that look like your Good ones go up, leads that
  look like your Low ones go down (up to ±25 points; the reason says
  "your ratings +8").
- **Next searches**:
  - search phrases that found your Good leads are read deeper, and phrases
    that only found Low leads are read less;
  - new channels that look like your Low leads are skipped;
  - new search phrases are learned from your Good leads.

The bar above the leads shows how many you've rated. **What it learned** lists
the words and channel types it now associates with Good and Low leads. Filter
by rating under **Filters → Your rating**.

Files: `data/ratings.json` (your ratings), `data/learned_model.json` (what was
learned), `finder/learning.py` (the learning code).

## Meaning, not just words

LeadTube reads each channel's **description and last-30-day video titles** and
turns them into a "meaning fingerprint" with a small model that runs on this
Mac (`fastembed`, ~64 MB in `.models/`, no internet needed after the first
download). So it understands that "C-suite mentor", "leadership advisor" and
"executive coach" are about the same thing.

Everything is anchored to **your ideal lead**, described in plain words in
section 1 of `ICP.md` (edit it any time). It's used three ways:
- **Fit score:** "ICP match +4" means the channel is closer in meaning to your
  ICP than a typical lead (up to +8), "ICP match -6" further away (down to -8).
- **Searches skip** channels whose meaning is far from your ICP (a school, a
  service club, a video studio...): shown as "off-ICP meaning" in the run summary.
- **Learning from your ratings** uses meaning too: leads that *mean* the same
  as your Good leads go up, even when they use different words.

If the model can't load, LeadTube simply works with words only.

## Deeper search: same-meaning phrases

Once a week, before a search, LeadTube builds up to 40 extra search phrases
from your keywords (no YouTube quota is used):
- **YouTube's own suggestions:** what people type after your phrases, kept
  only when the added words are useful, e.g. "for women", "new managers",
  "remote teams". Names, languages and celebrities are dropped.
- **Word swaps inside your niche:** coach ↔ mentor / advisor / consultant,
  executive ↔ C-suite / CEO, podcast ↔ show / interviews.

Each phrase must pass the niche rules and be close in meaning to your ICP;
phrases about jobs, courses, certifications or "how to become a coach" are
dropped. They're saved in `data/variation_keywords.txt` (delete any line you
don't want) and searched next to your keywords and learned phrases. To rebuild
now: `.venv/bin/python finder/youtube_finder.py --refresh-variations --dashboard`.

## Emails from Facebook

Facebook is searched **only when the coach's website has no email** (or they
have no website). Order: YouTube description → link-in-bio page → website
(homepage + contact/about pages) → web search → **Facebook**.

LeadTube searches Google for their Facebook page and for "*name* facebook
email" (Facebook pages need a login, so they aren't opened directly). It keeps
an email only if it clearly belongs to the coach:
- it's shown on **their own Facebook page**, or
- it's on **their website's domain or the same brand** (e.g. milewalk.com for
  milewalkacademy.com), or
- the address carries **their name or @handle**, and the result is about coaching or speaking
  (so a realtor with the same name is ignored).

These emails show an amber dot: double-check them.

**Generic inboxes** (support@, help@, service@) are kept only as a last resort
and only on the coach's own domain: many small coaching businesses publish
just one of those.

## Email page (your copy)

Sidebar → **Email**. Write your subject and message once. Use **Insert field**
to add a lead's details where you want them. The preview on the right shows
the email exactly as a real lead will get it (pick any lead from the dropdown).
It warns you if a field is empty for that lead. Save with the button or ⌘S.

| Field | Example |
|---|---|
| `{{greeting_name}}` | Sarah, or "there" when the name is unknown (use this for "Hi …") |
| `{{first_name}}` | Sarah (empty when unsure); `{{first_name\|there}}` sets your own fallback |
| `{{personal_line}}` | I watched your recent video "Leading through change" |
| `{{channel_name}}` | The Leadership Dance |
| `{{latest_video}}` | Leading through change (cleaned: no hashtags or emojis) |
| `{{content_kind}}` | podcast / YouTube channel |
| `{{subscribers}}`, `{{country}}`, `{{website}}` | 11.1K, United States, … |

Your copy is saved in `data/email_copy.json` and used in three places:
**Send to Smartlead**, the **Smartlead CSV**, and one-off Gmail emails.

## Smartlead

1. **Settings → Smartlead:** paste your API key (Smartlead: profile → Settings →
   API key), click **Test connection**, and choose a default campaign.
2. **In your Smartlead campaign:** set the email subject to `{{email_subject}}`
   and the body to `{{email_body}}`. LeadTube sends every lead with your copy
   already filled in for them (line breaks kept). You can also use the single
   fields above directly in Smartlead.
3. **Leads page:** filter (e.g. Top fit, Not in Smartlead), click **Send to
   Smartlead**, choose the campaign, check the first lead's email, then add.
   Leads are marked contacted and tagged "Smartlead", and they're never added
   twice. Smartlead's own block, unsubscribe and duplicate checks stay on.

**Export → Smartlead CSV** downloads the same thing as a file for importing by
hand (also works for Instantly or Lemlist). The record of what was sent is
kept in `data/smartlead.json`.

## Gmail (optional)

**Settings → Gmail:** your name, email address and a Gmail app password (Google
Account → Security → 2-Step Verification → App passwords). **Test login**
checks it and sends nothing. After that, opening a lead's row shows **Email
this lead**: your copy filled in for them, editable, sent from your inbox.
Limited to 30 a day by default (Settings → Gmail → Advanced). Nothing is added
to your email; it's sent exactly as written. Sent emails are logged in
`data/email_log.json`, and anyone in `data/unsubscribed.json` is never emailed.

## Speed

- **Searches** check 6 channels at the same time (same quota, about 4× faster),
  and retry a dropped connection a few times instead of stopping the run.
- **Websites** already read are remembered in `data/site_checks.json`: a site
  with no email is re-read after 14 days, one with an email after 30. So
  **Fill missing emails** re-runs take a minute or two instead of 10+. The memory
  resets by itself whenever the email rules are improved.

## Limits

- **YouTube:** 10,000 quota units a day, resetting at midnight US Pacific
  time. A page of results costs 100. A run of 72 new channels usually costs
  2,000–5,000, so about 2–4 runs a day.
- **Serper:** 2,500 free searches in total (one-time), at most 2 per channel
  without an email.

## Several YouTube keys

Each run uses one key from `YOUTUBE_API_KEYS`: whichever has more of today's quota left (tracked in
`data/key_usage.json`). If that key runs out partway through, the run switches
to the next key and carries on. The terminal and the dashboard log say which
key a run is using.

## Useful options

| Option | What it does |
|---|---|
| `--target 100` | stop after 100 new channels (default: no limit, use the day's quota) |
| `--countries "US, UK, Canada, Australia"` | choose countries ("America"/"USA" = US) |
| `--days 60` | allow channels that uploaded in the last 60 days |
| `--include-unknown-country` | keep channels that never set a country |
| `--no-websites` | skip website visits (fast, fewer emails) |
| `--no-web-search` | skip Serper web search |
| `--include-known` | also return channels already found before |
| `--dashboard` | open the dashboard if it's running |
| `--fill-missing` | only look up emails for channels in `all_channels.csv` that have none (no YouTube quota used) |
| `--clean` | re-check saved channels and move inactive / off-niche ones to `excluded_channels.csv` |
| `--yes` | don't ask questions, use defaults |

