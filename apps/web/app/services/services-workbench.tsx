"use client";

import {
  AlertCircle,
  Ban,
  BrainCircuit,
  Check,
  Clipboard,
  Cpu,
  Download,
  Files,
  Flame,
  Gauge,
  Image as ImageIcon,
  KeyRound,
  LoaderCircle,
  Play,
  RefreshCw,
  Rocket,
  ScanSearch,
  ServerCog,
  ShieldCheck,
  UploadCloud,
  Video,
  Webhook,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from "react";
import {
  catalogApi,
  type CapabilitySpec,
  type BatchInferenceRun,
  type DatasetVersion,
  type Deployment,
  type Evaluation,
  type EvaluationPolicy,
  type InferenceHealth,
  type InferenceResponse,
  type ModelVersion,
  type Project,
  type VisionEvent,
  type VisionEventReplay,
  type WorkflowSpec,
  type Workspace,
} from "../../lib/catalog-api";
import { ProjectChrome } from "../studio/project-chrome";

type VisibleSecret = { deploymentId: string; apiKey: string };
type ServicesView = "live" | "batch" | "publish" | "events";

const contractsByTask: Record<string, string> = {
  "object-detection": "detections.v1",
  classification: "classification.v1",
  segmentation: "mask.v1",
  pose: "keypoints.v1",
  ocr: "text.v1",
};

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 100);
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function listItems(value: string): string[] {
  return value
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function deliveryStatusLabel(status: VisionEvent["delivery_status"]): string {
  return {
    pending: "等待投递",
    delivering: "投递中",
    retrying: "等待重试",
    delivered: "已投递",
    failed: "投递失败",
  }[status];
}

function batchSourceSplitLabel(value: unknown): string {
  return {
    all: "全部划分",
    train: "训练集",
    valid: "验证集",
    test: "测试集",
  }[String(value)] ?? "未知划分";
}

export function ServicesWorkbench() {
  const searchParams = useSearchParams();
  const requestedProjectId = searchParams.get("project");
  const requestedModelVersionId = searchParams.get("model");
  const requestedDeploymentId = searchParams.get("deployment");
  const requestedView = searchParams.get("view");
  const view: ServicesView =
    requestedView === "batch" || requestedView === "publish" || requestedView === "events"
      ? requestedView
      : "live";
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [modelVersions, setModelVersions] = useState<ModelVersion[]>([]);
  const [policies, setPolicies] = useState<EvaluationPolicy[]>([]);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [capabilitySpecs, setCapabilitySpecs] = useState<CapabilitySpec[]>([]);
  const [workflowSpecs, setWorkflowSpecs] = useState<WorkflowSpec[]>([]);
  const [visionEvents, setVisionEvents] = useState<VisionEvent[]>([]);
  const [frozenDatasetVersions, setFrozenDatasetVersions] = useState<Array<DatasetVersion & { datasetName: string }>>([]);
  const [batchInferenceRuns, setBatchInferenceRuns] = useState<BatchInferenceRun[]>([]);
  const [eventReplay, setEventReplay] = useState<VisionEventReplay | null>(null);
  const [replayBusy, setReplayBusy] = useState<string | null>(null);
  const [modelVersionId, setModelVersionId] = useState("");
  const [showPolicyForm, setShowPolicyForm] = useState(false);
  const [policyName, setPolicyName] = useState("基础发布检查");
  const [policyMetric, setPolicyMetric] = useState("metrics/mAP50(B)");
  const [policyThreshold, setPolicyThreshold] = useState("0.8");
  const [serviceName, setServiceName] = useState("PPE 检测服务");
  const [endpointSlug, setEndpointSlug] = useState("ppe-detector");
  const [environment, setEnvironment] = useState<"staging" | "production">("production");
  const [capabilityDeploymentId, setCapabilityDeploymentId] = useState("");
  const [capabilitySlug, setCapabilitySlug] = useState("ppe-compliance");
  const [capabilityName, setCapabilityName] = useState("PPE 合规检测");
  const [capabilityProblem, setCapabilityProblem] = useState("识别固定摄像头画面中的安全帽与反光衣违规行为，用于现场安全巡检与告警。");
  const [capabilityClasses, setCapabilityClasses] = useState("person, hardhat, safety_vest");
  const [capabilityEvents, setCapabilityEvents] = useState("missing_hardhat, missing_safety_vest");
  const [verifiedScenes, setVerifiedScenes] = useState("construction-site, warehouse");
  const [unsupportedConditions, setUnsupportedConditions] = useState("严重逆光, 严重遮挡");
  const [captureConstraints, setCaptureConstraints] = useState("固定摄像头，人员高度建议不低于 80 像素；严重逆光和遮挡需单独验收。");
  const [deliveryProfiles, setDeliveryProfiles] = useState<Array<"shared-api" | "dedicated-endpoint">>(["shared-api"]);
  const [workflowCapabilitySpecId, setWorkflowCapabilitySpecId] = useState("");
  const [workflowSlug, setWorkflowSlug] = useState("ppe-alerts");
  const [workflowName, setWorkflowName] = useState("PPE 违规告警");
  const [workflowEvents, setWorkflowEvents] = useState("missing_hardhat, missing_safety_vest");
  const [workflowDeduplicationWindow, setWorkflowDeduplicationWindow] = useState("60");
  const [workflowWebhookUrl, setWorkflowWebhookUrl] = useState("");
  const [visibleSecret, setVisibleSecret] = useState<VisibleSecret | null>(null);
  const [testBusy, setTestBusy] = useState(false);
  const [prewarmBusy, setPrewarmBusy] = useState(false);
  const [healthBusy, setHealthBusy] = useState(false);
  const [inferenceHealth, setInferenceHealth] = useState<InferenceHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [testDeploymentId, setTestDeploymentId] = useState("");
  const [testApiKey, setTestApiKey] = useState("");
  const [testImage, setTestImage] = useState("");
  const [testImageName, setTestImageName] = useState("");
  const [testConfidence, setTestConfidence] = useState(0.25);
  const [inferenceResult, setInferenceResult] = useState<InferenceResponse | null>(null);
  const [batchDeploymentId, setBatchDeploymentId] = useState("");
  const [batchDatasetVersionId, setBatchDatasetVersionId] = useState("");
  const [batchSourceSplit, setBatchSourceSplit] = useState<"all" | "train" | "valid" | "test">("all");
  const [batchConfidence, setBatchConfidence] = useState(0.25);
  const [batchBusy, setBatchBusy] = useState(false);

  async function refresh(selectedWorkspace: Workspace, selectedProject: Project) {
    const [nextModels, nextPolicies, nextEvaluations, nextDeployments, nextCapabilitySpecs, nextWorkflowSpecs, nextVisionEvents, nextBatchRuns, datasets] = await Promise.all([
      catalogApi.listModelVersions(selectedWorkspace.id, selectedProject.id),
      catalogApi.listEvaluationPolicies(selectedWorkspace.id, selectedProject.id),
      catalogApi.listEvaluations(selectedWorkspace.id, selectedProject.id),
      catalogApi.listDeployments(selectedWorkspace.id, selectedProject.id),
      catalogApi.listCapabilitySpecs(selectedWorkspace.id, selectedProject.id),
      catalogApi.listWorkflowSpecs(selectedWorkspace.id, selectedProject.id),
      catalogApi.listVisionEvents(selectedWorkspace.id, selectedProject.id),
      catalogApi.listBatchInferenceRuns(selectedWorkspace.id, selectedProject.id),
      catalogApi.listDatasets(selectedWorkspace.id, selectedProject.id),
    ]);
    const versionGroups = await Promise.all(
      datasets.map(async (dataset) =>
        (await catalogApi.listVersions(selectedWorkspace.id, dataset.id)).map((version) => ({
          ...version,
          datasetName: dataset.name,
        })),
      ),
    );
    setModelVersions(nextModels);
    setPolicies(nextPolicies);
    setEvaluations(nextEvaluations);
    setDeployments(nextDeployments);
    setCapabilitySpecs(nextCapabilitySpecs);
    setWorkflowSpecs(nextWorkflowSpecs);
    setVisionEvents(nextVisionEvents);
    setBatchInferenceRuns(nextBatchRuns);
    setFrozenDatasetVersions(versionGroups.flat().filter((version) => version.status === "frozen"));
    setEventReplay(null);
  }

  useEffect(() => {
    void catalogApi
      .listWorkspaces()
      .then(async (workspaces) => {
        const selectedWorkspace = workspaces[0] ?? null;
        setWorkspace(selectedWorkspace);
        if (!selectedWorkspace) return;
        const projects = await catalogApi.listProjects(selectedWorkspace.id);
        const selectedProject = projects.find((item) => item.id === requestedProjectId) ?? projects[0] ?? null;
        setProject(selectedProject);
        if (selectedProject) await refresh(selectedWorkspace, selectedProject);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "发布与调用加载失败"))
      .finally(() => setLoading(false));
  }, [requestedProjectId]);

  const activePolicy = policies.find((policy) => policy.is_active) ?? null;
  const approvedModelIds = useMemo(
    () =>
      new Set(
        evaluations
          .filter(
            (evaluation) =>
              evaluation.policy_id === activePolicy?.id && evaluation.verdict === "approved",
          )
          .map((evaluation) => evaluation.model_version_id),
      ),
    [activePolicy, evaluations],
  );
  const eligibleModels = useMemo(
    () => modelVersions.filter((model) => approvedModelIds.has(model.id)),
    [approvedModelIds, modelVersions],
  );
  const publishedDeployments = useMemo(
    () => deployments.filter((deployment) => deployment.status === "published"),
    [deployments],
  );
  const batchEligibleDeployments = useMemo(
    () => publishedDeployments.filter((deployment) => deployment.task_type === "object-detection"),
    [publishedDeployments],
  );
  const deploymentsWithCapabilitySpec = useMemo(
    () => new Set(capabilitySpecs.map((spec) => spec.deployment_id)),
    [capabilitySpecs],
  );
  const capabilityEligibleDeployments = useMemo(
    () =>
      deployments.filter(
        (deployment) =>
          deployment.status === "published" &&
          deployment.environment === "production" &&
          !deploymentsWithCapabilitySpec.has(deployment.id),
      ),
    [deployments, deploymentsWithCapabilitySpec],
  );
  const workflowEligibleCapabilities = useMemo(
    () => capabilitySpecs.filter((spec) => spec.output.business_events.length > 0),
    [capabilitySpecs],
  );
  const selectedTestDeployment = useMemo(
    () => publishedDeployments.find((deployment) => deployment.id === testDeploymentId) ?? null,
    [publishedDeployments, testDeploymentId],
  );

  async function replayVisionEvent(event: VisionEvent) {
    if (!workspace || !project) return;
    if (eventReplay?.event_id === event.id) {
      setEventReplay(null);
      return;
    }
    setReplayBusy(event.id);
    setError(null);
    try {
      setEventReplay(
        await catalogApi.replayVisionEvent(workspace.id, project.id, event.id),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "事件回放加载失败");
    } finally {
      setReplayBusy(null);
    }
  }

  useEffect(() => {
    setModelVersionId((current) =>
      eligibleModels.some((model) => model.id === requestedModelVersionId)
        ? requestedModelVersionId ?? ""
        : eligibleModels.some((model) => model.id === current)
          ? current
          : eligibleModels[0]?.id ?? "",
    );
  }, [eligibleModels, requestedModelVersionId]);

  useEffect(() => {
    setTestDeploymentId((current) =>
      publishedDeployments.some((deployment) => deployment.id === requestedDeploymentId)
        ? requestedDeploymentId ?? ""
        : publishedDeployments.some((deployment) => deployment.id === current)
        ? current
        : publishedDeployments[0]?.id ?? "",
    );
  }, [publishedDeployments, requestedDeploymentId]);

  useEffect(() => {
    setBatchDeploymentId((current) =>
      batchEligibleDeployments.some((deployment) => deployment.id === current)
        ? current
        : batchEligibleDeployments[0]?.id ?? "",
    );
  }, [batchEligibleDeployments]);

  useEffect(() => {
    setBatchDatasetVersionId((current) =>
      frozenDatasetVersions.some((version) => version.id === current)
        ? current
        : frozenDatasetVersions[0]?.id ?? "",
    );
  }, [frozenDatasetVersions]);

  useEffect(() => {
    setCapabilityDeploymentId((current) =>
      capabilityEligibleDeployments.some((deployment) => deployment.id === current)
        ? current
        : capabilityEligibleDeployments[0]?.id ?? "",
    );
  }, [capabilityEligibleDeployments]);

  useEffect(() => {
    setWorkflowCapabilitySpecId((current) =>
      workflowEligibleCapabilities.some((spec) => spec.id === current)
        ? current
        : workflowEligibleCapabilities[0]?.id ?? "",
    );
  }, [workflowEligibleCapabilities]);

  useEffect(() => {
    if (!selectedTestDeployment) {
      setInferenceHealth(null);
      setHealthError(null);
      return;
    }
    let active = true;
    setHealthBusy(true);
    setHealthError(null);
    void catalogApi
      .getInferenceHealth(selectedTestDeployment)
      .then((health) => {
        if (active) setInferenceHealth(health);
      })
      .catch((reason) => {
        if (active) {
          setInferenceHealth(null);
          setHealthError(reason instanceof Error ? reason.message : "运行状态检查失败");
        }
      })
      .finally(() => {
        if (active) setHealthBusy(false);
      });
    return () => {
      active = false;
    };
  }, [selectedTestDeployment]);

  async function createDeployment(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !project || !modelVersionId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const deployment = await catalogApi.createDeployment(workspace.id, project.id, {
        model_version_id: modelVersionId,
        name: serviceName,
        endpoint_slug: endpointSlug,
        environment,
      });
      setVisibleSecret({ deploymentId: deployment.id, apiKey: deployment.api_key });
      setTestDeploymentId(deployment.id);
      setTestApiKey(deployment.api_key);
      await refresh(workspace, project);
      setNotice("服务已发布，请立即保存首次显示的 API 密钥");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "服务发布失败");
    } finally {
      setBusy(false);
    }
  }

  async function createPolicy(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !project) return;
    const threshold = Number(policyThreshold);
    if (!Number.isFinite(threshold)) {
      setError("最低要求必须是数字");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const policy = await catalogApi.createEvaluationPolicy(workspace.id, project.id, {
        name: policyName,
        rules: [{ metric: policyMetric, operator: ">=", threshold, label: null }],
      });
      await refresh(workspace, project);
      setShowPolicyForm(false);
      setNotice(`发布检查 v${policy.version_number} 已启用`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "发布检查保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function createCapabilitySpec(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !project || !capabilityDeploymentId) return;
    const classes = listItems(capabilityClasses);
    const scenes = listItems(verifiedScenes);
    if (!classes.length || !scenes.length || !deliveryProfiles.length) {
      setError("至少填写一个类别、已验证场景和交付方式");
      return;
    }
    const deployment = capabilityEligibleDeployments.find(
      (item) => item.id === capabilityDeploymentId,
    );
    if (!deployment) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const capability = await catalogApi.createCapabilitySpec(
        workspace.id,
        deployment.id,
        {
          capability_slug: capabilitySlug,
          display_name: capabilityName,
          problem_definition: capabilityProblem,
          input: {
            media_types: ["image/jpeg", "image/png", "image/webp"],
            max_payload_bytes: 8 * 1024 * 1024,
            capture_constraints: captureConstraints,
          },
          output: {
            contract: contractsByTask[deployment.task_type] ?? "predictions.v1",
            classes,
            business_events: listItems(capabilityEvents),
          },
          applicability: {
            verified_scenes: scenes,
            unsupported_conditions: listItems(unsupportedConditions),
          },
          delivery: {
            profiles: deliveryProfiles,
            data_retention_default: "none",
          },
        },
      );
      await refresh(workspace, project);
      setNotice(`能力契约 ${capability.capability_slug} v${capability.version_number} 已固化，不可原地修改`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "能力契约固化失败");
    } finally {
      setBusy(false);
    }
  }

  function toggleDeliveryProfile(profile: "shared-api" | "dedicated-endpoint") {
    setDeliveryProfiles((current) =>
      current.includes(profile)
        ? current.filter((item) => item !== profile)
        : [...current, profile],
    );
  }

  async function createWorkflowSpec(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !project || !workflowCapabilitySpecId) return;
    const events = listItems(workflowEvents);
    if (!events.length) {
      setError("至少选择一个需要输出的业务事件");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const workflow = await catalogApi.createWorkflowSpec(workspace.id, project.id, {
        workflow_slug: workflowSlug,
        display_name: workflowName,
        capability_spec_id: workflowCapabilitySpecId,
        event_types: events,
        deduplication_window_seconds: Number(workflowDeduplicationWindow),
        webhook_url: workflowWebhookUrl,
      });
      await refresh(workspace, project);
      setNotice(`工作流 ${workflow.workflow_slug} v${workflow.version_number} 已发布，等待接入事件运行时`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工作流发布失败");
    } finally {
      setBusy(false);
    }
  }

  async function setEnabled(deployment: Deployment, enabled: boolean) {
    if (!workspace || !project) return;
    setBusy(true);
    setError(null);
    try {
      if (enabled) await catalogApi.enableDeployment(workspace.id, deployment.id);
      else await catalogApi.disableDeployment(workspace.id, deployment.id);
      await refresh(workspace, project);
      setNotice(enabled ? "发布服务已启用" : "发布服务已停用");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "发布服务状态更新失败");
    } finally {
      setBusy(false);
    }
  }

  async function rotateKey(deployment: Deployment) {
    if (!workspace || !project) return;
    setBusy(true);
    setError(null);
    try {
      const rotated = await catalogApi.rotateDeploymentKey(workspace.id, deployment.id);
      setVisibleSecret({ deploymentId: deployment.id, apiKey: rotated.api_key });
      setTestDeploymentId(deployment.id);
      setTestApiKey(rotated.api_key);
      await refresh(workspace, project);
      setNotice("旧密钥已立即失效，请保存新密钥");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "密钥轮换失败");
    } finally {
      setBusy(false);
    }
  }

  async function copyValue(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice(`${label}已复制`);
    } catch {
      setError("浏览器没有允许复制，请手动选择文本");
    }
  }

  async function selectTestImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!new Set(["image/jpeg", "image/png", "image/webp"]).has(file.type)) {
      setError("调用测试只支持 JPEG、PNG 或 WebP 图片");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setError("调用测试图片不能超过 8 MB");
      return;
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error("图片读取失败"));
      reader.readAsDataURL(file);
    }).catch((reason) => {
      setError(reason instanceof Error ? reason.message : "图片读取失败");
      return "";
    });
    setTestImage(dataUrl);
    setTestImageName(file.name);
    setInferenceResult(null);
  }

  async function runInferenceTest(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !project || !selectedTestDeployment || !testApiKey || !testImage) return;
    setTestBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await catalogApi.predictDeployment(
        selectedTestDeployment,
        testApiKey,
        testImage,
        testConfidence,
      );
      setInferenceResult(result);
      await refresh(workspace, project);
      setNotice("推理完成，本次成功调用已计量");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "推理调用失败");
    } finally {
      setTestBusy(false);
    }
  }

  async function createBatchInferenceRun(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !project || !batchDeploymentId || !batchDatasetVersionId) return;
    setBatchBusy(true);
    setError(null);
    setNotice(null);
    try {
      const run = await catalogApi.createBatchInferenceRun(
        workspace.id,
        project.id,
        `batch-${crypto.randomUUID()}`,
        {
          deployment_id: batchDeploymentId,
          dataset_version_id: batchDatasetVersionId,
          source_split: batchSourceSplit,
          parameters: {
            confidence: batchConfidence,
            iou: 0.7,
            max_detections: 300,
            image_size: 640,
          },
        },
      );
      await refresh(workspace, project);
      setNotice(
        run.reused
          ? "已返回相同请求的批量推理任务"
          : "批量推理任务已进入队列，结果会固化为可下载的 NDJSON 产物",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "批量推理任务创建失败");
    } finally {
      setBatchBusy(false);
    }
  }

  async function downloadBatchOutput(run: BatchInferenceRun) {
    if (!workspace) return;
    setError(null);
    try {
      await catalogApi.downloadBatchInferenceOutput(workspace.id, run.id);
      setNotice("批量推理结果已开始下载");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "批量推理结果下载失败");
    }
  }

  async function refreshInferenceHealth() {
    if (!selectedTestDeployment) return;
    setHealthBusy(true);
    setHealthError(null);
    try {
      setInferenceHealth(await catalogApi.getInferenceHealth(selectedTestDeployment));
    } catch (reason) {
      setInferenceHealth(null);
      setHealthError(reason instanceof Error ? reason.message : "运行状态检查失败");
    } finally {
      setHealthBusy(false);
    }
  }

  async function prewarmSelectedModel() {
    if (!selectedTestDeployment || !testApiKey) return;
    setPrewarmBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await catalogApi.prewarmDeployment(selectedTestDeployment, testApiKey);
      setNotice(result.runtime.cache_hit ? "模型已在运行时缓存中" : "模型预热完成");
      await refreshInferenceHealth();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "模型预热失败");
    } finally {
      setPrewarmBusy(false);
    }
  }

  const runtimeCapacity = inferenceHealth?.runtime.capacity;
  const runtimeCache = inferenceHealth?.runtime.cache;
  const runtimeReady = inferenceHealth?.status === "ready";
  const runtimeNotConfigured = inferenceHealth?.runtime.status === "not_configured";
  const runtimeLabel = healthBusy
    ? "正在检查运行状态"
    : runtimeNotConfigured
      ? "等待服务器接入"
      : runtimeReady
        ? inferenceHealth.runtime.accepting_requests === false
          ? "运行时繁忙"
          : "运行时就绪"
        : "运行时不可用";
  const runtimeDetail = healthError
    ? healthError
    : runtimeNotConfigured
      ? "当前为公开演示环境，未连接推理服务器"
      : runtimeCapacity && runtimeCache
        ? `可用容量 ${runtimeCapacity.available_slots}/${runtimeCapacity.max_concurrent_requests} · 已缓存 ${runtimeCache.loaded_models}/${runtimeCache.max_cached_models} 个模型`
        : "等待网关返回端到端状态";

  if (loading) {
    return (
      <main className="services-main">
        <ProjectChrome active="publish" />
        <section className="panel services-loading" aria-live="polite">
          <LoaderCircle size={18} className="spinner" />
          <div><span className="eyebrow">发布控制面</span><h1>正在读取发布条件</h1></div>
        </section>
      </main>
    );
  }

  if (!workspace || !project) {
    return (
      <main className="services-main">
        <ProjectChrome active="publish" />
        <section className="panel services-prerequisite">
          <AlertCircle size={20} />
          <span className="eyebrow">缺少前置数据</span>
          <h1>请先创建项目</h1>
          <p>发布服务必须绑定项目内通过发布检查的模型版本。</p>
          <Link className="primary-button" href="/studio/data?createProject=1">创建项目</Link>
        </section>
      </main>
    );
  }

  return (
    <main className={`services-main services-view-${view}`}>
      <ProjectChrome active="publish" />

      {error ? (
        <div className="workbench-message error-message services-message" role="alert">
          <AlertCircle size={15} /><span>{error}</span><button type="button" onClick={() => setError(null)}>关闭</button>
        </div>
      ) : null}
      {notice ? (
        <div className="workbench-message notice-message services-message" role="status">
          <Check size={14} /><span>{notice}</span>
        </div>
      ) : null}

      <div className="services-view-tabs" aria-label="发布与调用" role="tablist">
        <Link className={view === "live" ? "is-active" : ""} href={`/services?project=${project.id}&view=live`} role="tab" aria-selected={view === "live"}>
          <ScanSearch size={14} />实时分析
        </Link>
        <Link className={view === "batch" ? "is-active" : ""} href={`/services?project=${project.id}&view=batch`} role="tab" aria-selected={view === "batch"}>
          <Files size={14} />批量处理
        </Link>
        <Link className={view === "publish" ? "is-active" : ""} href={`/services?project=${project.id}&view=publish`} role="tab" aria-selected={view === "publish"}>
          <ServerCog size={14} />服务设置
        </Link>
        <Link className={view === "events" ? "is-active" : ""} href={`/services?project=${project.id}&view=events`} role="tab" aria-selected={view === "events"}>
          <Webhook size={14} />事件
        </Link>
      </div>

      <section className="services-overview-grid" hidden={view !== "publish"}>
        <article className="panel services-readiness-card" id="release-check">
          <div className="services-card-heading">
            <span><ShieldCheck size={17} /></span>
            <div><span className="eyebrow">发布条件</span><h2>发布检查</h2></div>
          </div>
          <div className="readiness-list">
            <div className={activePolicy ? "ready" : "waiting"}><span>{activePolicy ? <Check size={12} /> : "1"}</span><div><strong>当前策略</strong><small>{activePolicy ? `${activePolicy.name} · v${activePolicy.version_number}` : "尚未配置"}</small></div></div>
            <div className={eligibleModels.length ? "ready" : "waiting"}><span>{eligibleModels.length ? <Check size={12} /> : "2"}</span><div><strong>通过模型</strong><small>{eligibleModels.length ? `${eligibleModels.length} 个版本可发布` : "等待模型通过检查"}</small></div></div>
            <div className={deployments.length ? "ready" : "waiting"}><span>{deployments.length ? <Check size={12} /> : "3"}</span><div><strong>在线端点</strong><small>{deployments.length ? `${deployments.length} 个服务已创建` : "等待首次发布"}</small></div></div>
          </div>
          {showPolicyForm ? (
            <form className="release-check-form" onSubmit={(event) => void createPolicy(event)}>
              <label><span>检查名称</span><input value={policyName} onChange={(event) => setPolicyName(event.target.value)} required /></label>
              <label><span>检查指标</span><select value={policyMetric} onChange={(event) => setPolicyMetric(event.target.value)}><option value="metrics/mAP50(B)">mAP50</option><option value="metrics/precision(B)">精确率</option><option value="metrics/recall(B)">召回率</option></select></label>
              <label><span>最低要求</span><input type="number" min="0" max="1" step="0.01" value={policyThreshold} onChange={(event) => setPolicyThreshold(event.target.value)} required /></label>
              <div><button className="text-button compact" type="button" onClick={() => setShowPolicyForm(false)}>取消</button><button className="primary-button compact" type="submit" disabled={busy}>{busy ? <LoaderCircle size={13} className="spinner" /> : <ShieldCheck size={13} />}启用</button></div>
            </form>
          ) : (
            <button className="secondary-button release-check-button" type="button" onClick={() => setShowPolicyForm(true)}>{activePolicy ? "新建检查版本" : "设置发布检查"}</button>
          )}
        </article>

        <form className="panel deployment-form" id="publish-service" onSubmit={(event) => void createDeployment(event)}>
          <div className="services-card-heading">
            <span><Rocket size={17} /></span>
            <div><span className="eyebrow">不可变发布</span><h2>发布服务</h2></div>
          </div>
          {eligibleModels.length ? (
            <div className="deployment-form-grid">
              <label><span>模型版本</span><select value={modelVersionId} onChange={(event) => setModelVersionId(event.target.value)}>{eligibleModels.map((model) => <option value={model.id} key={model.id}>{model.model_name} · v{model.version_number}</option>)}</select></label>
              <label><span>服务名称</span><input value={serviceName} onChange={(event) => { setServiceName(event.target.value); if (!deployments.length) setEndpointSlug(slugify(event.target.value) || "vision-service"); }} required /></label>
              <label><span>服务地址</span><div className="endpoint-input"><span>/</span><input value={endpointSlug} onChange={(event) => setEndpointSlug(slugify(event.target.value))} pattern="[a-z0-9][a-z0-9-]{2,119}" required /></div></label>
              <label><span>环境</span><select value={environment} onChange={(event) => setEnvironment(event.target.value as "staging" | "production")}><option value="production">生产</option><option value="staging">预发布</option></select></label>
              <button className="primary-button" type="submit" disabled={busy || !modelVersionId}>{busy ? <LoaderCircle size={14} className="spinner" /> : <Play size={14} fill="currentColor" />}发布服务</button>
            </div>
          ) : (
            <div className="deployment-empty">
              <Cpu size={19} /><div><strong>暂无可发布模型</strong><p>模型需要先通过当前发布检查。</p></div><Link href={activePolicy ? `/studio/training?project=${project.id}#acceptance-evaluation` : "#release-check"}>{activePolicy ? "检查模型" : "设置检查"}</Link>
            </div>
          )}
        </form>
      </section>

      <section className="panel capability-panel" hidden={view !== "publish"}>
        <div className="capability-panel-heading">
          <div className="services-card-heading">
            <span><ShieldCheck size={17} /></span>
            <div><span className="eyebrow">可交付能力</span><h2>能力契约</h2></div>
          </div>
          <span>{capabilitySpecs.length}</span>
        </div>
        <p className="capability-panel-note">能力契约固定发布服务、模型版本、独立检查依据、输入输出协议和适用边界。内容一经固化不可原地修改。</p>
        {capabilityEligibleDeployments.length ? (
          <form className="capability-form-grid" onSubmit={(event) => void createCapabilitySpec(event)}>
            <label><span>发布服务</span><select value={capabilityDeploymentId} onChange={(event) => setCapabilityDeploymentId(event.target.value)}>{capabilityEligibleDeployments.map((deployment) => <option value={deployment.id} key={deployment.id}>{deployment.name} · {deployment.model_name}</option>)}</select></label>
            <label><span>能力标识</span><input value={capabilitySlug} onChange={(event) => setCapabilitySlug(slugify(event.target.value))} pattern="[a-z0-9][a-z0-9-]{2,79}" required /></label>
            <label><span>能力名称</span><input value={capabilityName} onChange={(event) => setCapabilityName(event.target.value)} required /></label>
            <label><span>输出协议</span><input value={contractsByTask[capabilityEligibleDeployments.find((item) => item.id === capabilityDeploymentId)?.task_type ?? ""] ?? "predictions.v1"} readOnly /></label>
            <label className="capability-wide-field"><span>问题定义</span><textarea value={capabilityProblem} onChange={(event) => setCapabilityProblem(event.target.value)} required /></label>
            <label><span>输出类别</span><input value={capabilityClasses} onChange={(event) => setCapabilityClasses(event.target.value)} required /></label>
            <label><span>业务事件</span><input value={capabilityEvents} onChange={(event) => setCapabilityEvents(event.target.value)} placeholder="可选，逗号分隔" /></label>
            <label><span>已验证场景</span><input value={verifiedScenes} onChange={(event) => setVerifiedScenes(event.target.value)} required /></label>
            <label><span>不适用条件</span><input value={unsupportedConditions} onChange={(event) => setUnsupportedConditions(event.target.value)} placeholder="可选，逗号分隔" /></label>
            <label className="capability-wide-field"><span>采集要求与限制</span><textarea value={captureConstraints} onChange={(event) => setCaptureConstraints(event.target.value)} required /></label>
            <fieldset className="capability-delivery-options">
              <legend>交付方式</legend>
              <label><input type="checkbox" checked={deliveryProfiles.includes("shared-api")} onChange={() => toggleDeliveryProfile("shared-api")} />共享 API</label>
              <label><input type="checkbox" checked={deliveryProfiles.includes("dedicated-endpoint")} onChange={() => toggleDeliveryProfile("dedicated-endpoint")} />专属端点</label>
            </fieldset>
            <button className="primary-button" type="submit" disabled={busy || !capabilityDeploymentId}>{busy ? <LoaderCircle size={14} className="spinner" /> : <ShieldCheck size={14} />}固化能力契约</button>
          </form>
        ) : null}
        {capabilitySpecs.length ? (
          <div className="capability-spec-list">
            {capabilitySpecs.map((spec) => (
              <article key={spec.id}>
                <div><strong>{spec.display_name}</strong><small>{spec.capability_slug} · v{spec.version_number}</small></div>
                <p>{spec.problem_definition}</p>
                <span>{spec.output.contract} · {spec.applicability.verified_scenes.join("、")}</span>
                <code>{spec.content_hash.slice(0, 12)}</code>
              </article>
            ))}
          </div>
        ) : null}
        {!capabilityEligibleDeployments.length && !capabilitySpecs.length ? <div className="capability-empty"><ShieldCheck size={18} /><span>先发布一个通过独立数据检查的生产服务，再固化可交付能力。</span></div> : null}
      </section>

      <section className="panel workflow-panel" hidden={view !== "events"}>
        <div className="capability-panel-heading">
          <div className="services-card-heading">
            <span><Rocket size={17} /></span>
            <div><span className="eyebrow">模板编排</span><h2>事件工作流</h2></div>
          </div>
          <span>{workflowSpecs.length}</span>
        </div>
        <p className="capability-panel-note">首期只提供“PPE 违规事件 → Webhook”模板，固定能力调用、去重和签名投递步骤；失败请求按退避策略自动重试。</p>
        {workflowEligibleCapabilities.length ? (
          <form className="capability-form-grid" onSubmit={(event) => void createWorkflowSpec(event)}>
            <label><span>能力版本</span><select value={workflowCapabilitySpecId} onChange={(event) => setWorkflowCapabilitySpecId(event.target.value)}>{workflowEligibleCapabilities.map((spec) => <option value={spec.id} key={spec.id}>{spec.display_name} · v{spec.version_number}</option>)}</select></label>
            <label><span>工作流标识</span><input value={workflowSlug} onChange={(event) => setWorkflowSlug(slugify(event.target.value))} pattern="[a-z0-9][a-z0-9-]{2,79}" required /></label>
            <label><span>工作流名称</span><input value={workflowName} onChange={(event) => setWorkflowName(event.target.value)} required /></label>
            <label><span>去重窗口（秒）</span><input type="number" min="0" max="86400" step="1" value={workflowDeduplicationWindow} onChange={(event) => setWorkflowDeduplicationWindow(event.target.value)} required /></label>
            <label><span>输出事件</span><input value={workflowEvents} onChange={(event) => setWorkflowEvents(event.target.value)} required /></label>
            <label><span>Webhook 地址</span><input type="url" placeholder="https://example.com/events" value={workflowWebhookUrl} onChange={(event) => setWorkflowWebhookUrl(event.target.value)} required /></label>
            <button className="primary-button" type="submit" disabled={busy || !workflowCapabilitySpecId}>{busy ? <LoaderCircle size={14} className="spinner" /> : <Rocket size={14} />}发布模板工作流</button>
          </form>
        ) : <div className="capability-empty"><Rocket size={18} /><span>先固化包含业务事件的能力契约。</span></div>}
        {workflowSpecs.length ? (
          <div className="capability-spec-list">
            {workflowSpecs.map((workflow) => (
              <article key={workflow.id}>
                <div><strong>{workflow.display_name}</strong><small>{workflow.workflow_slug} · v{workflow.version_number}</small></div>
                <p>{workflow.event_types.join("、")} · 去重 {workflow.deduplication_window_seconds} 秒</p>
                <span>{workflow.template_key}</span>
                <code>{workflow.content_hash.slice(0, 12)}</code>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel event-delivery-panel" hidden={view !== "events"}>
        <div className="capability-panel-heading">
          <div className="services-card-heading">
            <span><Webhook size={17} /></span>
            <div><span className="eyebrow">事件运行</span><h2>投递记录</h2></div>
          </div>
          <span>{visionEvents.length}</span>
        </div>
        <p className="capability-panel-note">展示最近的业务事件及其 Webhook 投递结果，失败请求会保留错误摘要并自动重试。</p>
        {visionEvents.length ? (
          <div className="vision-event-list">
            {visionEvents.map((event) => {
              const replay = eventReplay?.event_id === event.id ? eventReplay : null;
              return (
                <div className="vision-event-record" key={event.id}>
                  <article>
                    <div className="vision-event-identity">
                      <span className={`vision-event-status ${event.delivery_status}`} aria-hidden="true" />
                      <div><strong>{event.workflow_name}</strong><small>{event.workflow_slug}</small></div>
                    </div>
                    <code>{event.event_type}</code>
                    <time dateTime={event.occurred_at}>{formatTime(event.occurred_at)}</time>
                    <span className={`vision-event-state ${event.delivery_status}`}>{deliveryStatusLabel(event.delivery_status)}</span>
                    <div className="vision-event-attempt" title={event.last_error ?? undefined}>
                      <strong>{event.attempt_count} 次</strong>
                      <small>{event.last_error ?? (event.delivered_at ? `完成于 ${formatTime(event.delivered_at)}` : "等待 Worker 处理")}</small>
                    </div>
                    <button
                      className="vision-event-replay-button"
                      type="button"
                      disabled={replayBusy !== null}
                      onClick={() => void replayVisionEvent(event)}
                    >
                      {replayBusy === event.id ? <LoaderCircle size={12} className="spinner" /> : <ScanSearch size={12} />}
                      {replay ? "收起依据" : "查看依据"}
                    </button>
                  </article>
                  {replay ? (
                    <div className="vision-event-replay" aria-live="polite">
                      <div className="vision-event-replay-heading">
                        <div>
                          <span className={replay.decision.matched ? "is-matched" : "is-incomplete"}>
                            {replay.decision.matched ? <Check size={12} /> : <AlertCircle size={12} />}
                            {replay.decision.matched ? "符合当前模板条件" : "无法确认命中"}
                          </span>
                          <p>只读取事件中保留的统计信息，不读取或重新推理原始图片。</p>
                        </div>
                        <code>{replay.template_key}</code>
                      </div>
                      <div className="vision-event-replay-grid">
                        <section>
                          <span>判定依据</span>
                          <strong>{replay.sample.person_count ?? "—"} 名人员 · {replay.sample.required_class_count ?? "—"} 个 {replay.sample.required_class ?? "目标类别"}</strong>
                          <small>{replay.sample.detection_count ?? "—"} 个检测结果{replay.sample.width && replay.sample.height ? ` · ${replay.sample.width} × ${replay.sample.height}` : ""}</small>
                        </section>
                        <section>
                          <span>来源与去重</span>
                          <strong>{replay.sample.source_id ?? "未记录来源"}</strong>
                          <small>{replay.sample.source_type ?? "—"} · {replay.decision.deduplication_window_seconds} 秒窗口</small>
                        </section>
                        <section>
                          <span>投递定位</span>
                          <strong>{replay.delivery.target_host ?? "未记录目标"}</strong>
                          <small>{deliveryStatusLabel(replay.delivery.status)} · 第 {replay.delivery.attempt_count} 次</small>
                        </section>
                      </div>
                      <ul>
                        {replay.decision.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                        {replay.delivery.last_error ? <li className="is-error">最近错误：{replay.delivery.last_error}</li> : null}
                      </ul>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="capability-empty"><Webhook size={18} /><span>工作流收到首个业务事件后，将在这里显示投递状态。</span></div>
        )}
      </section>

      {visibleSecret ? (
        <section className="panel deployment-secret" aria-live="polite" hidden={view !== "publish"}>
          <span className="secret-icon"><KeyRound size={17} /></span>
          <div><span className="eyebrow">仅显示一次</span><h2>保存 API 密钥</h2><p>关闭或刷新后无法再次查看；遗失时只能轮换。</p></div>
          <code>{visibleSecret.apiKey}</code>
          <button className="secondary-button" type="button" onClick={() => void copyValue(visibleSecret.apiKey, "API 密钥")}><Clipboard size={13} />复制</button>
          <button className="text-button" type="button" onClick={() => setVisibleSecret(null)}>我已保存</button>
        </section>
      ) : null}

      {publishedDeployments.length ? (
        <section className="panel inference-tester" id="live-analysis" hidden={view !== "live"}>
          <div className="inference-tester-heading">
            <div className="services-card-heading">
              <span><ScanSearch size={17} /></span>
              <div><span className="eyebrow">在线调用</span><h2>实时分析</h2></div>
            </div>
            <div className={`inference-health ${runtimeReady ? "is-ready" : "is-unavailable"}`}>
              <span className="inference-health-dot" aria-hidden="true" />
              <div><strong>{runtimeLabel}</strong><small>{runtimeDetail}</small></div>
              <button type="button" title="刷新运行状态" disabled={healthBusy} onClick={() => void refreshInferenceHealth()}>
                <RefreshCw size={13} className={healthBusy ? "spinner" : undefined} />
              </button>
            </div>
          </div>
          <div className="live-analysis-options" aria-label="分析方式">
            <div className="live-analysis-option-group">
              <span>算法</span>
              <div role="group" aria-label="算法类型">
                <button className="is-active" type="button" aria-pressed="true"><Cpu size={14} />视觉小模型<small>已接入</small></button>
                <button type="button" disabled title="待完成多模态模型供应商与凭据合同"><BrainCircuit size={14} />多模态大模型<small>待接入</small></button>
              </div>
            </div>
            <div className="live-analysis-option-group">
              <span>输入</span>
              <div role="group" aria-label="输入类型">
                <button className="is-active" type="button" aria-pressed="true"><ImageIcon size={14} />图像<small>已接入</small></button>
                <button type="button" disabled title="待完成视频流加密凭据、网络访问和任务恢复合同"><Video size={14} />实时视频流<small>待接入</small></button>
              </div>
            </div>
          </div>
          <form className="inference-test-form" onSubmit={(event) => void runInferenceTest(event)}>
            <label><span>视觉小模型</span><select value={testDeploymentId} onChange={(event) => { setTestDeploymentId(event.target.value); setInferenceResult(null); }}>{publishedDeployments.map((deployment) => <option value={deployment.id} key={deployment.id}>{deployment.name} · /{deployment.endpoint_slug}</option>)}</select></label>
            <label><span>API 密钥</span><input type="password" autoComplete="off" placeholder="smu_live_…" value={testApiKey} onChange={(event) => setTestApiKey(event.target.value)} required /></label>
            <label><span>置信度</span><input type="number" min="0" max="1" step="0.05" value={testConfidence} onChange={(event) => setTestConfidence(Number(event.target.value))} /></label>
            <label className="inference-file-field">
              <span>测试图片</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void selectTestImage(event)} />
              <span className="inference-file-button"><UploadCloud size={13} />{testImageName || "选择不超过 8 MB 的图片"}</span>
            </label>
            <div className="inference-test-actions">
              <button className="secondary-button" type="button" disabled={prewarmBusy || testBusy || !testApiKey} onClick={() => void prewarmSelectedModel()}>
                {prewarmBusy ? <LoaderCircle size={14} className="spinner" /> : <Flame size={14} />}预热模型
              </button>
              <button className="primary-button" type="submit" disabled={testBusy || prewarmBusy || !testImage || !testApiKey}>
                {testBusy ? <LoaderCircle size={14} className="spinner" /> : <Gauge size={14} />}执行推理
              </button>
            </div>
          </form>
          {inferenceResult ? (
            <div className="inference-result">
              <div className="inference-result-summary">
                <span><Check size={13} />调用成功</span>
                <strong>{inferenceResult.outputs.predictions[0]?.detections.length ?? 0} 个目标</strong>
                <small>{inferenceResult.outputs.runtime.inference_ms.toFixed(1)} 毫秒 · {inferenceResult.outputs.runtime.device}</small>
                <code>{inferenceResult.request_id}</code>
              </div>
              {(inferenceResult.outputs.predictions[0]?.detections ?? []).length ? (
                <div className="inference-detection-list">
                  {inferenceResult.outputs.predictions[0].detections.slice(0, 8).map((detection, index) => (
                    <div key={`${detection.class_id}-${index}`}>
                      <span>{detection.class_name}</span>
                      <strong>{(detection.confidence * 100).toFixed(1)}%</strong>
                      <code>{Math.round(detection.box.x1)}, {Math.round(detection.box.y1)} → {Math.round(detection.box.x2)}, {Math.round(detection.box.y2)}</code>
                    </div>
                  ))}
                </div>
              ) : <p className="inference-no-detections">当前置信度下没有检测到目标。</p>}
            </div>
          ) : null}
        </section>
      ) : (
        <section className="panel live-analysis-empty" hidden={view !== "live"}>
          <ScanSearch size={20} />
          <div><strong>尚无可用的视觉小模型</strong><p>先将通过独立检查的模型发布为在线服务。</p></div>
          <Link className="primary-button compact" href={`/services?project=${project.id}&view=publish#publish-service`}><Rocket size={13} />发布服务</Link>
        </section>
      )}

      <section className="panel batch-inference-panel" hidden={view !== "batch"}>
        <div className="batch-inference-heading">
          <div className="services-card-heading">
            <span><Files size={17} /></span>
            <div><span className="eyebrow">冻结数据处理</span><h2>批量推理</h2></div>
          </div>
          <button
            type="button"
            title="刷新批量任务状态"
            disabled={batchBusy || !workspace || !project}
            onClick={() => {
              if (workspace && project) void refresh(workspace, project);
            }}
          >
            <RefreshCw size={13} />刷新
          </button>
        </div>
        <p className="capability-panel-note">选择已发布服务和冻结数据版本后，Worker 在受限运行时中分批处理图片；结果不包含原始对象地址，并以可追溯的 NDJSON 产物保存。</p>
        {batchEligibleDeployments.length && frozenDatasetVersions.length ? (
          <form className="batch-inference-form" onSubmit={(event) => void createBatchInferenceRun(event)}>
            <label><span>发布服务</span><select value={batchDeploymentId} onChange={(event) => setBatchDeploymentId(event.target.value)}>{batchEligibleDeployments.map((deployment) => <option value={deployment.id} key={deployment.id}>{deployment.name} · {deployment.model_name} v{deployment.model_version_number}</option>)}</select></label>
            <label><span>冻结数据版本</span><select value={batchDatasetVersionId} onChange={(event) => setBatchDatasetVersionId(event.target.value)}>{frozenDatasetVersions.map((version) => <option value={version.id} key={version.id}>{version.datasetName} · v{version.version_number} · {version.asset_count.toLocaleString("zh-CN")} 张图片</option>)}</select></label>
            <label><span>处理范围</span><select value={batchSourceSplit} onChange={(event) => setBatchSourceSplit(event.target.value as "all" | "train" | "valid" | "test")}><option value="all">全部划分</option><option value="train">训练集</option><option value="valid">验证集</option><option value="test">测试集</option></select></label>
            <label><span>置信度</span><input type="number" min="0" max="1" step="0.05" value={batchConfidence} onChange={(event) => setBatchConfidence(Number(event.target.value))} /></label>
            <button className="primary-button" type="submit" disabled={batchBusy || !batchDeploymentId || !batchDatasetVersionId}>
              {batchBusy ? <LoaderCircle size={14} className="spinner" /> : <Files size={14} />}提交批量推理
            </button>
          </form>
        ) : (
          <div className="capability-empty"><Files size={18} /><span>{batchEligibleDeployments.length ? "需要先在数据页冻结至少一个图片数据版本。" : "需要先发布一个通过检查的目标检测服务。"}</span></div>
        )}
        {batchInferenceRuns.length ? (
          <div className="batch-inference-list">
            {batchInferenceRuns.slice(0, 8).map((run) => (
              <article key={run.id}>
                <div className="batch-inference-identity">
                  <span className={`deployment-status ${run.status}`} aria-hidden="true" />
                  <div><strong>{run.status === "succeeded" ? "结果已生成" : run.status === "failed" ? "任务失败" : run.status === "cancelled" ? "任务已取消" : "正在处理"}</strong><small>{batchSourceSplitLabel(run.recipe.source_split)} · {formatTime(run.created_at)}</small></div>
                </div>
                <div className="batch-inference-metric"><strong>{run.result?.summary.processed_asset_count ?? "—"}</strong><span>已处理图片</span></div>
                <div className="batch-inference-metric"><strong>{run.result?.summary.prediction_count ?? "—"}</strong><span>检测目标</span></div>
                <div className="batch-inference-progress"><span><i style={{ width: `${run.progress}%` }} /></span><small>{run.status === "failed" ? run.error_message ?? "处理失败" : `${run.progress}%`}</small></div>
                {run.result ? <button type="button" className="secondary-button" onClick={() => void downloadBatchOutput(run)}><Download size={13} />下载结果</button> : <code>{run.id.slice(0, 12)}</code>}
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel deployments-panel" hidden={view !== "publish"}>
        <div className="deployments-heading">
          <div className="services-card-heading"><span><ServerCog size={17} /></span><div><span className="eyebrow">真实状态</span><h2>服务端点</h2></div></div>
          <span>{deployments.length}</span>
        </div>
        {deployments.length ? (
          <div className="deployment-list">
            {deployments.map((deployment) => (
              <article className="deployment-row" key={deployment.id}>
                <div className="deployment-identity">
                  <span className={`deployment-status ${deployment.status}`} aria-hidden="true" />
                  <div><strong>{deployment.name}</strong><small>{deployment.model_name} · v{deployment.model_version_number} · 检查 v{deployment.evaluation_policy_version ?? "—"}</small></div>
                </div>
                <button className="deployment-endpoint" type="button" onClick={() => void copyValue(deployment.endpoint_url, "端点地址")} title="复制端点地址"><code>/{deployment.endpoint_slug}</code><Clipboard size={12} /></button>
                <div className="deployment-metric"><strong>{deployment.request_count.toLocaleString("zh-CN")}</strong><span>调用</span></div>
                <div className="deployment-metric"><strong>{deployment.billable_units.toLocaleString("zh-CN")}</strong><span>图像</span></div>
                <div className="deployment-meta"><span>{deployment.environment === "production" ? "生产" : "预发布"}</span><small>{deployment.status === "published" ? `发布于 ${formatTime(deployment.published_at)}` : `停用于 ${formatTime(deployment.disabled_at)}`}</small></div>
                <div className="deployment-actions">
                  <button type="button" disabled={busy} title="轮换 API 密钥" onClick={() => void rotateKey(deployment)}><RefreshCw size={13} /></button>
                  <button type="button" disabled={busy} title={deployment.status === "published" ? "停用服务" : "启用服务"} onClick={() => void setEnabled(deployment, deployment.status !== "published")}>
                    {deployment.status === "published" ? <Ban size={13} /> : <Play size={13} />}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="services-empty"><ServerCog size={22} /><strong>尚未发布服务</strong><p>通过发布检查的模型会出现在上方发布表单中。</p></div>
        )}
      </section>
    </main>
  );
}
