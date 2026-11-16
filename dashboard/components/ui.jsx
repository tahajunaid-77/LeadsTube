"use client";
// Small building blocks used across the dashboard.
import { useEffect, useRef } from "react";
import Icon from "@/components/Icon";

export function Button({ icon, children, variant = "", size = "", className = "", ...props }) {
  return (
    <button type="button" className={`btn ${variant} ${size} ${className}`} {...props}>
      {icon && <Icon name={icon} size="sm" />}
      {children !== undefined && <span>{children}</span>}
    </button>
  );
}

export function Spinner() { return <span className="spinner" aria-hidden="true" />; }

// Dropdown menu: closes when you click outside it or press Escape.
export function Menu({ label, icon, align = "left", open, onOpenChange, children, badge, className = "" }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDown = e => { if (ref.current && !ref.current.contains(e.target)) onOpenChange(false); };
    const onKey = e => { if (e.key === "Escape") onOpenChange(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open, onOpenChange]);
  return (
    <div className={`menu ${align} ${className}`} ref={ref}>
      <button type="button" className={`btn ${open ? "active" : ""}`} aria-expanded={open} onClick={() => onOpenChange(!open)}>
        {icon && <Icon name={icon} size="sm" />}<span>{label}</span>
        {badge ? <span className="count-dot">{badge}</span> : null}
        <Icon name="chevron" size="xs" />
      </button>
      {open && <div className="menu-panel">{children}</div>}
    </div>
  );
}

export function MenuItem({ icon, title, hint, onClick, disabled }) {
  return (
    <button type="button" className="menu-item" onClick={onClick} disabled={disabled}>
      {icon && <Icon name={icon} size="sm" />}
      <span><b>{title}</b>{hint && <small>{hint}</small>}</span>
    </button>
  );
}

// Modal built on the native <dialog> element (focus trap, Escape, backdrop).
export function Modal({ open, onClose, title, subtitle, children, footer, wide }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current; if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className={`modal ${wide ? "wide" : ""}`} onClose={onClose}
      onMouseDown={e => { if (e.target === ref.current) onClose(); }}>
      {open && (
        <div className="modal-inner">
          <div className="modal-head">
            <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
            <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}><Icon name="x" size="sm" /></button>
          </div>
          {children}
          {footer && <div className="modal-foot">{footer}</div>}
        </div>
      )}
    </dialog>
  );
}

export function Field({ label, hint, children, className = "" }) {
  return (
    <label className={`field ${className}`}>
      <span className="field-label">{label}{hint && <span className="none"> {hint}</span>}</span>
      {children}
    </label>
  );
}

export function Pill({ on, bad, children }) {
  return <span className={`pill ${on ? "on" : ""} ${bad ? "bad" : ""}`}>{children}</span>;
}
