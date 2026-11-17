"use client";
import { useEffect, useState } from "react";
import { Button, Field, Modal, Spinner } from "@/components/ui";
import { api, smartleadRow, useStored } from "@/lib/client";
import { render as fill } from "@/lib/personalize";
import { useCampaigns } from "@/components/settings/SettingsView";
import type { Lead, Shared } from "@/lib/types";

const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
const toHtml = (t: string) => String(t).replace(/[&<>"]/g, c => ESCAPES[c] ?? c).replace(/\n/g, "<br>");

// leads: the leads to send (your selection, or the current view). null = closed.
export default function SmartleadDialog({ leads, onClose, data, mail, copy, toast, loadData }:
  Shared & { leads: Lead[] | null; onClose: () => void }) {
  const open = !!leads;
  const [campaignId, setCampaignId] = useStored<string>("leads.slCampaign", "");
  const [campaigns, loadCampaigns] = useCampaigns();
  const [skipContacted, setSkipContacted] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (open) { setError(""); loadCampaigns().catch(() => {}); } },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [open]);

  const optOut = new Set(mail.optOut.map(e => e.toLowerCase()));
  const withEmail = (leads || []).filter(c => c.best_email && !optOut.has(c.best_email.toLowerCase()));
  const todo = withEmail.filter(c => !mail.smartlead[c.channel_link] && !(skipContacted && data.contacted[c.channel_link]));
  const first = todo[0];
  const firstRow = first ? smartleadRow(first) : null;
  const campaign = (campaigns.list || []).find(c => String(c.id) === String(campaignId));

  async function send() {
    if (!todo.length || !campaign) return;
    if (!confirm(`Add ${todo.length} leads to the Smartlead campaign "${campaign.name}"?`)) return;
    setBusy(true); setError("");
    try {
      const payload = todo.map(c => {
        const r = smartleadRow(c);
        return { link: c.channel_link, ...r,
          ...(copy.body ? { email_subject: fill(copy.subject, r), email_body: toHtml(fill(copy.body, r)) } : {}) };
      });
      const r = await api<{ added: number; skipped: number }>("/api/smartlead/push", { campaign_id: Number(campaign.id), campaign_name: campaign.name, leads: payload });
      toast(`Added ${r.added} to "${campaign.name}"${r.skipped ? `, ${r.skipped} skipped by Smartlead` : ""}`);
      onClose();
      await loadData();
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  }

  return (
    <Modal open={open} onClose={onClose} title="Send to Smartlead"
      subtitle={`Adds ${leads && leads.length !== data.channels.length ? "your selected / filtered" : "these"} leads to a campaign.`}
      footer={<>
        <span className="estimate">{busy && <Spinner />}{error || (campaigns.error && !campaigns.list?.length ? campaigns.error : "")}</span>
        <Button variant="primary" icon="send" onClick={send} disabled={busy || !todo.length || !campaign}>
          Add {todo.length} lead{todo.length === 1 ? "" : "s"}</Button>
      </>}>
      <Field label="Campaign">
        <select value={campaignId} onChange={e => setCampaignId(e.target.value)}>
          <option value="">{campaigns.loading ? "Loading campaigns…" : campaigns.list?.length ? "Choose a campaign" : "No active campaigns"}</option>
          {(campaigns.list || []).map(c => <option key={c.id} value={c.id}>{c.name}{c.status ? ` (${c.status.toLowerCase()})` : ""}</option>)}
        </select>
      </Field>
      <label className="check-label"><input type="checkbox" checked={skipContacted} onChange={e => setSkipContacted(e.target.checked)} />
        Skip channels already marked contacted</label>
      <p className="hint">
        {todo.length} of the {withEmail.length} leads with an email will be added
        {withEmail.length > todo.length ? " (the rest are already in Smartlead or marked contacted)." : "."}
        {copy.body ? " Your email is included as {{email_subject}} and {{email_body}}." : " Tip: write your email on the Email page to include it."}
      </p>
      {firstRow && (
        <div className="sl-preview">
          <h4>First lead</h4>
          <div className="mini-mail">
            <b>{first?.best_email}</b>
            {copy.body ? <><i>{fill(copy.subject, firstRow)}</i><p className="pre">{fill(copy.body, firstRow)}</p></>
              : <p>Hi {firstRow.greeting_name}, {firstRow.personal_line}…</p>}
          </div>
        </div>
      )}
    </Modal>
  );
}
