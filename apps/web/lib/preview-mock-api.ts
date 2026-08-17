import type {
  AnnotationTask,
  Asset,
  BatchInferenceRun,
  CapabilitySpec,
  CurrentIdentity,
  Dataset,
  DatasetVersion,
  DatasetVersionQualityReport,
  Deployment,
  Evaluation,
  EvaluationPolicy,
  MarketplaceBilling,
  MarketplaceSubscription,
  MarketplaceUsageRecord,
  ModelVersion,
  Project,
  ProviderDashboard,
  RunEvent,
  TrainingClassMetrics,
  TrainingEngine,
  TrainingReport,
  TrainingRun,
  VideoExtractionJob,
  VisionEvent,
  WorkflowSpec,
  Workspace,
} from "./catalog-api";

const previewNow = "2026-08-17T02:30:00Z";
const previewWorkspaceId = "demo-workspace";

export function isHostedPreview(): boolean {
  if (process.env.NEXT_PUBLIC_SENSEMU_PREVIEW_MODE === "true") return true;
  if (typeof window === "undefined") return false;
  return window.location.hostname.endsWith(".chatgpt.site");
}

const previewWorkspace: Workspace = {
  id: previewWorkspaceId,
  slug: "sensemu-demo",
  name: "SenseMu 演示空间",
  role: "owner",
  created_at: "2026-08-01T08:00:00Z",
};

const previewIdentity: CurrentIdentity = {
  id: "demo-user",
  email: null,
  email_verified: false,
  display_name: "演示访客",
  auth_mode: "development",
  memberships: [
    {
      workspace_id: previewWorkspace.id,
      workspace_slug: previewWorkspace.slug,
      workspace_name: previewWorkspace.name,
      role: "owner",
      joined_at: previewWorkspace.created_at,
    },
  ],
};

export const previewProjects: Project[] = [
  {
    id: "demo-project-ppe",
    workspace_id: previewWorkspaceId,
    workspace_slug: previewWorkspace.slug,
    slug: "ppe-safety",
    name: "PPE 安全穿戴检测",
    task_type: "object-detection",
    description: "识别人员、安全帽与反光衣，并定位未规范穿戴区域。",
    status: "active",
    created_at: "2026-08-05T09:30:00Z",
  },
  {
    id: "demo-project-defect",
    workspace_id: previewWorkspaceId,
    workspace_slug: previewWorkspace.slug,
    slug: "surface-defect",
    name: "工业表面缺陷检测",
    task_type: "object-detection",
    description: "识别金属表面的划痕、凹坑和脏污。",
    status: "paused",
    created_at: "2026-08-01T08:10:00Z",
  },
];

export const previewDatasets: Dataset[] = [
  {
    id: "demo-dataset-ppe",
    project_id: "demo-project-ppe",
    name: "工地安全穿戴数据",
    description: "固定监控视角下的安全帽与反光衣样本。",
    class_map: { "0": "人员", "1": "安全帽", "2": "反光衣" },
    created_at: "2026-08-06T03:20:00Z",
    asset_count: 1248,
    version_count: 3,
  },
  {
    id: "demo-dataset-defect",
    project_id: "demo-project-defect",
    name: "金属表面缺陷数据",
    description: "产线相机采集的金属表面缺陷样本。",
    class_map: { "0": "划痕", "1": "凹坑", "2": "脏污" },
    created_at: "2026-08-02T06:30:00Z",
    asset_count: 594,
    version_count: 2,
  },
];

const ppeAssets: Asset[] = Array.from({ length: 12 }, (_, index) => ({
  id: `demo-asset-ppe-${index + 1}`,
  uri: `s3://sensemu-demo/ppe/site-${String(index + 1).padStart(3, "0")}.jpg`,
  media_type: "image/jpeg",
  checksum_sha256: `${String(index + 1).padStart(2, "0")}${"a".repeat(62)}`,
  byte_size: 428_000 + index * 8_200,
  width: 1920,
  height: 1080,
  split: index < 8 ? "train" : index < 10 ? "valid" : "test",
  annotation_uri: index < 10 ? `s3://sensemu-demo/ppe/labels/${index + 1}.txt` : null,
  reused: false,
  created_at: `2026-08-${String(6 + Math.min(index, 8)).padStart(2, "0")}T08:00:00Z`,
}));

