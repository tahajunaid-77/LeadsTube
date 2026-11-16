// Server-side logic for the LeadTube dashboard (used by the Next.js API routes).
// Reads the tool's files (results/*.csv, data/*.json), API keys from ../.env, and
// starts finder/youtube_finder.py and finder/mailer.py. Nothing here runs in the browser.

import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

// The dashboard folder sits inside the tool's folder.
export const ROOT = path.resolve(process.cwd(), "..");
const RESULTS = path.join(ROOT, "results");
const DATA = path.join(ROOT, "data");
const FINDER = path.join(ROOT, "finder");
const ENV_FILE = path.join(ROOT, ".env");
export const MASTER = path.join(RESULTS, "all_channels.csv");
const HISTORY = path.join(RESULTS, "run_history.csv");
const CONTACTED = path.join(DATA, "contacted.json");
const SCRIPT = path.join(FINDER, "youtube_finder.py");
const MAILER = path.join(FINDER, "mailer.py");
const SETTINGS_FILE = path.join(DATA, "settings.json");    // name, address, SMTP, daily limit (no secrets)
const COPY_FILE = path.join(DATA, "email_copy.json");       // your email copy
const DRAFTS = path.join(DATA, "drafts.json");
const OPT_OUT = path.join(DATA, "unsubscribed.json");
const SEND_LOG = path.join(DATA, "email_log.json");
const SMARTLEAD_SENT = path.join(DATA, "smartlead.json");
const RATINGS = path.join(DATA, "ratings.json");             // your Good / Medium / Low ratings
const MODEL = path.join(DATA, "learned_model.json");         // what the tool learned from them
const LEARNER = path.join(FINDER, "learning.py");
const SMARTLEAD_API = process.env.SMARTLEAD_API_BASE || "https://server.smartlead.ai/api/v1"; // override only for testing

// Survives Next.js hot reloads in development.
const G = globalThis.__leadtube ??= {
  job: { running: false, mode: "", started: null, finished: null, code: null, log: "" },
  serperCache: { at: 0, value: null },
  writeChain: Promise.resolve(),
};

export class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

// ---------------------------------------------------------------- .env (API keys)

