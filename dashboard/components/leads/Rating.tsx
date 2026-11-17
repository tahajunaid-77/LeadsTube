"use client";
// Your own rating of a lead: Good / Medium / Low. Click again to clear it.
import Icon from "@/components/Icon";
import type { RatingValue } from "@/lib/types";

export const RATINGS: [RatingValue, string, string][] = [
  ["good", "Good fit", "thumbsUp"],
  ["medium", "Medium fit", "minusCircle"],
  ["low", "Low fit", "thumbsDown"],
];

export default function Rating({ value, onChange, size = "row" }:
  { value: RatingValue | undefined; onChange: (rating: RatingValue | null) => void; size?: "row" | "full" }) {
  return (
    <div className={`rating ${size}`} role="group" aria-label="Your rating" onClick={e => e.stopPropagation()}>
      {RATINGS.map(([key, label, icon]) => (
        <button key={key} type="button" className={`rate rate-${key}`} aria-pressed={value === key}
          title={value === key ? `${label} (click to clear)` : label} aria-label={label}
          onClick={() => onChange(value === key ? null : key)}>
          <Icon name={icon} size="xs" />{size === "full" && <span>{label.replace(" fit", "")}</span>}
        </button>
      ))}
    </div>
  );
}