const defectAssets: Asset[] = Array.from({ length: 8 }, (_, index) => ({
  id: `demo-asset-defect-${index + 1}`,
  uri: `s3://sensemu-demo/defect/line-a-${String(index + 1).padStart(3, "0")}.jpg`,
  media_type: "image/jpeg",
  checksum_sha256: `${String(index + 21).padStart(2, "0")}${"b".repeat(62)}`,
  byte_size: 312_000 + index * 5_800,
  width: 1600,
  height: 1200,
  split: index < 6 ? "train" : "valid",
  annotation_uri: `s3://sensemu-demo/defect/labels/${index + 1}.txt`,
  reused: false,
  created_at: "2026-08-03T09:00:00Z",
}));

const previewVersions: Record<string, DatasetVersion[]> = {
  "demo-dataset-ppe": [
    {
      id: "demo-version-ppe-v3",
      version_number: 3,
      status: "frozen",
      manifest_uri: "s3://sensemu-demo/ppe/versions/v3/manifest.json",
      asset_count: 1248,
      class_map: { "0": "人员", "1": "安全帽", "2": "反光衣" },
      frozen_at: "2026-08-16T08:30:00Z",
      created_at: "2026-08-16T08:30:00Z",
    },
    {
      id: "demo-version-ppe-v2",
      version_number: 2,
      status: "frozen",
      manifest_uri: "s3://sensemu-demo/ppe/versions/v2/manifest.json",
      asset_count: 980,
      class_map: { "0": "人员", "1": "安全帽", "2": "反光衣" },
      frozen_at: "2026-08-12T07:20:00Z",
      created_at: "2026-08-12T07:20:00Z",
    },
  ],
  "demo-dataset-defect": [
    {
      id: "demo-version-defect-v2",
      version_number: 2,
      status: "frozen",
      manifest_uri: "s3://sensemu-demo/defect/versions/v2/manifest.json",
      asset_count: 594,
      class_map: { "0": "划痕", "1": "凹坑", "2": "脏污" },
      frozen_at: "2026-08-13T05:30:00Z",
      created_at: "2026-08-13T05:30:00Z",
    },
  ],
};

const annotationTasks: Record<string, AnnotationTask[]> = {
  "demo-dataset-ppe": [
    {
      id: "demo-task-ppe-review",
      dataset_id: "demo-dataset-ppe",
      name: "安全穿戴样本复核",
      method: "smart",
      asset_scope: "all",
      status: "review",
      assigned_to_user_id: "demo-user",
      source_video_extraction_job_id: null,
      class_map: { "0": "人员", "1": "安全帽", "2": "反光衣" },
      asset_count: 120,
      completed_count: 96,
      created_at: "2026-08-15T03:10:00Z",
      updated_at: previewNow,
    },
    {
      id: "demo-task-ppe-done",
      dataset_id: "demo-dataset-ppe",
      name: "首批人工标注",
      method: "manual",
      asset_scope: "all",
      status: "done",
      assigned_to_user_id: "demo-user",
      source_video_extraction_job_id: null,
      class_map: { "0": "人员", "1": "安全帽", "2": "反光衣" },
      asset_count: 860,
      completed_count: 860,
      created_at: "2026-08-07T04:00:00Z",
      updated_at: "2026-08-12T06:20:00Z",
    },
  ],
  "demo-dataset-defect": [],
};

const trainingEngines: TrainingEngine[] = [
  {
    key: "ultralytics",
    label: "Ultralytics YOLO",
    task_types: ["object-detection"],
    models: ["yolo11n.pt", "yolo11s.pt", "yolo11m.pt"],
    defaults: {
      model: "yolo11s.pt",
      task: "detect",
      epochs: 80,
      image_size: 640,
      batch_size: 16,
      seed: 42,
    },
    executor: "docker",
  },
];

