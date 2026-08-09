"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DEFAULT_PROJECT_PATH, mutinyApi, type Project } from "@/lib/api";
import { Button, Chip, EmptyState, Skeleton } from "@/components/ui";

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [path, setPath] = useState(DEFAULT_PROJECT_PATH);
  const [name, setName] = useState("");

  async function refresh() {
    const { projects: list } = await mutinyApi.listProjects();
    setProjects(list);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { projects: list } = await mutinyApi.listProjects();
        if (!cancelled) setProjects(list);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const project = await mutinyApi.createProject({
        path: path.trim(),
        ...(name.trim() ? { name: name.trim() } : {}),
        adapter: "openai_agents",
      });
      await refresh();
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="page fade-in">
      <header className="page-header">
        <div>
          <p className="page-kicker">Workspace</p>
          <h1 className="page-title">Projects</h1>
          <p className="page-sub">
            Local project roots with{" "}
            <span className="font-mono text-dim">.mutiny/adapter.py</span> and{" "}
            <span className="font-mono text-dim">policy.yaml</span>. Campaigns
            belong to projects.
          </p>
        </div>
        <Link href="/campaigns" className="btn btn-secondary">
          Campaigns
        </Link>
      </header>

      <form onSubmit={onCreate} className="panel mt-6 max-w-xl p-4 space-y-4">
        <div>
          <label className="field-label" htmlFor="project-path">
            Project path
          </label>
          <input
            id="project-path"
            className="input font-mono"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder={DEFAULT_PROJECT_PATH}
            required
          />
        </div>
        <div>
          <label className="field-label" htmlFor="project-name">
            Name (optional)
          </label>
          <input
            id="project-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Defaults to directory name"
          />
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? "Registering…" : "Register project"}
        </Button>
      </form>

      {error && <p className="alert alert-error mt-4 max-w-xl">{error}</p>}

      <section className="mt-8">
        {loading && <Skeleton lines={4} className="max-w-xl" />}
        {!loading && projects.length === 0 && (
          <EmptyState title="No projects yet">
            <p>
              Register the sample path or your own project root to organize
              campaigns, policies, and regressions.
            </p>
          </EmptyState>
        )}
        {projects.length > 0 && (
          <div className="table-wrap">
            <table className="data-table min-w-[560px]">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Path</th>
                  <th>Adapter</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link href={`/projects/${p.id}`} className="row-link">
                        {p.name}
                      </Link>
                    </td>
                    <td className="font-mono text-xs text-muted max-w-[280px] truncate">
                      {p.path}
                    </td>
                    <td>
                      <Chip tone="blue">{p.adapter}</Chip>
                    </td>
                    <td className="text-xs text-muted whitespace-nowrap">
                      {new Date(p.updated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
