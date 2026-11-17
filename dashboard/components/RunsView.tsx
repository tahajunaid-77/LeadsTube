"use client";
import { num } from "@/lib/client";
import type { RunRow } from "@/lib/types";

export default function RunsView({ runs }: { runs: RunRow[] }) {
  const max = Math.max(1, ...runs.map(r => num(r.new_channels)));
  return (
    <section className="view">
      <div className="page-head"><div><h1>Runs</h1><div className="summary">Every search, newest first.</div></div></div>
      <div className="table-card">
        <table className="history">
          <thead><tr><th>Run</th><th>Date</th><th className="num">New channels</th><th className="num">With email</th>
            <th className="num col-hide">YouTube units</th><th className="col-hide" /></tr></thead>
          <tbody>
            {runs.length ? runs.slice().reverse().map(r => (
              <tr key={r.run}>
                <td><b>{r.run}</b></td><td className="muted">{r.date}</td>
                <td className="num">{r.new_channels}</td><td className="num">{r.with_email}</td>
                <td className="num col-hide muted">{num(r.youtube_units).toLocaleString()}</td>
                <td className="col-hide"><span className="minibar"><i style={{ width: num(r.new_channels) / max * 100 + "%" }} /></span></td>
              </tr>
            )) : <tr><td colSpan={6} className="none">No runs yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