export const previewRuns: TrainingRun[] = [
  {
    id: "demo-run-ppe-v3",
    project_id: "demo-project-ppe",
    dataset_version_id: "demo-version-ppe-v3",
    run_type: "training",
    status: "running",
    engine: "ultralytics",
    executor: "docker",
    recipe: { model: "yolo11s.pt", task: "detect", epochs: 80, image_size: 640, batch_size: 16 },
    progress: 68,
    artifact_prefix: "s3://sensemu-demo/runs/ppe-v3",
    spec_uri: "s3://sensemu-demo/runs/ppe-v3/spec.json",
    error_code: null,
    error_message: null,
    started_at: "2026-08-17T01:30:00Z",
    finished_at: null,
    created_at: "2026-08-17T01:28:00Z",
    updated_at: previewNow,
    reused: false,
  },
  {
    id: "demo-run-ppe-v2",
    project_id: "demo-project-ppe",
    dataset_version_id: "demo-version-ppe-v2",
    run_type: "training",
    status: "succeeded",
    engine: "ultralytics",
    executor: "docker",
    recipe: { model: "yolo11n.pt", task: "detect", epochs: 60, image_size: 640, batch_size: 16 },
    progress: 100,
    artifact_prefix: "s3://sensemu-demo/runs/ppe-v2",
    spec_uri: "s3://sensemu-demo/runs/ppe-v2/spec.json",
    error_code: null,
    error_message: null,
    started_at: "2026-08-16T07:00:00Z",
    finished_at: "2026-08-16T09:10:00Z",
    created_at: "2026-08-16T06:58:00Z",
    updated_at: "2026-08-16T09:10:00Z",
    reused: false,
  },
  {
    id: "demo-run-defect-v2",
    project_id: "demo-project-defect",
    dataset_version_id: "demo-version-defect-v2",
    run_type: "training",
    status: "succeeded",
    engine: "ultralytics",
    executor: "docker",
    recipe: { model: "yolo11n.pt", task: "detect", epochs: 50, image_size: 640, batch_size: 16 },
    progress: 100,
    artifact_prefix: "s3://sensemu-demo/runs/defect-v2",
    spec_uri: "s3://sensemu-demo/runs/defect-v2/spec.json",
    error_code: null,
    error_message: null,
    started_at: "2026-08-13T04:00:00Z",
    finished_at: "2026-08-13T06:45:00Z",
    created_at: "2026-08-13T03:58:00Z",
    updated_at: "2026-08-13T06:45:00Z",
    reused: false,
  },
];

export const previewModels: ModelVersion[] = [
  {
    id: "demo-model-ppe-v2",
    model_id: "demo-model-ppe",
    model_name: "PPE 安全穿戴模型",
    run_id: "demo-run-ppe-v2",
    version_number: 2,
    status: "ready",
    artifact_uri: "s3://sensemu-demo/models/ppe/v2/model.pt",
    metrics: { precision: 0.91, recall: 0.87, map50: 0.923, map50_95: 0.681 },
    created_at: "2026-08-16T09:10:00Z",
  },
  {
    id: "demo-model-defect-v2",
    model_id: "demo-model-defect",
    model_name: "表面缺陷检测模型",
    run_id: "demo-run-defect-v2",
    version_number: 2,
    status: "ready",
    artifact_uri: "s3://sensemu-demo/models/defect/v2/model.pt",
    metrics: { precision: 0.88, recall: 0.84, map50: 0.897, map50_95: 0.642 },
    created_at: "2026-08-13T06:45:00Z",
  },
];

export const previewDeployments: Deployment[] = [
  {
    id: "demo-deployment-ppe",
    workspace_id: previewWorkspaceId,
    project_id: "demo-project-ppe",
    model_version_id: "demo-model-ppe-v2",
    model_name: "PPE 安全穿戴模型",
    model_version_number: 2,
    task_type: "object-detection",
    evaluation_id: "demo-evaluation-ppe",
    evaluation_policy_version: 1,
    name: "工地安全穿戴服务",
    endpoint_slug: "ppe-safety-demo",
    endpoint_url: "https://api.example.invalid/v1/ppe-safety-demo:predict",
    environment: "staging",
    status: "published",
    spec_uri: "s3://sensemu-demo/deployments/ppe/spec.json",
    api_key_prefix: "sm_demo_",
    request_count: 12840,
    billable_units: 12840,
    published_at: "2026-08-16T12:00:00Z",
    disabled_at: null,
    created_at: "2026-08-16T11:55:00Z",
    updated_at: previewNow,
  },
];

