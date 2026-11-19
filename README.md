# LeadTube

**Find YouTube creators who match your ideal customer, get their contact details, and send them to your outreach tool.**

You describe who you're looking for (your ICP: ideal customer profile), for example business coaches, SaaS founders, fitness trainers, real estate agents, financial advisors or podcast hosts in a certain niche. LeadTube searches YouTube for active channels that match, finds each one's email, website and social profiles, scores how well they fit, and learns from your feedback which leads you like best. Everything is managed from a simple dashboard on your Mac.

<br>

## What it does

- 🔎 **Finds new channels** in your niche and chosen countries that posted in the last 45 days. It never shows you the same channel twice.
- 🎙️ **Finds podcasts through their guests**: it reads the episodes of podcasts you already have, and searches the guests' names to find other podcasts they appeared on.
- 📧 **Finds up to 2 emails per lead**: the owner's own address first, from their website and their public Facebook page.
- 🔗 **Collects profiles**: website, LinkedIn, Facebook, Instagram, X, TikTok, podcast.
- ⭐ **Scores every lead** from 0 to 100: *Top fit*, *Good fit*, *Possible* or *Low fit*.
- 🧠 **Learns from you**: rate leads Good, Medium or Low and it finds more like your Good ones.
- ✉️ **Sends leads to your cold-email tool** (Smartlead) or exports a CSV, with your email copy filled in for each lead.

<br>

## How it's different

Most lead tools either give you a database of big creators, or scrape whatever is on a YouTube page. LeadTube is built around **your** ideal customer:

| | Typical lead tools | LeadTube |
|---|---|---|
| **Who you get** | Large creators sorted by followers | Channels that match *your* ICP, scored for fit |
| **Freshness** | Often outdated lists | Only channels that posted in the last 45 days; never the same channel twice |
| **Finding more** | Keyword search only | Keywords, same-meaning phrases, and the guests of podcasts you already have |
| **Emails** | Only what's on the YouTube page | Website (contact pages too), Facebook Intro, link-in-bio pages and Google, ranked so the owner's own address comes first |
| **Getting better** | Same results every time | Learns from your Good / Medium / Low ratings and understands meaning, not just keywords |
| **Changing your target** | New filters or a new subscription | Edit one file (`ICP.md`) |
| **Cost and data** | Monthly subscription; your data on their servers | Runs on your Mac with free YouTube API keys; your leads stay with you |

<br>

## How much time it saves

Finding one good lead by hand usually means: searching YouTube, opening the channel, checking it's still active, reading the About section, judging the fit, finding their website, hunting for an email on the contact page and Facebook, finding their LinkedIn, and copying it all into a sheet. That's roughly **5–10 minutes per lead**.

| | By hand | With LeadTube |
|---|---|---|
| **100 leads** | about 8–16 hours | a few minutes to start a search, then it runs on its own |
| **Checking they're active and on-target** | open every channel | automatic (last 45 days, ICP match) |
| **Emails and profiles** | search each one | found automatically for every lead |
| **Avoiding duplicates** | keep track yourself | automatic: you never see the same channel twice |
| **Into your outreach tool** | copy and paste | one click to Smartlead or a CSV |

*Estimates: actual numbers depend on your niche and how much YouTube quota you have. A single search typically adds dozens of new leads.*

<br>

## Quick start

