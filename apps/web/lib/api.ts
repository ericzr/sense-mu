export type RunSummary = {
  run_id: string;
  project_name: string;
  dataset_version_number: number;
  status: string;
  progress: number;
  engine: string;
  model: string;
  executor: string;
  created_at: string;
  error_message: string | null;
};

export type OverviewResponse = {
  workspace_id: string | null;
  metrics: {
    datasets: number;
    assets: number;
    training_jobs_running: number;
    model_versions_ready: number;
    inference_calls_month: number;
  };
  projects: Array<{
    id: string;
    name: string;
    task_type: string;
    description: string | null;
    status: "active" | "paused";
    dataset_version_count: number;
    active_run_count: number;
    published_service_count: number;
    created_at: string;
  }>;
  datasets: Array<{
    id: string;
    project_id: string;
    project_name: string;
    name: string;
    description: string | null;
    asset_count: number;
    version_count: number;
    created_at: string;
  }>;
  active_runs: RunSummary[];
  recent_runs: RunSummary[];
};

const emptyOverview: OverviewResponse = {
  workspace_id: null,
  metrics: {
    datasets: 0,
    assets: 0,
    training_jobs_running: 0,
    model_versions_ready: 0,
    inference_calls_month: 0,
  },
  projects: [],
  datasets: [],
  active_runs: [],
  recent_runs: [],
};

type WorkspaceSummary = { id: string };

export async function getOverview(): Promise<OverviewResponse> {
  const configured = process.env.SENSEMU_API_URL;
  const baseUrl = (configured || "http://127.0.0.1:8000").replace(/\/$/, "");

  try {
    const workspacesResponse = await fetch(`${baseUrl}/api/v1/workspaces`, {
      headers: { accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(1_500),
    });
    if (!workspacesResponse.ok) return emptyOverview;
    const workspaces = (await workspacesResponse.json()) as WorkspaceSummary[];
    const workspaceId = workspaces[0]?.id;
    if (!workspaceId) return emptyOverview;

    const response = await fetch(`${baseUrl}/api/v1/overview`, {
      headers: {
        accept: "application/json",
        "X-Workspace-ID": workspaceId,
      },
      cache: "no-store",
      signal: AbortSignal.timeout(1_500),
    });
    if (!response.ok) return emptyOverview;
    return (await response.json()) as OverviewResponse;
  } catch {
    return emptyOverview;
  }
}
