"use client";

import {
  AlertCircle,
  ArrowUpRight,
  Check,
  Cpu,
  Database,
  FileCheck2,
  FlaskConical,
  LoaderCircle,
  Rocket,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  type Dataset,
  type DatasetVersion,
  type Deployment,
  type Evaluation,
  type EvaluationPolicy,
  type ModelVersion,
  type Project,
  type TrainingRun,
  type Workspace,
  catalogApi,
} from "../../lib/catalog-api";
import { ProjectChrome } from "./project-chrome";

type DatasetState = {
  dataset: Dataset;
  latestVersion: DatasetVersion | null;
};

const activeRunStatuses = new Set(["queued", "preparing", "running", "cancel_requested"]);
const runStatusLabels: Record<string, string> = {
  queued: "排队中",
  preparing: "准备中",
  running: "训练中",
  cancel_requested: "正在取消",
  cancelled: "已取消",
  succeeded: "已完成",
  failed: "失败",
};
const modelStatusLabels: Record<string, string> = {
  candidate: "待检查",
  validation_passed: "训练验证通过",
  validation_failed: "训练验证未通过",
  approved: "已通过",
  rejected: "未通过",
  archived: "已归档",
};

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function readMetric(metrics: Record<string, number>, keys: string[]): number | null {
  for (const key of keys) {
    if (typeof metrics[key] === "number") return metrics[key];
  }
  return null;
}

function formatScore(value: number | null): string {
  if (value === null) return "—";
  if (value >= 0 && value <= 1) return `${(value * 100).toFixed(1)}%`;
  return value.toFixed(1).replace(/\.0$/, "");
}