const previewPolicies: EvaluationPolicy[] = [
  {
    id: "demo-policy-ppe",
    project_id: "demo-project-ppe",
    version_number: 1,
    name: "上线门槛",
    rules: [
      { metric: "map50", operator: ">=", threshold: 0.85, label: "mAP50" },
      { metric: "recall", operator: ">=", threshold: 0.8, label: "召回率" },
    ],
    is_active: true,
    created_at: "2026-08-10T03:00:00Z",
  },
];

const previewEvaluations: Evaluation[] = [
  {
    id: "demo-evaluation-ppe",
    model_version_id: "demo-model-ppe-v2",
    model_name: "PPE 安全穿戴模型",
    model_version_number: 2,
    dataset_version_id: "demo-version-ppe-v3",
    policy_id: "demo-policy-ppe",
    policy_name: "上线门槛",
    policy_version: 1,
    source: "acceptance",
    status: "completed",
    verdict: "passed",
    metrics: { precision: 0.91, recall: 0.87, map50: 0.923, map50_95: 0.681 },
    rule_results: [
      { metric: "map50", operator: ">=", threshold: 0.85, label: "mAP50", actual: 0.923, passed: true, reason: null },
      { metric: "recall", operator: ">=", threshold: 0.8, label: "召回率", actual: 0.87, passed: true, reason: null },
    ],
    report_uri: "s3://sensemu-demo/evaluations/ppe/report.json",
    evaluated_at: "2026-08-16T10:30:00Z",
    created_at: "2026-08-16T10:20:00Z",
  },
];

const previewCapabilities: CapabilitySpec[] = [
  {
    id: "demo-capability-ppe",
    workspace_id: previewWorkspaceId,
    project_id: "demo-project-ppe",
    deployment_id: "demo-deployment-ppe",
    capability_slug: "ppe-safety-detection",
    version_number: 1,
    display_name: "安全穿戴检测",
    problem_definition: "判断作业人员是否佩戴安全帽和反光衣。",
    input: { media_types: ["image/jpeg", "image/png"], max_payload_bytes: 10_485_760, capture_constraints: "固定监控视角，白天或照明充足" },
    output: { contract: "object-detection.v1", classes: ["人员", "安全帽", "反光衣"], business_events: ["missing_helmet", "missing_vest"] },
    applicability: { verified_scenes: ["建筑工地", "厂区作业区"], unsupported_conditions: ["严重遮挡", "夜间无补光"] },
    delivery: { profiles: ["shared-api"], data_retention_default: "none" },
    evidence: { evaluation_id: "demo-evaluation-ppe" },
    status: "published",
    content_hash: "demo-capability-hash",
    spec_uri: "s3://sensemu-demo/capabilities/ppe/v1.json",
    published_at: "2026-08-16T11:30:00Z",
    created_at: "2026-08-16T11:30:00Z",
  },
];

const previewWorkflows: WorkflowSpec[] = [
  {
    id: "demo-workflow-ppe",
    workspace_id: previewWorkspaceId,
    project_id: "demo-project-ppe",
    capability_spec_id: "demo-capability-ppe",
    capability_slug: "ppe-safety-detection",
    capability_version_number: 1,
    workflow_slug: "ppe-alert",
    version_number: 1,
    display_name: "未规范穿戴告警",
    template_key: "ppe-missing-equipment",
    event_types: ["missing_helmet", "missing_vest"],
    deduplication_window_seconds: 60,
    webhook_url: "https://example.invalid/hooks/ppe-alert",
    status: "published",
    content_hash: "demo-workflow-hash",
    spec_uri: "s3://sensemu-demo/workflows/ppe-alert/v1.json",
    published_at: "2026-08-16T11:40:00Z",
    created_at: "2026-08-16T11:40:00Z",
  },
];

