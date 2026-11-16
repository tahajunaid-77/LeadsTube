"use client";
import { useEffect, useState } from "react";
import { Button, Field, Modal, Spinner } from "@/components/ui";
import { api, smartleadRow } from "@/lib/client";
import { render as fill } from "@/lib/personalize";

// One-off email from Gmail: your copy filled in for this lead, editable.
export default function ComposeDialog({ link, onClose, byLink, mail, copy, toast, loadMail, setContacted }) {
  const c = link ? byLink.get(link) : null;
  const draft = link ? mail.drafts[link] : null;
  const sent = draft?.status === "sent";
  const [to, setTo] = useState(""), [subject, setSubject] = useState(""), [body, setBody] = useState("");
  const [busy, setBusy] = useState(false), [msg, setMsg] = useState("");

  useEffect(() => {
    if (!c) return;
    const f = smartleadRow(c);
    setTo(draft?.to || c.best_email || "");
    setSubject(draft?.subject ?? fill(copy.subject, f));
    setBody(draft?.body ?? fill(copy.body, f));
    setMsg(sent ? `Sent ${new Date(draft.sent).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`
      : !copy.body ? "Tip: write your email once on the Email page and it fills in here." : `${mail.sentToday} of ${mail.limit} sent today`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [link]);

  async function saveDraft() {
    setBusy(true);
    try { await api("/api/email/save", { link, to, subject, body }); await loadMail(); toast("Draft saved"); onClose(); }
    catch (e) { setMsg(e.message); }
    setBusy(false);
  }
  async function discard() {
    await api("/api/email/discard", { link }).catch(() => {});
    await loadMail(); onClose();
  }
  async function send() {
    if (!to.trim() || !subject.trim() || !body.trim()) return setMsg("Fill in To, Subject and Message.");
    if (!mail.ready.sending) return setMsg("Connect Gmail in Settings first.");
    if (!confirm(`Send this email to ${to} now?`)) return;
    setBusy(true); setMsg("Sending…");
    try {
      await api("/api/email/send", { link, to: to.trim(), subject: subject.trim(), body: body.trim() });
      await setContacted([link], true); await loadMail();
      toast(`Sent to ${to}`); onClose();
    } catch (e) { setMsg(e.message); }
    setBusy(false);
  }

  return (
    <Modal open={!!c} onClose={onClose} title={c?.channel_name || "Email"} subtitle="Your copy with this lead's details. Edit anything before sending."
      footer={<>
        <span className="estimate">{busy && <Spinner />}{msg}</span>
        {!sent && <span className="panel-actions">
          {draft && <Button onClick={discard} disabled={busy}>Discard draft</Button>}
          <Button onClick={saveDraft} disabled={busy}>Save draft</Button>
          <Button variant="primary" icon="send" onClick={send} disabled={busy}>Send</Button>
        </span>}
      </>}>
      <Field label="To">
        <input type="email" list="compose-to" value={to} readOnly={sent} onChange={e => setTo(e.target.value)} />
        <datalist id="compose-to">{(c?.emailsList || []).map(e => <option key={e} value={e} />)}</datalist>
      </Field>
      <Field label="Subject"><input type="text" value={subject} readOnly={sent} onChange={e => setSubject(e.target.value)} /></Field>
      <Field label="Message"><textarea rows={12} value={body} readOnly={sent} onChange={e => setBody(e.target.value)} className="compose-body" /></Field>
    </Modal>
  );
}
