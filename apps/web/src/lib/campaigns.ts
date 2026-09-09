/**
 * Optional browser cache of recently viewed campaign IDs.
 * Campaign history source of truth is GET /api/campaigns — do not use this
 * for the campaigns list.
 */

const KEY = "mutiny.recentCampaigns";

/** @deprecated Prefer GET /api/campaigns. Kept as a no-op-friendly cache helper. */
export function rememberCampaign(id: string) {
  if (typeof window === "undefined") return;
  try {
    const prev = listRememberedCampaigns().filter((x) => x !== id);
    const next = [id, ...prev].slice(0, 24);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* ignore quota / private mode */
  }
}

/** @deprecated Prefer GET /api/campaigns. */
export function listRememberedCampaigns(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

type CampaignLike = {
  status?: string;
  config?: Record<string, unknown> | null;
};

function configString(
  campaign: CampaignLike | null | undefined,
  key: string
): string | null {
  const v = campaign?.config?.[key];
  return typeof v === "string" && v.trim() ? v : null;
}

/** True when Hosted ingested a Local CLI run (`execution_mode: local_cli`). */
export function isLocalCliCampaign(
  campaign: CampaignLike | null | undefined
): boolean {
  return configString(campaign, "execution_mode") === "local_cli";
}

/** Trusted in-process demo harness (not customer project code). */
export function isDemoHarnessCampaign(
  campaign: CampaignLike | null | undefined
): boolean {
  return configString(campaign, "target") === "in_process_demo";
}

/**
 * Where the campaign executed.
 * Uses `config.execution_mode` when present; otherwise labels demo vs interim
 * Hosted supervisor paths without claiming production observe-only.
 */
export function campaignExecutionLabel(
  campaign: CampaignLike | null | undefined
): string {
  if (isLocalCliCampaign(campaign)) return "Local CLI";
  if (isDemoHarnessCampaign(campaign)) return "Demo harness";
  const target = configString(campaign, "target");
  if (target) return "Hosted interim";
  return "Unknown";
}

/**
 * Hosted observation role for this campaign row.
 * Limitation: Hosted cannot show local-success + sync-failure — those runs
 * never fully land here (CLI pending file). A `failed` status on an ingested
 * local_cli campaign means the CLI reported campaign failure, not sync failure.
 */
export function campaignObservationLabel(
  campaign: CampaignLike | null | undefined
): string {
  const status = campaign?.status || "";
  const live = status === "running" || status === "created";

  if (isLocalCliCampaign(campaign)) {
    return live ? "Observing" : "Synced";
  }
  if (isDemoHarnessCampaign(campaign)) {
    return live ? "Demo live" : "Demo recorded";
  }
  return live ? "Live (interim)" : "Recorded (interim)";
}

/** Human-readable campaign status labels for the workspace list. */
export function campaignStatusLabel(status: string): string {
  switch (status) {
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "violation":
      return "Violation found";
    case "failed":
      return "Failed";
    case "created":
      return "Created";
    default:
      return status;
  }
}

export function campaignStatusChip(status: string): string {
  switch (status) {
    case "violation":
      return "chip-violation";
    case "running":
      return "chip-blue";
    case "completed":
      return "chip-success";
    case "failed":
      return "chip-violation";
    default:
      return "chip";
  }
}

/** Neutral observation labels for SSE / ingest event types (not “Hosted ran…”). */
export function campaignEventLabel(type: string): string {
  switch (type) {
    case "campaign.started":
      return "Campaign started";
    case "campaign.completed":
      return "Campaign completed";
    case "campaign.error":
      return "Campaign error";
    case "generation.started":
      return "Generation started";
    case "generation.completed":
      return "Generation completed";
    case "candidate.created":
      return "Candidate created";
    case "candidate.scored":
      return "Candidate scored";
    case "violation.detected":
      return "Violation detected";
    case "minimization.started":
      return "Minimization started";
    case "exploit.minimized":
      return "Exploit minimized";
    case "regression.created":
      return "Regression saved";
    case "ready":
      return "Stream ready";
    default:
      return type
        .split(".")
        .map((part) =>
          part ? part.charAt(0).toUpperCase() + part.slice(1) : part
        )
        .join(" ");
  }
}
