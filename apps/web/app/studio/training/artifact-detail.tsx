"use client";

import {
  AlertCircle,
  ArrowLeft,
  ArrowUpRight,
  Check,
  Clock3,
  Cpu,
  Database,
  FileCheck2,
  FlaskConical,
  LoaderCircle,
  Rocket,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { DynamicAssetImage } from "../../components/dynamic-asset-image";
import {
  type Dataset,
  type DatasetVersion,
  type Deployment,
  type Evaluation,
  type ModelVersion,
  type Project,
  type RunEvent,
  type TrainingClassMetrics,
  type TrainingReport,
  type TrainingRun,
  type TrainingVisualizationName,
  catalogApi,
} from "../../../lib/catalog-api";

type ArtifactDetailProps = {
  artifactId: string;
  kind: "run" | "model";
};

type VersionOption = {
  dataset: Dataset;
  version: DatasetVersion;
};

type TrainingVisualizationUrls = Partial<Record<TrainingVisualizationName, string>>;

const trainingVisualizationOptions: Array<{
  name: TrainingVisualizationName;
  title: string;
  description: string;
}> = [
  { name: "confusion_matrix", title: "类别对照", description: "按样本数量" },
  { name: "confusion_matrix_normalized", title: "类别对照（比例）", description: "按类别比例" },
];

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
const runEventLabels: Record<string, string> = {
  "job.queued": "已排队",
  "job.preparing": "准备执行",
  "job.started": "开始训练",
  "job.progressed": "训练进度更新",
  "job.cancel_requested": "已请求取消",
  "job.cancelled": "已取消",
  "job.failed": "训练失败",
  "job.lease_expired": "执行器失联，已恢复",
  "job.succeeded": "训练完成",
};
const modelStatusLabels: Record<string, string> = {
  candidate: "待检查",
  validation_passed: "训练验证通过",
  validation_failed: "训练验证未通过",
  approved: "已通过",
  rejected: "未通过",
  archived: "已归档",
};

const metricLabels: Record<string, string> = {
  "metrics/mAP50(B)": "mAP50",
  "metrics/mAP50-95(B)": "mAP50–95",
  "metrics/precision(B)": "精确率",
  "metrics/recall(B)": "召回率",
  "train/box_loss": "训练框损失",
  "train/cls_loss": "训练分类损失",
  "train/dfl_loss": "训练定位损失",
  "val/box_loss": "验证框损失",
  "val/cls_loss": "验证分类损失",
  "val/dfl_loss": "验证定位损失",
  mAP50: "mAP50",
  "mAP50-95": "mAP50–95",
  precision: "精确率",
  recall: "召回率",
};

function formatTime(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
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

function formatMetricName(metric: string): string {
  return metricLabels[metric] ?? metric;
}

function formatMetricValue(value: number | string | boolean | null): string {
  if (typeof value === "number") return formatScore(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  return value ?? "—";
}

function findTrainingReportMetric(report: TrainingReport): string | null {
  const preferredMetrics = [
    "metrics/mAP50(B)",
    "metrics/mAP50-95(B)",
    "metrics/precision(B)",
    "metrics/recall(B)",
  ];
  for (const metric of preferredMetrics) {
    if (report.rows.some((row) => typeof row.metrics[metric] === "number")) return metric;
  }
  return Object.keys(report.rows[0]?.metrics ?? {})[0] ?? null;
}

function TrainingReportPanel({ report }: { report: TrainingReport }) {
  const metric = findTrainingReportMetric(report);
  if (!metric) return null;
  const series = report.rows.flatMap((row) => {
    const value = row.metrics[metric];
    return typeof value === "number" ? [{ epoch: row.epoch, value }] : [];
  });
  if (series.length === 0) return null;

  const values = series.map((item) => item.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum;
  const chartWidth = 320;
  const chartHeight = 84;
  const inset = 8;
  const coordinates = series.map((item, index) => {
    const x = series.length === 1
      ? chartWidth / 2
      : inset + (index / (series.length - 1)) * (chartWidth - inset * 2);
    const y = span === 0
      ? chartHeight / 2
      : chartHeight - inset - ((item.value - minimum) / span) * (chartHeight - inset * 2);
    return { x, y };
  });
  const points = coordinates.map(({ x, y }) => `${x},${y}`).join(" ");
  const lastPoint = coordinates.at(-1) ?? coordinates[0];
  const first = series[0];
  const latest = series.at(-1) ?? first;

  return (
    <article className="panel training-detail-section training-report-section">
      <div className="training-detail-section-heading training-report-heading">
        <div><SlidersHorizontal size={16} /><h3>训练曲线</h3></div>
        <span>{series.length} 轮记录</span>
      </div>
      <div className="training-report-summary">
        <div><span>指标</span><strong>{formatMetricName(metric)}</strong></div>
        <div><span>开始</span><strong>{formatScore(first.value)}</strong></div>
        <div><span>最新</span><strong>{formatScore(latest.value)}</strong></div>
      </div>
      <div className="training-report-chart" role="img" aria-label={`${formatMetricName(metric)}训练曲线`}>
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none" aria-hidden="true">
          <line x1={inset} x2={chartWidth - inset} y1={chartHeight / 2} y2={chartHeight / 2} />
          <polyline points={points} />
          <circle cx={lastPoint.x} cy={lastPoint.y} r="3" />
        </svg>
      </div>
      <p className="training-report-note">第 {latest.epoch + 1} 轮 · 由训练产物 results.csv 生成</p>
    </article>
  );
}

function TrainingVisualizationsPanel({ visualizations }: { visualizations: TrainingVisualizationUrls }) {
  const entries = trainingVisualizationOptions.flatMap((option) => {
    const src = visualizations[option.name];
    return src ? [{ ...option, src }] : [];
  });
  if (entries.length === 0) return null;

  return (
    <article className="panel training-detail-section training-visualizations-section">
      <div className="training-detail-section-heading training-visualizations-heading">
        <div><FileCheck2 size={16} /><h3>类别识别情况</h3></div>
        <span>{entries.length} 项</span>
      </div>
      <div className="training-visualizations-grid">
        {entries.map((entry) => (
          <figure className="training-visualization" key={entry.name}>
            <DynamicAssetImage src={entry.src} alt={`${entry.title}图`} />
            <figcaption>
              <strong>{entry.title}</strong>
              <span>{entry.description}</span>
            </figcaption>
          </figure>
        ))}
      </div>
      <p className="training-report-note">由本次训练产生，可用来查看容易混淆的类别。</p>
    </article>
  );
}

function TrainingClassMetricsPanel({ metrics }: { metrics: TrainingClassMetrics }) {
  if (metrics.classes.length === 0) return null;

  return (
    <article className="panel training-detail-section training-class-metrics-section">
      <div className="training-detail-section-heading training-class-metrics-heading">
        <div><FileCheck2 size={16} /><h3>按类别查看</h3></div>
        <span>{metrics.classes.length} 类</span>
      </div>
      <div className="training-class-metrics-table" role="table" aria-label="类别识别指标">
        <div className="training-class-metrics-row is-heading" role="row">
          <span role="columnheader">类别</span>
          <span role="columnheader">mAP50</span>
          <span role="columnheader">精确率</span>
          <span role="columnheader">召回率</span>
        </div>
        {metrics.classes.map((item) => (
          <div className="training-class-metrics-row" role="row" key={item.class_id}>
            <strong role="cell">{item.name}</strong>
            <span role="cell">{formatScore(item.map50)}</span>
            <span role="cell">{formatScore(item.precision)}</span>
            <span role="cell">{formatScore(item.recall)}</span>
          </div>
        ))}
      </div>
      <p className="training-report-note">由本次训练的验证集复核产生。</p>
    </article>
  );
}

export function TrainingArtifactDetail({ artifactId, kind }: ArtifactDetailProps) {
  const requestedProjectId = useSearchParams().get("project");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [runEvents, setRunEvents] = useState<RunEvent[]>([]);
  const [trainingReport, setTrainingReport] = useState<TrainingReport | null>(null);
  const [trainingClassMetrics, setTrainingClassMetrics] = useState<TrainingClassMetrics | null>(null);
  const [trainingVisualizations, setTrainingVisualizations] = useState<TrainingVisualizationUrls>({});
  const [models, setModels] = useState<ModelVersion[]>([]);
  const [versions, setVersions] = useState<VersionOption[]>([]);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);

  useEffect(() => {
    let cancelled = false;
    const visualizationUrls: string[] = [];
    setLoading(true);
    setError(null);
    setTrainingVisualizations({});
    setTrainingClassMetrics(null);
    void catalogApi.listWorkspaces()
      .then(async (workspaces) => {
        const workspace = workspaces[0];
        if (!workspace) return;
        const projects = await catalogApi.listProjects(workspace.id);
        const selectedProject = projects.find((item) => item.id === requestedProjectId) ?? projects[0] ?? null;
        setProject(selectedProject);
        if (!selectedProject) return;

        const [nextRuns, nextModels, datasets, nextEvaluations, nextDeployments] = await Promise.all([
          catalogApi.listTrainingRuns(workspace.id, selectedProject.id),
          catalogApi.listModelVersions(workspace.id, selectedProject.id),
          catalogApi.listDatasets(workspace.id, selectedProject.id),
          catalogApi.listEvaluations(workspace.id, selectedProject.id),
          catalogApi.listDeployments(workspace.id, selectedProject.id),
        ]);
        const eventRunId = kind === "run"
          ? artifactId
          : nextModels.find((item) => item.id === artifactId)?.run_id ?? null;
        const reportRun = nextRuns.find((item) => item.id === eventRunId) ?? null;
        const [nextRunEvents, nextTrainingReport, nextTrainingClassMetrics] = await Promise.all([
          eventRunId ? catalogApi.listRunEvents(workspace.id, eventRunId) : Promise.resolve([]),
          reportRun?.status === "succeeded"
            ? catalogApi.getTrainingReport(workspace.id, reportRun.id).catch(() => null)
            : Promise.resolve(null),
          reportRun?.status === "succeeded"
            ? catalogApi.getTrainingClassMetrics(workspace.id, reportRun.id).catch(() => null)
            : Promise.resolve(null),
        ]);
        const visualizationEntries = reportRun?.status === "succeeded"
          ? await Promise.all(trainingVisualizationOptions.map(async ({ name }) => {
            const blob = await catalogApi
              .getTrainingVisualization(workspace.id, reportRun.id, name)
              .catch(() => null);
            if (!blob) return null;
            const url = URL.createObjectURL(blob);
            visualizationUrls.push(url);
            return [name, url] as const;
          }))
          : [];
        const versionGroups = await Promise.all(
          datasets.map(async (dataset) => ({
            dataset,
            versions: await catalogApi.listVersions(workspace.id, dataset.id),
          })),
        );
        if (cancelled) {
          visualizationUrls.forEach((url) => URL.revokeObjectURL(url));
          return;
        }
        setRuns(nextRuns);
        setRunEvents(nextRunEvents);
        setTrainingReport(nextTrainingReport);
        setTrainingClassMetrics(nextTrainingClassMetrics);
        setTrainingVisualizations(
          Object.fromEntries(visualizationEntries.flatMap((entry) => entry ? [entry] : [])) as TrainingVisualizationUrls,
        );
        setModels(nextModels);
        setVersions(versionGroups.flatMap(({ dataset, versions: items }) =>
          items.map((version) => ({ dataset, version })),
        ));
        setEvaluations(nextEvaluations);
        setDeployments(nextDeployments);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "详情加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      visualizationUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [artifactId, kind, requestedProjectId]);

  const run = kind === "run" ? runs.find((item) => item.id === artifactId) ?? null : null;
  const model = kind === "model" ? models.find((item) => item.id === artifactId) ?? null : null;
  const relatedRun = run ?? runs.find((item) => item.id === model?.run_id) ?? null;
  const relatedModel = model ?? models.find((item) => item.run_id === run?.id) ?? null;
  const datasetVersion = versions.find((item) => item.version.id === relatedRun?.dataset_version_id) ?? null;
  const evaluation = useMemo(
    () => evaluations.find((item) => item.model_version_id === relatedModel?.id) ?? null,
    [evaluations, relatedModel?.id],
  );
  const deployment = deployments.find((item) => item.model_version_id === relatedModel?.id) ?? null;
  const projectQuery = project ? `?project=${project.id}` : "";
  const trainingHref = `/studio/training${projectQuery}`;

  if (loading) {
    return (
      <section className="panel training-detail-loading" aria-live="polite">
        <LoaderCircle size={17} className="spinner" />正在读取详情…
      </section>
    );
  }

  if (error) {
    return (
      <section className="panel training-detail-empty">
        <AlertCircle size={20} />
        <h2>详情暂时无法打开</h2>
        <p>{error}</p>
        <Link className="secondary-button" href={trainingHref}>返回训练</Link>
      </section>
    );
  }

  if ((kind === "run" && !run) || (kind === "model" && !model)) {
    return (
      <section className="panel training-detail-empty">
        <AlertCircle size={20} />
        <h2>{kind === "run" ? "没有找到训练任务" : "没有找到模型"}</h2>
        <p>它可能已被移除，或不属于当前项目。</p>
        <Link className="secondary-button" href={trainingHref}>返回训练</Link>
      </section>
    );
  }

  if (kind === "run" && run) {
    const progress = Math.min(100, Math.max(0, run.progress));
    const status = runStatusLabels[run.status] ?? run.status;

    return (
      <section className="training-detail-workbench">
        <Link className="training-detail-back" href={trainingHref}><ArrowLeft size={14} />返回训练</Link>

        <article className="panel training-detail-hero">
          <div className="training-detail-hero-heading">
            <div>
              <span className={`training-detail-status is-${run.status}`}><i />{status}</span>
              <h2>{String(run.recipe.model ?? run.engine)}</h2>
              <p>任务 {run.id.slice(0, 8)} · 创建于 {formatTime(run.created_at)}</p>
            </div>
            <span className="training-detail-hero-icon"><FlaskConical size={20} /></span>
          </div>

          <div className="training-detail-progress-copy">
            <span>训练进度</span><strong>{progress}%</strong>
          </div>
          <span className="progress-track training-detail-progress"><span style={{ width: `${progress}%` }} /></span>

          <div className="training-detail-timeline">
            <div><span>创建时间</span><strong>{formatTime(run.created_at)}</strong></div>
            <div><span>开始时间</span><strong>{formatTime(run.started_at)}</strong></div>
            <div><span>完成时间</span><strong>{formatTime(run.finished_at)}</strong></div>
          </div>
        </article>

        <div className="training-detail-grid">
          <article className="panel training-detail-section">
            <div className="training-detail-section-heading"><SlidersHorizontal size={16} /><h3>训练参数</h3></div>
            <dl className="training-detail-spec-list">
              <div><dt>数据版本</dt><dd>{datasetVersion ? `${datasetVersion.dataset.name} · v${datasetVersion.version.version_number}` : run.dataset_version_id.slice(0, 8)}</dd></div>
              <div><dt>基础模型</dt><dd>{String(run.recipe.model ?? "—")}</dd></div>
              <div><dt>训练引擎</dt><dd>{run.engine}</dd></div>
              <div><dt>执行器</dt><dd>{run.executor}</dd></div>
              <div><dt>训练轮次</dt><dd>{String(run.recipe.epochs ?? "—")}</dd></div>
              <div><dt>图像尺寸</dt><dd>{run.recipe.image_size ? `${String(run.recipe.image_size)} px` : "—"}</dd></div>
              <div><dt>批量大小</dt><dd>{String(run.recipe.batch_size ?? "—")}</dd></div>
              <div><dt>随机种子</dt><dd>{String(run.recipe.seed ?? "—")}</dd></div>
            </dl>
          </article>

          <article className="panel training-detail-section">
            <div className="training-detail-section-heading"><Cpu size={16} /><h3>任务结果</h3></div>
            {relatedModel ? (
              <div className="training-detail-result">
                <span className="training-detail-result-icon"><Check size={18} /></span>
                <div><small>已生成模型</small><strong>{relatedModel.model_name} · v{relatedModel.version_number}</strong><p>{modelStatusLabels[relatedModel.status] ?? relatedModel.status}</p></div>
                <Link href={`/studio/training/models/${relatedModel.id}${projectQuery}`} aria-label="查看模型"><ArrowUpRight size={15} /></Link>
              </div>
            ) : run.status === "failed" ? (
              <div className="training-detail-result is-error">
                <span className="training-detail-result-icon"><AlertCircle size={18} /></span>
                <div><small>任务失败</small><strong>{run.error_code ?? "训练未完成"}</strong><p>{run.error_message ?? "请检查执行环境后重新提交。"}</p></div>
              </div>
            ) : (
              <div className="training-detail-result">
                <span className="training-detail-result-icon"><Clock3 size={18} /></span>
                <div><small>{activeRunStatuses.has(run.status) ? "等待训练完成" : "暂无模型"}</small><strong>{activeRunStatuses.has(run.status) ? "任务仍在运行" : "没有登记模型产物"}</strong><p>模型生成后会自动出现在这里。</p></div>
              </div>
            )}
          </article>
        </div>

        {trainingReport ? <TrainingReportPanel report={trainingReport} /> : null}
        {trainingClassMetrics ? <TrainingClassMetricsPanel metrics={trainingClassMetrics} /> : null}
        <TrainingVisualizationsPanel visualizations={trainingVisualizations} />

        <article className="panel training-detail-section training-events-section">
          <div className="training-detail-section-heading training-events-heading">
            <div><Clock3 size={16} /><h3>运行过程</h3></div>
            <span>{runEvents.length} 条记录</span>
          </div>
          {runEvents.length > 0 ? (
            <ol className="training-events-list">
              {runEvents.map((event) => (
                <li key={event.id}>
                  <span className={`training-event-marker is-${event.status}`} aria-hidden="true" />
                  <div className="training-event-copy">
                    <strong>{runEventLabels[event.event_type] ?? event.event_type}</strong>
                    <small>{formatTime(event.occurred_at)} · {event.progress}%</small>
                  </div>
                  {event.payload.error_message ? <p>{String(event.payload.error_message)}</p> : null}
                </li>
              ))}
            </ol>
          ) : (
            <p className="training-events-empty">执行器尚未回传运行事件。</p>
          )}
        </article>
      </section>
    );
  }

  if (!model || !relatedModel) return null;

  const map50 = readMetric(model.metrics, ["metrics/mAP50(B)", "mAP50", "map50"]);
  const map5095 = readMetric(model.metrics, ["metrics/mAP50-95(B)", "mAP50-95", "map50_95"]);
  const precision = readMetric(model.metrics, ["metrics/precision(B)", "precision"]);
  const recall = readMetric(model.metrics, ["metrics/recall(B)", "recall"]);

  return (
    <section className="training-detail-workbench">
      <Link className="training-detail-back" href={trainingHref}><ArrowLeft size={14} />返回训练</Link>

      <article className="panel training-detail-hero model-detail-hero">
        <div className="training-detail-hero-heading">
          <div>
            <span className={`training-detail-status is-${model.status}`}><i />{modelStatusLabels[model.status] ?? model.status}</span>
            <h2>{model.model_name} · v{model.version_number}</h2>
            <p>来自训练任务 {model.run_id.slice(0, 8)} · 创建于 {formatTime(model.created_at)}</p>
          </div>
          <span className="training-detail-hero-icon"><Cpu size={20} /></span>
        </div>

        <div className="model-detail-metrics">
          <div><span>mAP50</span><strong>{formatScore(map50)}</strong></div>
          <div><span>mAP50–95</span><strong>{formatScore(map5095)}</strong></div>
          <div><span>精确率</span><strong>{formatScore(precision)}</strong></div>
          <div><span>召回率</span><strong>{formatScore(recall)}</strong></div>
        </div>
      </article>

      <div className="training-detail-grid">
        <article className="panel training-detail-section">
          <div className="training-detail-section-heading"><Database size={16} /><h3>模型来源</h3></div>
          <dl className="training-detail-spec-list">
            <div><dt>数据版本</dt><dd>{datasetVersion ? `${datasetVersion.dataset.name} · v${datasetVersion.version.version_number}` : "—"}</dd></div>
            <div><dt>基础模型</dt><dd>{String(relatedRun?.recipe.model ?? "—")}</dd></div>
            <div><dt>训练轮次</dt><dd>{String(relatedRun?.recipe.epochs ?? "—")}</dd></div>
            <div><dt>图像尺寸</dt><dd>{relatedRun?.recipe.image_size ? `${String(relatedRun.recipe.image_size)} px` : "—"}</dd></div>
          </dl>
          {relatedRun ? <Link className="training-detail-inline-link" href={`/studio/training/runs/${relatedRun.id}${projectQuery}`}>查看训练任务<ArrowUpRight size={13} /></Link> : null}
        </article>

        <article className="panel training-detail-section">
          <div className="training-detail-section-heading"><FileCheck2 size={16} /><h3>模型状态</h3></div>
          <div className="model-detail-status-list">
            <div><span>模型检查</span><strong>{evaluation ? evaluation.verdict === "approved" ? "已通过" : "未通过" : "尚未检查"}</strong><small>{evaluation ? `${evaluation.policy_name} · ${formatTime(evaluation.evaluated_at)}` : "在发布前完成检查"}</small></div>
            <div><span>在线服务</span><strong>{deployment?.status === "published" ? "运行中" : "未发布"}</strong><small>{deployment ? deployment.name : "尚未创建在线服务"}</small></div>
          </div>
          <div className="training-detail-section-actions">
            <Link className="primary-button" href={`/services${projectQuery}${projectQuery ? "&" : "?"}view=publish&model=${model.id}`}><Rocket size={13} />测试与发布</Link>
          </div>
        </article>
      </div>

      {trainingReport ? <TrainingReportPanel report={trainingReport} /> : null}
      {trainingClassMetrics ? <TrainingClassMetricsPanel metrics={trainingClassMetrics} /> : null}
      <TrainingVisualizationsPanel visualizations={trainingVisualizations} />

      {evaluation ? (
        <article className="panel training-detail-section model-evaluation-section">
          <div className="training-detail-section-heading model-evaluation-heading">
            <div><FileCheck2 size={16} /><h3>检查结果</h3></div>
            <strong className={`model-evaluation-verdict is-${evaluation.verdict}`}>
              {evaluation.verdict === "approved" ? "已通过" : "未通过"}
            </strong>
          </div>
          <p className="model-evaluation-summary">
            {evaluation.policy_name} · {evaluation.source === "acceptance-dataset" ? "验收数据" : evaluation.source} · {formatTime(evaluation.evaluated_at)}
          </p>

          {Object.entries(evaluation.metrics).some(([, value]) => typeof value === "number") ? (
            <div className="model-evaluation-metrics">
              {Object.entries(evaluation.metrics)
                .filter(([, value]) => typeof value === "number")
                .slice(0, 4)
                .map(([metric, value]) => (
                  <div className="model-evaluation-metric" key={metric}>
                    <span>{formatMetricName(metric)}</span>
                    <strong>{formatMetricValue(value)}</strong>
                  </div>
                ))}
            </div>
          ) : null}

          {evaluation.rule_results.length > 0 ? (
            <div className="model-evaluation-rules">
              {evaluation.rule_results.map((rule, index) => (
                <div className="model-evaluation-rule" key={`${rule.metric}-${index}`}>
                  <span className={`model-evaluation-rule-icon is-${rule.passed ? "passed" : "failed"}`} aria-hidden="true">
                    {rule.passed ? <Check size={13} /> : <AlertCircle size={13} />}
                  </span>
                  <div className="model-evaluation-rule-copy">
                    <strong>{rule.label ?? formatMetricName(rule.metric)}</strong>
                    <small>
                      目标 {rule.operator} {formatScore(rule.threshold)} · 实际 {rule.actual === null ? "无结果" : formatScore(rule.actual)}
                    </small>
                    {rule.reason ? <small>{rule.reason}</small> : null}
                  </div>
                  <em className={`model-evaluation-rule-status is-${rule.passed ? "passed" : "failed"}`}>
                    {rule.passed ? "通过" : "未通过"}
                  </em>
                </div>
              ))}
            </div>
          ) : (
            <p className="model-evaluation-empty">本次检查没有配置逐项门禁。</p>
          )}
        </article>
      ) : null}
    </section>
  );
}