**You need:** a Mac, [Node.js](https://nodejs.org) (LTS) and Python 3. Everything else installs itself.

**1. Get the code**
```bash
git clone https://github.com/tahajunaid-77/LeadsTube.git
cd LeadsTube
```

**2. Add your keys.** Copy `.env.example` to `.env` and fill it in:

| Key | Needed? | Where to get it |
|---|---|---|
| `YOUTUBE_API_KEYS` | **Yes** | Google Cloud Console → *YouTube Data API v3* → Credentials. Add several, separated by commas, for more daily searches. |
| `SERPER_API_KEY` | Recommended | [serper.dev](https://serper.dev), for finding emails through Google. Several keys separated by commas: the next is used when one runs out. |
| `SMARTLEAD_API_KEY` | Optional | Smartlead → Settings → API key (or add it later in the dashboard) |
| `GMAIL_APP_PASSWORD` | Optional | For sending single emails from Gmail (or add it later in the dashboard) |

**3. Start it.** Double-click **`Start LeadTube.command`**.
The first start sets everything up (a few minutes). After that the dashboard opens at **http://localhost:3030**. Keep the small Terminal window open while you use it.

> If macOS says the file can't be opened: right-click it → **Open** → **Open** (only needed once).

<br>

## Using the dashboard

### Leads
Your list of leads, best fit first. Each row shows up to **2 emails**, each with a copy button.
- **Find new leads:** pick countries, how recent the uploads must be, and **How many**:
  - **A number** (e.g. 50) means "find me 50 good leads". **Count only** picks what counts: Top fit, Good fit or better, or Possible or better. Weaker leads found along the way are still saved.
  - **Empty** means "find as many as possible today", until the day's search budget is used.
- **Fill missing emails:** re-checks leads with no email, only shared inboxes (info@, pr@…) or just one email. Uses no YouTube quota.
- **Filters:** run, fit, country, email, status, your rating, content type, size, profiles.
- **Click a row** to see the full description, the last 30 days of videos, where the email was found, why it got its score, and whether it was *found through a guest*.
- **Rate** each lead 👍 Good, ○ Medium or 👎 Low. LeadTube learns from it (see *How it learns* below).
- **Tick leads** to export them (email, channel name, about, last video), mark them contacted, rate them or send them to Smartlead.

### Email
Write your email once. Use **Insert field** to add each lead's details, e.g. `{{greeting_name}}` (first name, or "there" if unknown) or `{{personal_line}}` ("I watched your recent video ..."). The preview shows the email exactly as a real lead will get it.

### Runs
Every search: when it ran, how many new leads it found and how many have an email.

### Settings
- **Ideal lead (ICP):** edit who you're looking for (see below).
- **Smartlead:** API key and default campaign. In your Smartlead campaign, set the subject to `{{email_subject}}` and the body to `{{email_body}}`, and every lead gets your copy with their details filled in.
- **Gmail** (optional): send single emails from your inbox (30 a day by default).

The sidebar shows today's YouTube quota and your Serper credits (all keys added up).

<br>

## Your ideal client: `ICP.md`

Everything about **who LeadTube looks for** is in one file, **`ICP.md`**. Point it at any niche: change the ideal-lead description, search phrases and roles, and LeadTube follows. Edit it in any text editor, or in the dashboard under **Settings → Ideal lead (ICP)**. No code changes needed.

It has plain sections such as:
- **Ideal lead:** a few sentences describing your perfect lead (plus optional *soft notes*: nice-to-haves, not rules).
- **Search phrases:** what LeadTube types into YouTube, e.g. `{business|marketing} coach` or `{saas|startup} founder podcast`.
- **Roles, topics and audience:** what makes a strong fit.
- **Not my ICP:** topics and kinds of channels to leave out.

Each section explains itself. Keep the section titles as they are; the dashboard won't save if one is missing, and **Undo last save** brings back the previous version.

<br>

## How it works

### 1. Finding channels
Each run mixes three kinds of search:

| Share | Search | How |
|---|---|---|
| ~72% | **Your search phrases** | Read page by page; LeadTube remembers where it stopped, so the next run continues instead of repeating. Phrases that keep finding good leads are read deeper. About half are podcast phrases. |
| (inside the 72%) | **Same-meaning phrases** | Once a week, up to 40 phrases that mean the same as yours (YouTube's own suggestions and word swaps you define, like coach → mentor). |
| ~28% | **Guest search** | Reads the episodes of podcasts you already have, picks out each guest's name (*"… with Jane Smith"*, *"Guest: Jane Smith"*, *"/ Jane Smith, Company"*), and searches YouTube for other podcasts that guest appeared on. Podcasts you rated Good go first; every guest is searched once. |

Every channel found, however it was found, must pass the same checks: in your countries, a real video (or regular Shorts) in the last 45 days, about your niche, close in meaning to your ideal lead, and not like the leads you rated Low.

### 2. Finding emails and profiles
For each new channel, in this order:
1. the YouTube description, About links and link-in-bio pages (short links like bit.ly are followed to the real page),
2. **their websites**, the one named after them first, up to 3 sites: the homepage, then contact and about pages (`/contact` and `/contact-us` are always tried) until a person's email is found. Sites built with JavaScript are opened in a real browser,
3. **their public Facebook page**: the email in its Intro box (no login needed),
4. Google (via Serper), only while the owner's own email is still missing: Google results for their Facebook page, then the owner's own name when the channel is a brand (*"… led by Jane Smith"*).

**Which emails are kept** (at most 2):

| Rank | Email |
|---|---|
| 1 | The channel owner's own name, on any domain: `jane@theircompany.com`, `janesmith@gmail.com` |
| 2 | `name@company.com` |
| 3 | `company@gmail.com` |
| 4 | `name@gmail.com` |
| 5–8 | `info@`, `hello@`, `contact@`, `enquiries@` (in that order) |
| 9–10 | other shared inboxes (`pr@`, `media@` …), then `support@` / `help@` |
| last | someone else's address that happened to be on the page |

One email comes from their **website** and one from **Facebook**; if Facebook has none, the best two from the website. An address must belong to the coach (their domain, their name or brand, or listed by them on Facebook) and its domain must be able to receive mail. Addresses of platforms (booking tools like cal.com and Calendly, form tools, podcast hosts, link shorteners…) are never kept. An **amber dot** means "found by Google search, worth a double-check".

### 3. Scoring
Every lead gets 0–100 points for things like having the roles, topics and audience in your ICP, having a podcast, being reachable (email, LinkedIn), being close in meaning to your ideal lead, and being named after a person (a small bonus: a personal brand is usually one reachable expert). The **Why this fit score** line shows the reasons.

### 4. How it learns
After **8 ratings** (with at least 2 Good and 2 Medium/Low), your ratings start shaping:
- **Fit scores:** leads like your Good ones go up, leads like your Low ones go down (up to ±25).
- **Searches:** phrases that found Good leads are searched deeper, and channels like your Low ones are skipped.
- **New phrases and guest search:** learned from your Good leads; your Good podcasts are the first whose guests are searched.

It reads mostly the channel description and recent video titles, and understands meaning (so "personal trainer" and "online fitness coach" count as similar) using a small AI model that runs on your Mac. The bar above your leads shows **What it learned**.

### 5. Speed and reliability
- Channels are checked **12 at a time**, emails looked up 12 at a time, and up to 6 browser pages at once.
- Connections are kept open and reused (HTTP/2), and YouTube is asked about 50 channels per call.
- If your router fails to look a website up, LeadTube asks public DNS (Cloudflare, Google) instead, for normal requests and for the browser.
- Everything already done is remembered: search pages, guests, website reads (but never a failed read), meaning fingerprints. Re-runs skip it.

<br>

## Costs and limits

| Service | Limit | What uses it |
|---|---|---|
| **YouTube Data API** | 10,000 units per key per day (free); resets at midnight US Pacific time | A search page (50 results) = 100 units. Checking a channel ≈ 2–3 units. Reading a podcast's episodes = 1 unit per 50 episodes. About 90 search pages per key per day; add more keys for more. |
| **Serper (Google)** | Credit packs; several keys are used one after another | 1 credit per search, only while a lead's own email is still missing (at most 400 per run). Fill missing emails skips leads searched in the last 30 days. |
| **Websites, Facebook pages, YouTube About pages** | Free | Read directly; `robots.txt` is respected. |
| **Gmail** | 30 emails a day (changeable) | Single emails only; for campaigns, use Smartlead. |

<br>

## Privacy

Your keys (`.env`), your leads (`results/`) and the tool's memory (`data/`) stay on your Mac and are never uploaded to GitHub (see `.gitignore`). The dashboard only runs on your own computer (`localhost`). Facebook pages are read logged out, exactly as anyone sees them.

<br>

## Project structure

```
LeadsTube/
├── Start LeadTube.command   one-click setup and start
├── ICP.md                   who you're looking for
├── .env.example             template for your API keys
├── finder/                  the search tool (Python)
├── dashboard/               the dashboard (Next.js + React, TypeScript)
├── results/                 your leads as CSV files (created on first search)
└── data/                    the tool's memory and settings (created automatically)
```

<details>
<summary><b>More detail: files, packages, commands and FAQ</b></summary>

<br>

**Python files (`finder/`)**

| File | What it does |
|---|---|
| `youtube_finder.py` | Searches YouTube, finds emails and profiles, scores leads, Fill missing emails |
| `guests.py` | Guest search: reads podcast episodes, picks out guest names, searches them |
| `learning.py` | Learns from your ratings |
| `semantic.py` | Meaning fingerprints (local AI model) |
| `variations.py` | Weekly same-meaning search phrases |
| `icp.py` | Reads `ICP.md` |
| `mailer.py` | Gmail sending |
| `settings.py` | Folder paths and `.env` |

**Python packages** (installed automatically into `.venv`)

| Package | Used for |
|---|---|
| `httpx[http2]` | Fast requests with reused connections (YouTube, Serper, websites) |
| `playwright` | Headless Chromium for JavaScript websites and Facebook pages |
| `fastembed` | Local AI model (`bge-small-en-v1.5`) for meaning: ICP match and learning |
| `dnspython` | Checks an email's domain can receive mail; public DNS fallback |
| `tldextract` | Correct domain matching (`.co.uk`, `.com.au` …) |
| `certifi` | Up-to-date security certificates |

**Dashboard (`dashboard/`):** Next.js 15 + React 19, written in TypeScript (strict). `app/` holds the page and the API routes, `components/` the screens, `lib/` the server logic (`backend.ts`: reads the CSV/JSON files, starts searches, talks to Smartlead), browser helpers (`client.ts`), email personalization (`personalize.ts`) and the shared data types (`types.ts`).

**Result files (`results/`):** `Search 01.csv`, `Search 02.csv`, ... (one per search), `all_channels.csv` (every lead), `excluded_channels.csv` (removed as inactive or off-niche; never found again), `run_history.csv`.

**Memory (`data/`):** `search_log.json` (pages read), `guest_search.json` (podcasts read, guests searched), `site_checks.json` (website reads), `embeddings.json` (meaning fingerprints), `email_checks.json` (when each lead was last searched on Google), `key_usage.json` (quota per key), `ratings.json` and `learned_model.json` (your ratings and what was learned).

**Commands** (run from the project folder; the dashboard does these for you):
```bash
npm run dev                                                # dashboard with live reload
npm --prefix dashboard run typecheck                       # check the dashboard code for type errors
.venv/bin/python finder/youtube_finder.py                  # a search from the terminal
.venv/bin/python finder/youtube_finder.py --no-guests      # a search without guest search
.venv/bin/python finder/youtube_finder.py --fill-missing   # look up missing emails & profiles (no YouTube quota)
.venv/bin/python finder/youtube_finder.py --clean          # remove inactive / off-niche leads
.venv/bin/python finder/youtube_finder.py --help           # all options
```

**FAQ**

- **The dashboard doesn't open.** Make sure the Terminal window from `Start LeadTube.command` is still open, then go to http://localhost:3030.
- **"Quota used up".** All your YouTube keys have used today's 10,000 units. They reset at midnight US Pacific time, or add another key to `.env`.
- **A lead has only one email.** The coach lists only one address on their website and Facebook. Run **Fill missing emails** after a while; it checks again for free.
- **A lead has the wrong email.** Emails with an amber dot came from Google; double-check those. Mark the lead **Low** so LeadTube learns.
- **I want different kinds of leads.** Edit `ICP.md` (Settings → Ideal lead), especially *Ideal lead* and *Search phrases*.
- **Start fresh on another computer.** Clone the repo, add `.env`, double-click `Start LeadTube.command`.

</details>
