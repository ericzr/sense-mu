import { getPreviewMockResult, isHostedPreview } from "./preview-mock-api";
import { clearAccessToken, getAccessToken } from "./auth-session";

export type Workspace = {
  id: string;
  slug: string;
  name: string;
  created_at: string;
  role: "owner" | "admin" | "member" | "viewer";
};

export type IdentityMembership = {
  workspace_id: string;
  workspace_slug: string;
  workspace_name: string;
  role: "owner" | "admin" | "member" | "viewer";
  joined_at: string;
};

export type CurrentIdentity = {
  id: string;
  email: string | null;
  email_verified: boolean;
  display_name: string | null;
  auth_mode: "development" | "oidc";
  memberships: IdentityMembership[];
};

export type WorkspaceMember = {
  id: string;
  user_id: string;
  email: string | null;
  display_name: string | null;
  role: "owner" | "admin" | "member" | "viewer";
  status: "active" | "suspended";
  joined_at: string;
  is_current_user: boolean;
};

export type WorkspaceInvitation = {
  id: string;
  email: string;
  role: "admin" | "member" | "viewer";
  status: "pending" | "accepted" | "revoked" | "expired";
  token_prefix: string;
  invited_by_user_id: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

export type WorkspaceInvitationSecret = WorkspaceInvitation & {
  invite_token: string;
  acceptance_url: string;
};

export type WorkspaceAccessEvent = {
  id: string;
  event_type: string;
  actor_user_id: string;
  actor_name: string;
  target_user_id: string | null;
  target_name: string | null;
  invitation_id: string | null;
  details: Record<string, string>;
  occurred_at: string;
};

export type DataMarketListing = {
  id: string;
  provider_workspace_id: string;
  provider_name: string;
  dataset_version_id: string;
  dataset_id: string;
  dataset_name: string;
  dataset_version_number: number;
  project_name: string;
  task_type: string;
  asset_count: number;
  class_map: Record<string, string>;
  quality_report: DatasetVersionQualityReport | null;
  title: string;
  summary: string;
  source_summary: string;
  collection_method: string;
  coverage_summary: string;
  known_limitations: string;
  license_code: "CC0-1.0" | "CC-BY-4.0" | "ODC-BY-1.0" | "CUSTOM-COMMERCIAL";
  custom_license_terms: string | null;
  allow_commercial_use: boolean;
  allow_model_training: boolean;
  allow_derivative_models: boolean;
  allow_redistribution: boolean;
  contains_personal_data: boolean;
  privacy_treatment: string;
  review_basis: "provider_attestation";
  status: "published";
  delivery_mode: "workspace_copy_after_authorization" | "not_prepared";
  delivery_status: "prepared_not_open" | "not_open";
  delivery_spec_hash: string | null;
  published_at: string;
};

export type DataMarketListingCreate = {
  title: string;
  summary: string;
  source_summary: string;
  collection_method: string;
  coverage_summary: string;
  known_limitations: string;
  license_code: DataMarketListing["license_code"];
  custom_license_terms: string | null;
  allow_commercial_use: boolean;
  allow_model_training: boolean;
  allow_derivative_models: boolean;
  allow_redistribution: boolean;
  contains_personal_data: boolean;
  privacy_treatment: string;
  rights_confirmed: true;
};

export type ProviderProfile = {
  id: string;
  workspace_id: string;
  public_name: string;
  summary: string;
  provider_type: "organization" | "individual";
  support_email: string;
  website_url: string | null;
  service_regions: string[];
  support_commitment: string;
  onboarding_status: "profile_complete";
  identity_verification_status: "not_started";
  payout_onboarding_status: "not_started";
  review_status: "not_submitted";
  created_at: string;
  updated_at: string;
};

export type ProviderAlgorithmListing = {
  id: string;
  title: string;
  category: string;
  status: string;
  price_per_1000_cents: number;
  monthly_quota_units: number;
  active_customer_grants: number;
  successful_units: number;
  published_at: string | null;
  review_note: string | null;
  reviewed_at: string | null;
};

export type ProviderDataListing = {
  id: string;
  title: string;
  dataset_name: string;
  dataset_version_number: number;
  asset_count: number;
  license_code: string;
  status: string;
  published_at: string;
};

export type ProviderSale = {
  id: string;
  order_number: string;
  listing_title: string;
  buyer_name: string;
  authorization_amount_yuan: number;
  payment_status: string;
  payment_intent_status: string | null;
  payment_provider: string | null;
  paid_amount_yuan: number;
  refunded_amount_yuan: number;
  created_at: string;
};

export type ProviderEarning = {
  id: string;
  listing_title: string;
  buyer_name: string;
  request_id: string;
  amount_yuan: number;
  settlement_status: string;
  occurred_at: string;
};

export type ProviderDashboard = {
  profile: ProviderProfile | null;
  algorithm_listing_count: number;
  data_listing_count: number;
  active_customer_grants: number;
  successful_units: number;
  authorized_sales_yuan: number;
  paid_sales_yuan: number;
  refunded_sales_yuan: number;
  unsettled_earnings_yuan: number;
  algorithm_listings: ProviderAlgorithmListing[];
  data_listings: ProviderDataListing[];
  sales: ProviderSale[];
  earnings: ProviderEarning[];
};

export type ProviderProfileUpdate = {
  public_name: string;
  summary: string;
  provider_type: "organization" | "individual";
  support_email: string;
  website_url: string | null;
  service_regions: string[];
  support_commitment: string;
};

export type Project = {
  id: string;
  workspace_id: string;
  workspace_slug: string;
  slug: string;
  name: string;
  task_type: string;
  description: string | null;
  status: "active" | "paused";
  created_at: string;
};

export type Dataset = {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  class_map: Record<string, string>;
  created_at: string;
  asset_count: number;
  version_count: number;
};

export type Asset = {
  id: string;
  uri: string;
  media_type: string;
  checksum_sha256: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  split: string | null;
  annotation_uri: string | null;
  reused: boolean;
  created_at: string;
};

export type AnnotationTask = {
  id: string;
  dataset_id: string;
  name: string;
  method: "manual" | "smart";
  asset_scope: "unlabeled" | "all" | "video_extraction";
  status: "annotating" | "review" | "done";
  assigned_to_user_id: string;
  source_video_extraction_job_id: string | null;
  class_map: Record<string, string>;
  asset_count: number;
  completed_count: number;
  created_at: string;
  updated_at: string;
};

export type VideoExtractionJob = {
  id: string;
  dataset_id: string;
  source_asset_id: string;
  idempotency_key: string;
  frame_interval_ms: number;
  deduplicate: boolean;
  status: "queued" | "preparing" | "running" | "succeeded" | "failed" | "cancel_requested" | "cancelled";
  progress: number;
  frames_created: number;
  error_code: string | null;
  error_message: string | null;
  execution_attempt: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DatasetVersion = {
  id: string;
  version_number: number;
  status: string;
  manifest_uri: string;
  asset_count: number;
  class_map: Record<string, string>;
  frozen_at: string | null;
  created_at: string;
};

export type DatasetVersionQualityReport = {
  dataset_version_id: string;
  schema_version: "1.0";
  asset_count: number;
  split_counts: Record<"train" | "valid" | "test", number>;
  annotated_asset_count: number;
  unannotated_asset_count: number;
  annotation_coverage_percent: number;
  class_distribution: Array<{
    class_id: number;
    class_name: string;
    annotation_count: number;
    asset_count: number;
  }>;
  image_dimensions: {
    known_asset_count: number;
    unknown_asset_count: number;
    min_width: number | null;
    max_width: number | null;
    min_height: number | null;
    max_height: number | null;
  };
  advisories: string[];
};

export type TrainingEngine = {
  key: string;
  label: string;
  task_types: string[];
  models: string[];
  defaults: {
    model: string;
    task: string;
    epochs: number;
    image_size: number;
    batch_size: number;
    seed: number;
  };
  executor: "docker";
};

export type TrainingRun = {
  id: string;
  project_id: string;
  dataset_version_id: string;
  run_type: string;
  status: string;
  engine: string;
  executor: string;
  recipe: Record<string, string | number>;
  progress: number;
  artifact_prefix: string | null;
  spec_uri: string | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  reused: boolean;
};

export type RunEvent = {
  id: string;
  event_id: string;
  run_id: string;
  sequence: number;
  event_type: string;
  status: string;
  progress: number;
  payload: Record<string, unknown>;
  occurred_at: string;
};

export type TrainingReportRow = {
  epoch: number;
  metrics: Record<string, number>;
};

export type TrainingReport = {
  run_id: string;
  rows: TrainingReportRow[];
};

export type TrainingVisualizationName = "confusion_matrix" | "confusion_matrix_normalized";

export type TrainingClassMetric = {
  class_id: number;
  name: string;
  precision: number | null;
  recall: number | null;
  map50: number | null;
  map50_95: number | null;
};

export type TrainingClassMetrics = {
  run_id: string;
  classes: TrainingClassMetric[];
};

export type BatchInferenceResult = {
  id: string;
  run_id: string;
  deployment_id: string;
  output_uri: string;
  report_uri: string;
  summary: {
    source_split: "all" | "train" | "valid" | "test";
    parameters: {
      confidence: number;
      iou: number;
      max_detections: number;
      image_size: number;
    };
    processed_asset_count: number;
    prediction_count: number;
    runtime: Record<string, string | number | boolean | null>;
    format: "ndjson";
  };
  completed_at: string;
};

export type BatchInferenceRun = TrainingRun & {
  result: BatchInferenceResult | null;
};

export type ModelVersion = {
  id: string;
  model_id: string;
  model_name: string;
  run_id: string;
  version_number: number;
  status: string;
  artifact_uri: string;
  metrics: Record<string, number>;
  created_at: string;
};

export type EvaluationRule = {
  metric: string;
  operator: ">=" | "<=" | ">" | "<";
  threshold: number;
  label: string | null;
};

export type EvaluationPolicy = {
  id: string;
  project_id: string;
  version_number: number;
  name: string;
  rules: EvaluationRule[];
  is_active: boolean;
  created_at: string;
};

export type EvaluationRuleResult = EvaluationRule & {
  actual: number | null;
  passed: boolean;
  reason: string | null;
};

export type Evaluation = {
  id: string;
  model_version_id: string;
  model_name: string;
  model_version_number: number;
  dataset_version_id: string;
  policy_id: string;
  policy_name: string;
  policy_version: number;
  source: string;
  status: string;
  verdict: string;
  metrics: Record<string, string | number | boolean | null>;
  rule_results: EvaluationRuleResult[];
  report_uri: string;
  evaluated_at: string;
  created_at: string;
};

export type Deployment = {
  id: string;
  workspace_id: string;
  project_id: string;
  model_version_id: string;
  model_name: string;
  model_version_number: number;
  task_type: string;
  evaluation_id: string | null;
  evaluation_policy_version: number | null;
  name: string;
  endpoint_slug: string;
  endpoint_url: string;
  environment: string;
  status: string;
  spec_uri: string | null;
  api_key_prefix: string | null;
  request_count: number;
  billable_units: number;
  published_at: string | null;
  disabled_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DeploymentSecret = Deployment & { api_key: string };

export type CapabilityInputSpec = {
  media_types: Array<"image/jpeg" | "image/png" | "image/webp">;
  max_payload_bytes: number;
  capture_constraints: string;
};

export type CapabilityOutputSpec = {
  contract: string;
  classes: string[];
  business_events: string[];
};

export type CapabilityApplicabilitySpec = {
  verified_scenes: string[];
  unsupported_conditions: string[];
};

export type CapabilityDeliverySpec = {
  profiles: Array<"shared-api" | "dedicated-endpoint">;
  data_retention_default: "none" | "customer-configured";
};

export type CapabilitySpec = {
  id: string;
  workspace_id: string;
  project_id: string;
  deployment_id: string;
  capability_slug: string;
  version_number: number;
  display_name: string;
  problem_definition: string;
  input: CapabilityInputSpec;
  output: CapabilityOutputSpec;
  applicability: CapabilityApplicabilitySpec;
  delivery: CapabilityDeliverySpec;
  evidence: Record<string, unknown>;
  status: "published";
  content_hash: string;
  spec_uri: string;
  published_at: string;
  created_at: string;
};

export type WorkflowSpec = {
  id: string;
  workspace_id: string;
  project_id: string;
  capability_spec_id: string;
  capability_slug: string;
  capability_version_number: number;
  workflow_slug: string;
  version_number: number;
  display_name: string;
  template_key: string;
  event_types: string[];
  deduplication_window_seconds: number;
  webhook_url: string;
  status: "published";
  content_hash: string;
  spec_uri: string;
  published_at: string;
  created_at: string;
};

export type VisionEvent = {
  id: string;
  request_id: string;
  event_type: string;
  occurred_at: string;
  workflow_spec_id: string;
  workflow_slug: string;
  workflow_name: string;
  delivery_id: string;
  delivery_status: "pending" | "delivering" | "retrying" | "delivered" | "failed";
  attempt_count: number;
  last_error: string | null;
  delivered_at: string | null;
};

export type VisionEventReplay = {
  event_id: string;
  request_id: string;
  event_type: string;
  occurred_at: string;
  workflow_slug: string;
  workflow_name: string;
  workflow_version: number;
  template_key: string;
  sample: {
    source_id: string | null;
    source_type: string | null;
    input_index: number | null;
    condition_kind: string | null;
    required_class: string | null;
    person_count: number | null;
    required_class_count: number | null;
    detection_count: number | null;
    width: number | null;
    height: number | null;
  };
  decision: {
    matched: boolean;
    reasons: string[];
    deduplication_key: string;
    deduplication_window_seconds: number;
  };
  delivery: {
    id: string;
    status: VisionEvent["delivery_status"];
    attempt_count: number;
    target_host: string | null;
    next_attempt_at: string;
    last_error: string | null;
    delivered_at: string | null;
  };
};

export type Detection = {
  class_id: number;
  class_name: string;
  confidence: number;
  box: { x1: number; y1: number; x2: number; y2: number };
};

export type InferenceResponse = {
  request_id: string;
  workspace: string;
  endpoint: string;
  model_version_id: string;
  contract: string;
  outputs: {
    request_id: string;
    contract: string;
    predictions: Array<{
      input: string;
      width: number;
      height: number;
      detections: Detection[];
    }>;
    runtime: {
      engine: string;
      device: string;
      inference_ms: number;
    };
  };
};

export type InferenceHealth = {
  status: "ready" | "not_ready";
  control_plane: { status: "ready" | "unavailable" };
  runtime: {
    configured: boolean;
    status: "ready" | "unavailable" | "not_configured";
    accepting_requests?: boolean;
    cache?: {
      loaded_models: number;
      max_cached_models: number;
      model_version_ids?: string[];
    };
    capacity?: {
      active_requests: number;
      waiting_requests: number;
      max_concurrent_requests: number;
      available_slots: number;
    };
  };
};

export type PrewarmResponse = {
  request_id: string;
  workspace: string;
  endpoint: string;
  model_version_id: string;
  runtime: {
    request_id: string;
    model_version_id: string;
    cache_hit: boolean;
    cache: {
      loaded_models: number;
      max_cached_models: number;
      model_version_ids: string[];
    };
    capacity: {
      active_requests: number;
      waiting_requests: number;
      max_concurrent_requests: number;
      available_slots: number;
    };
  };
};

export type MarketplaceListing = {
  id: string;
  provider_workspace_id: string;
  provider_name: string;
  deployment_id: string;
  capability_spec_id: string | null;
  capability_slug: string | null;
  capability_version_number: number | null;
  capability_display_name: string | null;
  capability_problem_definition: string | null;
  capability_output_contract: string | null;
  capability_verified_scenes: string[];
  capability_unsupported_conditions: string[];
  endpoint_url: string;
  model_name: string;
  model_version_number: number;
  task_type: string;
  title: string;
  summary: string;
  category: string;
  pricing_unit: string;
  price_per_1000_cents: number;
  monthly_quota_units: number;
  status: string;
  published_at: string | null;
  subscription_id: string | null;
  subscription_status: string | null;
  remaining_units: number | null;
};

export type MarketplaceListingSubmission = MarketplaceListing & {
  review_note: string | null;
  reviewed_at: string | null;
};

export type MarketplaceSubscription = {
  id: string;
  listing_id: string;
  buyer_workspace_id: string;
  listing_title: string;
  provider_name: string;
  endpoint_url: string;
  status: string;
  quota_units: number;
  reserved_units: number;
  consumed_units: number;
  remaining_units: number;
  price_per_1000_cents: number;
  api_key_prefix: string | null;
  credential_claimed_at: string | null;
  started_at: string | null;
  expires_at: string | null;
  order_number: string | null;
  payment_status: string | null;
};

export type MarketplaceSubscriptionSecret = MarketplaceSubscription & { api_key: string };

export type MarketplaceCheckout = MarketplaceSubscription & {
  payment_intent_id: string;
  payment_intent_status: string;
  expected_amount_yuan: number;
  payment_provider: string | null;
  checkout_available: boolean;
  reused: boolean;
};

export type MarketplaceUsageRecord = {
  id: string;
  request_id: string;
  subscription_id: string;
  listing_id: string;
  listing_title: string;
  provider_name: string;
  billable_units: number;
  unit: string;
  estimated_cost_yuan: number;
  dimensions: Record<string, string | number | boolean | null>;
  occurred_at: string;
};

export type MarketplaceOrder = {
  id: string;
  order_number: string;
  listing_id: string;
  subscription_id: string;
  listing_title: string;
  provider_name: string;
  currency: string;
  price_per_1000_cents: number;
  quota_units: number;
  authorization_amount_yuan: number;
  status: string;
  payment_status: string;
  entitlement_started_at: string | null;
  entitlement_expires_at: string | null;
  created_at: string;
  payment_intent_id: string | null;
  payment_intent_status: string | null;
  payment_provider: string | null;
  paid_amount_yuan: number;
  refunded_amount_yuan: number;
};

export type MarketplaceEarning = {
  id: string;
  usage_record_id: string;
  request_id: string;
  listing_title: string;
  buyer_name: string;
  amount_yuan: number;
  currency: string;
  settlement_status: string;
  occurred_at: string;
};

export type MarketplaceBilling = {
  authorization_ceiling_yuan: number;
  unsettled_earnings_yuan: number;
  orders: MarketplaceOrder[];
  earnings: MarketplaceEarning[];
};

type RequestOptions = RequestInit & { workspaceId?: string };

export type CatalogApiErrorCode =
  | "session_expired"
  | "permission_denied"
  | "service_unavailable"
  | "request_failed";

export class CatalogApiError extends Error {
  readonly status: number;
  readonly code: CatalogApiErrorCode;
  readonly detail: string | null;

  constructor(
    message: string,
    options: { status: number; code: CatalogApiErrorCode; detail?: string | null },
  ) {
    super(message);
    this.name = "CatalogApiError";
    this.status = options.status;
    this.code = options.code;
    this.detail = options.detail ?? null;
  }
}

const API_REQUEST_TIMEOUT_MS = 20_000;
const ARTIFACT_REQUEST_TIMEOUT_MS = 60_000;
const INFERENCE_REQUEST_TIMEOUT_MS = 75_000;

function isRequestTimeout(error: unknown): boolean {
  return error instanceof Error && error.name === "TimeoutError";
}

async function fetchWithTimeout(
  input: string | URL,
  init: RequestInit = {},
  timeoutMs = API_REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutError = new DOMException("Request timed out", "TimeoutError");
  const timeoutId = window.setTimeout(() => controller.abort(timeoutError), timeoutMs);
  const sourceSignal = init.signal;
  const forwardAbort = () => controller.abort(sourceSignal?.reason);

  if (sourceSignal?.aborted) {
    forwardAbort();
  } else {
    sourceSignal?.addEventListener("abort", forwardAbort, { once: true });
  }

  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
    sourceSignal?.removeEventListener("abort", forwardAbort);
  }
}

function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SENSEMU_API_URL;
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location.hostname === "localhost") {
    return "http://localhost:8000";
  }
  throw new Error("SenseMu API 尚未配置");
}