export function StudioOverview() {
  const requestedProjectId = useSearchParams().get("project");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [datasetStates, setDatasetStates] = useState<DatasetState[]>([]);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [modelVersions, setModelVersions] = useState<ModelVersion[]>([]);
  const [policies, setPolicies] = useState<EvaluationPolicy[]>([]);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);

  async function refreshProject(selectedWorkspace: Workspace, selectedProject: Project) {
    const [datasets, nextRuns, nextModels, nextPolicies, nextEvaluations, nextDeployments] = await Promise.all([
      catalogApi.listDatasets(selectedWorkspace.id, selectedProject.id),
      catalogApi.listTrainingRuns(selectedWorkspace.id, selectedProject.id),
      catalogApi.listModelVersions(selectedWorkspace.id, selectedProject.id),
      catalogApi.listEvaluationPolicies(selectedWorkspace.id, selectedProject.id),
      catalogApi.listEvaluations(selectedWorkspace.id, selectedProject.id),
      catalogApi.listDeployments(selectedWorkspace.id, selectedProject.id),
    ]);
    const nextDatasetStates = await Promise.all(
      datasets.map(async (dataset) => {
        const versions = await catalogApi.listVersions(selectedWorkspace.id, dataset.id);
        return { dataset, latestVersion: versions[0] ?? null };
      }),
    );
    setDatasetStates(nextDatasetStates);
    setRuns(nextRuns);
    setModelVersions(nextModels);
    setPolicies(nextPolicies);
    setEvaluations(nextEvaluations);
    setDeployments(nextDeployments);
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
        if (selectedProject) await refreshProject(selectedWorkspace, selectedProject);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "项目概览加载失败"))
      .finally(() => setLoading(false));
  }, [requestedProjectId]);

  useEffect(() => {
    if (!workspace || !project || !runs.some((run) => activeRunStatuses.has(run.status))) return;
    const timer = window.setInterval(() => {
      void refreshProject(workspace, project).catch((reason) =>
        setError(reason instanceof Error ? reason.message : "项目状态刷新失败"),
      );
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [workspace, project, runs]);

  const activePolicy = policies.find((policy) => policy.is_active) ?? null;
  const latestDataset = useMemo(
    () => datasetStates.find((item) => item.latestVersion) ?? datasetStates[0] ?? null,
    [datasetStates],
  );
  const activeRun = runs.find((run) => activeRunStatuses.has(run.status)) ?? null;
  const latestModel = modelVersions[0] ?? null;
  const latestEvaluation = evaluations.find((evaluation) => evaluation.source === "acceptance-dataset") ?? null;
  const currentEvaluation =
    evaluations.find(
      (evaluation) =>
        evaluation.policy_id === activePolicy?.id &&
        evaluation.model_version_id === latestModel?.id &&
        evaluation.source === "acceptance-dataset",
    ) ?? null;
  const publishedDeployment = deployments.find((deployment) => deployment.status === "published") ?? null;

  if (loading) {
    return (
      <main className="studio-main">
        <ProjectChrome active="overview" />
        <section className="panel overview-loading-card" aria-live="polite">
          <LoaderCircle size={17} className="spinner" />
          <div><strong>正在读取项目状态</strong><span>稍候即可继续当前工作</span></div>
        </section>
      </main>
    );
  }

  if (!workspace || !project) {
    return (
      <main className="studio-main">
        <ProjectChrome active="overview" />
        <section className="panel overview-prerequisite">
          <AlertCircle size={20} />
          <h1>还没有项目</h1>
          <p>创建项目后即可准备数据并开始训练。</p>
          <Link className="primary-button" href="/studio/data?createProject=1">创建项目</Link>
        </section>
      </main>
    );
  }

  const dataHref = `/studio/data?project=${project.id}`;
  const trainingHref = `/studio/training?project=${project.id}`;
  const servicesHref = `/services?project=${project.id}&view=live`;
  const publishHref = `/services?project=${project.id}&view=publish`;
  const draftAssetCount = latestDataset?.dataset.asset_count ?? 0;
  const nextStage = activeRun
    ? "training"
    : publishedDeployment
      ? "published"
      : latestModel
        ? "model"
        : latestDataset?.latestVersion
          ? "train"
          : draftAssetCount > 0
            ? "version"
            : "data";
  const map50 = latestModel
    ? readMetric(latestModel.metrics, ["metrics/mAP50(B)", "mAP50", "map50"])
    : null;
  const precision = latestModel
    ? readMetric(latestModel.metrics, ["metrics/precision(B)", "precision"])
    : null;
  const recall = latestModel
    ? readMetric(latestModel.metrics, ["metrics/recall(B)", "recall"])
    : null;

  const recentArtifacts = [
    ...datasetStates.flatMap((state) => state.latestVersion ? [{
      id: `dataset-${state.latestVersion.id}`,
      type: "数据版本",
      name: `${state.dataset.name} · v${state.latestVersion.version_number}`,
      status: "已就绪",
      tone: "positive",
      updatedAt: state.latestVersion.created_at,
      href: dataHref,
      icon: Database,
    }] : []),
    ...runs.slice(0, 2).map((run) => ({
      id: `run-${run.id}`,
      type: "训练任务",
      name: String(run.recipe.model ?? run.engine),
      status: runStatusLabels[run.status] ?? run.status,
      tone: activeRunStatuses.has(run.status) ? "active" : run.status === "failed" ? "negative" : "muted",
      updatedAt: run.updated_at,
      href: `/studio/training/runs/${run.id}?project=${project.id}`,
      icon: FlaskConical,
    })),
    ...modelVersions.slice(0, 2).map((model) => ({
      id: `model-${model.id}`,
      type: "模型",
      name: `${model.model_name} · v${model.version_number}`,
      status: modelStatusLabels[model.status] ?? model.status,
      tone: model.status === "approved" || model.status === "validation_passed" ? "positive" : "muted",
      updatedAt: model.created_at,
      href: `/studio/training/models/${model.id}?project=${project.id}`,
      icon: Cpu,
    })),
    ...(latestEvaluation ? [{
      id: `evaluation-${latestEvaluation.id}`,
      type: "模型检查",
      name: `${latestEvaluation.model_name} · v${latestEvaluation.model_version_number}`,
      status: latestEvaluation.verdict === "approved" ? "已通过" : "未通过",
      tone: latestEvaluation.verdict === "approved" ? "positive" : "negative",
      updatedAt: latestEvaluation.evaluated_at,
      href: `/studio/training/models/${latestEvaluation.model_version_id}?project=${project.id}`,
      icon: FileCheck2,
    }] : []),
    ...deployments.slice(0, 1).map((deployment) => ({
      id: `deployment-${deployment.id}`,
      type: "在线服务",
      name: deployment.name,
      status: deployment.status === "published" ? "运行中" : deployment.status,
      tone: deployment.status === "published" ? "positive" : "muted",
      updatedAt: deployment.updated_at,
      href: servicesHref,
      icon: Rocket,
    })),
  ]
    .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime())
    .slice(0, 5);

  return (
    <main className="studio-main">
      <ProjectChrome active="overview" />

      {error ? (
        <div className="workbench-message error-message overview-message" role="alert">
          <AlertCircle size={15} /><span>{error}</span><button type="button" onClick={() => setError(null)}>关闭</button>
        </div>
      ) : null}

      <section className={`panel overview-next-card is-${nextStage}`}>
        {nextStage === "training" && activeRun ? (
          <>
            <div className="overview-next-heading">
              <div>
                <span className="overview-live-status"><i />{runStatusLabels[activeRun.status] ?? activeRun.status}</span>
                <h2>{String(activeRun.recipe.model ?? activeRun.engine)}</h2>
                <p>训练进行中，可以离开页面，任务会在后台继续。</p>
              </div>
              <strong className="overview-progress-value">{activeRun.progress}%</strong>
            </div>
            <span className="progress-track overview-progress-track" aria-label={`训练进度 ${activeRun.progress}%`}>
              <span style={{ width: `${activeRun.progress}%` }} />
            </span>
            <div className="overview-next-meta">
              <span>训练轮次 {String(activeRun.recipe.epochs ?? "—")}</span>
              <span>{activeRun.executor}</span>
              <span>{activeRun.started_at ? `开始于 ${formatTime(activeRun.started_at)}` : "等待执行"}</span>
            </div>
            <div className="overview-next-actions">
              <Link className="primary-button" href={trainingHref}>查看训练<ArrowUpRight size={14} /></Link>
            </div>
          </>
        ) : null}

        {nextStage === "data" ? (
          <>
            <div className="overview-next-heading">
              <div><span className="overview-step-label">下一步</span><h2>准备第一版训练数据</h2><p>先导入图像或视频，再完成标注并生成可训练版本。</p></div>
              <Database size={24} strokeWidth={1.5} aria-hidden="true" />
            </div>
            <div className="overview-checklist" aria-label="数据准备步骤">
              <span className="is-done"><i><Check size={11} /></i>项目已创建</span>
              <span><i>2</i>导入素材</span>
              <span><i>3</i>完成标注</span>
              <span><i>4</i>生成版本</span>
            </div>
            <div className="overview-next-actions">
              <Link className="primary-button" href={dataHref}>继续准备数据<ArrowUpRight size={14} /></Link>
            </div>
          </>
        ) : null}

        {nextStage === "version" ? (
          <>
            <div className="overview-next-heading">
              <div><span className="overview-step-label">下一步</span><h2>生成第一版训练数据</h2><p>草稿中已有 {draftAssetCount.toLocaleString("zh-CN")} 个资产，确认标注后即可生成固定版本。</p></div>
              <Database size={24} strokeWidth={1.5} aria-hidden="true" />
            </div>
            <div className="overview-checklist compact">
              <span className="is-done"><i><Check size={11} /></i>素材已导入</span>
              <span><i>2</i>检查标注</span>
              <span><i>3</i>生成版本</span>
            </div>
            <div className="overview-next-actions">
              <Link className="primary-button" href={dataHref}>检查并生成版本<ArrowUpRight size={14} /></Link>
            </div>
          </>
        ) : null}

        {nextStage === "train" && latestDataset?.latestVersion ? (
          <>
            <div className="overview-next-heading">
              <div><span className="overview-step-label">下一步</span><h2>开始首次训练</h2><p>数据版本已经就绪，现在可以选择基础模型并提交训练。</p></div>
              <FlaskConical size={24} strokeWidth={1.5} aria-hidden="true" />
            </div>
            <div className="overview-ready-summary">
              <div><span>数据版本</span><strong>v{latestDataset.latestVersion.version_number}</strong></div>
              <div><span>资产</span><strong>{latestDataset.latestVersion.asset_count.toLocaleString("zh-CN")}</strong></div>
              <div><span>类别</span><strong>{Object.keys(latestDataset.latestVersion.class_map).length}</strong></div>
            </div>
            <div className="overview-next-actions">
              <Link className="secondary-button" href={dataHref}>查看数据</Link>
              <Link className="primary-button" href={trainingHref}>开始训练<ArrowUpRight size={14} /></Link>
            </div>
          </>
        ) : null}

        {nextStage === "model" && latestModel ? (
          <>
            <div className="overview-next-heading">
              <div><span className="overview-step-label">最新模型</span><h2>{latestModel.model_name} · v{latestModel.version_number}</h2><p>{currentEvaluation ? currentEvaluation.verdict === "approved" ? "模型检查已经通过，可以进行在线测试或发布。" : "模型检查未通过，建议先查看结果。" : "训练已经完成，先测试效果再决定是否发布。"}</p></div>
              <Cpu size={24} strokeWidth={1.5} aria-hidden="true" />
            </div>
            <div className="overview-model-metrics">
              <div><span>mAP50</span><strong>{formatScore(map50)}</strong></div>
              <div><span>精确率</span><strong>{formatScore(precision)}</strong></div>
              <div><span>召回率</span><strong>{formatScore(recall)}</strong></div>
            </div>
            <div className="overview-next-actions">
              <Link className="secondary-button" href={trainingHref}>查看模型</Link>
              <Link className="primary-button" href={publishHref}>测试与发布<ArrowUpRight size={14} /></Link>
            </div>
          </>
        ) : null}

        {nextStage === "published" && publishedDeployment ? (
          <>
            <div className="overview-next-heading">
              <div><span className="overview-live-status"><i />服务运行中</span><h2>{publishedDeployment.name}</h2><p>模型已经发布，可以查看调用情况或继续迭代新版本。</p></div>
              <Rocket size={24} strokeWidth={1.5} aria-hidden="true" />
            </div>
            <div className="overview-ready-summary">
              <div><span>模型</span><strong>{publishedDeployment.model_name} · v{publishedDeployment.model_version_number}</strong></div>
              <div><span>调用</span><strong>{publishedDeployment.request_count.toLocaleString("zh-CN")}</strong></div>
              <div><span>状态</span><strong>正常</strong></div>
            </div>
            <div className="overview-next-actions">
              <Link className="secondary-button" href={trainingHref}>继续迭代</Link>
              <Link className="primary-button" href={servicesHref}>查看在线服务<ArrowUpRight size={14} /></Link>
            </div>
          </>
        ) : null}
      </section>

      <section className="panel overview-artifacts-card">
        <div className="overview-artifacts-heading">
          <h2>最近产物</h2>
          <span>{recentArtifacts.length} 项</span>
        </div>
        {recentArtifacts.length > 0 ? (
          <div className="overview-artifact-list">
            {recentArtifacts.map((artifact) => {
              const Icon = artifact.icon;
              return (
                <Link href={artifact.href} className="overview-artifact-row" key={artifact.id}>
                  <span className="overview-artifact-icon"><Icon size={16} strokeWidth={1.6} aria-hidden="true" /></span>
                  <span className="overview-artifact-copy"><small>{artifact.type}</small><strong>{artifact.name}</strong></span>
                  <span className={`overview-artifact-status is-${artifact.tone}`}>{artifact.status}</span>
                  <time dateTime={artifact.updatedAt}>{formatTime(artifact.updatedAt)}</time>
                  <ArrowUpRight size={14} aria-hidden="true" />
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="overview-artifacts-empty">项目还没有产物，从上方的下一步开始。</div>
        )}
      </section>
    </main>
  );
}
