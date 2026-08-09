import type { ReactNode } from "react";

export type TimelineTone = "default" | "live" | "violation" | "ok";

export type TimelineEntry = {
  id: string;
  type: string;
  meta?: string;
  ts?: string;
  tone?: TimelineTone;
};

const toneClass: Record<TimelineTone, string> = {
  default: "",
  live: "timeline-dot-live",
  violation: "timeline-dot-violation",
  ok: "timeline-dot-ok",
};

export function Timeline({
  entries,
  empty,
}: {
  entries: TimelineEntry[];
  empty?: ReactNode;
}) {
  if (entries.length === 0) {
    return (
      <ul className="timeline">
        <li className="timeline-item">
          <span className="timeline-dot" />
          <span className="timeline-meta">{empty ?? "No events yet"}</span>
          <span />
        </li>
      </ul>
    );
  }

  return (
    <ul className="timeline">
      {entries.map((ev) => (
        <li key={ev.id} className="timeline-item">
          <span className={`timeline-dot ${toneClass[ev.tone ?? "default"]}`} />
          <div>
            <span className="timeline-type">{ev.type}</span>
            {ev.meta ? <span className="timeline-meta"> · {ev.meta}</span> : null}
          </div>
          {ev.ts ? <span className="timeline-ts">{ev.ts}</span> : <span />}
        </li>
      ))}
    </ul>
  );
}
