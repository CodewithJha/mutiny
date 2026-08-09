"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  mutinyApi,
  type RegressionDetail,
  type TestRunResult,
} from "@/lib/api";
import {
  Button,
  Chip,
  Collapsible,
  EmptyState,
  JsonBlock,
  Skeleton,
} from "@/components/ui";

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function StatusChip({ status }: { status: string | null | undefined }) {
  if (!status) return <Chip>never</Chip>;
  if (status === "PASS") return <Chip tone="success">PASS</Chip>;
  if (status === "FAIL") return <Chip tone="violation">FAIL</Chip>;
  return <Chip tone="amber">{status}</Chip>;
}

export default function TestDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = String(params.id);
  const [row, setRow] = useState<RegressionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [lastResult, setLastResult] = useState<TestRunResult | null>(null);

  const refresh = useCallback(async () => {
    const r = await mutinyApi.getRegression(id);
    setRow(r);
  }, [id]);

  useEffect(() => {
    refresh()
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [refresh]);

  async function run(fixedAgent: boolean) {
    setBusy(true);
    setError(null);
    try {
      const out = await mutinyApi.runTests(id, fixedAgent);
      setLastResult(out);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this regression and its run history?")) return;
    setBusy(true);
    try {
      await mutinyApi.deleteRegression(id);
      router.push("/tests");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="page page-narrow fade-in">
        <Skeleton lines={5} />
      </div>
    );
  }

  if (!row) {
    return (
      <div className="page page-narrow fade-in">
        <p className="alert alert-error">{error || "Not found"}</p>
        <Link href="/tests" className="btn btn-secondary mt-4">
          Back to tests
        </Link>
      </div>
    );
  }

  const art = row.artifact;
  const rules =
    art.expected?.must_not_violate?.join(", ") ||
    art.policy_rule_ids?.join(", ") ||
    "—";
  const policyVer =
    art.provenance?.policy_version ||
    row.last_run?.policy_version ||
    "—";
  const runs = row.runs || [];

  return (
    <div className="page page-narrow fade-in">
      <p className="breadcrumb">
        <Link href="/tests">Tests</Link>
        {" / "}
        <span className="text-dim">{art.name}</span>
      </p>

      <header className="page-header mt-1">
        <div>
          <h1 className="page-title">{art.name}</h1>
          <div className="meta-row">
            <StatusChip status={row.last_run?.status} />
            <span className="meta-item">
              Rule <span className="meta-value">{rules}</span>
            </span>
            <span className="meta-item">
              Policy{" "}
              <span className="meta-value">
                {policyVer === "—" ? "—" : `v${policyVer}`}
              </span>
            </span>
            <span className="meta-item">
              ID{" "}
              <span className="meta-value" title={row.id}>
                {row.id.slice(0, 8)}…
              </span>
            </span>
          </div>
        </div>
        <div className="action-bar">
          <Button disabled={busy} onClick={() => run(false)}>
            {busy ? "Running…" : "Run"}
          </Button>
          <Button
            variant="success"
            disabled={busy}
            onClick={() => run(true)}
          >
            Fixed agent
          </Button>
          <Button variant="danger" disabled={busy} onClick={remove}>
            Delete
          </Button>
        </div>
      </header>

      {error && <p className="alert alert-error mt-6">{error}</p>}

      {lastResult && (
        <section className="panel mt-6 p-4">
          <p className="field-label">Latest replay</p>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <StatusChip status={lastResult.status} />
            <span className="font-mono text-xs text-muted">
              {lastResult.duration_ms != null
                ? `${Math.round(lastResult.duration_ms)}ms`
                : ""}
              {lastResult.fixed_agent ? " · fixed_agent" : ""}
            </span>
          </p>
          <p className="mt-1 text-sm text-muted">{lastResult.summary}</p>
          {lastResult.evidence && lastResult.evidence.length > 0 && (
            <JsonBlock value={lastResult.evidence} className="mt-3" compact />
          )}
        </section>
      )}

      <div className="meta-strip mt-6">
        <div className="meta-strip-item">
          <div className="label">Expected</div>
          <div className="value text-sm">
            Must <span className="text-success">not</span> violate
          </div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Rules</div>
          <div className="value font-mono text-sm">{rules}</div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Turns</div>
          <div className="value text-sm">
            {art.provenance?.minimized_turn_count ?? art.conversation.length}
            {art.provenance?.minimized_from_turns != null
              ? ` (from ${art.provenance.minimized_from_turns})`
              : ""}
          </div>
        </div>
      </div>

      <section className="mt-8">
        <h2 className="inspector-section-title">Conversation</h2>
        <ol className="msg-list">
          {art.conversation.map((line, i) => (
            <li key={i} className="msg-item">
              <span className="msg-role">turn {i + 1}</span>
              <p className="msg-body">{line}</p>
            </li>
          ))}
        </ol>
      </section>

      {row.candidate_id && (
        <p className="mt-4 text-xs text-muted">
          From candidate{" "}
          <Link
            href={`/exploit/${row.candidate_id}`}
            className="font-mono text-primary hover:underline"
          >
            {row.candidate_id}
          </Link>
        </p>
      )}

      <section className="mt-8">
        <h2 className="text-sm font-semibold mb-3">Replay history</h2>
        {runs.length === 0 ? (
          <EmptyState title="No runs yet">
            <p>Hit Run to replay this regression against the current agent.</p>
          </EmptyState>
        ) : (
          <ul className="list-stack">
            {runs.map((run) => (
              <li key={run.id} className="panel p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <StatusChip status={run.status} />
                    <span className="font-mono text-[11px] text-muted">
                      {formatWhen(run.created_at)}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-muted">
                    {run.duration_ms != null
                      ? `${Math.round(run.duration_ms)}ms`
                      : "—"}
                    {run.policy_version ? ` · policy v${run.policy_version}` : ""}
                    {run.fixed_agent ? " · fixed" : ""}
                  </span>
                </div>
                {run.summary && (
                  <p className="mt-1 text-xs text-muted">{run.summary}</p>
                )}
                {run.violated_rule_ids?.length > 0 && (
                  <p className="mt-1 font-mono text-xs text-violation">
                    {run.violated_rule_ids.join(", ")}
                  </p>
                )}
                {run.evidence?.length > 0 && (
                  <Collapsible
                    title={`Tool evidence (${run.evidence.length})`}
                    defaultOpen={false}
                  >
                    <div className="p-3">
                      <JsonBlock value={run.evidence} compact />
                    </div>
                  </Collapsible>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
