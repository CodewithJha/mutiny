"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { mutinyApi, type ProjectDetail } from "@/lib/api";
import { campaignStatusChip, campaignStatusLabel } from "@/lib/campaigns";
import { CodeBlock, EmptyState, Skeleton } from "@/components/ui";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = String(params.id);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await mutinyApi.getProject(projectId);
        if (!cancelled) setProject(p);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (loading) {
    return (
      <div className="page fade-in">
        <Skeleton lines={3} className="max-w-lg" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="page fade-in">
        <p className="alert alert-error">{error || "Project not found"}</p>
        <Link href="/projects" className="btn btn-secondary mt-4">
          Back to projects
        </Link>
      </div>
    );
  }

  const policy =
    project.policies && "policy_set" in project.policies
      ? project.policies
      : null;
  const policyError =
    project.policies && "error" in project.policies
      ? project.policies.error
      : null;
  const lastRun = project.last_run;

  return (
    <div className="page fade-in">
      <header className="page-header">
        <div>
          <p className="breadcrumb">
            <Link href="/projects">Projects</Link>
            {" / "}
            <span className="text-dim">{project.name}</span>
          </p>
          <h1 className="page-title">{project.name}</h1>
          <p className="page-sub font-mono !text-xs">{project.path}</p>
        </div>
        <div className="action-bar">
          <Link
            href={`/policies?project_path=${encodeURIComponent(project.path)}`}
            className="btn btn-secondary"
          >
            Policies
          </Link>
          <Link href="/campaigns" className="btn btn-secondary">
            Observe campaigns
          </Link>
        </div>
      </header>

      <section className="panel mt-6 max-w-xl p-4 space-y-3">
        <h2 className="text-sm font-semibold text-text">
          Run locally, observe here
        </h2>
        <p className="text-sm text-muted">
          Hosted observes lineage for this project. Execute the campaign on your
          machine with the Mutiny CLI —{" "}
          <code>--hosted</code> means local Core + Hosted sync, not remote
          execution.
        </p>
        <CodeBlock compact copyable label="CLI">
          {`mutiny run --hosted
# or: mutiny run --path . --hosted-url http://127.0.0.1:8000`}
        </CodeBlock>
      </section>

      {error && <p className="alert alert-error mt-4 max-w-xl">{error}</p>}

      <div className="meta-strip mt-6">
        <div className="meta-strip-item">
          <div className="label">Adapter</div>
          <div className="value font-mono text-sm">
            {project.current_adapter || project.adapter}
          </div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Last campaign</div>
          <div className="value text-sm">
            {lastRun ? (
              <Link
                href={`/campaign/${lastRun.id}`}
                className="text-primary hover:underline"
              >
                {campaignStatusLabel(lastRun.status)}
              </Link>
            ) : (
              "—"
            )}
          </div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Policies</div>
          <div className="value text-sm">
            {policy
              ? `${policy.policy_set.rules.length} rules · v${policy.version || policy.policy_set.version}`
              : "—"}
          </div>
        </div>
      </div>

      <section className="mt-8">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-sm font-semibold text-text">Policies</h2>
          <Link
            href={`/policies?project_path=${encodeURIComponent(project.path)}`}
            className="text-xs text-primary hover:underline"
          >
            Open editor
          </Link>
        </div>
        {policyError && <p className="alert alert-error">{policyError}</p>}
        {policy && (
          <div className="panel p-4">
            <ul className="space-y-1.5">
              {policy.policy_set.rules.slice(0, 8).map((r) => (
                <li key={r.id} className="font-mono text-xs text-muted">
                  <span className="text-dim">{r.id}</span>
                  <span> — {r.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="mt-8">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-sm font-semibold text-text">Recent campaigns</h2>
          <Link href="/campaigns" className="text-xs text-primary hover:underline">
            All
          </Link>
        </div>
        {(project.recent_campaigns || []).length === 0 ? (
          <EmptyState title="No campaigns yet">
            <p>
              Run <code>mutiny run --hosted</code> locally to sync lineage for
              this project.
            </p>
          </EmptyState>
        ) : (
          <ul className="list-stack">
            {(project.recent_campaigns || []).map((c) => (
              <li key={c.id}>
                <Link href={`/campaign/${c.id}`} className="list-row">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-xs text-dim">
                      {c.id.slice(0, 8)}…
                    </span>
                    <span className={`chip ${campaignStatusChip(c.status)}`}>
                      {campaignStatusLabel(c.status)}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-8">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-sm font-semibold text-text">Recent regressions</h2>
          <Link href="/regressions" className="text-xs text-primary hover:underline">
            All
          </Link>
        </div>
        {(project.recent_regressions || []).length === 0 ? (
          <p className="text-sm text-muted">No regressions for this project.</p>
        ) : (
          <ul className="list-stack">
            {(project.recent_regressions || []).map((r) => (
              <li key={r.id}>
                <Link href={`/tests/${r.id}`} className="list-row">
                  <p className="text-sm text-text">{r.artifact.name}</p>
                  <p className="mt-1 font-mono text-xs text-muted">{r.id.slice(0, 8)}…</p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
