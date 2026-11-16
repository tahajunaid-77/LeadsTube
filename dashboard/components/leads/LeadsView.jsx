"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { Button, Menu, MenuItem } from "@/components/ui";
import LeadRow from "@/components/leads/LeadRow";
import LearningBar from "@/components/leads/LearningBar";
import { RATINGS } from "@/components/leads/Rating";
import { COUNTRY, downloadCsv, smartleadRow, today, useStored } from "@/lib/client";
import { render as fill } from "@/lib/personalize";

const PAGE = 100;
const NO_FILTERS = { q: "", fit: "", country: "", email: "", status: "", match: "", type: "", size: "", social: "", rating: "" };
const MORE_KEYS = ["rating", "match", "type", "size", "social"];
const toHtml = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])).replace(/\n/g, "<br>");

export default function LeadsView({ data, mail, copy, toast, setContacted, setRating, onFindLeads, onSmartlead, onCompose, job }) {
  const { channels, runs, contacted } = data;
  const ratings = data.ratings || {};
  const [filters, setFilters] = useStored("leads.filters2", NO_FILTERS);
  const [run, setRun] = useStored("leads.run", "");
  const [sort, setSort] = useStored("leads.sort", { key: "fit", dir: -1 });
  const [shown, setShown] = useState(PAGE);
  const [openRow, setOpenRow] = useState(null);
  const [selected, setSelected] = useState(() => new Set());
  const [menu, setMenu] = useState("");          // which dropdown is open
  const f = { ...NO_FILTERS, ...filters };
  const setF = (k, v) => { setFilters(prev => ({ ...prev, [k]: v })); setShown(PAGE); setOpenRow(null); };

  const isDone = c => !!contacted[c.channel_link];
  const runNames = useMemo(() => [...new Set(runs.map(r => r.run).concat(channels.map(c => c.found_in).filter(Boolean)))]
    .sort((a, b) => b.localeCompare(a, undefined, { numeric: true })), [runs, channels]);
  const countries = useMemo(() => [...new Set(channels.map(c => c.country))].sort(), [channels]);

  // ---- filter + sort
  const list = useMemo(() => {
    const q = f.q.trim().toLowerCase(), minFit = parseInt(f.fit, 10) || 0;
    const [lo, hi] = f.size ? f.size.split("-").map(Number) : [0, Infinity];
    const out = channels.filter(c => {
      if (run && c.found_in !== run) return false;
      if (minFit && c.fit < minFit) return false;
      if (f.country && c.country !== f.country) return false;
      if (f.email === "has" && !c.best_email) return false;
      if (f.email === "trusted" && !(c.best_email && !c.web)) return false;
      if (f.email === "none" && c.best_email) return false;
      if (f.status === "todo" && isDone(c)) return false;
      if (f.status === "done" && !isDone(c)) return false;
      if (f.status === "smartlead" && !mail.smartlead[c.channel_link]) return false;
      if (f.status === "not-smartlead" && mail.smartlead[c.channel_link]) return false;
      if (f.status === "sent" && mail.drafts[c.channel_link]?.status !== "sent") return false;
      if (f.rating === "none" ? ratings[c.channel_link] : f.rating && ratings[c.channel_link]?.rating !== f.rating) return false;
      if (f.match && c.niche_match !== f.match) return false;
      if (f.type === "Shorts" ? c.activity !== "Shorts" : f.type === "LongVideos" ? c.activity === "Shorts" : f.type && c.content_type !== f.type) return false;
      if (f.size && !(c.subs >= lo && c.subs < hi)) return false;
      if (f.social && !c[f.social]) return false;
      if (q && ![c.channel_name, c.emails, c.website, c.description, c.recent_videos, c.channel_link, c.linkedin, c.facebook, c.instagram]
        .join(" ").toLowerCase().includes(q)) return false;
      return true;
    });
    const d = sort.dir;
    const cmp = {
      fit: (a, b) => d * (a.fit - b.fit) || b.subs - a.subs,
      name: (a, b) => d * a.channel_name.localeCompare(b.channel_name),
      subs: (a, b) => d * (a.subs - b.subs),
      upload: (a, b) => d * (a.last_upload || "").localeCompare(b.last_upload || ""),
    }[sort.key] || (() => 0);
    return out.sort(cmp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channels, contacted, ratings, mail, run, sort, filters]);

  // Drop selections that no longer exist (e.g. after a cleanup).
  useEffect(() => {
    setSelected(prev => { const next = new Set([...prev].filter(l => channels.some(c => c.channel_link === l))); return next.size === prev.size ? prev : next; });
  }, [channels]);

  const selectedLeads = useMemo(() => channels.filter(c => selected.has(c.channel_link)), [channels, selected]);
  const allInView = list.length > 0 && list.every(c => selected.has(c.channel_link));
  const someInView = list.some(c => selected.has(c.channel_link));
  const headCheck = useRef(null);
  useEffect(() => { if (headCheck.current) headCheck.current.indeterminate = someInView && !allInView; }, [someInView, allInView]);

  const toggle = link => setSelected(prev => { const n = new Set(prev); n.has(link) ? n.delete(link) : n.add(link); return n; });
  const toggleAll = () => setSelected(prev => {
    const n = new Set(prev);
    if (allInView) list.forEach(c => n.delete(c.channel_link)); else list.forEach(c => n.add(c.channel_link));
    return n;
  });
  const sortBy = key => setSort(s => s.key === key ? { key, dir: -s.dir } : { key, dir: key === "name" ? 1 : -1 });
  const arrow = key => sort.key === key ? (sort.dir > 0 ? " ↑" : " ↓") : "";

  // ---- exports
  const stamp = today();
  function exportSelected() {
    const rows = selectedLeads.filter(c => c.best_email);
    if (!rows.length) return toast("None of the selected leads has an email");
    downloadCsv(`Selected leads ${stamp}.csv`, ["Email", "Channel name", "About the channel", "Last video"],
      rows.map(c => [c.best_email, c.channel_name, c.description, c.latest_video_title]));
    toast(`${rows.length} leads exported`);
  }
  function exportSmartlead() {
    const rows = list.filter(c => c.best_email);
    if (!rows.length) return toast("No channels with an email in this view");
    const cols = ["email", "first_name", "company_name", "website", "linkedin_profile", "location", "greeting_name", "channel_name",
      "latest_video", "personal_line", "content_kind", "subscribers", "youtube_link", "fit_score"];
    const withCopy = !!copy.body;
    downloadCsv(`Smartlead ${run || "All runs"} ${stamp}.csv`, withCopy ? cols.concat("email_subject", "email_body") : cols,
      rows.map(c => { const r = smartleadRow(c);
        return cols.map(k => r[k]).concat(withCopy ? [fill(copy.subject, r), toHtml(fill(copy.body, r))] : []); }));
    toast(`${rows.length} leads exported`);
  }
  function exportFull() {
    const cols = ["channel_name", "channel_link", "country", "subscribers", "last_upload", "best_email", "emails", "email_source",
      "website", "linkedin", "facebook", "instagram", "twitter", "tiktok", "podcast", "booking", "found_in"];
    downloadCsv(`${run || "All runs"} (filtered) ${stamp}.csv`, cols.concat("contacted"),
      list.map(c => cols.map(k => c[k]).concat(contacted[c.channel_link] || "")));
  }
  async function copyEmails() {
    const emails = list.map(c => c.best_email).filter(Boolean);
    if (!emails.length) return toast("No emails in this view");
    await navigator.clipboard.writeText(emails.join(", ")).catch(() => {});
    toast(`${emails.length} emails copied`);
  }

  const withEmail = channels.filter(c => c.best_email).length;
  const latest = runNames[0] || "";
  const when = data.updated ? new Date(data.updated).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
  const moreCount = MORE_KEYS.filter(k => f[k]).length;
  const nSel = selected.size;

  return (
    <section className="view">
      <div className="page-head">
        <div>
          <h1>Leads</h1>
          <div className="summary">
            {!data.loaded ? "Loading…" : data.error ? `Couldn't load leads: ${data.error}` : <>
              <b>{channels.length}</b> channels · <b>{withEmail}</b> with email · <b>{Object.keys(contacted).length}</b> contacted
              {latest && <> · {latest} added <b>{channels.filter(c => c.found_in === latest).length}</b></>}
              {when && <span className="none"> · updated {when}</span>}</>}
          </div>
        </div>
        <Button variant="primary" icon="search" onClick={onFindLeads}>{job?.running ? "Search running…" : "Find new leads"}</Button>
      </div>

      <LearningBar learning={data.learning} ratings={ratings} />

      <div className="toolbar">
        <label className="search">
          <Icon name="search" size="sm" />
          <input type="search" placeholder="Search name, email, website" aria-label="Search" value={f.q} onChange={e => setF("q", e.target.value)} />
        </label>
        <select aria-label="Run" value={run} onChange={e => { setRun(e.target.value); setShown(PAGE); }}>
          <option value="">All runs ({channels.length})</option>
          {runNames.map(r => <option key={r} value={r}>{r} ({channels.filter(c => c.found_in === r).length})</option>)}
        </select>
        <select aria-label="Fit" value={f.fit} onChange={e => setF("fit", e.target.value)}>
          <option value="">Any fit</option><option value="75">Top fit</option><option value="55">Good fit +</option><option value="35">Possible +</option>
        </select>
        <select aria-label="Country" value={f.country} onChange={e => setF("country", e.target.value)}>
          <option value="">All countries</option>
          {countries.map(c => <option key={c} value={c}>{COUNTRY[c] || c}</option>)}
        </select>
        <select aria-label="Email" value={f.email} onChange={e => setF("email", e.target.value)}>
          <option value="">Any email</option><option value="has">Has email</option><option value="trusted">Verified email</option><option value="none">No email</option>
        </select>
        <select aria-label="Status" value={f.status} onChange={e => setF("status", e.target.value)}>
          <option value="">Any status</option><option value="todo">Not contacted</option><option value="done">Contacted</option>
          <option value="not-smartlead">Not in Smartlead</option><option value="smartlead">In Smartlead</option>
          <option value="sent">Emailed from LeadTube</option>
        </select>
        <Menu label="Filters" icon="sliders" align="right" badge={moreCount} open={menu === "filters"} onOpenChange={o => setMenu(o ? "filters" : "")}>
          <div className="filters-panel">
            <label>Your rating<select value={f.rating} onChange={e => setF("rating", e.target.value)}>
              <option value="">Any rating</option><option value="good">Rated Good</option><option value="medium">Rated Medium</option>
              <option value="low">Rated Low</option><option value="none">Not rated yet</option></select></label>
            <label>Niche match<select value={f.match} onChange={e => setF("match", e.target.value)}>
              <option value="">Any match</option><option value="strong">Strong match</option><option value="weak">Weak match</option></select></label>
            <label>Content<select value={f.type} onChange={e => setF("type", e.target.value)}>
              <option value="">Videos + podcasts</option><option value="Podcast">Podcasts</option><option value="Videos">Videos</option>
              <option value="LongVideos">Recent long videos</option><option value="Shorts">Shorts only lately</option></select></label>
            <label>Subscribers<select value={f.size} onChange={e => setF("size", e.target.value)}>
              <option value="">Any size</option><option value="0-1000">Under 1K</option><option value="1000-10000">1K to 10K</option>
              <option value="10000-100000">10K to 100K</option><option value="100000-1e12">100K+</option></select></label>
            <label>Profiles<select value={f.social} onChange={e => setF("social", e.target.value)}>
              <option value="">Any profiles</option><option value="linkedin">Has LinkedIn</option><option value="facebook">Has Facebook</option>
              <option value="instagram">Has Instagram</option><option value="website">Has website</option></select></label>
            <button type="button" className="link-btn" onClick={() => { setFilters(NO_FILTERS); setRun(""); setMenu(""); }}>Reset all filters</button>
          </div>
        </Menu>
      </div>

      {nSel > 0 ? (
        <div className="bar selection-bar" role="region" aria-label="Selected leads">
          <span className="sel-count"><Icon name="checkCircle" size="sm" /><b>{nSel}</b> selected
            <span className="none"> · {selectedLeads.filter(c => c.best_email).length} with email</span></span>
          <span className="bar-actions">
            <Button icon="download" onClick={exportSelected} title="Email, channel name, about the channel, last video">Export CSV</Button>
            <Menu label="Rate" icon="thumbsUp" align="right" open={menu === "rate"} onOpenChange={o => setMenu(o ? "rate" : "")}>
              <div className="menu-list">
                {RATINGS.map(([key, label, icon]) => <MenuItem key={key} icon={icon} title={label} hint={`Rate all ${nSel} as ${label.toLowerCase()}`}
                  onClick={() => { setMenu(""); setRating([...selected], key); toast(`${nSel} rated ${label.toLowerCase()}`); }} />)}
                <MenuItem icon="x" title="Clear rating" onClick={() => { setMenu(""); setRating([...selected], null); }} />
              </div>
            </Menu>
            <Button icon="userCheck" onClick={() => { setContacted([...selected], true); toast(`${nSel} marked contacted`); }}>Mark contacted</Button>
            <Button icon="userX" onClick={() => { setContacted([...selected], false); toast(`${nSel} marked not contacted`); }}>Unmark</Button>
            <Button variant="primary" icon="send" onClick={() => onSmartlead(selectedLeads)}>Send to Smartlead</Button>
            <button type="button" className="icon-btn" aria-label="Clear selection" title="Clear selection" onClick={() => setSelected(new Set())}>
              <Icon name="x" size="sm" /></button>
          </span>
        </div>
      ) : (
        <div className="bar">
          <span>{list.length} channels · {list.filter(c => c.best_email).length} with email</span>
          <span className="bar-actions">
            <Menu label="Export" icon="download" align="right" open={menu === "export"} onOpenChange={o => setMenu(o ? "export" : "")}>
              <div className="menu-list">
                <MenuItem icon="table" title="Smartlead CSV" hint="Fields + your email copy" onClick={() => { setMenu(""); exportSmartlead(); }} />
                <MenuItem icon="download" title="Full CSV" hint="Every column, for spreadsheets" onClick={() => { setMenu(""); exportFull(); }} />
                <MenuItem icon="copy" title="Copy emails" hint="Paste anywhere" onClick={() => { setMenu(""); copyEmails(); }} />
              </div>
            </Menu>
            <Button variant="primary" icon="send" onClick={() => onSmartlead(list)}>Send to Smartlead</Button>
          </span>
        </div>
      )}

      <div className="table-card">
        <table className="leads">
          <thead>
            <tr>
              <th className="check"><input ref={headCheck} type="checkbox" aria-label="Select all in this view" title="Select all in this view"
                checked={allInView} onChange={toggleAll} /></th>
              <th className="sortable" onClick={() => sortBy("fit")} title="How close the channel is to your target (learns from your ratings)">Fit{arrow("fit")}</th>
              <th title="Your rating: Good, Medium or Low. LeadTube learns from it.">Your rating</th>
              <th className="sortable" onClick={() => sortBy("name")}>Channel{arrow("name")}</th>
              <th className="sortable num" onClick={() => sortBy("subs")}>Subs{arrow("subs")}</th>
              <th className="sortable" onClick={() => sortBy("upload")}>Last upload{arrow("upload")}</th>
              <th>Email</th>
              <th>Profiles</th>
            </tr>
          </thead>
          <tbody>
            {list.slice(0, shown).map(c => (
              <LeadRow key={c.channel_link} c={c} open={openRow === c.channel_link} selected={selected.has(c.channel_link)}
                contactedOn={contacted[c.channel_link]} mail={mail}
                rating={ratings[c.channel_link]?.rating} onRate={r => setRating([c.channel_link], r)}
                onToggleOpen={() => setOpenRow(o => o === c.channel_link ? null : c.channel_link)}
                onSelect={() => toggle(c.channel_link)}
                onContacted={v => setContacted([c.channel_link], v)}
                onCompose={() => onCompose(c.channel_link)} toast={toast} />
            ))}
          </tbody>
        </table>
        {data.loaded && !list.length && <div className="empty">No channels match these filters.</div>}
      </div>
      {list.length > shown && <Button className="more-rows" onClick={() => setShown(s => s + PAGE)}>Show more ({list.length - shown} left)</Button>}
    </section>
  );
}
