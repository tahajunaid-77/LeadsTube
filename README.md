# LeadTube

**Find coaches, consultants and podcast hosts on YouTube who fit your ideal client, get their contact details, and send them to your outreach tool.**

LeadTube searches YouTube for active channels in your niche, finds each one's email, website and social profiles, scores how well they fit, and learns from your feedback which leads you like best. Everything is managed from a simple dashboard on your Mac.

<br>

## What it does

- 🔎 **Finds new channels** in your niche and chosen countries that posted in the last 45 days. It never shows you the same channel twice.
- 📧 **Finds contact emails** from the channel, the coach's website, Google and Facebook.
- 🔗 **Collects profiles**: website, LinkedIn, Facebook, Instagram, X, TikTok, podcast.
- ⭐ **Scores every lead** from 0 to 100: *Top fit*, *Good fit*, *Possible* or *Low fit*.
- 🧠 **Learns from you**: rate leads Good, Medium or Low and it finds more like your Good ones.
- ✉️ **Sends to Smartlead** (or exports a CSV), with your email copy filled in for each lead.

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
| `SERPER_API_KEY` | Recommended | [serper.dev](https://serper.dev), for finding emails through Google |
| `SMARTLEAD_API_KEY` | Optional | Smartlead → Settings → API key (or add it later in the dashboard) |
| `GMAIL_APP_PASSWORD` | Optional | For sending single emails from Gmail (or add it later in the dashboard) |

**3. Start it.** Double-click **`Start LeadTube.command`**.
The first start sets everything up (a few minutes). After that the dashboard opens at **http://localhost:3030**. Keep the small Terminal window open while you use it.

> If macOS says the file can't be opened: right-click it → **Open** → **Open** (only needed once).

<br>

## Using the dashboard

### Leads
Your list of leads, best fit first.
- **Find new leads:** pick countries, how recent the uploads must be, and **How many**:
  - **A number** (e.g. 50) means "find me 50 good leads". **Count only** picks what counts: Top fit, Good fit or better, or Possible or better. Weaker leads found along the way are still saved.
  - **Empty** means "find as many as possible today", until the day's search budget is used.
- **Filters:** run, fit, country, email, status, your rating, content type, size, profiles.
- **Click a row** to see the full description, the last 30 days of videos, all emails and why it got its score.
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

<br>

## Your ideal client: `ICP.md`

Everything about **who LeadTube looks for** is in one file, **`ICP.md`**. Edit it in any text editor, or in the dashboard under **Settings → Ideal lead (ICP)**. No code changes needed.

It has plain sections such as:
- **Ideal lead:** a few sentences describing your perfect lead.
- **Search phrases:** what LeadTube types into YouTube, e.g. `{executive|leadership} coach`.
- **Roles, topics and audience:** what makes a strong fit.
- **Not my ICP:** topics and kinds of channels to leave out.

Each section explains itself. Keep the section titles as they are; the dashboard won't save if one is missing, and **Undo last save** brings back the previous version.

<br>

## How it works

**Finding channels.** LeadTube searches YouTube with your search phrases, page by page, and remembers where it stopped, so the next search continues instead of repeating. Once a week it also adds up to 40 phrases that mean the same as yours (from YouTube's own suggestions and word swaps like coach → mentor). A channel is kept only if it's in your countries, posted a real video (or regular Shorts) in the last 45 days, talks about your niche, and is close in meaning to your ideal lead.

**Finding emails.** In this order, until one is found:
1. the YouTube description,
2. link-in-bio pages,
3. the coach's website (homepage and contact/about pages),
4. a Google search,
5. their Facebook page (only when the website has no email).

Emails must clearly belong to the coach, and their domain must be able to receive mail. An **amber dot** means "found by search, worth a double-check".

**Scoring.** Every lead gets 0–100 points for things like a strong role (executive/leadership coach), your core topic, who they work with, having a podcast, being reachable (email, LinkedIn), and how close they are in meaning to your ideal lead.

**How it learns.** After **8 ratings** (with at least 2 Good and 2 Medium/Low), your ratings start shaping:
- **Fit scores:** leads like your Good ones go up, leads like your Low ones go down (up to ±25).
- **Searches:** phrases that found Good leads are searched deeper, and channels like your Low ones are skipped.
- **New phrases:** learned from your Good leads.

It reads mostly the channel description and recent video titles, and understands meaning (so "C-suite mentor" ≈ "executive coach") using a small AI model that runs on your Mac. The bar above your leads shows **What it learned**.

<br>

## Costs and limits

| | Limit | Notes |
|---|---|---|
| **YouTube API** | 10,000 units per key per day (free) | About 90 search pages per key per day. Resets at midnight US Pacific time. Add more keys for more. |
| **Serper** | One-time credit pack | Used only when a channel's own pages have no email. |
| **Gmail** | 30 emails a day (changeable) | For campaigns, use Smartlead. |

The sidebar shows today's usage live.

<br>

## Privacy

Your keys (`.env`), your leads (`results/`) and the tool's memory (`data/`) stay on your Mac and are never uploaded to GitHub (see `.gitignore`). The dashboard only runs on your own computer (`localhost`).

<br>

## Project structure

```
LeadsTube/
├── Start LeadTube.command   one-click setup and start
├── ICP.md                   who you're looking for
├── .env.example             template for your API keys
├── finder/                  the search tool (Python)
├── dashboard/               the dashboard (Next.js + React)
├── results/                 your leads as CSV files (created on first search)
└── data/                    the tool's memory and settings (created automatically)
```

<details>
<summary><b>More detail: files, commands and FAQ</b></summary>

<br>

**Python files (`finder/`)**

| File | What it does |
|---|---|
| `youtube_finder.py` | Searches YouTube, finds emails and profiles, scores leads |
| `learning.py` | Learns from your ratings |
| `semantic.py` | Meaning fingerprints (local AI model, `fastembed`) |
| `variations.py` | Weekly same-meaning search phrases |
| `icp.py` | Reads `ICP.md` |
| `mailer.py` | Gmail sending |
| `settings.py` | Folder paths and `.env` |

**Result files (`results/`):** `Search 01.csv`, `Search 02.csv`, ... (one per search), `all_channels.csv` (every lead), `excluded_channels.csv` (removed as inactive or off-niche; never found again), `run_history.csv`.

**Commands** (run from the project folder; the dashboard does these for you):
```bash
npm run dev                                                # dashboard with live reload
.venv/bin/python finder/youtube_finder.py                  # a search from the terminal
.venv/bin/python finder/youtube_finder.py --fill-missing   # look up missing emails & profiles (no YouTube quota)
.venv/bin/python finder/youtube_finder.py --clean          # remove inactive / off-niche leads
.venv/bin/python finder/youtube_finder.py --help           # all options
```

**FAQ**

- **The dashboard doesn't open.** Make sure the Terminal window from `Start LeadTube.command` is still open, then go to http://localhost:3030.
- **"Quota used up".** All your YouTube keys have used today's 10,000 units. They reset at midnight US Pacific time, or add another key to `.env`.
- **A lead has the wrong email.** Emails with an amber dot came from search; double-check those. Mark the lead **Low** so LeadTube learns.
- **I want different kinds of leads.** Edit `ICP.md` (Settings → Ideal lead), especially *Ideal lead* and *Search phrases*.
- **Start fresh on another computer.** Clone the repo, add `.env`, double-click `Start LeadTube.command`.

</details>
