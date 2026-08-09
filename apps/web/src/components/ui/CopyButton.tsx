"use client";

import { useState } from "react";

export function CopyButton({
  text,
  label = "Copy",
  className = "",
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch (e) {
      setCopied(false);
      window.alert(
        e instanceof Error
          ? `Copy failed: ${e.message}`
          : "Copy failed — clipboard permission denied."
      );
    }
  }

  return (
    <button
      type="button"
      className={`btn btn-ghost btn-sm copy-btn${copied ? " is-copied" : ""} ${className}`.trim()}
      onClick={() => void onCopy()}
      aria-label={copied ? "Copied" : `Copy ${label}`}
    >
      {copied ? "Copied" : label}
    </button>
  );
}
