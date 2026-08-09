"use client";

import type { ReactNode } from "react";
import { useId, useState } from "react";

export function Collapsible({
  title,
  children,
  defaultOpen = false,
  badge,
}: {
  title: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  badge?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();

  return (
    <div className="collapsible">
      <button
        type="button"
        className="collapsible-trigger"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="inline-flex items-center gap-2">
          <span aria-hidden style={{ opacity: 0.55, fontSize: 10 }}>
            {open ? "▾" : "▸"}
          </span>
          {title}
        </span>
        {badge}
      </button>
      {open ? (
        <div id={id} className="collapsible-body">
          {children}
        </div>
      ) : null}
    </div>
  );
}
