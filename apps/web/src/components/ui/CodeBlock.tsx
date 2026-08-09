"use client";

import { useState } from "react";

export function CodeBlock({
  children,
  className = "",
  compact = false,
  copyable = false,
  label,
}: {
  children: string;
  className?: string;
  compact?: boolean;
  copyable?: boolean;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  }

  if (!copyable) {
    return (
      <pre
        className={`code-block ${compact ? "code-block-sm" : ""} ${className}`.trim()}
      >
        {children}
      </pre>
    );
  }

  return (
    <div className={`ide-well ${className}`.trim()}>
      <div className="ide-well-bar">
        <span>{label || "code"}</span>
        <button
          type="button"
          className="btn btn-ghost btn-sm copy-btn"
          onClick={() => void onCopy()}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className={`code-block ${compact ? "code-block-sm" : ""}`.trim()}>
        {children}
      </pre>
    </div>
  );
}

/** Compact JSON dump for tool args / evidence — craft without a full viewer. */
export function JsonBlock({
  value,
  compact = false,
  className = "",
  copyable = true,
  label = "JSON",
}: {
  value: unknown;
  compact?: boolean;
  className?: string;
  copyable?: boolean;
  label?: string;
}) {
  return (
    <CodeBlock
      compact={compact}
      className={className}
      copyable={copyable}
      label={label}
    >
      {JSON.stringify(value, null, 2)}
    </CodeBlock>
  );
}
