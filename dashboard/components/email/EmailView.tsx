"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { Button, Field, Menu, MenuItem } from "@/components/ui";
import { api, smartleadRow } from "@/lib/client";
import { FIELD_LIST, missing, render as fill } from "@/lib/personalize";
import type { Copy, Shared } from "@/lib/types";

// Write your email once; the preview shows it for a real lead.
export default function EmailView({ data, copy, setCopy, toast }: Shared) {
  const [subject, setSubject] = useState(copy.subject || "");
  const [body, setBody] = useState(copy.body || "");
  const [status, setStatus] = useState("");
  const [fieldsOpen, setFieldsOpen] = useState(false);
  const [leadLink, setLeadLink] = useState("");
  const lastFocus = useRef<"subject" | "body">("body");
  const subjectRef = useRef<HTMLInputElement>(null), bodyRef = useRef<HTMLTextAreaElement>(null);

  // Load the saved copy once it arrives.
  const loadedFor = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (copy.updated && loadedFor.current !== copy.updated && subject === "" && body === "") {
      setSubject(copy.subject || ""); setBody(copy.body || "");
    }
    loadedFor.current = copy.updated;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copy.updated]);

  const leads = useMemo(() => data.channels.filter(c => c.best_email).sort((a, b) => b.fit - a.fit).slice(0, 60), [data.channels]);
  const lead = leads.find(c => c.channel_link === leadLink) || leads[0];
  const f = lead ? smartleadRow(lead) : null;
  const empty = f ? missing(subject + " " + body, f) : [];
  const dirty = subject !== (copy.subject || "") || body !== (copy.body || "");

  async function save() {
    try {
      const saved = await api<Copy>("/api/copy", { subject, body });
      setCopy(saved); setStatus(""); toast("Email saved");
    } catch (e) { setStatus((e as Error).message); }
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); save(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function insert(field: string) {
    const tag = `{{${field}}}`;
    const isSubject = lastFocus.current === "subject";
    const el = isSubject ? subjectRef.current : bodyRef.current;
    const value = isSubject ? subject : body;
    const s = el?.selectionStart ?? value.length, e = el?.selectionEnd ?? value.length;
    const next = value.slice(0, s) + tag + value.slice(e);
    (isSubject ? setSubject : setBody)(next);
    setFieldsOpen(false);
    requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(s + tag.length, s + tag.length); });
  }

  return (
    <section className="view">
      <div className="page-head">
        <div><h1>Email</h1><div className="summary">Write your email once. Each lead&apos;s details are filled in automatically.</div></div>
      </div>
      <div className="email-grid">
        <div className="card">
          <div className="card-head compact">
            <h2>Your copy</h2>
            <Menu label="Insert field" icon="braces" align="right" open={fieldsOpen} onOpenChange={setFieldsOpen}>
              <div className="menu-list field-list">
                {FIELD_LIST.map(([k, d]) => <MenuItem key={k} title={<code>{`{{${k}}}`}</code>} hint={d} onClick={() => insert(k)} />)}
              </div>
            </Menu>
          </div>
          <Field label="Subject">
            <input ref={subjectRef} type="text" value={subject} placeholder="e.g. quick question about {{channel_name}}"
              onFocus={() => { lastFocus.current = "subject"; }} onChange={e => setSubject(e.target.value)} />
          </Field>
          <Field label="Message">
            <textarea ref={bodyRef} rows={13} value={body} className="copy-body"
              placeholder={"Hi {{greeting_name}},\n\n{{personal_line}}, really enjoyed it.\n\n…"}
              onFocus={() => { lastFocus.current = "body"; }} onChange={e => setBody(e.target.value)} />
          </Field>
          <div className="card-foot">
            <span className="estimate">{status || (dirty ? "Unsaved changes" : copy.updated ? "Saved" : "")}</span>
            <Button variant="primary" icon="check" onClick={save}>Save</Button>
          </div>
        </div>

        <div className="card">
          <div className="card-head compact">
            <h2><Icon name="eye" size="sm" /> Preview</h2>
            <select aria-label="Preview with lead" value={lead?.channel_link || ""} onChange={e => setLeadLink(e.target.value)}>
              {leads.map(c => <option key={c.channel_link} value={c.channel_link}>{c.channel_name.slice(0, 40)}</option>)}
            </select>
          </div>
          <div className="preview">
            <div className="preview-row"><span>To</span><b>{lead?.best_email || "–"}</b></div>
            <div className="preview-row"><span>Subject</span><b>{f ? fill(subject, f) || "(no subject)" : ""}</b></div>
            <div className="preview-body">{!f ? "Find some leads first." : fill(body, f) || "Start typing your email on the left."}</div>
          </div>
          {empty.length > 0 && (
            <div className="note warn"><Icon name="info" size="sm" />
              <span>Empty for this lead: {empty.map(m => <code key={m}>{`{{${m}}}`}</code>)}. Use <code>{"{{greeting_name}}"}</code> instead
                of <code>{"{{first_name}}"}</code>, or a fallback like <code>{"{{first_name|there}}"}</code>.</span></div>
          )}
          <div className="note"><Icon name="info" size="sm" />
            <span>In your Smartlead campaign, set the subject to <code>{"{{email_subject}}"}</code> and the body
              to <code>{"{{email_body}}"}</code>. Every lead you send from LeadTube gets this email with their details filled in.</span></div>
        </div>
      </div>
    </section>
  );
}
