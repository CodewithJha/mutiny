"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  DEFAULT_PROJECT_PATH,
  mutinyApi,
  type PolicyContent,
  type PolicyEntry,
  type PolicyRule,
} from "@/lib/api";
import { Button, Chip, Skeleton } from "@/components/ui";

function projectPathFromQuery(): string {
  if (typeof window === "undefined") return DEFAULT_PROJECT_PATH;
  const raw = new URLSearchParams(window.location.search).get("project_path");
  return raw?.trim() || DEFAULT_PROJECT_PATH;
}

function formatConstraint(
  label: string,
  value: Record<string, unknown> | undefined
): string | null {
  if (!value || Object.keys(value).length === 0) return null;
  const parts = Object.entries(value).map(([k, v]) => {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const op = Object.entries(v as Record<string, unknown>)
        .map(([ok, ov]) => `${ok} ${JSON.stringify(ov)}`)
        .join(", ");
      return `${k} ${op}`;
    }
    return `${k} = ${JSON.stringify(v)}`;
  });
  return `${label}: ${parts.join(" · ")}`;
}

export default function PoliciesPage() {
  const [projectPath, setProjectPath] = useState(DEFAULT_PROJECT_PATH);
  const [entry, setEntry] = useState<PolicyEntry | null>(null);
  const [content, setContent] = useState<PolicyContent | null>(null);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    setStatus(null);
    try {
      const [list, raw] = await Promise.all([
        mutinyApi.policies(path),
        mutinyApi.policyContent(path),
      ]);
      setEntry(list.policies[0] ?? null);
      setContent(raw);
      setDraft(raw.content);
      setEditing(false);
    } catch (e) {
      setEntry(null);
      setContent(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const path = projectPathFromQuery();
    setProjectPath(path);
    void load(path);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSave() {
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const saved = await mutinyApi.savePolicyContent(draft, projectPath);
      setContent(saved);
      setDraft(saved.content);
      setEntry({
        id: projectPath.split("/").filter(Boolean).pop() || "project",
        project_path: saved.project_path,
        path: saved.path,
        version: saved.version,
        target: saved.policy_set.target,
        policy_set: saved.policy_set,
      });
      setEditing(false);
      setStatus(`Saved v${saved.version} → ${saved.path}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const rules: PolicyRule[] = entry?.policy_set.rules ?? [];

  return (
    <div className="page page-narrow fade-in">
      <header className="page-header">
        <div>
          <p className="page-kicker">Project → Policies → Campaign</p>
          <h1 className="page-title">Policies</h1>
          <p className="page-sub">
            Explicit tool invariants from the project{" "}
            <span className="font-mono text-dim">policy.yaml</span>. Same file
            for CLI and Hosted.
          </p>
        </div>
        <Link href="/campaigns" className="btn btn-primary">
          Run Campaign
        </Link>
      </header>

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="flex min-w-[16rem] flex-1 flex-col">
          <span className="field-label">project_path</span>
          <input
            className="input font-mono"
            value={projectPath}
            onChange={(e) => setProjectPath(e.target.value)}
            spellCheck={false}
          />
        </label>
        <Button
          variant="secondary"
          disabled={loading}
          onClick={() => void load(projectPath)}
        >
          Reload
        </Button>
        {!editing ? (
          <Button
            variant="secondary"
            disabled={loading || !content}
            onClick={() => setEditing(true)}
          >
            Edit
          </Button>
        ) : (
          <>
            <Button disabled={saving} onClick={() => void onSave()}>
              {saving ? "Saving…" : "Save"}
            </Button>
            <Button
              variant="ghost"
              disabled={saving}
              onClick={() => {
                setDraft(content?.content ?? "");
                setEditing(false);
                setError(null);
              }}
            >
              Cancel
            </Button>
          </>
        )}
      </div>

      {error && <p className="alert alert-error mt-4">{error}</p>}
      {status && <p className="alert alert-ok mt-4">{status}</p>}
      {loading && <Skeleton lines={6} className="mt-6" />}

      {!loading && !error && !entry && (
        <p className="alert alert-error mt-6">
          No policy set found for{" "}
          <span className="font-mono">{projectPath}</span>. Check the path or
          run <span className="font-mono">mutiny init</span>.
        </p>
      )}

      {!loading && entry && (
        <section className="mt-8">
          <div className="mb-4">
            <p className="field-label">Policy set</p>
            <h2 className="font-mono text-lg font-semibold text-text">
              {entry.id}
            </h2>
            <p className="mt-1 text-sm text-muted">
              Target{" "}
              <span className="font-mono text-dim">
                {entry.policy_set.target}
              </span>
              {" · "}v{entry.policy_set.version}
              {entry.path && (
                <>
                  {" · "}
                  <span className="font-mono text-xs">{entry.path}</span>
                </>
              )}
            </p>
          </div>

          {editing ? (
            <div className="ide-well">
              <div className="ide-well-bar">
                <span>policy.yaml</span>
                <span>YAML · editable</span>
              </div>
              <textarea
                className="textarea font-mono text-xs min-h-[28rem] border-0 rounded-none"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                spellCheck={false}
                aria-label="Policy YAML editor"
              />
            </div>
          ) : (
            <ul className="list-stack">
              {rules.map((rule) => {
                const when = formatConstraint("When", rule.when);
                const require = formatConstraint("Require", rule.require);
                const forbid = formatConstraint("Forbid", rule.forbid);
                return (
                  <li key={rule.id} className="list-row">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-semibold text-text">
                        {rule.tool}
                      </span>
                      <Chip tone="blue">
                        {rule.invariant || rule.kind}
                      </Chip>
                    </div>
                    <h3 className="mt-2 text-base font-semibold text-text">
                      {rule.description}
                    </h3>
                    <p className="mt-1 font-mono text-xs text-muted">
                      {rule.id}
                    </p>
                    {rule.explanation && (
                      <p className="mt-2 text-sm text-muted">{rule.explanation}</p>
                    )}
                    <ul className="mt-3 space-y-1 text-sm text-dim">
                      {when && <li className="font-mono text-xs">{when}</li>}
                      {require && (
                        <li className="font-mono text-xs">{require}</li>
                      )}
                      {forbid && (
                        <li className="font-mono text-xs">{forbid}</li>
                      )}
                      {!when && !require && !forbid && (
                        <li className="text-muted text-xs">No extra conditions</li>
                      )}
                    </ul>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
