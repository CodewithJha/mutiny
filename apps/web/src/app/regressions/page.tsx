"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { mutinyApi } from "@/lib/api";
import { Button, EmptyState, Skeleton } from "@/components/ui";

type RegRow = {
  id: string;
  campaign_id: string | null;
  candidate_id: string | null;
  artifact: {
    name: string;
    conversation: string[];
    expected: { must_not_violate: string[] };
  };
  created_at: string;
};

type RunResult = {
  status: string;
  violated_rule_ids: string[];
  fixed_agent: boolean;
};

type Story = {
  fail?: RunResult;
  pass?: RunResult;
};

export default function RegressionsPage() {
  const [regs, setRegs] = useState<RegRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [stories, setStories] = useState<Record<string, Story>>({});

  useEffect(() => {
    mutinyApi
      .regressions()
      .then((r) => setRegs(r.regressions as RegRow[]))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function run(id: string, fixed: boolean) {
    setBusyId(id);
    setError(null);
    try {
      const out = await mutinyApi.runTests(id, fixed);
      setStories((prev) => ({
        ...prev,
        [id]: {
          ...prev[id],
          ...(fixed ? { pass: out } : { fail: out }),
        },
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function runStory(id: string) {
    setBusyId(id);
    setError(null);
    try {
      const fail = await mutinyApi.runTests(id, false);
      const pass = await mutinyApi.runTests(id, true);
      setStories((prev) => ({ ...prev, [id]: { fail, pass } }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page fade-in">
      <header className="page-header">
        <div>
          <p className="page-kicker">Evidence → Suite</p>
          <h1 className="page-title">Regressions</h1>
          <p className="page-sub">
            Permanent tests from verified violations. Vulnerable agent must{" "}
            <span className="text-violation font-semibold">FAIL</span>, fixed
            agent must <span className="text-success font-semibold">PASS</span>.
          </p>
        </div>
        <Link href="/tests" className="btn btn-secondary">
          Tests dashboard
        </Link>
      </header>

      {error && <p className="alert alert-error mt-6">{error}</p>}
      {loading && <Skeleton lines={4} className="mt-6" />}

      {!loading && regs.length === 0 && !error && (
        <EmptyState
          title="No regressions saved"
          className="mt-8"
          action={
            <Link href="/campaigns" className="btn btn-primary mt-2">
              Go to campaigns
            </Link>
          }
        >
          <p>
            Find a violation in a campaign, minimize the exploit, then save a
            regression to lock in the FAIL → PASS story.
          </p>
        </EmptyState>
      )}

      {regs.length > 0 && (
        <div className="table-wrap mt-8">
          <table className="data-table min-w-[720px]">
            <thead>
              <tr>
                <th>Regression</th>
                <th>Must not violate</th>
                <th>Source</th>
                <th>Story</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {regs.map((r) => {
                const story = stories[r.id];
                return (
                  <tr key={r.id}>
                    <td>
                      <Link href={`/tests/${r.id}`} className="row-link">
                        {r.artifact.name}
                      </Link>
                      <p className="mt-0.5 font-mono text-[10px] text-muted">
                        {r.id.slice(0, 8)}…
                      </p>
                    </td>
                    <td className="font-mono text-xs">
                      {r.artifact.expected.must_not_violate.join(", ") || "—"}
                    </td>
                    <td className="text-xs text-muted">
                      {r.candidate_id ? (
                        <Link
                          href={`/exploit/${r.candidate_id}`}
                          className="font-mono text-primary hover:underline"
                        >
                          {r.candidate_id.slice(0, 8)}…
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="text-xs">
                      {story?.fail || story?.pass ? (
                        <span>
                          {story.fail && (
                            <span
                              className={
                                story.fail.status === "FAIL"
                                  ? "text-violation font-semibold"
                                  : "text-muted"
                              }
                            >
                              {story.fail.status}
                            </span>
                          )}
                          {story.fail && story.pass && " → "}
                          {story.pass && (
                            <span
                              className={
                                story.pass.status === "PASS"
                                  ? "text-success font-semibold"
                                  : "text-violation font-semibold"
                              }
                            >
                              {story.pass.status}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1.5">
                        <Button
                          size="sm"
                          disabled={busyId === r.id}
                          onClick={() => runStory(r.id)}
                        >
                          {busyId === r.id ? "…" : "FAIL→PASS"}
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          disabled={busyId === r.id}
                          onClick={() => run(r.id, false)}
                        >
                          Vulnerable
                        </Button>
                        <Button
                          variant="success"
                          size="sm"
                          disabled={busyId === r.id}
                          onClick={() => run(r.id, true)}
                        >
                          Fixed
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

      {regs.map((r) => {
        const story = stories[r.id];
        if (!story?.fail && !story?.pass) return null;
        return (
          <div key={`detail-${r.id}`} className="mt-4 panel p-4">
            <p className="field-label">{r.artifact.name} · conversation</p>
            <ol className="msg-list mt-2">
              {r.artifact.conversation.map((line, i) => (
                <li key={i} className="msg-item">
                  <span className="msg-role">turn {i + 1}</span>
                  <p className="msg-body">{line}</p>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
    </div>
  );
}
