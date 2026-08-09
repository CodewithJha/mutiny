"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { DEFAULT_PROJECT_PATH, mutinyApi, type Campaign } from "@/lib/api";
import { campaignStatusChip, campaignStatusLabel } from "@/lib/campaigns";
import { Button, EmptyState, Skeleton } from "@/components/ui";

export default function CampaignsPage() {
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [attest, setAttest] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { campaigns: list } = await mutinyApi.listCampaigns({ limit: 100 });
        if (!cancelled) setCampaigns(list);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setCampaigns([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    const running = campaigns.filter(
      (c) => c.status === "running" || c.status === "created"
    ).length;
    const violations = campaigns.filter(
      (c) => c.violation || c.status === "violation"
    ).length;
    const completed = campaigns.filter((c) => c.status === "completed").length;
    return { total: campaigns.length, running, violations, completed };
  }, [campaigns]);

  async function startCampaign() {
    setError(null);
    if (!attest) {
      setError("Check attestation — authorized testing only.");
      return;
    }
    setBusy(true);
    try {
      const camp = await mutinyApi.createCampaign({
        population_size: 8,
        max_generations: 6,
        elite_count: 2,
        stop_on_first_violation: true,
        max_turns: 4,
        rng_seed: 5,
        use_boundary_seeds: true,
        target: "openai_agents",
        project_path: DEFAULT_PROJECT_PATH,
      });
      await mutinyApi.startCampaign(camp.id, true);
      router.push(`/campaign/${camp.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="page fade-in">
      <header className="page-header">
        <div>
          <p className="page-kicker">Operate</p>
          <h1 className="page-title">Campaigns</h1>
          <p className="page-sub">
            Evolutionary runs against project policies. Open a campaign for the
            evolution graph and verified evidence above the fold.
          </p>
        </div>
      </header>

      <section className="campaigns-hero" aria-labelledby="campaigns-start">
        <div className="campaigns-hero-row">
          <div>
            <h2 id="campaigns-start">Start a campaign</h2>
            <p>
              Hunt tool-call policy breaks on the sample harness — or your
              registered project. Attestation required.
            </p>
          </div>
          <Button disabled={busy} onClick={startCampaign}>
            {busy ? "Starting…" : "Start campaign"}
          </Button>
        </div>

        <label className="checkbox-row campaigns-attest">
          <input
            type="checkbox"
            checked={attest}
            onChange={(e) => setAttest(e.target.checked)}
          />
          <span>
            I attest this campaign targets only systems I am authorized to test
            (sample / owned agents).
          </span>
        </label>

        {!loading && campaigns.length > 0 && (
          <div className="stat-pills">
            <div className="stat-pill">
              <span className="k">Total</span>
              <span className="v">{stats.total}</span>
            </div>
            <div className="stat-pill">
              <span className="k">Running</span>
              <span className="v">{stats.running}</span>
            </div>
            <div className="stat-pill">
              <span className="k">Violations</span>
              <span className="v">{stats.violations}</span>
            </div>
            <div className="stat-pill">
              <span className="k">Completed</span>
              <span className="v">{stats.completed}</span>
            </div>
          </div>
        )}
      </section>

      {error && <p className="alert alert-error mt-4 max-w-xl">{error}</p>}

      <div className="mt-8">
        {loading && <Skeleton lines={5} />}

        {!loading && campaigns.length === 0 && (
          <EmptyState
            title="No campaigns yet"
            action={
              <Button className="mt-2" disabled={busy} onClick={startCampaign}>
                {busy ? "Starting…" : "Start first campaign"}
              </Button>
            }
          >
            <p>
              Start a campaign to evolve prompts against policy rules. You&apos;ll
              land on the live evolution graph when scoring begins.
            </p>
          </EmptyState>
        )}

        {campaigns.length > 0 && (
          <div className="table-wrap mt-2">
            <table className="data-table min-w-[720px]">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Status</th>
                  <th>Project</th>
                  <th>Gens</th>
                  <th>Elapsed</th>
                  <th>Violation</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((camp) => {
                  const status = camp.status || "unknown";
                  const metrics = camp.metrics;
                  const elapsed =
                    typeof metrics?.elapsed_ms === "number"
                      ? metrics.elapsed_ms
                      : null;
                  const gens =
                    camp.generation ??
                    (typeof metrics?.generations_completed === "number"
                      ? metrics.generations_completed
                      : null);
                  const projectName =
                    camp.project?.name || camp.project?.path || "—";
                  return (
                    <tr key={camp.id}>
                      <td>
                        <Link
                          href={`/campaign/${camp.id}`}
                          className="row-link font-mono text-xs"
                        >
                          {camp.id.slice(0, 10)}…
                        </Link>
                      </td>
                      <td>
                        <span className={`chip ${campaignStatusChip(status)}`}>
                          {campaignStatusLabel(status)}
                        </span>
                      </td>
                      <td className="text-xs text-muted max-w-[160px] truncate">
                        {projectName}
                      </td>
                      <td className="font-mono text-xs">
                        {gens != null ? gens : "—"}
                      </td>
                      <td className="font-mono text-xs">
                        {elapsed != null ? `${elapsed}ms` : "—"}
                      </td>
                      <td className="text-xs">
                        {camp.violation || status === "violation" ? (
                          <span className="text-violation">Yes</span>
                        ) : status === "completed" ? (
                          <span className="text-muted">No</span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td className="text-xs text-muted whitespace-nowrap">
                        {camp.created_at
                          ? new Date(camp.created_at).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
