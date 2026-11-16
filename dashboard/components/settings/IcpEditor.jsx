"use client";
// Edit ICP.md: the one file that describes who LeadTube looks for.
import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Spinner } from "@/components/ui";
import { api } from "@/lib/client";

export default function IcpEditor({ toast }) {
  const [text, setText] = useState(null);
  const [saved, setSaved] = useState("");
  const [canUndo, setCanUndo] = useState(false);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const area = useRef(null);

  const load = d => { setText(d.text); setSaved(d.text); setCanUndo(d.canUndo); };
  useEffect(() => { api("/api/icp").then(load).catch(e => setStatus(e.message)); }, []);

  const sections = useMemo(() => (text || "").split("\n").map((l, i) => [l, i]).filter(([l]) => l.startsWith("## "))
    .map(([l, i]) => [l.replace(/^##\s*/, ""), i]), [text]);
  const dirty = text !== null && text !== saved;

  async function save(undo) {
    setBusy(true); setStatus("");
    try {
      load(await api("/api/icp", undo ? { undo: true } : { text }));
      toast(undo ? "Previous ICP restored" : "ICP saved. Used from the next search.");
    } catch (e) { setStatus(e.message); }
    setBusy(false);
  }
  useEffect(() => {
    const onKey = e => { if ((e.metaKey || e.ctrlKey) && e.key === "s" && dirty) { e.preventDefault(); save(false); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  function jump(lineNo) {
    const el = area.current; if (!el) return;
    const idx = text.split("\n").slice(0, lineNo).join("\n").length + (lineNo ? 1 : 0);
    el.focus(); el.setSelectionRange(idx, idx);
    const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || 20;
    el.scrollTop = Math.max(0, lineNo * lineHeight - 8);
  }

  return (
    <div className="card">
      <div className="card-head">
        <div><h2>Ideal lead (ICP)</h2>
          <p>The one file that decides who LeadTube looks for: search phrases, roles, topics, audience and what isn&apos;t your ICP.
            Saved as <code>ICP.md</code>. Section titles must stay; the lists under them are yours to change.</p></div>
      </div>
      {text === null ? <Spinner /> : <>
        <div className="icp-tools">
          <select aria-label="Jump to section" value="" onChange={e => jump(Number(e.target.value))}>
            <option value="">Jump to section…</option>
            {sections.map(([title, line]) => <option key={line} value={line}>{title}</option>)}
          </select>
          <span className="none">{sections.length} sections · lines starting with &gt; are explanations</span>
        </div>
        <textarea ref={area} className="icp-text" spellCheck={false} value={text} onChange={e => setText(e.target.value)} />
      </>}
      <div className="card-foot">
        <span className="estimate">{busy && <Spinner />}{status || (dirty ? "Unsaved changes" : "")}</span>
        <span className="panel-actions">
          <Button icon="history" onClick={() => save(true)} disabled={busy || !canUndo} title="Go back to the version before your last save">Undo last save</Button>
          <Button variant="primary" icon="check" onClick={() => save(false)} disabled={busy || !dirty}>Save</Button>
        </span>
      </div>
    </div>
  );
}
