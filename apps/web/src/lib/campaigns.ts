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
