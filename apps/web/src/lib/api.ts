export type Project = {
  id: string;
  name: string;
  path: string;
  adapter: string;
  created_at: string;
  updated_at: string;
};

export type ProjectDetail = Project & {
  policies?: PolicyEntry | { error: string };
  recent_campaigns?: Campaign[];
  recent_regressions?: Array<{
    id: string;
    campaign_id: string | null;
    candidate_id: string | null;
    artifact: {
      name: string;
      conversation: string[];
      expected: { must_not_violate: string[] };
    };
    created_at: string;
  }>;
  last_run?: Campaign | null;
  current_adapter?: string;
};

export type Campaign = {
  id: string;
  status: string;
  config: Record<string, unknown>;
  metrics: Record<string, unknown> | null;
  created_at: string;
  completed_at: string | null;
  finished_at?: string | null;
  project_id?: string | null;
  project?: Project | null;
  generation?: number | null;
  violation?: boolean;
};

export type Candidate = {
  id: string;
  campaign_id: string;
  parent_id: string | null;
  generation: number;
  genome: {
    id: string;
    parent_id?: string | null;
    generation: number;
    strategy: string;
    mutations: string[];
    target_rule_ids: string[];
    messages: { role: string; content: string }[];
  };
  fitness: number | null;
  status: string;
  violated: boolean;
  hits: Array<{
    rule_id: string;
    violated: boolean;
    evidence?: {
      message?: string;
      arguments?: Record<string, unknown>;
      tool_name?: string;
      tool_call_id?: string;
    };
    proximity?: number;
  }>;
  trace?: {
    all_tool_calls?: Array<{
      id: string;
      name: string;
      arguments: Record<string, unknown>;
    }>;
    turns?: unknown[];
  } | null;
};

/** Local Hosted default — sample customer project (same as Milestone A). */
export const DEFAULT_PROJECT_PATH = "examples/openai_support_agent";

export type PolicyRule = {
  id: string;
  description: string;
  tool: string;
  kind: string;
  invariant?: string;
  explanation?: string;
  when?: Record<string, unknown>;
  require?: Record<string, unknown>;
  forbid?: Record<string, unknown>;
};

export type PolicySet = {
  version: string;
  target: string;
  rules: PolicyRule[];
};

export type PolicyEntry = {
  id: string;
  project_path?: string;
  path?: string;
  version?: string;
  target?: string;
  policy_set: PolicySet;
};

export type PolicyContent = {
  project_path: string;
  path: string;
  format: string;
  content: string;
  version: string;
  policy_set: PolicySet;
};

export type SseEvent = {
  id?: number;
  campaign_id?: string;
  ts?: string;
  type: string;
  payload?: Record<string, unknown>;
};