function notifySessionExpired(): void {
  clearAccessToken();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("sensemu:session-expired"));
  }
}

function apiErrorForResponse(status: number, detail: string | null): CatalogApiError {
  if (status === 401) {
    notifySessionExpired();
    return new CatalogApiError("登录状态已失效，请重新登录后重试", {
      status,
      code: "session_expired",
      detail,
    });
  }
  if (status === 403) {
    return new CatalogApiError("当前账号没有执行该操作的权限", {
      status,
      code: "permission_denied",
      detail,
    });
  }
  if (status >= 500) {
    return new CatalogApiError(detail ?? "身份或服务暂时不可用，请稍后重试", {
      status,
      code: "service_unavailable",
      detail,
    });
  }
  return new CatalogApiError(detail ?? `请求失败 (${status})`, {
    status,
    code: "request_failed",
    detail,
  });
}

function serviceUnavailableError(message: string): CatalogApiError {
  return new CatalogApiError(message, {
    status: 0,
    code: "service_unavailable",
  });
}

function addAccessToken(headers: Headers): void {
  const accessToken = getAccessToken();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const previewResult = getPreviewMockResult(path, options);
  if (previewResult.handled) return previewResult.value as T;

  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.workspaceId) headers.set("X-Workspace-ID", options.workspaceId);
  addAccessToken(headers);

  let response: Response;
  try {
    response = await fetchWithTimeout(`${apiBaseUrl()}${path}`, { ...options, headers });
  } catch (error) {
    if (isRequestTimeout(error)) {
      throw serviceUnavailableError("SenseMu API 请求超时，请稍后重试");
    }
    throw serviceUnavailableError("无法连接 SenseMu API，请确认服务地址与网络连接");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw apiErrorForResponse(response.status, payload?.detail ?? null);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("text/plain")) return (await response.text()) as T;
  return (await response.json()) as T;
}

