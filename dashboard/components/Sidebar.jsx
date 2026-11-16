"use client";
import Icon from "@/components/Icon";

const NAV = [
  ["leads", "Leads", "users"],
  ["email", "Email", "mail"],
  ["runs", "Runs", "history"],
  ["settings", "Settings", "settings"],
];

function UsageCard({ limits }) {
  if (!limits) return null;
  const left = limits.youtube.reduce((a, k) => a + k.left, 0);
  const quota = limits.youtube.reduce((a, k) => a + k.quota, 0) || 1;
  const pct = Math.round(left / quota * 100);
  const tone = pct > 40 ? "ok" : pct > 10 ? "mid" : "low";
  const h = Math.floor(limits.resetsInMs / 3600000), m = Math.round((limits.resetsInMs % 3600000) / 60000);
  const perKey = limits.youtube.map(k => `${k.name} ${k.label}: ${k.left.toLocaleString()} left`).join("\n");
  return (
    <div className="usage" aria-label="API limits">
      <div className="usage-title">Today's usage</div>
      <div className="meter-row" title={perKey}>
        <span className="limit"><span className="limit-name">YouTube quota</span>
          <b>{Math.round(left / 100) / 10}K <span className="none">/ {quota / 1000}K</span></b></span>
        <span className="meter"><i className={tone} style={{ width: pct + "%" }} /></span>
      </div>
      <span className="limit" title="About this many search pages left today across your keys">
        <span className="limit-name">Search pages</span><b>~{Math.floor(left / 101)}</b></span>
      <span className="limit"><span className="limit-name">Resets in</span><b>{h}h {m}m</b></span>
      <span className="limit" title="Serper web-search credits (one-time pack)">
        <span className="limit-name">Serper credits</span><b>{limits.serper == null ? "–" : limits.serper.toLocaleString()}</b></span>
    </div>
  );
}

export default function Sidebar({ view, onView, limits, theme, onTheme, ready, copyReady }) {
  const active = theme || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const dots = { email: copyReady, settings: ready.smartlead };
  return (
    <aside className="sidebar">
      <div className="brand"><img src="/favicon.svg" alt="" width={24} height={24} /><span>LeadTube</span></div>
      <div className="nav-label">Workspace</div>
      <nav className="nav" aria-label="Main">
        {NAV.map(([key, label, icon]) => (
          <button key={key} type="button" className="nav-item" aria-current={view === key ? "page" : undefined}
            aria-pressed={view === key} onClick={() => onView(key)}>
            <Icon name={icon} /><span>{label}</span>
            {key in dots && <span className={`status-dot ${dots[key] ? "on" : ""}`}
              title={key === "email" ? (copyReady ? "Email written" : "No email written yet") : (ready.smartlead ? "Smartlead connected" : "Smartlead not connected")} />}
          </button>
        ))}
      </nav>
      <div className="side-foot">
        <UsageCard limits={limits} />
        <div className="seg theme" role="group" aria-label="Theme">
          <button type="button" aria-pressed={active === "light"} title="Light mode" aria-label="Light mode" onClick={() => onTheme("light")}>
            <Icon name="sun" size="sm" /></button>
          <button type="button" aria-pressed={active === "dark"} title="Dark mode" aria-label="Dark mode" onClick={() => onTheme("dark")}>
            <Icon name="moon" size="sm" /></button>
        </div>
      </div>
    </aside>
  );
}
