"use client";
// Small building blocks used across the dashboard.
import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import Icon from "@/components/Icon";

type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  icon?: string; children?: ReactNode; variant?: string; size?: string;
};
export function Button({ icon, children, variant = "", size = "", className = "", ...props }: ButtonProps) {
  return (
    <button type="button" className={`btn ${variant} ${size} ${className}`} {...props}>
      {icon && <Icon name={icon} size="sm" />}
      {children !== undefined && <span>{children}</span>}
    </button>
  );
}

export function Spinner() { return <span className="spinner" aria-hidden="true" />; }

// Dropdown menu: closes when you click outside it or press Escape.
interface MenuProps {
  label: ReactNode; icon?: string; align?: "left" | "right"; open: boolean; onOpenChange: (open: boolean) => void;
  children: ReactNode; badge?: ReactNode; className?: string;
}
export function Menu({ label, icon, align = "left", open, onOpenChange, children, badge, className = "" }: MenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onOpenChange(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onOpenChange(false); };
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

export function MenuItem({ icon, title, hint, onClick, disabled }:
  { icon?: string; title: ReactNode; hint?: ReactNode; onClick?: () => void; disabled?: boolean }) {
  return (
    <button type="button" className="menu-item" onClick={onClick} disabled={disabled}>
      {icon && <Icon name={icon} size="sm" />}
      <span><b>{title}</b>{hint && <small>{hint}</small>}</span>
    </button>
  );
}

// Modal built on the native <dialog> element (focus trap, Escape, backdrop).
interface ModalProps {
  open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode;
  children?: ReactNode; footer?: ReactNode; wide?: boolean;
}
export function Modal({ open, onClose, title, subtitle, children, footer, wide }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
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

export function Field({ label, hint, children, className = "" }:
  { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <label className={`field ${className}`}>
      <span className="field-label">{label}{hint && <span className="none"> {hint}</span>}</span>
      {children}
    </label>
  );
}

export function Pill({ on, bad, children }: { on?: boolean; bad?: boolean; children: ReactNode }) {
  return <span className={`pill ${on ? "on" : ""} ${bad ? "bad" : ""}`}>{children}</span>;
}
