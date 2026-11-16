"use client";
import { useEffect, useRef } from "react";
import { Button, Field, Modal, Spinner } from "@/components/ui";
import { api, num, useStored } from "@/lib/client";

const COUNTRIES = ["US", "UK", "Canada", "Australia", "Ireland", "New Zealand", "Norway", "Netherlands", "Germany", "Singapore", "UAE"];
const DEFAULTS = { target: "", days: "45", keywords: "", fitGoal: "good", countries: ["US", "UK", "Canada", "Norway", "Netherlands"] };
const GOALS = [["top", "Top fit only"], ["good", "Good fit or better"], ["possible", "Possible or better"]];

export default function FindLeadsDialog({ open, onClose, job, onStarted, toast }) {
  const [opts, setOpts] = useStored("leads.runOpts", DEFAULTS);
  const o = { ...DEFAULTS, ...opts, countries: Array.isArray(opts.countries) ? opts.countries : DEFAULTS.countries };
  const set = (k, v) => setOpts({ ...o, [k]: v });
  const running = !!job?.running;
  const logRef = useRef(null);
  useEffect(() => { const el = logRef.current; if (el) el.scrollTop = el.scrollHeight; }, [job?.log]);

  async function start(mode) {
    try {
      await api("/api/run", mode === "emails" ? { mode } : { mode, target: o.target, countries: o.countries.join(", "), days: o.days,
        keywords: o.keywords.trim(), fitGoal: o.fitGoal });
      onStarted();
    } catch (e) { toast(e.message); }
  }
  async function stop() {
    if (!confirm("Stop the current run? Channels found so far will be saved.")) return;
    try { await api("/api/run/stop", {}); toast("Stopping… saving what was found"); } catch (e) { toast(e.message); }
  }

  const n = o.countries.length, t = num(o.target);
  const label = job?.mode === "emails" ? "Filling emails & profiles" : job?.mode === "other" ? "A run" : "Search";
  return (
    <Modal open={open} onClose={onClose} title="Find new leads"
      subtitle="Searches YouTube for new channels in your niche. Channels you already have are skipped."
      footer={<>
        <Button icon="refresh" onClick={() => start("emails")} disabled={running}
          title="Re-check saved channels for missing emails and social profiles (no YouTube quota)">Fill missing emails</Button>
        <span className="panel-actions">
          {running && <Button icon="square" onClick={stop}>Stop run</Button>}
          <Button variant="primary" icon="play" onClick={() => start("search")} disabled={running || !n}>Start search</Button>
        </span>
      </>}>
      <div className="field">
        <span className="field-label">Countries</span>
        <div className="chips">
          {COUNTRIES.map(c => (
            <button key={c} type="button" className="chip-toggle" aria-pressed={o.countries.includes(c)}
              onClick={() => set("countries", o.countries.includes(c) ? o.countries.filter(x => x !== c) : o.countries.concat(c))}>{c}</button>
          ))}
        </div>
      </div>
      <div className="row3">
        <Field label="How many">
          <input type="number" min={1} max={5000} placeholder="As many as possible" value={o.target} onChange={e => set("target", e.target.value)} />
        </Field>
        <Field label="Count only">
          <select value={o.fitGoal} disabled={!num(o.target)} onChange={e => set("fitGoal", e.target.value)}
            title={num(o.target) ? "Which leads count toward How many. Lower-fit leads are still saved." : "Only used when How many is set"}>
            {GOALS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <Field label="Uploaded within">
          <select value={o.days} onChange={e => set("days", e.target.value)}>
            {["30", "45", "60", "90"].map(d => <option key={d} value={d}>{d} days</option>)}
          </select>
        </Field>
      </div>
      <Field label="Keywords" hint="optional; empty uses your keyword list">
        <input type="text" placeholder="e.g. culture podcast, {leadership|executive} coach" value={o.keywords} onChange={e => set("keywords", e.target.value)} />
      </Field>
      <p className="hint">{!n ? "Pick at least one country."
        : `${n} ${n === 1 ? "country" : "countries"} · ${t ? `${t} new leads that are ${GOALS.find(g => g[0] === o.fitGoal)?.[1].toLowerCase()} (lower-fit ones saved too)` : "as many as the quota allows"} · active in last ${o.days} days · ${o.keywords.trim() ? "your keywords" : "smart keyword list"}`}</p>
      {job && (job.running || job.finished) && (
        <div className="run-status">{running ? <><Spinner />{label} running…</>
          : `${label} finished${job.code === 0 ? "" : ` with an error (code ${job.code})`}.`}</div>
      )}
      {job?.log && <pre className="log" ref={logRef}>{job.log}</pre>}
    </Modal>
  );
}