async function requestBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  if (isHostedPreview()) {
    const response = await fetch("/catalog-vision-samples.png");
    if (!response.ok) throw new Error("演示图片加载失败");
    return response.blob();
  }

  const headers = new Headers(options.headers);
  headers.set("Accept", "image/png");
  if (options.workspaceId) headers.set("X-Workspace-ID", options.workspaceId);
  addAccessToken(headers);

  let response: Response;
  try {
    response = await fetchWithTimeout(`${apiBaseUrl()}${path}`, { ...options, headers });
  } catch (error) {
    if (isRequestTimeout(error)) {
      throw serviceUnavailableError("SenseMu API 请求超时，请稍后重试");
    }
    throw serviceUnavailableError("无法连接 SenseMu API，请确认服务地址与网络连接");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw apiErrorForResponse(response.status, payload?.detail ?? null);
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.startsWith("image/png")) {
    throw new Error("训练评估图响应格式无效");
  }
  return response.blob();
}

export const catalogApi = {
  getCurrentIdentity: () => request<CurrentIdentity>("/api/v1/identity/me"),
  listWorkspaces: () => request<Workspace[]>("/api/v1/workspaces"),
  createWorkspace: (payload: { slug: string; name: string }) =>
    request<Workspace>("/api/v1/workspaces", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listWorkspaceMembers: (workspaceId: string) =>
    request<WorkspaceMember[]>("/api/v1/workspace-members", { workspaceId }),
  updateWorkspaceMemberRole: (
    workspaceId: string,
    membershipId: string,
    role: "admin" | "member" | "viewer",
  ) =>
    request<WorkspaceMember>(`/api/v1/workspace-members/${membershipId}`, {
      method: "PATCH",
      workspaceId,
      body: JSON.stringify({ role }),
    }),
  suspendWorkspaceMember: (workspaceId: string, membershipId: string) =>
    request<WorkspaceMember>(
      `/api/v1/workspace-members/${membershipId}:suspend`,
      { method: "POST", workspaceId },
    ),
  listWorkspaceInvitations: (workspaceId: string) =>
    request<WorkspaceInvitation[]>("/api/v1/workspace-invitations", {
      workspaceId,
    }),
  createWorkspaceInvitation: (
    workspaceId: string,
    payload: { email: string; role: "admin" | "member" | "viewer" },
  ) =>
    request<WorkspaceInvitationSecret>("/api/v1/workspace-invitations", {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  revokeWorkspaceInvitation: (workspaceId: string, invitationId: string) =>
    request<WorkspaceInvitation>(
      `/api/v1/workspace-invitations/${invitationId}:revoke`,
      { method: "POST", workspaceId },
    ),
  acceptWorkspaceInvitation: (inviteToken: string) =>
    request<WorkspaceMember>("/api/v1/workspace-invitations:accept", {
      method: "POST",
      body: JSON.stringify({ invite_token: inviteToken }),
    }),
  listWorkspaceAccessEvents: (workspaceId: string, limit = 50) =>
    request<WorkspaceAccessEvent[]>(
      `/api/v1/workspace-access-events?limit=${limit}`,
      { workspaceId },
    ),
  listDataMarketListings: (workspaceId: string) =>
    request<DataMarketListing[]>("/api/v1/data-market/listings", { workspaceId }),
  createDataMarketListing: (
    workspaceId: string,
    datasetVersionId: string,
    payload: DataMarketListingCreate,
  ) =>
    request<DataMarketListing>(
      `/api/v1/dataset-versions/${datasetVersionId}/data-listing`,
      { method: "POST", workspaceId, body: JSON.stringify(payload) },
    ),
  getProviderDashboard: (workspaceId: string, limit = 50) =>
    request<ProviderDashboard>(`/api/v1/provider/dashboard?limit=${limit}`, {
      workspaceId,
    }),
  updateProviderProfile: (workspaceId: string, payload: ProviderProfileUpdate) =>
    request<ProviderProfile>("/api/v1/provider/profile", {
      method: "PATCH",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  listProjects: (workspaceId: string) =>
    request<Project[]>("/api/v1/projects", { workspaceId }),
  createProject: (
    workspaceId: string,
    payload: { slug: string; name: string; task_type: string },
  ) =>
    request<Project>("/api/v1/projects", {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  pauseProject: (workspaceId: string, projectId: string) =>
    request<Project>(`/api/v1/projects/${projectId}:pause`, {
      method: "POST",
      workspaceId,
    }),
  resumeProject: (workspaceId: string, projectId: string) =>
    request<Project>(`/api/v1/projects/${projectId}:resume`, {
      method: "POST",
      workspaceId,
    }),
  archiveProject: (workspaceId: string, projectId: string) =>
    request<Project>(`/api/v1/projects/${projectId}:archive`, {
      method: "POST",
      workspaceId,
    }),
  listDatasets: (workspaceId: string, projectId: string) =>
    request<Dataset[]>(`/api/v1/projects/${projectId}/datasets`, { workspaceId }),
  createDataset: (workspaceId: string, projectId: string, payload: { name: string }) =>
    request<Dataset>(`/api/v1/projects/${projectId}/datasets`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  deleteDataset: (workspaceId: string, datasetId: string) =>
    request<void>(`/api/v1/datasets/${datasetId}`, {
      method: "DELETE",
      workspaceId,
    }),
  listAssets: (workspaceId: string, datasetId: string) =>
    request<Asset[]>(`/api/v1/datasets/${datasetId}/assets`, { workspaceId }),
  getAssetContent: async (
    workspaceId: string,
    datasetId: string,
    assetId: string,
    signal?: AbortSignal,
  ) => {
    if (isHostedPreview()) {
      const response = await fetch("/catalog-vision-samples.png", { signal });
      if (!response.ok) throw new Error("演示素材加载失败");
      return response.blob();
    }

    let response: Response;
    try {
      response = await fetchWithTimeout(
        `${apiBaseUrl()}/api/v1/datasets/${datasetId}/assets/${assetId}/content`,
        {
          headers: (() => {
            const headers = new Headers({ "X-Workspace-ID": workspaceId });
            addAccessToken(headers);
            return headers;
          })(),
          signal,
        },
      );
    } catch (error) {
      if (signal?.aborted) throw error;
      if (isRequestTimeout(error)) throw new Error("素材预览加载超时");
      throw new Error("素材预览加载失败");
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw apiErrorForResponse(response.status, payload?.detail ?? null);
    }
    return response.blob();
  },
  listVersions: (workspaceId: string, datasetId: string) =>
    request<DatasetVersion[]>(`/api/v1/datasets/${datasetId}/versions`, { workspaceId }),
  updateDatasetClassMap: (
    workspaceId: string,
    datasetId: string,
    classMap: Record<string, string>,
  ) =>
    request<Dataset>(`/api/v1/datasets/${datasetId}/classes`, {
      method: "PATCH",
      workspaceId,
      body: JSON.stringify({ class_map: classMap }),
    }),
  getDatasetVersionQualityReport: (workspaceId: string, versionId: string) =>
    request<DatasetVersionQualityReport>(
      `/api/v1/dataset-versions/${versionId}/quality-report`,
      { workspaceId },
    ),
  createUploadIntent: (
    workspaceId: string,
    datasetId: string,
    payload: {
      filename: string;
      content_type: string;
      byte_size: number;
      checksum_sha256: string;
    },
  ) =>
    request<{
      method: "PUT";
      upload_url: string;
      object_key: string;
      headers: Record<string, string>;
      expires_in: number;
    }>(`/api/v1/datasets/${datasetId}/uploads`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  registerAsset: (
    workspaceId: string,
    datasetId: string,
    payload: {
      object_key: string;
      media_type: string;
      checksum_sha256: string;
      byte_size: number;
      width: number | null;
      height: number | null;
    },
  ) =>
    request<Asset>(`/api/v1/datasets/${datasetId}/assets`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  listSourceVideos: (workspaceId: string, datasetId: string) =>
    request<Asset[]>(`/api/v1/datasets/${datasetId}/source-videos`, { workspaceId }),
  listVideoExtractions: (workspaceId: string, datasetId: string) =>
    request<VideoExtractionJob[]>(`/api/v1/datasets/${datasetId}/video-extractions`, {
      workspaceId,
    }),
  createVideoExtraction: (
    workspaceId: string,
    datasetId: string,
    idempotencyKey: string,
    payload: {
      source_asset_id: string;
      frame_interval_ms: number;
      deduplicate: boolean;
    },
  ) =>
    request<VideoExtractionJob>(`/api/v1/datasets/${datasetId}/video-extractions`, {
      method: "POST",
      workspaceId,
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    }),
  cancelVideoExtraction: (workspaceId: string, jobId: string) =>
    request<VideoExtractionJob>(`/api/v1/video-extractions/${jobId}:cancel`, {
      method: "POST",
      workspaceId,
    }),
  createAnnotationTaskFromVideoExtraction: (
    workspaceId: string,
    datasetId: string,
    jobId: string,
    name: string,
    classMap: Record<string, string>,
  ) =>
    request<AnnotationTask>(
      `/api/v1/datasets/${datasetId}/video-extractions/${jobId}/annotation-task`,
      {
        method: "PUT",
        workspaceId,
        body: JSON.stringify({ name, class_map: classMap }),
      },
    ),
  updateDatasetItem: (
    workspaceId: string,
    datasetId: string,
    assetId: string,
    split: "train" | "valid" | "test",
  ) =>
    request<Asset>(`/api/v1/datasets/${datasetId}/items/${assetId}`, {
      method: "PATCH",
      workspaceId,
      body: JSON.stringify({ split }),
    }),
  createAnnotationUploadIntent: (
    workspaceId: string,
    datasetId: string,
    assetId: string,
    payload: {
      filename: string;
      byte_size: number;
      checksum_sha256: string;
    },
  ) =>
    request<{
      method: "PUT";
      upload_url: string;
      object_key: string;
      headers: Record<string, string>;
      expires_in: number;
    }>(`/api/v1/datasets/${datasetId}/items/${assetId}/annotation-uploads`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  registerAnnotation: (
    workspaceId: string,
    datasetId: string,
    assetId: string,
    payload: {
      object_key: string;
      byte_size: number;
      checksum_sha256: string;
    },
  ) =>
    request<Asset>(`/api/v1/datasets/${datasetId}/items/${assetId}/annotation`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  getAnnotationContent: (
    workspaceId: string,
    datasetId: string,
    assetId: string,
    signal?: AbortSignal,
  ) =>
    request<string>(`/api/v1/datasets/${datasetId}/items/${assetId}/annotation`, {
      workspaceId,
      signal,
      headers: { Accept: "text/plain" },
    }),
  listAnnotationTasks: (workspaceId: string, datasetId: string) =>
    request<AnnotationTask[]>(`/api/v1/datasets/${datasetId}/annotation-tasks`, {
      workspaceId,
    }),
  getAnnotationTask: (workspaceId: string, datasetId: string, taskId: string) =>
    request<AnnotationTask>(
      `/api/v1/datasets/${datasetId}/annotation-tasks/${taskId}`,
      { workspaceId },
    ),
  listAnnotationTaskAssets: (workspaceId: string, datasetId: string, taskId: string) =>
    request<Asset[]>(
      `/api/v1/datasets/${datasetId}/annotation-tasks/${taskId}/assets`,
      { workspaceId },
    ),
  createAnnotationTask: (
    workspaceId: string,
    datasetId: string,
    payload: {
      name: string;
      method: "manual" | "smart";
      asset_scope: "unlabeled" | "all";
      class_map: Record<string, string>;
    },
  ) =>
    request<AnnotationTask>(`/api/v1/datasets/${datasetId}/annotation-tasks`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  updateAnnotationTaskStatus: (
    workspaceId: string,
    datasetId: string,
    taskId: string,
    status: "review" | "done",
  ) =>
    request<AnnotationTask>(
      `/api/v1/datasets/${datasetId}/annotation-tasks/${taskId}`,
      {
        method: "PATCH",
        workspaceId,
        body: JSON.stringify({ status }),
      },
    ),
  downloadAnnotationTaskPackage: async (
    workspaceId: string,
    datasetId: string,
    taskId: string,
  ) => {
    let response: Response;
    try {
      response = await fetchWithTimeout(
        `${apiBaseUrl()}/api/v1/datasets/${datasetId}/annotation-tasks/${taskId}/yolo-package`,
        {
          headers: (() => {
            const headers = new Headers({ "X-Workspace-ID": workspaceId });
            addAccessToken(headers);
            return headers;
          })(),
        },
        ARTIFACT_REQUEST_TIMEOUT_MS,
      );
    } catch (error) {
      if (isRequestTimeout(error)) throw new Error("任务包导出超时，请稍后重试");
      throw new Error("无法连接 SenseMu API，请确认本地服务已启动");
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw apiErrorForResponse(response.status, payload?.detail ?? null);
    }
    const objectUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `annotation-task-${taskId}.zip`;
    link.click();
    URL.revokeObjectURL(objectUrl);
  },
  createAnnotationTaskYoloImportUploadIntent: (
    workspaceId: string,
    datasetId: string,
    taskId: string,
    payload: { filename: string; byte_size: number; checksum_sha256: string },
  ) =>
    request<{
      method: "PUT";
      upload_url: string;
      object_key: string;
      headers: Record<string, string>;
      expires_in: number;
    }>(
      `/api/v1/datasets/${datasetId}/annotation-tasks/${taskId}/yolo-import-uploads`,
      { method: "POST", workspaceId, body: JSON.stringify(payload) },
    ),
  importAnnotationTaskYoloPackage: (
    workspaceId: string,
    datasetId: string,
    taskId: string,
    payload: { object_key: string; byte_size: number; checksum_sha256: string },
  ) =>
    request<{ task: AnnotationTask; imported_asset_count: number }>(
      `/api/v1/datasets/${datasetId}/annotation-tasks/${taskId}/yolo-import`,
      { method: "POST", workspaceId, body: JSON.stringify(payload) },
    ),
  freezeDataset: (
    workspaceId: string,
    datasetId: string,
    classMap: Record<string, string>,
  ) =>
    request<DatasetVersion>(`/api/v1/datasets/${datasetId}/versions:freeze`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify({ class_map: classMap }),
    }),
  listTrainingEngines: () => request<TrainingEngine[]>("/api/v1/training/engines"),
  listTrainingRuns: (workspaceId: string, projectId: string) =>
    request<TrainingRun[]>(`/api/v1/projects/${projectId}/training-runs`, { workspaceId }),
  listRunEvents: (workspaceId: string, runId: string) =>
    request<RunEvent[]>(`/api/v1/training-runs/${runId}/events`, { workspaceId }),
  getTrainingReport: (workspaceId: string, runId: string) =>
    request<TrainingReport>(`/api/v1/training-runs/${runId}/report`, { workspaceId }),
  getTrainingClassMetrics: (workspaceId: string, runId: string) =>
    request<TrainingClassMetrics>(`/api/v1/training-runs/${runId}/class-metrics`, { workspaceId }),
  getTrainingVisualization: (
    workspaceId: string,
    runId: string,
    visualization: TrainingVisualizationName,
  ) =>
    requestBlob(`/api/v1/training-runs/${runId}/visualizations/${visualization}`, { workspaceId }),
  createTrainingRun: (
    workspaceId: string,
    projectId: string,
    idempotencyKey: string,
    payload: {
      dataset_version_id: string;
      engine: string;
      executor: string;
      recipe: Record<string, string | number>;
    },
  ) =>
    request<TrainingRun>(`/api/v1/projects/${projectId}/training-runs`, {
      method: "POST",
      workspaceId,
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    }),
  cancelTrainingRun: (workspaceId: string, runId: string) =>
    request<TrainingRun>(`/api/v1/training-runs/${runId}:cancel`, {
      method: "POST",
      workspaceId,
    }),
  dispatchTrainingRun: (workspaceId: string, runId: string) =>
    request<TrainingRun>(`/api/v1/training-runs/${runId}:dispatch`, {
      method: "POST",
      workspaceId,
    }),
  listModelVersions: (workspaceId: string, projectId: string) =>
    request<ModelVersion[]>(`/api/v1/projects/${projectId}/model-versions`, { workspaceId }),
  listEvaluationPolicies: (workspaceId: string, projectId: string) =>
    request<EvaluationPolicy[]>(`/api/v1/projects/${projectId}/evaluation-policies`, {
      workspaceId,
    }),
  createEvaluationPolicy: (
    workspaceId: string,
    projectId: string,
    payload: { name: string; rules: EvaluationRule[] },
  ) =>
    request<EvaluationPolicy>(`/api/v1/projects/${projectId}/evaluation-policies`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  listEvaluations: (workspaceId: string, projectId: string) =>
    request<Evaluation[]>(`/api/v1/projects/${projectId}/evaluations`, { workspaceId }),
  listAcceptanceRuns: (workspaceId: string, projectId: string) =>
    request<TrainingRun[]>(`/api/v1/projects/${projectId}/acceptance-runs`, {
      workspaceId,
    }),
  createAcceptanceRun: (
    workspaceId: string,
    projectId: string,
    modelVersionId: string,
    idempotencyKey: string,
    payload: {
      dataset_version_id: string;
      image_size: number;
      batch_size: number;
    },
  ) =>
    request<TrainingRun>(
      `/api/v1/projects/${projectId}/model-versions/${modelVersionId}/acceptance-runs`,
      {
        method: "POST",
        workspaceId,
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(payload),
      },
    ),
  evaluateModelVersion: (workspaceId: string, modelVersionId: string) =>
    request<Evaluation>(`/api/v1/model-versions/${modelVersionId}:evaluate`, {
      method: "POST",
      workspaceId,
    }),
  listDeployments: (workspaceId: string, projectId: string) =>
    request<Deployment[]>(`/api/v1/projects/${projectId}/deployments`, { workspaceId }),
  listBatchInferenceRuns: (workspaceId: string, projectId: string) =>
    request<BatchInferenceRun[]>(`/api/v1/projects/${projectId}/batch-inference-runs`, {
      workspaceId,
    }),
  createBatchInferenceRun: (
    workspaceId: string,
    projectId: string,
    idempotencyKey: string,
    payload: {
      deployment_id: string;
      dataset_version_id: string;
      source_split: "all" | "train" | "valid" | "test";
      parameters: {
        confidence: number;
        iou: number;
        max_detections: number;
        image_size: number;
      };
    },
  ) =>
    request<BatchInferenceRun>(`/api/v1/projects/${projectId}/batch-inference-runs`, {
      method: "POST",
      workspaceId,
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(payload),
    }),
  downloadBatchInferenceOutput: async (workspaceId: string, runId: string) => {
    let response: Response;
    try {
      response = await fetchWithTimeout(
        `${apiBaseUrl()}/api/v1/batch-inference-runs/${runId}/output`,
        {
          headers: (() => {
            const headers = new Headers({ "X-Workspace-ID": workspaceId });
            addAccessToken(headers);
            return headers;
          })(),
        },
        ARTIFACT_REQUEST_TIMEOUT_MS,
      );
    } catch (error) {
      if (isRequestTimeout(error)) throw new Error("结果下载超时，请稍后重试");
      throw new Error("无法连接 SenseMu API，请确认本地服务已启动");
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw apiErrorForResponse(response.status, payload?.detail ?? null);
    }
    const objectUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `batch-inference-${runId}.ndjson`;
    link.click();
    URL.revokeObjectURL(objectUrl);
  },
  createDeployment: (
    workspaceId: string,
    projectId: string,
    payload: {
      model_version_id: string;
      name: string;
      endpoint_slug: string;
      environment: "staging" | "production";
    },
  ) =>
    request<DeploymentSecret>(`/api/v1/projects/${projectId}/deployments`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  disableDeployment: (workspaceId: string, deploymentId: string) =>
    request<Deployment>(`/api/v1/deployments/${deploymentId}:disable`, {
      method: "POST",
      workspaceId,
    }),
  listCapabilitySpecs: (workspaceId: string, projectId: string) =>
    request<CapabilitySpec[]>(`/api/v1/projects/${projectId}/capability-specs`, {
      workspaceId,
    }),
  createCapabilitySpec: (
    workspaceId: string,
    deploymentId: string,
    payload: {
      capability_slug: string;
      display_name: string;
      problem_definition: string;
      input: CapabilityInputSpec;
      output: CapabilityOutputSpec;
      applicability: CapabilityApplicabilitySpec;
      delivery: CapabilityDeliverySpec;
    },
  ) =>
    request<CapabilitySpec>(`/api/v1/deployments/${deploymentId}/capability-spec`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  listWorkflowSpecs: (workspaceId: string, projectId: string) =>
    request<WorkflowSpec[]>(`/api/v1/projects/${projectId}/workflow-specs`, {
      workspaceId,
    }),
  listVisionEvents: (workspaceId: string, projectId: string, limit = 20) =>
    request<VisionEvent[]>(
      `/api/v1/projects/${projectId}/vision-events?limit=${limit}`,
      { workspaceId },
    ),
  replayVisionEvent: (workspaceId: string, projectId: string, eventId: string) =>
    request<VisionEventReplay>(
      `/api/v1/projects/${projectId}/vision-events/${eventId}/replay`,
      { workspaceId },
    ),
  createWorkflowSpec: (
    workspaceId: string,
    projectId: string,
    payload: {
      workflow_slug: string;
      display_name: string;
      capability_spec_id: string;
      event_types: string[];
      deduplication_window_seconds: number;
      webhook_url: string;
    },
  ) =>
    request<WorkflowSpec>(`/api/v1/projects/${projectId}/workflow-specs`, {
      method: "POST",
      workspaceId,
      body: JSON.stringify(payload),
    }),
  enableDeployment: (workspaceId: string, deploymentId: string) =>
    request<Deployment>(`/api/v1/deployments/${deploymentId}:enable`, {
      method: "POST",
      workspaceId,
    }),
  rotateDeploymentKey: (workspaceId: string, deploymentId: string) =>
    request<DeploymentSecret>(`/api/v1/deployments/${deploymentId}:rotate-key`, {
      method: "POST",
      workspaceId,
    }),
  listMarketplaceListings: (workspaceId: string) =>
    request<MarketplaceListing[]>("/api/v1/marketplace/listings", { workspaceId }),
  listMarketplaceSubmissions: (workspaceId: string) =>
    request<MarketplaceListingSubmission[]>("/api/v1/marketplace/submissions", {
      workspaceId,
    }),
  createMarketplaceListing: (
    workspaceId: string,
    capabilitySpecId: string,
    payload: {
      title: string;
      summary: string;
      price_per_1000_cents: number;
      monthly_quota_units: number;
    },
  ) =>
    request<MarketplaceListing>(
      `/api/v1/capability-specs/${capabilitySpecId}/marketplace-listing`,
      {
        method: "POST",
        workspaceId,
        body: JSON.stringify(payload),
      },
    ),
  subscribeMarketplaceListing: (workspaceId: string, listingId: string) =>
    request<MarketplaceCheckout>(
      `/api/v1/marketplace/listings/${listingId}/subscriptions`,
      { method: "POST", workspaceId },
    ),
  listMarketplaceSubscriptions: (workspaceId: string) =>
    request<MarketplaceSubscription[]>("/api/v1/marketplace/subscriptions", {
      workspaceId,
    }),
  claimMarketplaceSubscriptionKey: (workspaceId: string, subscriptionId: string) =>
    request<MarketplaceSubscriptionSecret>(
      `/api/v1/marketplace/subscriptions/${subscriptionId}:claim-key`,
      { method: "POST", workspaceId },
    ),
  rotateMarketplaceSubscriptionKey: (workspaceId: string, subscriptionId: string) =>
    request<MarketplaceSubscriptionSecret>(
      `/api/v1/marketplace/subscriptions/${subscriptionId}:rotate-key`,
      { method: "POST", workspaceId },
    ),
  listMarketplaceUsageRecords: (workspaceId: string, limit = 50) =>
    request<MarketplaceUsageRecord[]>(
      `/api/v1/marketplace/usage-records?limit=${limit}`,
      { workspaceId },
    ),
  getMarketplaceBilling: (workspaceId: string, limit = 50) =>
    request<MarketplaceBilling>(`/api/v1/marketplace/billing?limit=${limit}`, {
      workspaceId,
    }),
  getInferenceHealth: async (deployment: Deployment): Promise<InferenceHealth> => {
    if (isHostedPreview()) {
      return {
        status: "not_ready",
        control_plane: { status: "ready" },
        runtime: { configured: false, status: "not_configured" },
      };
    }
    let healthUrl: string;
    try {
      healthUrl = `${new URL(deployment.endpoint_url).origin}/health/ready`;
    } catch {
      throw new Error("推理服务地址无效，无法检查运行状态");
    }
    let response: Response;
    try {
      response = await fetchWithTimeout(healthUrl, { cache: "no-store" }, 5_000);
    } catch (error) {
      if (isRequestTimeout(error)) throw new Error("推理网关状态检查超时");
      throw new Error("无法连接推理网关");
    }
    const payload = (await response.json().catch(() => null)) as InferenceHealth | null;
    if (!payload || !payload.status) {
      throw new Error(`运行状态响应无效 (${response.status})`);
    }
    return payload;
  },
  prewarmDeployment: async (
    deployment: Deployment,
    apiKey: string,
  ): Promise<PrewarmResponse> => {
    const prewarmUrl = deployment.endpoint_url.replace(/:predict$/, ":prewarm");
    let response: Response;
    try {
      response = await fetchWithTimeout(
        prewarmUrl,
        {
          method: "POST",
          headers: {
            "X-API-Key": apiKey,
            "X-Request-ID": `webwarm-${crypto.randomUUID()}`,
          },
        },
        INFERENCE_REQUEST_TIMEOUT_MS,
      );
    } catch (error) {
      if (isRequestTimeout(error)) throw new Error("模型预热超时，请稍后重试");
      throw new Error("无法连接推理网关，请确认网关和运行时已启动");
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { detail?: string | { message?: string } }
        | null;
      const detail = payload?.detail;
      throw new Error(
        typeof detail === "string"
          ? detail
          : detail?.message ?? `模型预热失败 (${response.status})`,
      );
    }
    return (await response.json()) as PrewarmResponse;
  },
  predictDeployment: async (
    deployment: Deployment,
    apiKey: string,
    imageDataUrl: string,
    confidence: number,
  ): Promise<InferenceResponse> => {
    let response: Response;
    try {
      response = await fetchWithTimeout(
        deployment.endpoint_url,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": apiKey,
            "X-Request-ID": `webtest-${crypto.randomUUID()}`,
          },
          body: JSON.stringify({
            inputs: [imageDataUrl],
            parameters: { confidence },
          }),
        },
        INFERENCE_REQUEST_TIMEOUT_MS,
      );
    } catch (error) {
      if (isRequestTimeout(error)) throw new Error("推理请求超时，请稍后重试");
      throw new Error("无法连接推理网关，请确认网关和运行时已启动");
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { detail?: string | { message?: string } }
        | null;
      const detail = payload?.detail;
      throw new Error(
        typeof detail === "string"
          ? detail
          : detail?.message ?? `推理请求失败 (${response.status})`,
      );
    }
    return (await response.json()) as InferenceResponse;
  },
};
