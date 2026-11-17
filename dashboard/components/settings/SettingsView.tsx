"use client";
import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { Button, Field, Pill, Spinner } from "@/components/ui";
import { api, useStored } from "@/lib/client";
import IcpEditor from "@/components/settings/IcpEditor";
import type { ChangeEvent } from "react";
import type { Campaign, PublicSettings, SettingsTab, Shared } from "@/lib/types";

type CampaignState = { list: Campaign[] | null; error: string; loading: boolean };
type SettingsForm = Partial<PublicSettings>;

const SAVED = "· saved (leave empty to keep)";

export function useCampaigns(): [CampaignState, () => Promise<Campaign[]>] {
  const [state, setState] = useState<CampaignState>({ list: null, error: "", loading: false });
  async function load(): Promise<Campaign[]> {
    setState(s => ({ ...s, loading: true, error: "" }));
    try { const { campaigns } = await api<{ campaigns: Campaign[] }>("/api/smartlead/campaigns"); setState({ list: campaigns, error: "", loading: false }); return campaigns; }
    catch (e) { setState({ list: [], error: (e as Error).message, loading: false }); throw e; }
  }
  return [state, load];
}

export default function SettingsView({ mail, loadMail, toast, tab, onTab }:
  Shared & { tab: SettingsTab; onTab: (tab: SettingsTab) => void }) {
  const [form, setForm] = useState<SettingsForm | null>(null);
  const [status, setStatus] = useState<Record<"smartlead" | "sending", string>>({ smartlead: "", sending: "" });
  const [busy, setBusy] = useState("");
  const [campaigns, loadCampaigns] = useCampaigns();
  const [defaultCampaign, setDefaultCampaign] = useStored<string>("leads.slCampaign", "");
  const active: SettingsTab = (["icp", "smartlead", "sending"] as SettingsTab[]).includes(tab) ? tab : "smartlead";

  useEffect(() => { api<PublicSettings>("/api/settings").then(setForm).catch(() => setForm({})); }, []);
  useEffect(() => { if (mail.ready.smartlead && campaigns.list === null) loadCampaigns().catch(() => {}); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mail.ready.smartlead]);

  const set = (k: keyof SettingsForm) => (e: ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, [k]: e.target.value }));
  const say = (k: "smartlead" | "sending", msg: string) => setStatus(s => ({ ...s, [k]: msg }));

  async function save(section?: "smartlead" | "sending") {
    const saved = await api<PublicSettings>("/api/settings", form);
    setForm(f => ({ ...saved, from_name: f?.from_name, from_email: f?.from_email, smtp_host: f?.smtp_host, smtp_port: f?.smtp_port, daily_limit: f?.daily_limit }));
    await loadMail();
    if (section) { say(section, "Saved."); toast("Settings saved"); }
  }
  async function testSmartlead() {
    setBusy("smartlead"); say("smartlead", "");
    try {
      await save(); const list = await loadCampaigns();
      say("smartlead", list.length ? "Connected. Pick a default campaign." : "Connected, but no active campaigns yet.");
    } catch (e) { say("smartlead", (e as Error).message); }
    setBusy("");
  }
  async function testGmail() {
    setBusy("sending"); say("sending", "");
    try { await save(); const r = await api<{ message?: string }>("/api/email/test", {}); say("sending", r.message || "Login works."); }
    catch (e) { say("sending", (e as Error).message); }
    setBusy("");
  }

  const connected = campaigns.list && !campaigns.error;
  return (
    <section className="view">
      <div className="page-head"><div><h1>Settings</h1><div className="summary">Your ideal lead and connections. Saved only on this Mac.</div></div></div>
      <div className="settings">
        <nav className="settings-nav" aria-label="Settings sections">
          <button type="button" aria-pressed={active === "icp"} onClick={() => onTab("icp")}>
            <Icon name="users" size="sm" />Ideal lead (ICP)</button>
          <button type="button" aria-pressed={active === "smartlead"} onClick={() => onTab("smartlead")}>
            <Icon name="plug" size="sm" />Smartlead<span className={`status-dot ${mail.ready.smartlead ? "on" : ""}`} /></button>
          <button type="button" aria-pressed={active === "sending"} onClick={() => onTab("sending")}>
            <Icon name="mail" size="sm" />Gmail <span className="tag-opt">optional</span><span className={`status-dot ${mail.ready.sending ? "on" : ""}`} /></button>
        </nav>

        <div className="settings-body">
          {active === "icp" ? <IcpEditor toast={toast} /> : !form ? <div className="card"><Spinner /></div> : active === "smartlead" ? (
            <div className="card">
              <div className="card-head">
                <div><h2>Smartlead</h2><p>Send leads straight into your Smartlead campaigns.</p></div>
                {connected && campaigns.list ? <Pill on>Connected · {campaigns.list.length} campaign{campaigns.list.length === 1 ? "" : "s"}</Pill>
                  : campaigns.error ? <Pill bad>Not connected</Pill>
                  : <Pill on={mail.ready.smartlead}>{mail.ready.smartlead ? "Key saved" : "Not connected"}</Pill>}
              </div>
              <Field label="API key" hint={form.smartlead_api_key_set ? SAVED : ""}>
                <input type="password" autoComplete="off" placeholder="Paste your Smartlead API key"
                  value={form.smartlead_api_key || ""} onChange={set("smartlead_api_key")} />
              </Field>
              <p className="hint small">In Smartlead: profile → Settings → API key.</p>
              <Field label="Default campaign">
                <select value={defaultCampaign} onChange={e => { setDefaultCampaign(e.target.value); toast("Default campaign saved"); }}>
                  <option value="">{campaigns.loading ? "Loading campaigns…" : connected ? "Choose a campaign" : "Connect to load campaigns"}</option>
                  {(campaigns.list || []).map(c => <option key={c.id} value={c.id}>{c.name}{c.status ? ` (${c.status.toLowerCase()})` : ""}</option>)}
                </select>
              </Field>
              <div className="card-foot">
                <span className="estimate">{busy === "smartlead" && <Spinner />}{status.smartlead}</span>
                <span className="panel-actions">
                  <Button icon="refresh" onClick={testSmartlead} disabled={!!busy}>Test connection</Button>
                  <Button variant="primary" icon="check" onClick={() => save("smartlead").catch((e: Error) => say("smartlead", e.message))}>Save</Button>
                </span>
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="card-head">
                <div><h2>Gmail</h2><p>Optional. Send one email at a time from LeadTube. For campaigns, use Smartlead.</p></div>
                <Pill on={mail.ready.sending}>{mail.ready.sending ? "Connected" : "Off"}</Pill>
              </div>
              <div className="row2">
                <Field label="Your name"><input type="text" placeholder="Taha" value={form.from_name || ""} onChange={set("from_name")} /></Field>
                <Field label="Email address"><input type="email" autoComplete="off" placeholder="you@yourdomain.com"
                  value={form.from_email || ""} onChange={set("from_email")} /></Field>
              </div>
              <Field label="App password" hint={form.app_password_set ? SAVED : ""}>
                <input type="password" autoComplete="new-password" placeholder="16-letter app password" value={form.app_password || ""} onChange={set("app_password")} />
              </Field>
              <p className="hint small">Google Account → Security → 2-Step Verification → App passwords.</p>
              <details className="fields-help">
                <summary>Advanced</summary>
                <div className="row3">
                  <Field label="SMTP server"><input type="text" value={form.smtp_host || ""} onChange={set("smtp_host")} /></Field>
                  <Field label="Port"><input type="number" min={1} max={65535} value={form.smtp_port || ""} onChange={set("smtp_port")} /></Field>
                  <Field label="Max per day"><input type="number" min={1} max={500} value={form.daily_limit || ""} onChange={set("daily_limit")} /></Field>
                </div>
              </details>
              <div className="card-foot">
                <span className="estimate">{busy === "sending" && <Spinner />}{status.sending}</span>
                <span className="panel-actions">
                  <Button icon="refresh" onClick={testGmail} disabled={!!busy} title="Signs in to your email account. Sends nothing.">Test login</Button>
                  <Button variant="primary" icon="check" onClick={() => save("sending").catch((e: Error) => say("sending", e.message))}>Save</Button>
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
