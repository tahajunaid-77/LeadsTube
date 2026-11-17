// Personalization fields for cold email tools (Smartlead, Instantly...).
// No AI: everything comes from what LeadTube already found about the channel.
import type { PersonalFields } from "@/lib/types";

/** The lead columns personalization reads. */
export type LeadLike = Partial<Record<"channel_name" | "description" | "best_email" | "latest_video_title" | "subscribers" | "country" | "fit_score" | "channel_link" | "website" | "linkedin", string>>;

// Words that are never a first name.
const NOT_NAMES = new Set(("the a an and of for with by to in on at my your our dr dr. mr mrs ms coach coaching coaches " +
  "leadership leader leaders lead leading executive exec ceo official team group inc llc ltd co company consulting consultant " +
  "consultants podcast show channel tv media studio studios academy institute school university network collective " +
  "business success life career growth global international impact training trainer speaker speaking speaks keynote " +
  "development strategies strategy solutions partners advisors advisory management human people culture work workplace " +
  "women woman men black real true new next better best simple modern daily weekly radio talk talks conversations " +
  "insights mindset motivation all personal city town county state nation rocket unlocked unfiltered uncensored hr sales marketing build building grow corporate competitor enterprises enterprise associates association llc. ventures labs lab works project projects foundation center centre brand brands method methods effect edge way path journey summit health wealth faith family kingdom church").split(/\s+/));
// Inbox names that belong to a role, not a person.
const ROLE_INBOX = new Set(("info contact hello hi hey team admin support office mail email sales booking bookings book " +
  "podcast pod show media press pr partnerships partner partners inquiries inquiry enquiries enquiry connect help events " +
  "speaking speaker coach coaching studio news newsletter marketing hr jobs careers social community general welcome " +
  "service services customer clients client business biz host hosts editor feedback questions ask yes all me us office1 web website websitebookings").split(/\s+/));

