"use client";
// The dashboard runs only in the browser (it reads your saved filters, theme, etc.).
import dynamic from "next/dynamic";

const Dashboard = dynamic(() => import("@/components/Dashboard"), {
  ssr: false,
  loading: () => <div className="boot">Loading LeadTube…</div>,
});

export default function ClientApp() { return <Dashboard />; }
