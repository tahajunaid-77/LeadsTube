"use client";
// Your own rating of a lead: Good / Medium / Low. Click again to clear it.
import Icon from "@/components/Icon";

export const RATINGS = [
  ["good", "Good fit", "thumbsUp"],
  ["medium", "Medium fit", "minusCircle"],
  ["low", "Low fit", "thumbsDown"],
];

export default function Rating({ value, onChange, size = "row" }) {
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