/** Prefer Mutiny `{ error: { message } }`, then FastAPI `detail`, then status text. */
function messageFromErrorBody(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const record = body as Record<string, unknown>;
  const err = record.error;
  if (err && typeof err === "object") {
    const msg = (err as Record<string, unknown>).message;
    if (typeof msg === "string" && msg.trim()) return msg;
    const code = (err as Record<string, unknown>).code;
    if (typeof code === "string" && code.trim()) return code;
  }
  const detail = record.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object") {
    const msg = (detail as Record<string, unknown>).message;
    if (typeof msg === "string" && msg.trim()) return msg;
    try {
      return JSON.stringify(detail);
    } catch {
      /* fall through */
    }
  }
  try {
    return JSON.stringify(body);
  } catch {
    return fallback;
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    const why = e instanceof Error ? e.message : String(e);
    throw new Error(
      `Cannot reach API (${path}): ${why}. Is Mutiny API running on :8000?`
    );
  }
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = messageFromErrorBody(body, detail);
    } catch {
      /* non-JSON body — keep statusText */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type Health = {
  status: string;
  api: boolean;
  db: boolean;
  model: string;
  version?: string;
  mutator_mode?: string;
  llm_configured?: boolean;
  db_latency_ms?: number | null;
  running_campaigns?: number;
  target_allowlist?: string[];
  adapter_loading?: string;
};

function withProjectPath(path: string, projectPath?: string): string {
  const pp = projectPath ?? DEFAULT_PROJECT_PATH;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}project_path=${encodeURIComponent(pp)}`;
}

export const mutinyApi = {
  health: () => api<Health>("/api/health"),
  listProjects: () => api<{ projects: Project[] }>("/api/projects"),
  getProject: (id: string) => api<ProjectDetail>(`/api/projects/${id}`),
  createProject: (body: { path: string; name?: string; adapter?: string }) =>
    api<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  policies: (projectPath?: string) =>
    api<{ policies: PolicyEntry[]; project_path: string }>(
      withProjectPath("/api/policies", projectPath)
    ),
  policy: (id: string, projectPath?: string) =>
    api<PolicyEntry>(withProjectPath(`/api/policies/${id}`, projectPath)),
  policyContent: (projectPath?: string) =>
    api<PolicyContent>(withProjectPath("/api/policies/content", projectPath)),
  savePolicyContent: (content: string, projectPath?: string) =>
    api<PolicyContent & { ok: boolean }>(
      withProjectPath("/api/policies/content", projectPath),
      { method: "PUT", body: JSON.stringify({ content }) }
    ),
  listCampaigns: (params?: {
    status?: string;
    project_id?: string;
    project?: string;
    violation?: boolean;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.project_id) qs.set("project_id", params.project_id);
    if (params?.project) qs.set("project", params.project);
    if (params?.violation !== undefined) {
      qs.set("violation", String(params.violation));
    }
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api<{ campaigns: Campaign[] }>(`/api/campaigns${suffix}`);
  },
  createCampaign: (body: Record<string, unknown>) =>
    api<Campaign>("/api/campaigns", { method: "POST", body: JSON.stringify(body) }),
  getCampaign: (id: string) => api<Campaign>(`/api/campaigns/${id}`),
  startCampaign: (id: string, attestation: boolean) =>
    api<Campaign>(`/api/campaigns/${id}/start`, {
      method: "POST",
      body: JSON.stringify({ attestation }),
    }),
  candidates: (campaignId: string) =>
    api<{ candidates: Candidate[] }>(`/api/campaigns/${campaignId}/candidates`),
  candidate: (id: string) => api<Candidate>(`/api/candidates/${id}`),
  minimize: (id: string) =>
    api<{
      still_reproduces: boolean;
      minimized_turn_count: number;
      original_turn_count: number;
      reexec_count: number;
      minimized_genome: Candidate["genome"];
    }>(`/api/candidates/${id}/minimize`, { method: "POST", body: "{}" }),
  saveRegression: (id: string, name: string) =>
    api<{ id: string; artifact: unknown }>(`/api/candidates/${id}/regression`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  regressions: () =>
    api<{ regressions: RegressionRow[] }>("/api/regressions"),
  getRegression: (id: string) =>
    api<RegressionDetail>(`/api/regressions/${id}`),
  deleteRegression: (id: string) =>
    api<{ deleted: boolean; id: string }>(`/api/regressions/${id}`, {
      method: "DELETE",
    }),
  testsSummary: () => api<TestsSummary>("/api/tests/summary"),
  listTestRuns: (params?: { regression_id?: string; status?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.regression_id) qs.set("regression_id", params.regression_id);
    if (params?.status) qs.set("status", params.status);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return api<{ runs: TestRun[] }>(`/api/tests/runs${suffix}`);
  },
  runTests: (regressionId: string, fixedAgent = false) =>
    api<TestRunResult>("/api/tests/run", {
      method: "POST",
      body: JSON.stringify({
        regression_id: regressionId,
        fixed_agent: fixedAgent,
      }),
    }),
  runTestsBatch: (body: {
    regression_ids?: string[];
    run_all?: boolean;
    failed_only?: boolean;
    fixed_agent?: boolean;
  }) =>
    api<TestsBatchResult>("/api/tests/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export type TestRun = {
  id: string;
  regression_id: string;
  status: string;
  duration_ms: number | null;
  policy_version: string | null;
  agent_version: string | null;
  fixed_agent: boolean;
  violated_rule_ids: string[];
  evidence: Array<{ tool?: string; arguments?: Record<string, unknown>; id?: string }>;
  summary: string | null;
  created_at: string;
};

export type RegressionArtifact = {
  name: string;
  target?: string;
  conversation: string[];
  policy_rule_ids?: string[];
  expected: { must_not_violate: string[] };
  provenance?: {
    campaign_id?: string | null;
    candidate_id?: string | null;
    policy_version?: string | null;
    minimized_from_turns?: number;
    minimized_turn_count?: number;
    rule_ids?: string[];
  };
};

export type RegressionRow = {
  id: string;
  campaign_id: string | null;
  candidate_id: string | null;
  path?: string | null;
  artifact: RegressionArtifact;
  created_at: string;
  last_run?: TestRun | null;
};

export type RegressionDetail = RegressionRow & {
  runs?: TestRun[];
};

export type TestRunResult = {
  regression_id: string;
  name?: string;
  status: string;
  violated_rule_ids: string[];
  fixed_agent: boolean;
  duration_ms?: number;
  policy_version?: string | null;
  agent_version?: string | null;
  evidence?: TestRun["evidence"];
  summary?: string;
  rule_ids?: string[];
  run_id?: string;
  created_at?: string;
};

export type TestsBatchResult = {
  results: TestRunResult[];
  passed: number;
  failed: number;
  skipped: number;
};

export type TestsSummary = {
  regression_count: number;
  passed: number;
  failed: number;
  never_run: number;
  pass_rate: number | null;
  recent_runs: TestRun[];
  failed_regressions: RegressionRow[];
};

/** Browser SSE with snapshot resume via after_id query when reconnecting. */
export function subscribeCampaignEvents(
  campaignId: string,
  onEvent: (ev: SseEvent) => void,
  afterId = 0,
  onError?: (message: string) => void
): () => void {
  const es = new EventSource(
    `/api/campaigns/${campaignId}/events?after_id=${afterId}`
  );
  let reportedClose = false;
  es.onmessage = (msg) => {
    reportedClose = false;
    try {
      const data = JSON.parse(msg.data) as SseEvent;
      onEvent(data);
    } catch {
      /* ignore malformed frames; keep stream open */
    }
  };
  es.onerror = () => {
    // Browser auto-reconnects while CONNECTING; only surface a hard close once.
    if (es.readyState === EventSource.CLOSED && !reportedClose) {
      reportedClose = true;
      onError?.(
        "Live event stream closed. Campaign status will keep polling."
      );
    }
  };
  return () => es.close();
}
