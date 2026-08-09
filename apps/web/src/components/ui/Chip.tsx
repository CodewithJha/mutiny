import type { ReactNode } from "react";

type Tone = "default" | "blue" | "purple" | "amber" | "violation" | "success";

const toneClass: Record<Tone, string> = {
  default: "",
  blue: "chip-blue",
  purple: "chip-purple",
  amber: "chip-amber",
  violation: "chip-violation",
  success: "chip-success",
};

export function Chip({
  tone = "default",
  children,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={`chip ${toneClass[tone]} ${className}`.trim()}>
      {children}
    </span>
  );
}
