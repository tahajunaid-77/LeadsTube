"use client";
// Small browser helpers shared by the components.
import { useEffect, useState } from "react";
import { fields as personalFields } from "@/lib/personalize";

export async function api(path, body) {
  const res = await fetch(path, body !== undefined
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : { cache: "no-store" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

// A value kept in localStorage (per browser), e.g. filters, theme, last page.
export function useStored(key, initial) {
  const [value, setValue] = useState(() => {
    try { const v = localStorage.getItem(key); return v === null ? initial : JSON.parse(v); } catch { return initial; }
  });
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} }, [key, value]);
  return [value, setValue];
}

export const COUNTRY = { US: "US", GB: "UK", CA: "Canada", AU: "Australia", NZ: "New Zealand", IE: "Ireland", IN: "India",
  DE: "Germany", FR: "France", NL: "Netherlands", NO: "Norway", SG: "Singapore", AE: "UAE", ZA: "South Africa", unknown: "Unknown" };

export const num = v => { const n = parseInt(v, 10); return isNaN(n) ? 0 : n; };
export const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M"
  : n >= 1e3 ? (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, "") + "K" : String(n);
export function ago(d) {
  if (!d) return "";
  const days = Math.round((new Date() - new Date(d + "T12:00:00")) / 864e5);
  return days <= 0 ? "Today" : days === 1 ? "Yesterday" : days < 30 ? days + " days ago" : Math.round(days / 30) + " mo ago";
}
export const fitClass = s => s >= 75 ? "top" : s >= 55 ? "good" : s >= 35 ? "ok" : "low";
export const handleOf = link => (link.match(/\/(@[^/?#]+)/) || [])[1] || "";

// A lead with the parsed numbers the UI sorts and filters on.
export function prepareChannel(c) {
  return { ...c, subs: num(c.subscribers), fit: num(c.fit_score),
    web: (c.email_source || "").startsWith("web search"),
    emailsList: (c.emails || "").split(";").map(e => e.trim()).filter(Boolean) };
}

// Personalization fields as Smartlead expects them.
export function smartleadRow(c) {
  const f = personalFields(c);
  return { ...f, company_name: f.channel_name, linkedin_profile: f.linkedin, location: f.country };
}

// ---------------- CSV download
const cell = v => { v = String(v ?? ""); return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
export function downloadCsv(filename, header, rows) {
  const text = "﻿" + [header.map(cell).join(",")].concat(rows.map(r => r.map(cell).join(","))).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
export const today = () => new Date().toISOString().slice(0, 10);