export async function readEnv() {
  const out = {};
  const text = await fsp.readFile(ENV_FILE, "utf8").catch(() => "");
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const i = line.indexOf("=");
    out[line.slice(0, i).trim()] = line.slice(i + 1).trim().replace(/^["']|["']$/g, "");
  }
  return out;
}
// Change one key, keeping the rest of the file (comments included).
async function setEnv(key, value) {
  const clean = String(value).replace(/[\r\n]/g, "").trim();
  G.writeChain = G.writeChain.then(async () => {
    const lines = (await fsp.readFile(ENV_FILE, "utf8").catch(() => "")).split(/\r?\n/);
    const at = lines.findIndex(l => new RegExp(`^\\s*${key}\\s*=`).test(l));
    if (at >= 0) lines[at] = `${key}=${clean}`; else lines.push(`${key}=${clean}`);
    await fsp.writeFile(ENV_FILE, lines.join("\n").replace(/\n*$/, "\n"), { mode: 0o600 });
  });
  return G.writeChain;
}

// ---------------------------------------------------------------- files

export function parseCsv(text) {
  text = text.replace(/^﻿/, "");
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else quoted = false; }
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(field); field = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else field += ch;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  if (!rows.length) return [];
  const [head, ...body] = rows;
  return body.map(r => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
}
export async function readCsv(file) {
  try { return parseCsv(await fsp.readFile(file, "utf8")); }
  catch (e) { if (e.code === "ENOENT") return []; throw e; }
}
export async function readJson(file, fallback) {
  try { return JSON.parse(await fsp.readFile(file, "utf8")); } catch { return fallback; }
}
// Writes are queued so two requests never overwrite each other.
export function updateJson(file, fallback, change) {
  G.writeChain = G.writeChain.then(async () => {
    const value = change(await readJson(file, fallback));
    await fsp.mkdir(path.dirname(file), { recursive: true });
    await fsp.writeFile(file + ".tmp", JSON.stringify(value, null, 1));
    await fsp.rename(file + ".tmp", file);
    return value;
  });
  return G.writeChain;
}
export async function findLead(link) {
  return (await readCsv(MASTER)).find(r => r.channel_link === link);
}

// ---------------------------------------------------------------- leads

export async function getData() {
  const [channels, runs, contacted, ratings, learning] = await Promise.all([
    readCsv(MASTER), readCsv(HISTORY), readJson(CONTACTED, {}), readJson(RATINGS, {}), learningStatus()]);
  const updated = fs.existsSync(MASTER) ? fs.statSync(MASTER).mtime : null;
  return { channels, runs, contacted, ratings, learning, updated };
}

// ---------------------------------------------------------------- your ratings + learning

const RATING_VALUES = new Set(["good", "medium", "low"]);
export async function setRatings(links, rating) {
  if (rating !== null && !RATING_VALUES.has(rating)) throw new HttpError(400, "Rating must be good, medium or low.");
  const state = await updateJson(RATINGS, {}, r => {
    const date = new Date().toISOString().slice(0, 10);
    for (const link of links) { if (rating) r[link] = { rating, date }; else delete r[link]; }
    return r;
  });
  scheduleRelearn();
  return { ok: true, count: Object.keys(state).length };
}
async function learningStatus() {
  const m = await readJson(MODEL, null);
  if (!m) return { active: false, ratings: 0, counts: { good: 0, medium: 0, low: 0 }, needed: 8, likes: [], dislikes: [] };
  const { active, ratings, counts, needed, likes, dislikes, trained_at } = m;
  return { active, ratings, counts, needed, likes, dislikes, trained_at, relearning: !!G.relearn?.running };
}
// Retrain a few seconds after the last rating change, then re-score every lead.
function scheduleRelearn() {
  G.relearn ??= { timer: null, running: false, again: false };
  clearTimeout(G.relearn.timer);
  G.relearn.timer = setTimeout(runRelearn, 2500);
}
function runRelearn() {
  const st = G.relearn;
  if (st.running) { st.again = true; return; }
  st.running = true;
  const child = spawn(pythonPath(), [LEARNER, "--rescore"], { cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  child.on("error", () => { st.running = false; });
  child.on("close", () => { st.running = false; if (st.again) { st.again = false; runRelearn(); } });
}
export function setContacted(links, value) {
  return updateJson(CONTACTED, {}, state => {
    const today = new Date().toISOString().slice(0, 10);
    for (const link of links) { if (value) state[link] = state[link] || today; else delete state[link]; }
    return state;
  });
}

// ---------------------------------------------------------------- runs (python tool)

const LOG_LIMIT = 60_000;
const pythonPath = () => {
  const venv = path.join(ROOT, ".venv", "bin", "python");
  return fs.existsSync(venv) ? venv : "python3";
};
async function lockPid() {
  return parseInt((await fsp.readFile(path.join(DATA, "run.lock"), "utf8").catch(() => "")).split(" ")[0], 10) || 0;
}

export function startJob({ mode, target, countries, days, keywords, fitGoal }) {
  const job = G.job;
  if (job.running) throw new HttpError(409, "A run is already in progress.");
  const args = ["-u", SCRIPT, "--yes", "--no-open"];
  if (mode === "emails") args.push("--fill-missing");
  else {
    const t = parseInt(target, 10);
    if (t > 0) {
      args.push("--target", String(Math.min(5000, t)));
      // which leads count toward "How many" (lower-fit ones are still saved)
      if (["top", "good", "possible"].includes(fitGoal)) args.push("--fit-goal", fitGoal);
    }
    if (countries && /^[\w ,.'-]{1,200}$/.test(countries)) args.push("--countries", countries);
    const d = parseInt(days, 10);
    if (d >= 7 && d <= 365) args.push("--days", String(d));
    // custom keywords (spintax allowed); one argument, never through a shell
    if (typeof keywords === "string" && keywords.trim() && keywords.length <= 500 && !/[\r\n]/.test(keywords))
      args.push("--keywords", keywords.trim());
  }
  Object.assign(job, { running: true, mode, started: new Date().toISOString(), finished: null, code: null, log: "" });
  // detached: the run keeps going (and saves its results) even if the dashboard restarts
  const child = spawn(pythonPath(), args, { cwd: ROOT, detached: true, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  const append = chunk => { job.log = (job.log + chunk.toString()).slice(-LOG_LIMIT); };
  child.stdout.on("data", append);
  child.stderr.on("data", append);
  child.on("error", err => { append(`\nCould not start Python: ${err.message}\n`); });
  child.on("close", code => Object.assign(job, { running: false, finished: new Date().toISOString(), code }));
  return { ok: true };
}
export async function jobStatus() {
  const job = G.job;
  if (!job.running) {
    const pid = await lockPid();
    let alive = false;
    if (pid) { try { process.kill(pid, 0); alive = true; } catch {} }
    if (alive) return { ...job, running: true, mode: "other",
      log: job.log + "\nAnother run is in progress (started from Terminal or before a restart). Results appear when it finishes.\n" };
  }
  return job;
}
export async function stopJob() {
  const pid = await lockPid();
  if (!pid) throw new HttpError(409, "No run is in progress.");
  try { process.kill(pid, "SIGTERM"); } catch { throw new HttpError(409, "No run is in progress."); }
  return { ok: true };
}

// ---------------------------------------------------------------- API limits

const DAILY_QUOTA = 10000;
const pacificDay = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Los_Angeles" }).format(new Date());
function msUntilPacificMidnight() {
  const la = new Date(new Date().toLocaleString("en-US", { timeZone: "America/Los_Angeles" }));
  const next = new Date(la); next.setHours(24, 0, 0, 0);
  return next - la;
}
async function serperBalance(refresh) {
  const cache = G.serperCache;
  if (!refresh && Date.now() - cache.at < 10 * 60 * 1000) return cache.value;
  const key = (await readEnv()).SERPER_API_KEY;
  let value = null;
  if (key) {
    try {
      const res = await fetch("https://google.serper.dev/account", { headers: { "X-API-KEY": key }, signal: AbortSignal.timeout(8000) });
      if (res.ok) value = (await res.json()).balance ?? null;
    } catch {}
  }
  G.serperCache = { at: Date.now(), value };
  return value;
}
export async function limits(refresh) {
  const ytKeys = [...new Set(((await readEnv()).YOUTUBE_API_KEYS || "").split(",").map(k => k.trim()).filter(Boolean))];
  const usage = (await readJson(path.join(DATA, "key_usage.json"), {}))[pacificDay()] || {};
  const keys = ytKeys.map((k, i) => [i ? `Backup ${i}` : "Main", k]).map(([name, k]) => {
    const used = Math.min(DAILY_QUOTA, usage["key ..." + k.slice(-4)] || 0);
    return { name, label: "…" + k.slice(-4), used, left: DAILY_QUOTA - used, quota: DAILY_QUOTA };
  });
  return { youtube: keys, resetsInMs: msUntilPacificMidnight(), serper: await serperBalance(refresh) };
}

// ---------------------------------------------------------------- settings (Smartlead + Gmail)

// Secrets live in .env; everything else in data/settings.json.
const SECRETS = { app_password: "GMAIL_APP_PASSWORD", smartlead_api_key: "SMARTLEAD_API_KEY" };
const PLAIN_FIELDS = ["from_name", "from_email", "smtp_host", "smtp_port", "daily_limit"];
const SETTING_DEFAULTS = { smtp_host: "smtp.gmail.com", smtp_port: 465, daily_limit: 30 };

async function readSettings() {
  const [plain, envVars] = await Promise.all([readJson(SETTINGS_FILE, {}), readEnv()]);
  const s = { ...SETTING_DEFAULTS, ...plain };
  for (const [field, key] of Object.entries(SECRETS)) s[field] = envVars[key] || "";
  return s;
}
// Settings go to the browser with secrets hidden (only whether they are set).
export async function publicSettings() {
  const s = await readSettings();
  const out = {};
  for (const k of PLAIN_FIELDS) out[k] = s[k] ?? "";
  for (const k of Object.keys(SECRETS)) { out[k] = ""; out[k + "_set"] = !!s[k]; }
  return out;
}
export async function saveSettings(body) {
  await updateJson(SETTINGS_FILE, {}, s => {
    for (const k of PLAIN_FIELDS) {
      if (!(k in body)) continue;
      s[k] = k === "smtp_port" || k === "daily_limit"
        ? Math.max(1, Math.min(k === "smtp_port" ? 65535 : 500, parseInt(body[k], 10) || 0))
        : String(body[k]).slice(0, 300);
    }
    return s;
  });
  for (const [field, key] of Object.entries(SECRETS))
    if (typeof body[field] === "string" && body[field].trim()) await setEnv(key, body[field]);   // empty = keep
  return publicSettings();
}

// ---------------------------------------------------------------- email copy + Gmail (mailer.py)

export async function getCopy() { return readJson(COPY_FILE, { subject: "", body: "" }); }
export async function saveCopy({ subject, body }) {
  const copy = { subject: String(subject ?? "").slice(0, 300), body: String(body ?? "").slice(0, 10000), updated: new Date().toISOString() };
  return updateJson(COPY_FILE, {}, () => copy);
}

export function runMailer(command, payload, timeoutMs = 120_000) {
  return new Promise(resolve => {
    const child = spawn(pythonPath(), [MAILER, command], { cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
    let out = "", err = "";
    const timer = setTimeout(() => child.kill("SIGTERM"), timeoutMs);
    child.stdout.on("data", c => { out += c; });
    child.stderr.on("data", c => { err += c; });
    child.on("error", e => { clearTimeout(timer); resolve({ error: `Could not start Python: ${e.message}` }); });
    child.on("close", () => {
      clearTimeout(timer);
      try { resolve(JSON.parse(out.trim().split("\n").pop())); }
      catch { resolve({ error: (err.trim().split("\n").pop() || "The email helper stopped unexpectedly.").slice(0, 300) }); }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

export async function emailState() {
  const [drafts, optOut, log, settings, smartleadSent] = await Promise.all([
    readJson(DRAFTS, {}), readJson(OPT_OUT, []), readJson(SEND_LOG, []), readSettings(), readJson(SMARTLEAD_SENT, {})]);
  const today = new Date().toLocaleDateString("en-CA");
  return {
    drafts, optOut, smartlead: smartleadSent,
    sentToday: log.filter(e => (e.date || "").startsWith(today)).length,
    limit: settings.daily_limit || 30,
    ready: { sending: !!settings.from_email && !!settings.app_password, smartlead: !!settings.smartlead_api_key },
  };
}
export async function saveDraft({ link, to, subject, body }) {
  if (!(await findLead(link))) throw new HttpError(404, "Channel not found.");
  await updateJson(DRAFTS, {}, d => ({ ...d, [link]: { ...(d[link] || {}), to: String(to || ""), subject: String(subject || ""),
    body: String(body || ""), status: d[link]?.status === "sent" ? "sent" : "draft", updated: new Date().toISOString() } }));
  return { ok: true };
}
export async function discardDraft({ link }) {
  await updateJson(DRAFTS, {}, d => { if (d[link]?.status !== "sent") delete d[link]; return d; });
  return { ok: true };
}
export async function sendEmail({ link, to, subject, body }) {
  if (!(await findLead(link))) throw new HttpError(404, "Channel not found.");
  if ((await readJson(DRAFTS, {}))[link]?.status === "sent") throw new HttpError(409, "Already emailed this channel.");
  const r = await runMailer("send", { link, to, subject, body }, 90_000);
  if (r.error) throw new HttpError(400, r.error);
  await updateJson(DRAFTS, {}, d => ({ ...d, [link]: { to, subject, body, status: "sent", sent: new Date().toISOString() } }));
  await setContacted([link], true);
  return r;
}
export async function testEmailLogin() {
  const r = await runMailer("test", {}, 60_000);
  if (r.error) throw new HttpError(400, r.error);
  return r;
}

// ---------------------------------------------------------------- Smartlead

async function smartlead(pathname, options = {}) {
  const key = (await readEnv()).SMARTLEAD_API_KEY;
  if (!key) throw new HttpError(400, "Add your Smartlead API key in Settings first.");
  const url = `${SMARTLEAD_API}${pathname}${pathname.includes("?") ? "&" : "?"}api_key=${encodeURIComponent(key)}`;
  let res;
  try { res = await fetch(url, { ...options, headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(60_000) }); }
  catch { throw new HttpError(502, "Couldn't reach Smartlead. Check your internet connection."); }
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = { message: text.slice(0, 200) }; }
  if (!res.ok) throw new HttpError(502, res.status === 401 || res.status === 403
    ? "Smartlead rejected the API key. Check it in Settings."
    : `Smartlead error (${res.status}): ${data.message || data.error || "unknown"}`);
  return data;
}
const clip = (v, n = 500) => String(v ?? "").slice(0, n);
function smartleadLead(l) {
  return {
    email: clip(l.email, 200), first_name: clip(l.first_name, 100), company_name: clip(l.channel_name, 200),
    website: clip(l.website), linkedin_profile: clip(l.linkedin), location: clip(l.country, 100),
    custom_fields: {
      greeting_name: clip(l.greeting_name, 100), channel_name: clip(l.channel_name, 200), latest_video: clip(l.latest_video, 200),
      personal_line: clip(l.personal_line, 300), content_kind: clip(l.content_kind, 50), subscribers: clip(l.subscribers, 20),
      country: clip(l.country, 100), youtube_link: clip(l.youtube_link), fit_score: clip(l.fit_score, 5),
      ...(l.email_subject ? { email_subject: clip(l.email_subject, 300) } : {}),
      ...(l.email_body ? { email_body: clip(l.email_body, 10000) } : {}),
    },
  };
}
export async function smartleadCampaigns() {
  const list = await smartlead("/campaigns/");
  const campaigns = (Array.isArray(list) ? list : list.data || []).map(c => ({ id: c.id, name: c.name, status: c.status }))
    .filter(c => c.id && !/ARCHIVED|STOPPED|COMPLETED/i.test(c.status || ""));
  return { campaigns };
}
export async function smartleadPush({ campaign_id, campaign_name, leads }) {
  if (!/^\d+$/.test(String(campaign_id))) throw new HttpError(400, "Pick a campaign.");
  if (!Array.isArray(leads) || !leads.length) throw new HttpError(400, "No leads to add.");
  const optOut = new Set((await readJson(OPT_OUT, [])).map(e => e.toLowerCase()));
  const already = await readJson(SMARTLEAD_SENT, {});
  const known = new Set((await readCsv(MASTER)).map(r => r.channel_link));
  const todo = leads.filter(l => known.has(l.link) && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(l.email || "")
    && !optOut.has(l.email.toLowerCase()) && !already[l.link]);
  if (!todo.length) throw new HttpError(400, "All these leads were already added, opted out, or have no email.");
  let added = 0, skipped = 0;
  for (let i = 0; i < todo.length; i += 400) {   // Smartlead takes up to 400 per request
    const batch = todo.slice(i, i + 400);
    const r = await smartlead(`/campaigns/${encodeURIComponent(campaign_id)}/leads`, { method: "POST",
      body: JSON.stringify({ lead_list: batch.map(smartleadLead), settings: { ignore_global_block_list: false,
        ignore_unsubscribe_list: false, ignore_duplicate_leads_in_other_campaign: false } }) });
    added += r.added_count ?? r.upload_count ?? batch.length;
    skipped += r.skipped_count ?? r.already_added_to_campaign ?? 0;
    const date = new Date().toISOString().slice(0, 10);
    await updateJson(SMARTLEAD_SENT, {}, d => { for (const l of batch) d[l.link] = { campaign_id: Number(campaign_id),
      campaign: clip(campaign_name, 200), email: l.email, date }; return d; });
    await setContacted(batch.map(l => l.link), true);
  }
  return { ok: true, sent: todo.length, added, skipped };
}

// ---------------------------------------------------------------- ICP.md (who you're looking for)

const ICP_FILE = path.join(ROOT, "ICP.md");
const ICP_PREVIOUS = path.join(DATA, "ICP.previous.md");   // last saved version, for "Undo"
const ICP_SECTIONS = ["ideal lead", "search phrases", "keep a channel only if it mentions", "strong-match words",
  "best-fit roles", "roles", "core topic words", "topics they work on", "who they work with (decision makers)",
  "who they work with (any business setting)", "skills they teach", "credentials", "speaker and author signs",
  "words that show their line of work", "niche words for new search phrases", "endings for learned phrases",
  "not my icp: topics", "not my icp: churches and ministries", "not my icp: media, schools and companies",
  "organisations, not a person", "generic words (never someone's name)", "word swaps for deeper search",
  "useful words in youtube suggestions", "phrases that are not leads"];
const sectionKey = line => line.replace(/^##\s*/, "").replace(/^\d+\.\s*/, "").trim().toLowerCase();

export async function getIcp() {
  const [text, previous] = await Promise.all([fsp.readFile(ICP_FILE, "utf8").catch(() => ""),
    fsp.readFile(ICP_PREVIOUS, "utf8").catch(() => "")]);
  const stat = fs.existsSync(ICP_FILE) ? fs.statSync(ICP_FILE).mtime : null;
  return { text, updated: stat, canUndo: !!previous && previous !== text };
}
export async function saveIcp({ text, undo }) {
  const current = await fsp.readFile(ICP_FILE, "utf8").catch(() => "");
  if (undo) {
    const previous = await fsp.readFile(ICP_PREVIOUS, "utf8").catch(() => "");
    if (!previous) throw new HttpError(400, "Nothing to undo.");
    text = previous;
  }
  if (typeof text !== "string" || text.length > 200_000) throw new HttpError(400, "ICP text is missing or too long.");
  const present = new Set(text.split(/\r?\n/).filter(l => l.startsWith("## ")).map(sectionKey));
  const missing = ICP_SECTIONS.filter(k => !present.has(k));
  if (missing.length) throw new HttpError(400, `Missing section${missing.length > 1 ? "s" : ""}: ${missing.join(", ")}. Section titles must stay as they are.`);
  if (current && current !== text) await fsp.writeFile(ICP_PREVIOUS, current);
  await fsp.writeFile(ICP_FILE, text.replace(/\r\n/g, "\n"));
  return getIcp();
}