const previewEvents: VisionEvent[] = [
  {
    id: "demo-event-ppe-1",
    request_id: "demo-request-001",
    event_type: "missing_helmet",
    occurred_at: "2026-08-17T02:20:00Z",
    workflow_spec_id: "demo-workflow-ppe",
    workflow_slug: "ppe-alert",
    workflow_name: "未规范穿戴告警",
    delivery_id: "demo-delivery-001",
    delivery_status: "delivered",
    attempt_count: 1,
    last_error: null,
    delivered_at: "2026-08-17T02:20:02Z",
  },
];

const previewBatchRuns: BatchInferenceRun[] = [
  {
    ...previewRuns[1],
    id: "demo-batch-ppe",
    run_type: "inference.batch",
    dataset_version_id: "demo-version-ppe-v3",
    recipe: { confidence: 0.45, iou: 0.7, image_size: 640, source_split: "test" },
    result: {
      id: "demo-batch-result-ppe",
      run_id: "demo-batch-ppe",
      deployment_id: "demo-deployment-ppe",
      output_uri: "s3://sensemu-demo/batches/ppe/predictions.ndjson",
      report_uri: "s3://sensemu-demo/batches/ppe/report.json",
      summary: {
        source_split: "test",
        parameters: { confidence: 0.45, iou: 0.7, max_detections: 100, image_size: 640 },
        processed_asset_count: 126,
        prediction_count: 402,
        runtime: { engine: "onnxruntime", device: "cpu", duration_seconds: 18.6 },
        format: "ndjson",
      },
      completed_at: "2026-08-16T13:20:00Z",
    },
  },
];

const previewProvider: ProviderDashboard = {
  profile: null,
  algorithm_listing_count: 1,
  data_listing_count: 1,
  active_customer_grants: 6,
  successful_units: 12840,
  authorized_sales_yuan: 336,
  paid_sales_yuan: 168,
  refunded_sales_yuan: 0,
  unsettled_earnings_yuan: 42.8,
  algorithm_listings: [
    { id: "mock-alg-ppe", title: "工地安全穿戴检测", category: "目标检测", status: "published", price_per_1000_cents: 1680, monthly_quota_units: 20000, active_customer_grants: 6, successful_units: 12840, published_at: "2026-08-16T12:00:00Z", review_note: null, reviewed_at: "2026-08-16T11:50:00Z" },
  ],
  data_listings: [
    { id: "mock-data-ppe", title: "工地安全穿戴数据集", dataset_name: "工地安全穿戴数据", dataset_version_number: 3, asset_count: 1248, license_code: "CUSTOM-COMMERCIAL", status: "published", published_at: "2026-08-16T12:10:00Z" },
  ],
  sales: [
    { id: "demo-sale-1", order_number: "SM20260816001", listing_title: "工地安全穿戴检测", buyer_name: "华东制造演示客户", authorization_amount_yuan: 168, payment_status: "paid", payment_intent_status: "succeeded", payment_provider: "demo", paid_amount_yuan: 168, refunded_amount_yuan: 0, created_at: "2026-08-16T14:00:00Z" },
  ],
  earnings: [
    { id: "demo-earning-1", listing_title: "工地安全穿戴检测", buyer_name: "华东制造演示客户", request_id: "demo-request-001", amount_yuan: 0.0168, settlement_status: "pending", occurred_at: previewNow },
  ],
};

const previewSubscriptions: MarketplaceSubscription[] = [
  {
    id: "demo-subscription-ppe",
    listing_id: "mock-alg-ppe",
    buyer_workspace_id: previewWorkspaceId,
    listing_title: "工地安全穿戴检测",
    provider_name: "SenseMu 精选",
    endpoint_url: "https://api.example.invalid/v1/ppe-safety-demo:predict",
    status: "active",
    quota_units: 20000,
    reserved_units: 0,
    consumed_units: 3280,
    remaining_units: 16720,
    price_per_1000_cents: 1680,
    api_key_prefix: "sm_demo_",
    credential_claimed_at: "2026-08-16T14:00:00Z",
    started_at: "2026-08-16T14:00:00Z",
    expires_at: "2026-09-16T14:00:00Z",
    order_number: "SM20260816002",
    payment_status: "paid",
  },
];

