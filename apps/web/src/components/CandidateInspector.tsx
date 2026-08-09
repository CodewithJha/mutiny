"use client";

import type { Candidate } from "@/lib/api";
import {
  Button,
  Chip,
  Collapsible,
  EmptyState,
  JsonBlock,
  Skeleton,
} from "@/components/ui";

type Props = {
  candidate: Candidate | null;
  loading?: boolean;
  onMinimize?: () => void;
  onSave?: () => void;
  minimizeBusy?: boolean;
  saveBusy?: boolean;
  minimizeResult?: {
    still_reproduces: boolean;
    minimized_turn_count: number;
    original_turn_count: number;
    reexec_count: number;
    minimized_genome: Candidate["genome"];
  } | null;
  savedId?: string | null;
};

/**
 * Evidence-first inspector.
 * Story: Verified Violation → Tool Evidence (JSON hero) → Minimize/Save →
 * Conversation (collapsed) → Debug (collapsed).
 */
export function CandidateInspector({
  candidate,
  loading,
  onMinimize,
  onSave,
  minimizeBusy,
  saveBusy,
  minimizeResult,
  savedId,
}: Props) {
  if (loading) {
    return (
      <div className="inspector-scroll">
        <Skeleton lines={5} />
        <div className="skeleton mt-4" style={{ height: 140 }} aria-hidden />
      </div>
    );
  }

  if (!candidate) {
    return (
      <EmptyState title="Select a candidate" className="m-4">
        <p>
          Click a node in the evolution graph to inspect tool calls and verified
          violations.
        </p>
      </EmptyState>
    );
  }

  const hit = candidate.hits?.find((h) => h.violated);
  const tools =
    candidate.trace?.all_tool_calls ??
    (hit?.evidence?.tool_name
      ? [
          {
            id: hit.evidence.tool_call_id || "tc",
            name: hit.evidence.tool_name,
            arguments: hit.evidence.arguments || {},
          },
        ]
      : []);

  const evidenceHero =
    hit?.evidence?.arguments ??
    (tools[0]?.arguments as Record<string, unknown> | undefined);

  return (
    <div className="inspector">
      <div className="inspector-head">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="panel-title">Evidence</span>
            {candidate.violated ? (
              <Chip tone="violation">Violated</Chip>
            ) : (
              <Chip tone="blue">Scored</Chip>
            )}
          </div>
          <dl className="inspector-meta">
            <div>
              <dt>Strategy</dt>
              <dd className="font-mono">{candidate.genome.strategy}</dd>
            </div>
            <div>
              <dt>Gen</dt>
              <dd className="font-mono">{candidate.generation}</dd>
            </div>
            <div>
              <dt>Fitness</dt>
              <dd className="font-mono">
                {candidate.fitness == null
                  ? "—"
                  : candidate.fitness.toFixed(3)}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="inspector-scroll">
        {/* 1. Verified violation — before transcript */}
        {hit && (
          <section className="inspector-section">
            <h4 className="inspector-section-title">Verified violation</h4>
            <div className="evidence-block">
              <p className="evidence-kicker">Rule broken</p>
              <p className="rule-id">{hit.rule_id}</p>
              {hit.evidence?.message && (
                <p className="evidence-msg">{hit.evidence.message}</p>
              )}
            </div>
          </section>
        )}

        {/* 2. Tool evidence JSON — visual hero */}
        <section className="inspector-section">
          <h4 className="inspector-section-title">Tool evidence</h4>
          {tools.length === 0 && !evidenceHero ? (
            <p className="text-sm text-muted">No tool calls on this candidate.</p>
          ) : (
            <div className="tool-evidence-hero">
              {tools.map((tc) => (
                <div key={tc.id} className="tool-call tool-call-hero">
                  <div className="tool-call-bar">
                    <p className="tool-call-name">{tc.name}</p>
                    <span className="tool-call-id font-mono">{tc.id.slice(0, 8)}</span>
                  </div>
                  <JsonBlock
                    value={tc.arguments}
                    className="tool-json"
                    compact
                    label="arguments"
                  />
                </div>
              ))}
              {hit?.evidence && tools.length === 0 && (
                <JsonBlock
                  value={hit.evidence}
                  compact
                  label="evidence"
                  className="tool-json"
                />
              )}
            </div>
          )}
        </section>

        {/* 3. Minimize / Save — adjacent to evidence */}
        {candidate.violated && (
          <section className="inspector-actions">
            <h4 className="inspector-section-title">Minimize → Regression</h4>
            <div className="inspector-action-row">
              <Button
                variant="primary"
                disabled={minimizeBusy}
                onClick={onMinimize}
              >
                {minimizeBusy ? "Minimizing…" : "Minimize"}
              </Button>
              <Button
                variant="secondary"
                disabled={saveBusy || !candidate.violated}
                onClick={onSave}
              >
                {saveBusy ? "Saving…" : "Save regression"}
              </Button>
            </div>
            {minimizeResult && (
              <div className="alert alert-ok text-sm mt-3">
                Turns {minimizeResult.original_turn_count} →{" "}
                {minimizeResult.minimized_turn_count} · re-execs{" "}
                {minimizeResult.reexec_count} · still reproduces:{" "}
                <strong>{String(minimizeResult.still_reproduces)}</strong>
                <JsonBlock
                  value={minimizeResult.minimized_genome.messages.map(
                    (m) => m.content
                  )}
                  className="mt-2 max-h-28"
                  compact
                  label="minimized"
                />
              </div>
            )}
            {savedId && (
              <p className="mt-2 text-sm text-success">
                Saved{" "}
                <span className="font-mono">{savedId.slice(0, 8)}…</span>
                {" — "}
                replay with <code>mutiny test</code>.
              </p>
            )}
          </section>
        )}

        {/* 4. Conversation — collapsed (secondary) */}
        <Collapsible
          title="Conversation"
          badge={
            <span className="font-mono text-[10px] text-muted normal-case tracking-normal">
              {candidate.genome.messages.length} turns
            </span>
          }
          defaultOpen={!candidate.violated}
        >
          <ul className="msg-list p-3">
            {candidate.genome.messages.map((m, i) => (
              <li key={i} className="msg-item">
                <span className="msg-role">{m.role}</span>
                <p className="msg-body">{m.content}</p>
              </li>
            ))}
          </ul>
        </Collapsible>

        <Collapsible title="Debug" defaultOpen={false}>
          <div className="p-3 font-mono text-[11px] text-muted space-y-1">
            <div>id · {candidate.id}</div>
            <div>campaign · {candidate.campaign_id}</div>
            <div>parent · {candidate.parent_id || "—"}</div>
            <div>
              mutations · {candidate.genome.mutations?.join(", ") || "—"}
            </div>
          </div>
        </Collapsible>
      </div>
    </div>
  );
}
