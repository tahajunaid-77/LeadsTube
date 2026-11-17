"use client";
// Shows what LeadTube has learned from your Good / Medium / Low ratings.
import { useState } from "react";
import Icon from "@/components/Icon";
import type { ReactNode } from "react";
import type { LearningStatus, Ratings, RatingValue } from "@/lib/types";

export default function LearningBar({ learning, ratings }: { learning: LearningStatus | null; ratings: Ratings }) {
  const [open, setOpen] = useState(false);
  const rated = Object.keys(ratings).length;
  const c: Record<RatingValue, number> = { good: 0, medium: 0, low: 0 };
  for (const v of Object.values(ratings)) if (c[v.rating] !== undefined) c[v.rating]++;
  const active = learning?.active;
  const needGood = Math.max(0, 2 - c.good), needOther = Math.max(0, 2 - c.medium - c.low), needTotal = Math.max(0, 8 - rated);

  let text: ReactNode;
  if (!rated) text = <>Rate leads <b>Good</b>, <b>Medium</b> or <b>Low</b> with the buttons in each row. LeadTube learns what you like and uses it for fit scores and the next searches.</>;
  else if (!active) text = <>{rated} rated ({c.good} good · {c.medium} medium · {c.low} low). Learning starts after{" "}
    {[needTotal && `${needTotal} more`, needGood && `${needGood} more Good`, needOther && `${needOther} more Medium/Low`].filter(Boolean).join(", ") || "a moment"}.</>;
  else if (learning) text = <>Learning from <b>{learning.ratings}</b> ratings ({learning.counts.good} good · {learning.counts.medium} medium · {learning.counts.low} low).
    Fit scores and the next searches use them.</>;

  return (
    <div className={`learning-bar ${active ? "on" : ""}`}>
      <Icon name="sparkles" size="sm" />
      <span className="learning-text">{text}</span>
      {learning && active && (learning.likes?.length || learning.dislikes?.length) ? (
        <button type="button" className="link-btn" onClick={() => setOpen(o => !o)}>{open ? "Hide" : "What it learned"}</button>
      ) : null}
      {learning && open && active && (
        <div className="learned">
          <div><h4>More like your Good leads</h4>{learning.likes.map(t => <span key={t} className="chip good">{t}</span>)}</div>
          <div><h4>More like your Low leads</h4>{learning.dislikes.map(t => <span key={t} className="chip low">{t}</span>)}</div>
        </div>
      )}
    </div>
  );
}