const previewUsage: MarketplaceUsageRecord[] = [
  { id: "demo-usage-1", request_id: "demo-consumer-request-1", subscription_id: "demo-subscription-ppe", listing_id: "mock-alg-ppe", listing_title: "工地安全穿戴检测", provider_name: "SenseMu 精选", billable_units: 24, unit: "image", estimated_cost_yuan: 0.4032, dimensions: { source: "online" }, occurred_at: "2026-08-17T02:10:00Z" },
  { id: "demo-usage-2", request_id: "demo-consumer-request-2", subscription_id: "demo-subscription-ppe", listing_id: "mock-alg-ppe", listing_title: "工地安全穿戴检测", provider_name: "SenseMu 精选", billable_units: 18, unit: "image", estimated_cost_yuan: 0.3024, dimensions: { source: "batch" }, occurred_at: "2026-08-16T09:20:00Z" },
];

const previewBilling: MarketplaceBilling = {
  authorization_ceiling_yuan: 168,
  unsettled_earnings_yuan: 0,
  orders: [
    {
      id: "demo-order-1",
      order_number: "SM20260816002",
      listing_id: "mock-alg-ppe",
      subscription_id: "demo-subscription-ppe",
      listing_title: "工地安全穿戴检测",
      provider_name: "SenseMu 精选",
      currency: "CNY",
      price_per_1000_cents: 1680,
      quota_units: 20000,
      authorization_amount_yuan: 168,
      status: "active",
      payment_status: "paid",
      entitlement_started_at: "2026-08-16T14:00:00Z",
      entitlement_expires_at: "2026-09-16T14:00:00Z",
      created_at: "2026-08-16T14:00:00Z",
      payment_intent_id: "demo-payment-1",
      payment_intent_status: "succeeded",
      payment_provider: "demo",
      paid_amount_yuan: 168,
      refunded_amount_yuan: 0,
    },
  ],
  earnings: [],
};

function assetsForDataset(datasetId: string): Asset[] {
  return datasetId === "demo-dataset-defect" ? defectAssets : ppeAssets;
}

function qualityReport(versionId: string): DatasetVersionQualityReport {
  const defect = versionId.includes("defect");
  const assetCount = defect ? 594 : 1248;
  const classes = defect ? ["划痕", "凹坑", "脏污"] : ["人员", "安全帽", "反光衣"];
  return {
    dataset_version_id: versionId,
    schema_version: "1.0",
    asset_count: assetCount,
    split_counts: { train: Math.round(assetCount * 0.8), valid: Math.round(assetCount * 0.1), test: assetCount - Math.round(assetCount * 0.9) },
    annotated_asset_count: Math.round(assetCount * 0.94),
    unannotated_asset_count: assetCount - Math.round(assetCount * 0.94),
    annotation_coverage_percent: 94,
    class_distribution: classes.map((name, index) => ({ class_id: index, class_name: name, annotation_count: Math.round(assetCount * (1.4 - index * 0.18)), asset_count: Math.round(assetCount * (0.76 - index * 0.1)) })),
    image_dimensions: { known_asset_count: assetCount, unknown_asset_count: 0, min_width: 1280, max_width: 3840, min_height: 720, max_height: 2160 },
    advisories: ["演示数据：正式训练前请复核长尾场景与类别平衡。"],
  };
}

function trainingReport(runId: string): TrainingReport {
  return {
    run_id: runId,
    rows: Array.from({ length: 12 }, (_, index) => {
      const epoch = (index + 1) * 5;
      return {
        epoch,
        metrics: {
          "train/box_loss": Number((1.42 - index * 0.083).toFixed(3)),
          "train/cls_loss": Number((1.08 - index * 0.064).toFixed(3)),
          "metrics/precision": Number((0.52 + index * 0.035).toFixed(3)),
          "metrics/recall": Number((0.46 + index * 0.037).toFixed(3)),
          "metrics/mAP50(B)": Number((0.48 + index * 0.04).toFixed(3)),
          "metrics/mAP50-95(B)": Number((0.26 + index * 0.038).toFixed(3)),
        },
      };
    }),
  };
}

