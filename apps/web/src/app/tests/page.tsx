"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  mutinyApi,
  type RegressionRow,
  type TestsSummary,
} from "@/lib/api";
import { Button, Chip, EmptyState, Skeleton } from "@/components/ui";

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
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

export default function TestsPage() {
  const [regs, setRegs] = useState<RegressionRow[]>([]);
  const [summary, setSummary] = useState<TestsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [liveLog, setLiveLog] = useState<string[]>([]);
  const [batchReport, setBatchReport] = useState<{
    passed: number;
    failed: number;
    skipped: number;
  } | null>(null);

  const refresh = useCallback(async () => {
    const settled = await Promise.allSettled([
      mutinyApi.regressions(),
      mutinyApi.testsSummary(),
    ]);
    const [regsResult, summaryResult] = settled;
    const problems: string[] = [];

    if (regsResult.status === "fulfilled") {
      setRegs(regsResult.value.regressions);
    } else {
      setRegs([]);
      problems.push(
        regsResult.reason instanceof Error
          ? regsResult.reason.message
          : String(regsResult.reason)
      );
    }

    if (summaryResult.status === "fulfilled") {
      setSummary(summaryResult.value);
    } else {
      setSummary(null);
      problems.push(
        summaryResult.reason instanceof Error
          ? `Tests summary: ${summaryResult.reason.message}`
          : `Tests summary: ${String(summaryResult.reason)}`
      );
    }

    if (problems.length) {
      throw new Error(problems.join(" · "));
    }
  }, []);

  useEffect(() => {
    refresh()
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [refresh]);

  const allSelected = useMemo(
    () => regs.length > 0 && selected.size === regs.length,
    [regs.length, selected.size]
  );

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(regs.map((r) => r.id)));
  }

  async function runBatch(
    mode: "all" | "failed" | "selected" | "one",
    id?: string
  ) {
    setError(null);
    setBatchReport(null);
    setLiveLog([]);
    setBusy(mode === "one" && id ? id : mode);
    try {
      const append = (line: string) =>
        setLiveLog((prev) => [...prev, line]);

      if (mode === "one" && id) {
        append(`→ Running ${id} …`);
        const out = await mutinyApi.runTests(id, false);
        append(
          `${out.status === "PASS" ? "✓" : "✗"} ${out.name || id} …… ${out.status}` +
            (out.duration_ms != null
              ? ` (${Math.round(out.duration_ms)}ms)`
              : "")
        );
        setBatchReport({
          passed: out.status === "PASS" ? 1 : 0,
          failed: out.status === "FAIL" ? 1 : 0,
          skipped: out.status === "SKIPPED" ? 1 : 0,
        });
      } else {
        const body =
          mode === "all"
            ? { run_all: true, fixed_agent: false }
            : mode === "failed"
              ? { failed_only: true, fixed_agent: false }
              : {
                  regression_ids: Array.from(selected),
                  fixed_agent: false,
                };
        if (mode === "selected" && selected.size === 0) {
          setError("Select at least one regression.");
          return;
        }
        append(
          mode === "all"
            ? "→ Run all …"
            : mode === "failed"
              ? "→ Run failed …"
              : `→ Run selected (${selected.size}) …`
        );
        const batch = await mutinyApi.runTestsBatch(body);
        for (const r of batch.results) {
          const mark =
            r.status === "PASS" ? "✓" : r.status === "FAIL" ? "✗" : "○";
          append(
            `${mark} ${r.name || r.regression_id} …… ${r.status}` +
              (r.duration_ms != null
                ? ` (${Math.round(r.duration_ms)}ms)`
                : "")
          );
        }
        append(
          `Summary: ${batch.passed} Passed / ${batch.failed} Failed / ${batch.skipped} Skipped`
        );
        setBatchReport({
          passed: batch.passed,
          failed: batch.failed,
          skipped: batch.skipped,
        });
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this regression and its run history?")) return;
    setBusy(id);
    setError(null);
    try {
      await mutinyApi.deleteRegression(id);
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="page fade-in">
      <header className="page-header">
        <div>
          <p className="page-kicker">Replay</p>
          <h1 className="page-title">Tests</h1>
          <p className="page-sub">
            Replay saved regressions after you fix the agent — same Core path as{" "}
            <span className="font-mono text-dim">mutiny test</span>.
          </p>
        </div>
        <div className="action-bar">
          <Button
            disabled={!!busy || regs.length === 0}
            onClick={() => runBatch("all")}
          >
            {busy === "all" ? "Running…" : "Run All"}
          </Button>
          <Button
            variant="secondary"
            disabled={!!busy || !summary?.failed}
            onClick={() => runBatch("failed")}
          >
            {busy === "failed" ? "Running…" : "Run Failed"}
          </Button>
          <Button
            variant="secondary"
            disabled={!!busy || selected.size === 0}
            onClick={() => runBatch("selected")}
          >
            {busy === "selected" ? "Running…" : "Run Selected"}
          </Button>
        </div>
      </header>

      {error && <p className="alert alert-error mt-6">{error}</p>}

      <div className="meta-strip mt-6">
        <div className="meta-strip-item">
          <div className="label">Regressions</div>
          <div className="value">
            {summary ? String(summary.regression_count) : "—"}
          </div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Pass rate</div>
          <div className="value">
            {summary?.pass_rate != null ? `${summary.pass_rate}%` : "—"}
          </div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Failed</div>
          <div
            className={`value ${summary && summary.failed > 0 ? "text-violation" : ""}`}
          >
            {summary ? String(summary.failed) : "—"}
          </div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Never run</div>
          <div className="value">
            {summary ? String(summary.never_run) : "—"}
          </div>
        </div>
      </div>

      {(liveLog.length > 0 || batchReport) && (
        <section className="panel mt-6 p-4">
          <p className="field-label">Run report</p>
          <pre className="code-block mt-2 max-h-48">
            {liveLog.join("\n")}
          </pre>
          {batchReport && (
            <p className="mt-3 text-sm text-muted">
              Summary:{" "}
              <span className="text-success">{batchReport.passed} Passed</span>
              {" / "}
              <span className="text-violation">{batchReport.failed} Failed</span>
              {" / "}
              {batchReport.skipped} Skipped
            </p>
          )}
        </section>
      )}

      {loading && <Skeleton lines={6} className="mt-6" />}

      {!loading && regs.length === 0 && !error && (
        <EmptyState
          title="No regression tests yet"
          className="mt-8"
          action={
            <Link href="/campaigns" className="btn btn-primary mt-2">
              Go to campaigns
            </Link>
          }
        >
          <p>
            Discover a violation in a campaign, minimize, save a regression —
            then this dashboard becomes your post-fix home.
          </p>
        </EmptyState>
      )}

      {regs.length > 0 && (
        <div className="table-wrap mt-8">
          <table className="data-table min-w-[720px]">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    aria-label="Select all"
                  />
                </th>
                <th>Regression</th>
                <th>Status</th>
                <th>Rule</th>
                <th>Last run</th>
                <th>Duration</th>
                <th>Policy</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {regs.map((r) => {
                const last = r.last_run;
                const rules =
                  r.artifact.expected?.must_not_violate?.join(", ") ||
                  r.artifact.policy_rule_ids?.join(", ") ||
                  "—";
                const policyVer =
                  last?.policy_version ||
                  r.artifact.provenance?.policy_version ||
                  "—";
                return (
                  <tr key={r.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.has(r.id)}
                        onChange={() => toggle(r.id)}
                        aria-label={`Select ${r.artifact.name}`}
                      />
                    </td>
                    <td>
                      <Link href={`/tests/${r.id}`} className="row-link">
                        {r.artifact.name}
                      </Link>
                      <p className="mt-0.5 font-mono text-[10px] text-muted">
                        {r.id.slice(0, 8)}…
                      </p>
                    </td>
                    <td>
                      <StatusChip status={last?.status} />
                    </td>
                    <td className="font-mono text-xs">{rules}</td>
                    <td className="text-xs text-muted">
                      {formatWhen(last?.created_at)}
                    </td>
                    <td className="font-mono text-xs">
                      {last?.duration_ms != null
                        ? `${Math.round(last.duration_ms)}ms`
                        : "—"}
                    </td>
                    <td className="font-mono text-xs">
                      {policyVer === "—" ? "—" : `v${policyVer}`}
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1.5">
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={!!busy}
                          onClick={() => runBatch("one", r.id)}
                        >
                          {busy === r.id ? "…" : "Run"}
                        </Button>
                        <Link
                          href={`/tests/${r.id}`}
                          className="btn btn-secondary btn-sm"
                        >
                          View
                        </Link>
                        <Button
                          size="sm"
                          variant="danger"
                          disabled={!!busy}
                          onClick={() => remove(r.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {summary && summary.recent_runs.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm font-semibold text-text">Recent runs</h2>
          <ul className="mt-3 list-stack">
            {summary.recent_runs.slice(0, 8).map((run) => (
              <li
                key={run.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-md)] border border-border px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-2">
                  <StatusChip status={run.status} />
                  <Link
                    href={`/tests/${run.regression_id}`}
                    className="font-mono text-xs text-primary hover:underline"
                  >
                    {run.regression_id.slice(0, 8)}…
                  </Link>
                  <span className="text-xs text-muted">{run.summary || ""}</span>
                </div>
                <span className="font-mono text-[11px] text-muted">
                  {formatWhen(run.created_at)}
                  {run.duration_ms != null
                    ? ` · ${Math.round(run.duration_ms)}ms`
                    : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
