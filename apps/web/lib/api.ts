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

const demoOverview: OverviewResponse = {
  workspace_id: "demo-workspace",
  metrics: {
    datasets: 2,
    assets: 20,
    training_jobs_running: 1,
    model_versions_ready: 2,
    inference_calls_month: 12840,
  },
  projects: [
    {
      id: "demo-project-ppe",
      name: "PPE 安全穿戴检测",
      task_type: "object-detection",
      description: "识别人员、安全帽和反光衣。",
      status: "active",
      dataset_version_count: 3,
      active_run_count: 1,
      published_service_count: 1,
      created_at: "2026-08-05T09:30:00Z",
    },
    {
      id: "demo-project-defect",
      name: "工业表面缺陷检测",
      task_type: "object-detection",
      description: "识别划痕、凹坑和脏污。",
      status: "paused",
      dataset_version_count: 2,
      active_run_count: 0,
      published_service_count: 0,
      created_at: "2026-08-01T08:10:00Z",
    },
  ],
  datasets: [
    {
      id: "demo-dataset-ppe",
      project_id: "demo-project-ppe",
      project_name: "PPE 安全穿戴检测",
      name: "工地安全穿戴数据",
      description: "固定监控视角下的安全帽与反光衣样本。",
      asset_count: 12,
      version_count: 3,
      created_at: "2026-08-15T10:20:00Z",
    },
    {
      id: "demo-dataset-defect",
      project_id: "demo-project-defect",
      project_name: "工业表面缺陷检测",
      name: "金属表面缺陷数据",
      description: "产线相机采集的金属表面缺陷样本。",
      asset_count: 8,
      version_count: 2,
      created_at: "2026-08-11T14:40:00Z",
    },
  ],
  active_runs: [
    {
      run_id: "demo-run-ppe-v3",
      project_name: "PPE 安全穿戴检测",
      dataset_version_number: 3,
      status: "running",
      progress: 68,
      engine: "ultralytics",
      model: "YOLO11s",
      executor: "docker",
      created_at: "2026-08-17T01:30:00Z",
      error_message: null,
    },
  ],
  recent_runs: [
    {
      run_id: "demo-run-ppe-v2",
      project_name: "PPE 安全穿戴检测",
      dataset_version_number: 2,
      status: "succeeded",
      progress: 100,
      engine: "ultralytics",
      model: "YOLO11n",
      executor: "docker",
      created_at: "2026-08-16T09:10:00Z",
      error_message: null,
    },
    {
      run_id: "demo-run-defect-v2",
      project_name: "工业表面缺陷检测",
      dataset_version_number: 2,
      status: "succeeded",
      progress: 100,
      engine: "ultralytics",
      model: "YOLO11n",
      executor: "docker",
      created_at: "2026-08-13T06:45:00Z",
      error_message: null,
    },
  ],
};

type WorkspaceSummary = { id: string };

export async function getOverview(): Promise<OverviewResponse> {
  if (process.env.SENSEMU_PREVIEW_MODE === "true") return demoOverview;
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
