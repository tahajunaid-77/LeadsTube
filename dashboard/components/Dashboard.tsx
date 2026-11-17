"use client";
// The whole dashboard: loads data, keeps the shared state, and shows one page at a time.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, prepareChannel, useStored } from "@/lib/client";
import Sidebar from "@/components/Sidebar";
import LeadsView from "@/components/leads/LeadsView";
import EmailView from "@/components/email/EmailView";
import RunsView from "@/components/RunsView";
import SettingsView from "@/components/settings/SettingsView";
import FindLeadsDialog from "@/components/dialogs/FindLeadsDialog";
import SmartleadDialog from "@/components/dialogs/SmartleadDialog";
import ComposeDialog from "@/components/dialogs/ComposeDialog";
import type { Copy, DashboardData, DataPayload, Job, Lead, Limits, MailState, RatingValue, SettingsTab, Shared, View } from "@/lib/types";

const EMPTY_MAIL: MailState = { drafts: {}, optOut: [], smartlead: {}, sentToday: 0, limit: 30, ready: { sending: false, smartlead: false } };

export default function Dashboard() {
  const [view, setView] = useStored<View>("leads.view", "leads");
  const [theme, setTheme] = useStored<"" | "light" | "dark">("leads.theme", "");
  const [data, setData] = useState<DashboardData>({ channels: [], runs: [], contacted: {}, ratings: {}, learning: null, updated: null, loaded: false, error: "" });
  const [mail, setMail] = useState(EMPTY_MAIL);
  const [copy, setCopy] = useState<Copy>({ subject: "", body: "" });
  const [limits, setLimits] = useState<Limits | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [toastMsg, setToastMsg] = useState("");
  const [runOpen, setRunOpen] = useState(false);
  const [smartleadLeads, setSmartleadLeads] = useState<Lead[] | null>(null);   // leads to send, or null when closed
  const [composeLink, setComposeLink] = useState<string | null>(null);
  const [settingsTab, setSettingsTab] = useStored<SettingsTab>("leads.settingsTab", "smartlead");
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const toast = useCallback((msg: string) => {
    setToastMsg(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastMsg(""), 2200);
  }, []);

  // ---- loading
  const loadMail = useCallback(async () => { setMail(await api<MailState>("/api/email/state").catch(() => EMPTY_MAIL)); }, []);
  const loadCopy = useCallback(async () => { setCopy(await api<Copy>("/api/copy").catch(() => ({ subject: "", body: "" }))); }, []);
  const loadData = useCallback(async () => {
    try {
      const d = await api<DataPayload>("/api/data");
      setData({ ...d, channels: d.channels.map(prepareChannel), loaded: true, error: "" });
    } catch (e) { setData(prev => ({ ...prev, loaded: true, error: (e as Error).message })); }
    await loadMail();
  }, [loadMail]);
  const loadLimits = useCallback(async (refresh?: boolean) => {
    const l = await api<Limits>("/api/limits" + (refresh ? "?refresh=1" : "")).catch(() => null);
    if (l) setLimits(l);
  }, []);

  useEffect(() => { loadData(); loadCopy(); loadLimits(); const t = setInterval(() => loadLimits(), 60000); return () => clearInterval(t); },
    [loadData, loadCopy, loadLimits]);

  // ---- searches started from the dashboard (or Terminal): poll while running
  const wasRunning = useRef(false);
  const pollJob = useCallback(async () => {
    const j = await api<Job>("/api/run").catch(() => null);
    if (!j) return;
    setJob(j);
    if (wasRunning.current && !j.running) {
      await loadData(); loadLimits(true);
      toast(j.code === 0 ? "Run finished. Leads updated." : "Run stopped. See the log.");
    }
    wasRunning.current = j.running;
  }, [loadData, loadLimits, toast]);
  useEffect(() => { pollJob(); }, [pollJob]);
  useEffect(() => {
    if (!job?.running) return;
    const t = setInterval(pollJob, 1500);
    const l = setInterval(() => loadLimits(), 10000);
    return () => { clearInterval(t); clearInterval(l); };
  }, [job?.running, pollJob, loadLimits]);

  // ---- theme
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
  }, [theme]);

  // ---- contacted (one or many leads)
  const setContacted = useCallback(async (links: string[], value: boolean) => {
    setData(prev => {
      const contacted = { ...prev.contacted };
      const today = new Date().toISOString().slice(0, 10);
      for (const l of links) { if (value) contacted[l] = contacted[l] || today; else delete contacted[l]; }
      return { ...prev, contacted };
    });
    try { await api("/api/contacted", { links, contacted: value }); }
    catch { toast("Couldn't save. Is the dashboard still running?"); }
  }, [toast]);

  // ---- your ratings (Good / Medium / Low): saved, then the tool re-learns and re-scores
  const relearnTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const setRating = useCallback(async (links: string[], rating: RatingValue | null) => {
    setData(prev => {
      const ratings = { ...prev.ratings };
      const date = new Date().toISOString().slice(0, 10);
      for (const l of links) { if (rating) ratings[l] = { rating, date }; else delete ratings[l]; }
      return { ...prev, ratings };
    });
    try { await api("/api/ratings", { links, rating }); }
    catch { toast("Couldn't save the rating. Is the dashboard still running?"); return; }
    clearTimeout(relearnTimer.current);
    relearnTimer.current = setTimeout(() => loadData(), 7000);   // fit scores update after re-learning
  }, [toast, loadData]);

  const openSettings = useCallback((tab?: SettingsTab) => { if (tab) setSettingsTab(tab); setView("settings"); }, [setSettingsTab, setView]);
  const byLink = useMemo(() => new Map(data.channels.map(c => [c.channel_link, c])), [data.channels]);

  const shared: Shared = { data, mail, copy, toast, loadData, loadMail, setCopy, setContacted, setRating, openSettings, byLink };
  const pages: View[] = ["leads", "email", "runs", "settings"];
  const page: View = pages.includes(view) ? view : "leads";

  return (
    <div className="app">
      <Sidebar view={page} onView={setView} limits={limits} theme={theme} onTheme={setTheme}
        ready={mail.ready} copyReady={!!copy.body} />
      <main className="main">
        {page === "leads" && <LeadsView {...shared} job={job}
          onFindLeads={() => setRunOpen(true)}
          onSmartlead={(leads: Lead[]) => mail.ready.smartlead ? setSmartleadLeads(leads) : (openSettings("smartlead"), toast("Add your Smartlead API key first"))}
          onCompose={setComposeLink} />}
        {page === "email" && <EmailView {...shared} />}
        {page === "runs" && <RunsView runs={data.runs} />}
        {page === "settings" && <SettingsView {...shared} tab={settingsTab} onTab={setSettingsTab} />}
      </main>

      <FindLeadsDialog open={runOpen} onClose={() => setRunOpen(false)} job={job} onStarted={pollJob} toast={toast} />
      <SmartleadDialog leads={smartleadLeads} onClose={() => setSmartleadLeads(null)} {...shared} />
      <ComposeDialog link={composeLink} onClose={() => setComposeLink(null)} {...shared} />

      <div className={`toast ${toastMsg ? "show" : ""}`} role="status">{toastMsg}</div>
    </div>
  );
}
