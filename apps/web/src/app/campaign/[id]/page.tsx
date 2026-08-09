"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ReactFlowProvider } from "@xyflow/react";
import {
  mutinyApi,
  subscribeCampaignEvents,
  type Campaign,
  type Candidate,
  type SseEvent,
} from "@/lib/api";
import { EvolutionGraph } from "@/components/EvolutionGraph";
import { CandidateInspector } from "@/components/CandidateInspector";
import {
  Chip,
  Collapsible,
  Skeleton,
  Timeline,
  type TimelineEntry,
  type TimelineTone,
} from "@/components/ui";
import { campaignStatusLabel } from "@/lib/campaigns";

type MinimizeResult = {
  still_reproduces: boolean;
  minimized_turn_count: number;
  original_turn_count: number;
  reexec_count: number;
  minimized_genome: Candidate["genome"];
};

function eventTone(type: string): TimelineTone {
  if (type.includes("violation")) return "violation";
  if (type.includes("completed") || type.includes("started")) return "ok";
  if (type.includes("scored") || type.includes("generation")) return "live";
  return "default";
}

export default function CampaignPage() {
  const params = useParams();
  const campaignId = String(params.id);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<Candidate | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [minimizeBusy, setMinimizeBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [minimizeResult, setMinimizeResult] = useState<MinimizeResult | null>(
    null
  );
  const [savedId, setSavedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const lastEventId = useRef(0);
  const autoSelected = useRef(false);

  const refreshCandidates = useCallback(async () => {
    const { candidates: list } = await mutinyApi.candidates(campaignId);
    setCandidates(list);
    return list;
  }, [campaignId]);

  const refreshCampaign = useCallback(async () => {
    const c = await mutinyApi.getCampaign(campaignId);
    setCampaign(c);
    return c;
  }, [campaignId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refreshCampaign();
        await refreshCandidates();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshCampaign, refreshCandidates]);

  useEffect(() => {
    const unsub = subscribeCampaignEvents(
      campaignId,
      (ev: SseEvent) => {
        if (typeof ev.id === "number" && ev.id > lastEventId.current) {
          lastEventId.current = ev.id;
        }
        if (ev.type === "ready") return;

        setEvents((prev) => [ev, ...prev].slice(0, 80));

        if (
          ev.type === "candidate.scored" ||
          ev.type === "violation.detected" ||
          ev.type === "generation.completed" ||
          ev.type === "campaign.completed" ||
          ev.type === "campaign.started"
        ) {
          void refreshCandidates().catch((e) =>
            setError(e instanceof Error ? e.message : String(e))
          );
          void refreshCampaign().catch((e) =>
            setError(e instanceof Error ? e.message : String(e))
          );
        }
      },
      lastEventId.current,
      (streamMsg) => setError(streamMsg)
    );

    const poll = setInterval(() => {
      void refreshCampaign().catch((e) =>
        setError(e instanceof Error ? e.message : String(e))
      );
      void refreshCandidates().catch((e) =>
        setError(e instanceof Error ? e.message : String(e))
      );
    }, 2000);

    return () => {
      unsub();
      clearInterval(poll);
    };
  }, [campaignId, refreshCandidates, refreshCampaign]);

  useEffect(() => {
    const violator = candidates.find((c) => c.violated);
    if (!violator || autoSelected.current) return;
    autoSelected.current = true;
    setSelectedId(violator.id);
  }, [candidates]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedDetail(null);
      setMinimizeResult(null);
      setSavedId(null);
      return;
    }
    const fromList = candidates.find((c) => c.id === selectedId);
    if (fromList) setSelectedDetail(fromList);
    let cancelled = false;
    setDetailLoading(true);
    mutinyApi
      .candidate(selectedId)
      .then((full) => {
        if (!cancelled) setSelectedDetail(full);
      })
      .catch((e) => {
        if (!cancelled) {
          // Keep list snapshot in the inspector, but surface the detail failure.
          setError(
            e instanceof Error
              ? `Candidate detail: ${e.message}`
              : `Candidate detail: ${String(e)}`
          );
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, candidates]);

  const bestFitness = useMemo(() => {
    const vals = candidates
      .map((c) => c.fitness)
      .filter((f): f is number => f != null);
    return vals.length ? Math.max(...vals) : null;
  }, [candidates]);

  const maxGen = useMemo(
    () =>
      candidates.length ? Math.max(...candidates.map((c) => c.generation)) : 0,
    [candidates]
  );

  const metrics = campaign?.metrics;
  const elapsed =
    typeof metrics?.elapsed_ms === "number" ? metrics.elapsed_ms : null;
  const phase = typeof metrics?.phase === "string" ? metrics.phase : null;
  const policyVersion =
    typeof metrics?.policy_version === "string" ||
    typeof metrics?.policy_version === "number"
      ? String(metrics.policy_version)
      : typeof campaign?.config?.policy_version === "string" ||
          typeof campaign?.config?.policy_version === "number"
        ? String(campaign.config.policy_version)
        : null;
  const projectLabel =
    campaign?.project?.name ||
    campaign?.project?.path ||
    (typeof campaign?.config?.project_path === "string"
      ? campaign.config.project_path
      : null);
  const violated =
    candidates.some((c) => c.violated) || campaign?.status === "violation";
  const searching =
    campaign?.status === "running" || campaign?.status === "created";
  const status = campaign?.status || "…";

  const timelineEntries: TimelineEntry[] = useMemo(
    () =>
      events.map((ev, i) => {
        const bits: string[] = [];
        if (ev.payload?.candidate_id != null) {
          bits.push(String(ev.payload.candidate_id).slice(0, 8));
        }
        if (ev.payload?.fitness != null) {
          bits.push(`fit ${String(ev.payload.fitness)}`);
        }
        return {
          id: `${ev.id ?? ev.type}-${i}`,
          type: ev.type,
          meta: bits.join(" · ") || undefined,
          ts:
            typeof ev.ts === "string"
              ? new Date(ev.ts).toLocaleTimeString()
              : undefined,
          tone: eventTone(ev.type),
        };
      }),
    [events]
  );

  async function onMinimize() {
    if (!selectedId) return;
    setMinimizeBusy(true);
    setError(null);
    try {
      const result = await mutinyApi.minimize(selectedId);
      setMinimizeResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMinimizeBusy(false);
    }
  }

  async function onSave() {
    if (!selectedId) return;
    setSaveBusy(true);
    setError(null);
    try {
      const saved = await mutinyApi.saveRegression(
        selectedId,
        "refund_limit_regression"
      );
      setSavedId(saved.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaveBusy(false);
    }
  }

  const statusTone =
    violated || status === "violation"
      ? "violation"
      : status === "running"
        ? "blue"
        : status === "completed"
          ? "success"
          : "purple";

  if (loading && !campaign) {
    return (
      <div className="page page-wide fade-in">
        <Skeleton lines={2} className="max-w-md" />
        <div className="meta-strip mt-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="meta-strip-item">
              <div className="skeleton skeleton-line" />
              <div className="skeleton skeleton-line mt-2" style={{ width: "40%" }} />
            </div>
          ))}
        </div>
        <div className="campaign-layout">
          <div className="panel campaign-graph-panel">
            <div className="skeleton m-4" style={{ flex: 1, minHeight: 400 }} />
          </div>
          <div className="panel campaign-inspector-panel">
            <Skeleton lines={8} className="p-4" />
          </div>
        </div>
      </div>
    );
  }

  if (!loading && !campaign) {
    return (
      <div className="page page-wide fade-in">
        <p className="breadcrumb">
          <Link href="/campaigns">Campaigns</Link>
          {" / "}
          <span className="font-mono text-dim">{campaignId.slice(0, 8)}</span>
        </p>
        <p className="alert alert-error mt-4">
          {error || "Campaign not found or API unavailable."}
        </p>
        <Link href="/campaigns" className="btn btn-secondary mt-4">
          Back to campaigns
        </Link>
      </div>
    );
  }

  const storyStep = violated
    ? minimizeResult || savedId
      ? "regression"
      : "evidence"
    : searching
      ? "search"
      : "done";

  return (
    <div className="page page-wide fade-in campaign-page">
      <header className="page-header campaign-header">
        <div className="min-w-0">
          <p className="breadcrumb">
            <Link href="/campaigns">Campaigns</Link>
            {" / "}
            {campaign?.project?.id ? (
              <Link href={`/projects/${campaign.project.id}`}>
                {projectLabel || "Project"}
              </Link>
            ) : (
              <span className="text-dim">{projectLabel || "Campaign"}</span>
            )}
            {" / "}
            <span className="font-mono text-dim">{campaignId.slice(0, 8)}</span>
          </p>
          <h1 className="page-title">
            {searching && !violated
              ? "Searching for a break"
              : violated
                ? "Break found"
                : "Campaign"}
          </h1>
          <div className="campaign-status-row">
            <Chip tone={statusTone}>
              {searching && !violated ? (
                <>
                  <span className="pulse-dot" /> live
                </>
              ) : (
                campaignStatusLabel(status)
              )}
            </Chip>
            {phase && <Chip>{phase}</Chip>}
            {violated && <Chip tone="violation">Verified violation</Chip>}
            {policyVersion && (
              <span className="meta-item">
                Policy <span className="meta-value">v{policyVersion}</span>
              </span>
            )}
            {projectLabel && (
              <span className="meta-item truncate max-w-[14rem]" title={projectLabel}>
                <span className="meta-value">{projectLabel}</span>
              </span>
            )}
          </div>
        </div>
        <div className="action-bar">
          <Link href="/campaigns" className="btn btn-ghost btn-sm">
            All campaigns
          </Link>
        </div>
      </header>

      <ol className="campaign-story" aria-label="Investigation story">
        <li className="is-done">
          <span className="campaign-story-label">Policy</span>
          <span className="campaign-story-detail">
            {policyVersion ? `v${policyVersion}` : "loaded"}
          </span>
        </li>
        <li className={storyStep === "search" ? "is-active" : "is-done"}>
          <span className="campaign-story-label">Progress</span>
          <span className="campaign-story-detail">
            gen {maxGen}
            {elapsed != null ? ` · ${elapsed}ms` : ""}
          </span>
        </li>
        <li
          className={
            storyStep === "search"
              ? "is-active"
              : storyStep === "evidence" || storyStep === "regression" || storyStep === "done"
                ? "is-done"
                : ""
          }
        >
          <span className="campaign-story-label">Evolution</span>
          <span className="campaign-story-detail">
            {candidates.length} candidates
          </span>
        </li>
        <li
          className={
            violated
              ? storyStep === "evidence"
                ? "is-active is-violation"
                : "is-done is-violation"
              : ""
          }
        >
          <span className="campaign-story-label">Violation</span>
          <span className="campaign-story-detail">
            {violated ? "verified" : "pending"}
          </span>
        </li>
        <li
          className={
            violated
              ? storyStep === "evidence"
                ? "is-active"
                : "is-done"
              : ""
          }
        >
          <span className="campaign-story-label">Evidence</span>
          <span className="campaign-story-detail">tool JSON</span>
        </li>
        <li
          className={
            storyStep === "regression"
              ? "is-active is-pass"
              : savedId
                ? "is-done is-pass"
                : ""
          }
        >
          <span className="campaign-story-label">Regression</span>
          <span className="campaign-story-detail">
            {savedId ? "saved" : minimizeResult ? "minimized" : "—"}
          </span>
        </li>
      </ol>

      <div className="meta-strip meta-strip-compact">
        <div className="meta-strip-item">
          <div className="label">Generation</div>
          <div className="value">{maxGen}</div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Population</div>
          <div className="value">{candidates.length}</div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Best fitness</div>
          <div className="value">
            {bestFitness == null ? "—" : bestFitness.toFixed(3)}
          </div>
        </div>
        <div className="meta-strip-item">
          <div className="label">Elapsed</div>
          <div className="value">{elapsed == null ? "—" : `${elapsed}ms`}</div>
        </div>
      </div>

      {error && <p className="alert alert-error mt-4">{error}</p>}

      {searching && !violated && (
        <p className="alert alert-info mt-4">
          Scoring real tool calls against project policies…
        </p>
      )}

      <div className="campaign-layout">
        <div className="panel campaign-graph-panel">
          <div className="panel-header">
            <h2 className="panel-title">Evolution</h2>
            <span className="panel-meta font-mono">
              {candidates.length} · select a node
            </span>
          </div>
          <div className="min-h-0 flex-1">
            <ReactFlowProvider>
              <EvolutionGraph
                candidates={candidates}
                selectedId={selectedId}
                onSelect={(id) => {
                  setMinimizeResult(null);
                  setSavedId(null);
                  setSelectedId(id);
                }}
              />
            </ReactFlowProvider>
          </div>
        </div>

        <div className="panel campaign-inspector-panel">
          <CandidateInspector
            candidate={selectedDetail}
            loading={detailLoading && !selectedDetail}
            onMinimize={onMinimize}
            onSave={onSave}
            minimizeBusy={minimizeBusy}
            saveBusy={saveBusy}
            minimizeResult={minimizeResult}
            savedId={savedId}
          />
        </div>
      </div>

      <div className="campaign-history mt-4">
        <Collapsible
          title="History"
          defaultOpen={false}
          badge={
            <span className="font-mono text-[10px] text-muted normal-case tracking-normal">
              {events.length} events
            </span>
          }
        >
          <div className="p-3">
            <Timeline entries={timelineEntries} empty="Listening for SSE…" />
          </div>
        </Collapsible>
      </div>
    </div>
  );
}