const cap = (w: string) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
const words = (s: string | undefined): string[] => (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").match(/[A-Za-z][A-Za-z'’-]*/g) || [];

function firstName(c: LeadLike): string {
  const name = c.channel_name || "";
  const nameWords = words(name).map(w => w.toLowerCase());
  const descWords = new Set(words((c.description || "").slice(0, 300)).filter(w => /^[A-Z][a-z]/.test(w)).map(w => w.toLowerCase()));
  // 1. Personal inbox whose name also appears in the channel name / description: stephanie@... + "Stephanie Wachman".
  const local = ((c.best_email || "").split("@")[0] || "").toLowerCase();
  const part = local.split(/[._+\-0-9]/)[0];
  if (part.length >= 3 && part.length <= 12 && /^[a-z]+$/.test(part) && !ROLE_INBOX.has(part) && !NOT_NAMES.has(part)
      && (nameWords.includes(part) || descWords.has(part))) return cap(part);
  // 2. Channel named after a person: "Matt Foss | Leadership Coach", "Dr. Joanna Lott Coaching".
  //    Each part of the title is checked ("Speak by Design | Stephanie Bickel"); a part must start
  //    with two capitalized words that aren't business words ("Lee Povey Leadership Coach" -> Lee).
  for (const seg of name.split(/\s[|\-–—:•·~]\s|[|•·~:,]/)) {
    const ws = words(seg.replace(/^\s*(dr\.?|coach|mr\.?|mrs\.?|ms\.?)\s+/i, ""));
    const [f, l] = ws;
    if (!f || !l) continue;
    const nameLike = (w: string) => /^[A-Z][a-z'’-]+$/.test(w) && !NOT_NAMES.has(w.toLowerCase());
    if (nameLike(f) && (nameLike(l) || /^[A-Z][a-z]*[A-Z][a-z]+$/.test(l))) return f;
  }
  // 3. "I'm Sarah" / "My name is Sarah" in the description.
  const m = (c.description || "").match(/\b(?:I['’]m|I am|my name is|Hi,? I['’]m)\s+([A-Z][a-z]{2,})\b/);
  if (m && !NOT_NAMES.has(m[1].toLowerCase())) return m[1];
  return "";
}

// Video title without hashtags, emojis, "| Channel name" tails; cut at ~80 chars on a word.
function cleanTitle(t: string | undefined, channelName: string | undefined): string {
  let s = (t || "").replace(/#[\w-]+/g, "").replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, "");
  const ch = (channelName || "").split(/[|:–-]/)[0].trim();
  s = s.split(/\s[|]\s/).filter(p => !ch || p.trim().toLowerCase() !== ch.toLowerCase()).join(" | ");
  s = s.replace(/^\s*(ep\.?|episode)\s*#?\d+\s*[|:–-]\s*/i, "");
  s = s.replace(/\s+/g, " ").replace(/[\s|:–-]+$/, "").trim();
  const letters = s.replace(/[^A-Za-z]/g, "");
  if (letters.length > 8 && letters === letters.toUpperCase()) s = s.charAt(0) + s.slice(1).toLowerCase();
  if (s.length > 80) s = s.slice(0, 80).replace(/\s+\S*$/, "") + "…";
  return s;
}

// Treated as a podcast only when the channel calls itself one, so the wording matches.
const isPodcast = (c: LeadLike) => /podcast|\bshow\b|radio/i.test(c.channel_name || "") || /^\s*(ep\.?|episode)\s*#?\d/i.test(c.latest_video_title || "");

function personalLine(c: LeadLike, title: string) {
  const podcast = isPodcast(c);
  if (title) return podcast ? `I listened to your recent episode "${title}"` : `I watched your recent video "${title}"`;
  return `I came across ${c.channel_name} on YouTube`;
}

const COUNTRY: Record<string, string> = { US: "United States", GB: "United Kingdom", CA: "Canada", AU: "Australia", NZ: "New Zealand",
  IE: "Ireland", NO: "Norway", NL: "Netherlands", DE: "Germany", SG: "Singapore", AE: "UAE" };

function fields(c: LeadLike): PersonalFields {
  const first = firstName(c);
  const title = cleanTitle(c.latest_video_title, c.channel_name);
  const subs = parseInt(c.subscribers || "", 10) || 0;
  return {
    email: (c.best_email || "").trim(),
    first_name: first,
    greeting_name: first || "there",
    channel_name: (c.channel_name || "").replace(/\s+/g, " ").trim(),
    latest_video: title,
    personal_line: personalLine(c, title),
    content_kind: isPodcast(c) ? "podcast" : "YouTube channel",
    subscribers: subs >= 1000 ? (subs >= 1e6 ? (subs / 1e6).toFixed(1).replace(/\.0$/, "") + "M" : Math.round(subs / 100) / 10 + "K") : String(subs || ""),
    country: COUNTRY[c.country || ""] || c.country || "",
    fit_score: String(c.fit_score || ""),
    youtube_link: c.channel_link || "",
    website: c.website || "",
    linkedin: c.linkedin || "",
  };
}

// Fills {{field}} or {{field|fallback}} in your copy with this lead's values.
function render(template: string | undefined, fields: object): string {
  const f = fields as Record<string, unknown>;
  return String(template || "").replace(/\{\{\s*([a-z_]+)\s*(?:\|\s*([^}]*?)\s*)?\}\}/gi, (_m, key: string, fallback?: string) => {
    const v = f[key.toLowerCase()];
    return v != null && v !== "" ? String(v) : (fallback ?? "");
  });
}
// Fields used in a template that are empty for this lead (so the preview can warn).
function missing(template: string | undefined, fields: object): string[] {
  const f = fields as Record<string, unknown>;
  const out = new Set<string>();
  String(template || "").replace(/\{\{\s*([a-z_]+)\s*(\|[^}]*)?\}\}/gi, (m, key: string, fb?: string) => {
    if (!fb && (f[key.toLowerCase()] == null || f[key.toLowerCase()] === "")) out.add(key);
    return m;
  });
  return [...out];
}
const FIELD_LIST: [string, string][] = [
  ["greeting_name", "First name, or \"there\""],
  ["first_name", "First name (empty if unsure)"],
  ["personal_line", "I watched your recent video \"…\""],
  ["channel_name", "Their channel name"],
  ["latest_video", "Latest video title"],
  ["content_kind", "podcast / YouTube channel"],
  ["subscribers", "Subscriber count, e.g. 12K"],
  ["country", "Country"],
  ["website", "Their website"],
];


export { firstName, cleanTitle, fields, render, missing, FIELD_LIST, COUNTRY };
