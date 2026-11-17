"use client";
import Icon from "@/components/Icon";
import { Button } from "@/components/ui";
import { COUNTRY, ago, fitClass, fmt, handleOf } from "@/lib/client";
import Rating from "@/components/leads/Rating";
import type { MouseEvent } from "react";
import type { Lead, MailState, ProfileField, RatingValue } from "@/lib/types";

const PROFILES: [ProfileField, string][] = [["website", "Website"], ["linkedin", "LinkedIn"], ["facebook", "Facebook"], ["instagram", "Instagram"],
  ["twitter", "X"], ["tiktok", "TikTok"], ["podcast", "Podcast"], ["booking", "Booking"], ["channel_link", "YouTube"]];

function ProfileIcons({ c }: { c: Lead }) {
  return (
    <div className="icons">
      {PROFILES.filter(([k]) => c[k]).map(([k, label]) => {
        let kind = k === "channel_link" ? "youtube" : k;
        if (k === "podcast") kind = /spotify/i.test(c[k]) ? "spotify" : /apple/i.test(c[k]) ? "apple" : "podcast";
        const icon = k === "channel_link" ? "youtube" : k;
        return (
          <a key={k} className={`ic ic-${kind}`} href={c[k]} target="_blank" rel="noopener noreferrer" title={label} aria-label={label}
            onClick={e => e.stopPropagation()}><Icon name={icon} size="sm" /></a>
        );
      })}
    </div>
  );
}

function FitBadge({ c }: { c: Lead }) {
  if (c.fit_score === "" || c.fit_score === undefined) return null;
  return (
    <span className={`fit fit-${fitClass(c.fit)}`} title={c.fit_label + (c.fit_reason ? ": " + c.fit_reason : "")}>
      <b>{c.fit}</b><span className="fit-label">{c.fit_label}</span>
    </span>
  );
}

// Titles of videos posted in the last 30 days (what LeadTube reads, with the description).
function RecentVideos({ c }: { c: Lead }) {
  const titles = (c.recent_videos || "").split(" | ").map(t => t.trim()).filter(Boolean);
  if (!titles.length) return <><h4>Latest video</h4><p>{c.latest_video_title || "–"}</p></>;
  return (
    <>
      <h4>Videos in the last 30 days ({titles.length})</h4>
      <ul className="video-list">{titles.slice(0, 10).map((t, i) => <li key={i}>{t}</li>)}</ul>
      {titles.length > 10 && <p className="none">+{titles.length - 10} more</p>}
    </>
  );
}

function MailTag({ c, mail }: { c: Lead; mail: MailState }) {
  const sl = mail.smartlead[c.channel_link];
  if (sl) return <span className="mail-tag sent" title={`Added to Smartlead campaign "${sl.campaign}" on ${sl.date}`}>Smartlead</span>;
  const d = mail.drafts[c.channel_link];
  if (!d) return null;
  return d.status === "sent"
    ? <span className="mail-tag sent" title={`Emailed ${(d.sent || "").slice(0, 10)}`}>Sent</span>
    : <span className="mail-tag draft" title="Draft saved">Draft</span>;
}

interface LeadRowProps {
  c: Lead; open: boolean; selected: boolean; contactedOn: string | undefined; mail: MailState;
  rating: RatingValue | undefined; onRate: (rating: RatingValue | null) => void; onToggleOpen: () => void;
  onSelect: () => void; onContacted: (value: boolean) => void; onCompose: () => void; toast: (msg: string) => void;
}
export default function LeadRow({ c, open, selected, contactedOn, mail, rating, onRate, onToggleOpen, onSelect, onContacted, onCompose, toast }: LeadRowProps) {
  const handle = handleOf(c.channel_link);
  const src = (c.email_source || "").replace(/^web search: /, "").split(";")[0].trim();
  const draft = mail.drafts[c.channel_link];
  const stop = (e: MouseEvent) => e.stopPropagation();
  return (
    <>
      <tr className={`row ${contactedOn ? "done" : ""} ${selected ? "selected" : ""}`} onClick={onToggleOpen}>
        <td className="check" onClick={stop}>
          <input type="checkbox" checked={selected} onChange={onSelect} aria-label={`Select ${c.channel_name}`} />
        </td>
        <td className="fit-cell"><FitBadge c={c} /></td>
        <td className="rating-cell"><Rating value={rating} onChange={onRate} /></td>
        <td className="name-cell">
          <div className="name">{c.channel_name}{contactedOn && <span className="contacted-tag" title={`Contacted ${contactedOn}`}>Contacted</span>}</div>
          <div className="handle">{[handle, COUNTRY[c.country] || c.country].filter(Boolean).join(" · ")}</div>
        </td>
        <td className="num inline subs">{c.subscribers === "" ? <span className="none">–</span> : fmt(c.subs)}</td>
        <td className="inline muted" title={c.last_upload + (c.activity === "Shorts" ? " · posts Shorts / short clips only lately" : "")}>
          {ago(c.last_upload)}{c.activity === "Shorts" && <span className="shorts-tag">Shorts</span>}
        </td>
        <td className="email-cell">
          {c.best_email ? (
            <span className="email">
              <span className={`dot ${c.web ? "web" : ""}`} title={c.web ? "Found by web search: double-check" : "From their website or YouTube"} />
              <span className="addr" title={c.best_email}>{c.best_email}</span>
              <button type="button" className="copy" title="Copy email" aria-label="Copy email"
                onClick={e => { stop(e); navigator.clipboard.writeText(c.best_email).then(() => toast("Email copied")); }}>
                <Icon name="copy" size="xs" /></button>
              <MailTag c={c} mail={mail} />
            </span>
          ) : <span className="none">No email</span>}
        </td>
        <td className="profiles-cell"><ProfileIcons c={c} /></td>
      </tr>
      {open && (
        <tr className="detail">
          <td colSpan={8}>
            <div className="detail-grid">
              <div>
                <h4>About</h4><p>{c.description || <span className="none">No description</span>}</p>
                <RecentVideos c={c} />
              </div>
              <div>
                <div className="detail-actions">
                  <Button size="small" icon={contactedOn ? "userX" : "userCheck"} onClick={() => onContacted(!contactedOn)}>
                    {contactedOn ? "Mark not contacted" : "Mark contacted"}</Button>
                  {c.best_email && (draft || mail.ready.sending) && (
                    <Button size="small" icon="mail" onClick={onCompose}>
                      {!draft ? "Email this lead" : draft.status === "sent" ? "View sent email" : "Open draft"}</Button>)}
                </div>
                <h4>Email found on</h4>
                <p>{src.startsWith("http") ? <a href={src} target="_blank" rel="noopener noreferrer">{src}</a> : (src || "–")}</p>
                {c.emailsList.length > 1 && <><h4>Other emails</h4><p>{c.emailsList.slice(1).map(e => <span key={e}>{e}<br /></span>)}</p></>}
                {c.fit_reason && <><h4>Why this fit score</h4><p>{c.fit_label} ({c.fit}/100): {c.fit_reason}</p></>}
                <h4>Details</h4>
                <p>{c.subscribers ? c.subs.toLocaleString() + " subscribers · " : ""}{c.content_type} · {c.niche_match === "strong" ? "strong match" : "weak match"} · found in {c.found_in}{contactedOn ? ` · contacted ${contactedOn}` : ""}</p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