export type PreviewMockResult = { handled: boolean; value?: unknown };

export function getPreviewMockResult(path: string, init: RequestInit = {}): PreviewMockResult {
  if (!isHostedPreview()) return { handled: false };
  const requestUrl = new URL(path, "https://preview.invalid");
  const pathname = requestUrl.pathname;
  const method = (init.method ?? "GET").toUpperCase();

  if (method !== "GET") {
    const projectStatusMatch = pathname.match(/^\/api\/v1\/projects\/([^/]+):(pause|resume)$/);
    if (projectStatusMatch) {
      const project = previewProjects.find((item) => item.id === projectStatusMatch[1]);
      return { handled: true, value: project ? { ...project, status: projectStatusMatch[2] === "pause" ? "paused" : "active" } : null };
    }
    if (method === "DELETE" || pathname.endsWith(":archive") || pathname.endsWith(":disable")) {
      return { handled: true, value: undefined };
    }
    throw new Error("当前为演示数据，新增与修改不会保存");
  }

  if (pathname === "/api/v1/identity/me") return { handled: true, value: previewIdentity };
  if (pathname === "/api/v1/workspaces") return { handled: true, value: [previewWorkspace] };
  if (pathname === "/api/v1/projects") return { handled: true, value: previewProjects };
  if (pathname === "/api/v1/training/engines") return { handled: true, value: trainingEngines };
  if (pathname === "/api/v1/provider/dashboard") return { handled: true, value: previewProvider };
  if (pathname === "/api/v1/marketplace/listings" || pathname === "/api/v1/marketplace/submissions" || pathname === "/api/v1/data-market/listings") return { handled: true, value: [] };
  if (pathname === "/api/v1/marketplace/subscriptions") return { handled: true, value: previewSubscriptions };
  if (pathname === "/api/v1/marketplace/usage-records") return { handled: true, value: previewUsage };
  if (pathname === "/api/v1/marketplace/billing") return { handled: true, value: previewBilling };

  const projectDatasets = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/datasets$/);
  if (projectDatasets) return { handled: true, value: previewDatasets.filter((item) => item.project_id === projectDatasets[1]) };
  const projectRuns = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/training-runs$/);
  if (projectRuns) return { handled: true, value: previewRuns.filter((item) => item.project_id === projectRuns[1] && item.run_type === "training") };
  const acceptanceRuns = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/acceptance-runs$/);
  if (acceptanceRuns) return { handled: true, value: [] };
  const projectModels = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/model-versions$/);
  if (projectModels) {
    const runIds = previewRuns.filter((item) => item.project_id === projectModels[1]).map((item) => item.id);
    return { handled: true, value: previewModels.filter((item) => runIds.includes(item.run_id)) };
  }
  const projectPolicies = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/evaluation-policies$/);
  if (projectPolicies) return { handled: true, value: projectPolicies[1] === "demo-project-ppe" ? previewPolicies : [] };
  const projectEvaluations = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/evaluations$/);
  if (projectEvaluations) return { handled: true, value: projectEvaluations[1] === "demo-project-ppe" ? previewEvaluations : [] };
  const projectDeployments = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/deployments$/);
  if (projectDeployments) return { handled: true, value: previewDeployments.filter((item) => item.project_id === projectDeployments[1]) };
  const projectBatchRuns = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/batch-inference-runs$/);
  if (projectBatchRuns) return { handled: true, value: previewBatchRuns.filter((item) => item.project_id === projectBatchRuns[1]) };
  const projectCapabilities = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/capability-specs$/);
  if (projectCapabilities) return { handled: true, value: previewCapabilities.filter((item) => item.project_id === projectCapabilities[1]) };
  const projectWorkflows = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/workflow-specs$/);
  if (projectWorkflows) return { handled: true, value: previewWorkflows.filter((item) => item.project_id === projectWorkflows[1]) };
  const projectEvents = pathname.match(/^\/api\/v1\/projects\/([^/]+)\/vision-events$/);
  if (projectEvents) return { handled: true, value: previewEvents };

  const datasetAssets = pathname.match(/^\/api\/v1\/datasets\/([^/]+)\/assets$/);
  if (datasetAssets) return { handled: true, value: assetsForDataset(datasetAssets[1]) };
  const datasetVersions = pathname.match(/^\/api\/v1\/datasets\/([^/]+)\/versions$/);
  if (datasetVersions) return { handled: true, value: previewVersions[datasetVersions[1]] ?? [] };
  const sourceVideos = pathname.match(/^\/api\/v1\/datasets\/([^/]+)\/source-videos$/);
  if (sourceVideos) return { handled: true, value: [] as Asset[] };
  const videoExtractions = pathname.match(/^\/api\/v1\/datasets\/([^/]+)\/video-extractions$/);
  if (videoExtractions) return { handled: true, value: [] as VideoExtractionJob[] };
  const taskAssets = pathname.match(/^\/api\/v1\/datasets\/([^/]+)\/annotation-tasks\/([^/]+)\/assets$/);
  if (taskAssets) return { handled: true, value: assetsForDataset(taskAssets[1]).slice(0, 8) };
  const taskDetail = pathname.match(/^\/api\/v1\/datasets\/([^/]+)\/annotation-tasks\/([^/]+)$/);
  if (taskDetail) return { handled: true, value: (annotationTasks[taskDetail[1]] ?? []).find((item) => item.id === taskDetail[2]) ?? null };
  const taskList = pathname.match(/^\/api\/v1\/datasets\/([^/]+)\/annotation-tasks$/);
  if (taskList) return { handled: true, value: annotationTasks[taskList[1]] ?? [] };
  if (/^\/api\/v1\/datasets\/[^/]+\/items\/[^/]+\/annotation$/.test(pathname)) {
    return { handled: true, value: "0 0.50 0.52 0.28 0.72\n1 0.48 0.31 0.12 0.14\n2 0.51 0.60 0.22 0.30\n" };
  }
  const quality = pathname.match(/^\/api\/v1\/dataset-versions\/([^/]+)\/quality-report$/);
  if (quality) return { handled: true, value: qualityReport(quality[1]) };

  const runEvents = pathname.match(/^\/api\/v1\/training-runs\/([^/]+)\/events$/);
  if (runEvents) {
    const run = previewRuns.find((item) => item.id === runEvents[1]);
    const events: RunEvent[] = run ? [
      { id: `${run.id}-event-1`, event_id: `${run.id}-queued`, run_id: run.id, sequence: 1, event_type: "queued", status: "queued", progress: 0, payload: {}, occurred_at: run.created_at },
      { id: `${run.id}-event-2`, event_id: `${run.id}-started`, run_id: run.id, sequence: 2, event_type: "started", status: "running", progress: 1, payload: {}, occurred_at: run.started_at ?? run.created_at },
      { id: `${run.id}-event-3`, event_id: `${run.id}-progress`, run_id: run.id, sequence: 3, event_type: "progress", status: run.status, progress: run.progress, payload: { epoch: run.status === "running" ? 54 : 60 }, occurred_at: run.updated_at },
    ] : [];
    return { handled: true, value: events };
  }
  const runReport = pathname.match(/^\/api\/v1\/training-runs\/([^/]+)\/report$/);
  if (runReport) return { handled: true, value: trainingReport(runReport[1]) };
  const classMetrics = pathname.match(/^\/api\/v1\/training-runs\/([^/]+)\/class-metrics$/);
  if (classMetrics) {
    const metrics: TrainingClassMetrics = { run_id: classMetrics[1], classes: [
      { class_id: 0, name: "人员", precision: 0.94, recall: 0.92, map50: 0.96, map50_95: 0.72 },
      { class_id: 1, name: "安全帽", precision: 0.91, recall: 0.87, map50: 0.93, map50_95: 0.68 },
      { class_id: 2, name: "反光衣", precision: 0.88, recall: 0.83, map50: 0.89, map50_95: 0.63 },
    ] };
    return { handled: true, value: metrics };
  }

  return { handled: false };
}
