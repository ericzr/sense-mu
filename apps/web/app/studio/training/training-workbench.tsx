"use client";

import {
  AlertCircle,
  ArrowUpRight,
  BadgeCheck,
  Ban,
  Box,
  Check,
  Cpu,
  Database,
  FlaskConical,
  LoaderCircle,
  Play,
  RefreshCw,
  ShieldCheck,
  TestTubeDiagonal,
  Timer,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type Dataset,
  type DatasetVersion,
  type Evaluation,
  type EvaluationPolicy,
  type ModelVersion,
  type Project,
  type TrainingEngine,
  type TrainingRun,
  type Workspace,
  catalogApi,
} from "../../../lib/catalog-api";

type VersionOption = {
  dataset: Dataset;
  version: DatasetVersion;
};

const statusLabels: Record<string, string> = {
  queued: "排队中",
  preparing: "准备中",
  running: "运行中",
  cancel_requested: "正在取消",
  cancelled: "已取消",
  succeeded: "已完成",
  failed: "已失败",
};

const activeStatuses = new Set(["queued", "preparing", "running", "cancel_requested"]);
const modelStatusLabels: Record<string, string> = {
  candidate: "候选版本",
  validation_passed: "训练验证通过",
  validation_failed: "训练验证未通过",
  approved: "已通过",
  rejected: "未通过",
  archived: "已归档",
};

const comparisonMetrics = [
  { label: "mAP50", keys: ["metrics/mAP50(B)", "mAP50", "map50"] },
  { label: "mAP50–95", keys: ["metrics/mAP50-95(B)", "mAP50-95", "map50_95"] },
  { label: "精确率", keys: ["metrics/precision(B)", "precision"] },
  { label: "召回率", keys: ["metrics/recall(B)", "recall"] },
];

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function readModelMetric(model: ModelVersion, keys: string[]): number | null {
  for (const key of keys) {
    const value = model.metrics[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function formatModelMetric(value: number | null): string {
  if (value === null) return "—";
  return value >= 0 && value <= 1 ? `${(value * 100).toFixed(1)}%` : value.toFixed(2);
}

function ModelComparisonPanel({ models }: { models: ModelVersion[] }) {
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");

  useEffect(() => {
    setLeftId((current) => models.some((model) => model.id === current) ? current : models[0]?.id ?? "");
    setRightId((current) => models.some((model) => model.id === current) ? current : models[1]?.id ?? "");
  }, [models]);

  if (models.length < 2) return null;
  const left = models.find((model) => model.id === leftId) ?? models[0];
  const right = models.find((model) => model.id === rightId) ?? models[1];

  function chooseLeft(id: string) {
    setLeftId(id);
    if (id === right.id) setRightId(models.find((model) => model.id !== id)?.id ?? id);
  }

  function chooseRight(id: string) {
    setRightId(id);
    if (id === left.id) setLeftId(models.find((model) => model.id !== id)?.id ?? id);
  }

  return (
    <article className="panel model-comparison-card">
      <div className="training-card-heading">
        <span className="training-card-icon"><Box size={17} /></span>
        <div>
          <h2>模型对比</h2>
          <p>只比较已登记版本的真实训练结果。</p>
        </div>
      </div>
      <div className="model-comparison-selectors">
        <label className="training-field">
          <span>版本一</span>
          <select value={left.id} onChange={(event) => chooseLeft(event.target.value)}>
            {models.map((model) => <option value={model.id} key={model.id}>{model.model_name} · v{model.version_number}</option>)}
          </select>
        </label>
        <label className="training-field">
          <span>版本二</span>
          <select value={right.id} onChange={(event) => chooseRight(event.target.value)}>
            {models.map((model) => <option value={model.id} key={model.id}>{model.model_name} · v{model.version_number}</option>)}
          </select>
        </label>
      </div>
      <div className="model-comparison-table" role="table" aria-label="模型指标对比">
        <div className="model-comparison-row is-heading" role="row">
          <span role="columnheader">指标</span>
          <span role="columnheader">{left.model_name} · v{left.version_number}</span>
          <span role="columnheader">{right.model_name} · v{right.version_number}</span>
        </div>
        {comparisonMetrics.map((metric) => (
          <div className="model-comparison-row" role="row" key={metric.label}>
            <span role="cell">{metric.label}</span>
            <strong role="cell">{formatModelMetric(readModelMetric(left, metric.keys))}</strong>
            <strong role="cell">{formatModelMetric(readModelMetric(right, metric.keys))}</strong>
          </div>
        ))}
      </div>
    </article>
  );
}

export function TrainingWorkbench() {
  const searchParams = useSearchParams();
  const requestedProjectId = searchParams.get("project");
  const requestedDatasetVersionId = searchParams.get("datasetVersion");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [engines, setEngines] = useState<TrainingEngine[]>([]);
  const [versionOptions, setVersionOptions] = useState<VersionOption[]>([]);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [acceptanceRuns, setAcceptanceRuns] = useState<TrainingRun[]>([]);
  const [modelVersions, setModelVersions] = useState<ModelVersion[]>([]);
  const [policies, setPolicies] = useState<EvaluationPolicy[]>([]);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [datasetVersionId, setDatasetVersionId] = useState("");
  const [engineKey, setEngineKey] = useState("ultralytics");
  const [model, setModel] = useState("yolo26s.pt");
  const [epochs, setEpochs] = useState(100);
  const [imageSize, setImageSize] = useState(640);
  const [batchSize, setBatchSize] = useState(16);
  const [seed, setSeed] = useState(42);
  const [acceptanceModelVersionId, setAcceptanceModelVersionId] = useState("");
  const [acceptanceDatasetVersionId, setAcceptanceDatasetVersionId] = useState("");
  const [acceptanceImageSize, setAcceptanceImageSize] = useState(640);
  const [acceptanceBatchSize, setAcceptanceBatchSize] = useState(16);
  const idempotencyKey = useRef<string | null>(null);
  const acceptanceIdempotencyKey = useRef<string | null>(null);

  const selectedEngine = useMemo(
    () => engines.find((engine) => engine.key === engineKey) ?? engines[0],
    [engineKey, engines],
  );

  const acceptanceOptions = useMemo(() => {
    const selectedModel = modelVersions.find(
      (version) => version.id === acceptanceModelVersionId,
    );
    const trainingRun = runs.find((run) => run.id === selectedModel?.run_id);
    return versionOptions.filter(
      ({ version }) => version.id !== trainingRun?.dataset_version_id,
    );
  }, [acceptanceModelVersionId, modelVersions, runs, versionOptions]);

  const activePolicy = policies.find((policy) => policy.is_active) ?? null;

  const refreshProjectState = useCallback(async (selectedWorkspace: Workspace, selectedProject: Project) => {
    const [
      datasets,
      nextRuns,
      nextModels,
      nextAcceptanceRuns,
      nextPolicies,
      nextEvaluations,
    ] = await Promise.all([
      catalogApi.listDatasets(selectedWorkspace.id, selectedProject.id),
      catalogApi.listTrainingRuns(selectedWorkspace.id, selectedProject.id),
      catalogApi.listModelVersions(selectedWorkspace.id, selectedProject.id),
      catalogApi.listAcceptanceRuns(selectedWorkspace.id, selectedProject.id),
      catalogApi.listEvaluationPolicies(selectedWorkspace.id, selectedProject.id),
      catalogApi.listEvaluations(selectedWorkspace.id, selectedProject.id),
    ]);
    const versionsByDataset = await Promise.all(
      datasets.map(async (dataset) => ({
        dataset,
        versions: await catalogApi.listVersions(selectedWorkspace.id, dataset.id),
      })),
    );
    const options = versionsByDataset.flatMap(({ dataset, versions }) =>
      versions
        .filter((version) => version.status === "frozen")
        .map((version) => ({ dataset, version })),
    );
    setVersionOptions(options);
    setDatasetVersionId((current) =>
      options.some(({ version }) => version.id === current)
        ? current
        : options.find(({ version }) => version.id === requestedDatasetVersionId)?.version.id
          ?? options[0]?.version.id
          ?? "",
    );
    setRuns(nextRuns);
    setModelVersions(nextModels);
    setAcceptanceRuns(nextAcceptanceRuns);
    setPolicies(nextPolicies);
    setEvaluations(nextEvaluations);
    setAcceptanceModelVersionId((current) =>
      nextModels.some((version) => version.id === current)
        ? current
        : nextModels[0]?.id ?? "",
    );
  }, [requestedDatasetVersionId]);

  useEffect(() => {
    void Promise.all([catalogApi.listWorkspaces(), catalogApi.listTrainingEngines()])
      .then(async ([workspaces, nextEngines]) => {
        const selectedWorkspace = workspaces[0] ?? null;
        setEngines(nextEngines);
        setWorkspace(selectedWorkspace);
        if (!selectedWorkspace) return;
        const projects = await catalogApi.listProjects(selectedWorkspace.id);
        const selectedProject = projects.find((item) => item.id === requestedProjectId) ?? projects[0] ?? null;
        setProject(selectedProject);
        if (selectedProject) await refreshProjectState(selectedWorkspace, selectedProject);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "训练数据加载失败"))
      .finally(() => setLoading(false));
  }, [refreshProjectState, requestedProjectId]);

  useEffect(() => {
    if (
      !workspace
      || !project
      || ![...runs, ...acceptanceRuns].some((run) => activeStatuses.has(run.status))
    ) return;
    const timer = window.setInterval(() => {
      void Promise.all([
        catalogApi.listTrainingRuns(workspace.id, project.id),
        catalogApi.listModelVersions(workspace.id, project.id),
        catalogApi.listAcceptanceRuns(workspace.id, project.id),
        catalogApi.listEvaluations(workspace.id, project.id),
      ]).then(([nextRuns, nextModels, nextAcceptanceRuns, nextEvaluations]) => {
        setRuns(nextRuns);
        setModelVersions(nextModels);
        setAcceptanceRuns(nextAcceptanceRuns);
        setEvaluations(nextEvaluations);
      });
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [workspace, project, runs, acceptanceRuns]);

  useEffect(() => {
    setAcceptanceDatasetVersionId((current) =>
      acceptanceOptions.some(({ version }) => version.id === current)
        ? current
        : acceptanceOptions[0]?.version.id ?? "",
    );
  }, [acceptanceOptions]);

  async function submitTraining(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !project || !datasetVersionId || !selectedEngine) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    idempotencyKey.current ??= crypto.randomUUID();
    try {
      const run = await catalogApi.createTrainingRun(
        workspace.id,
        project.id,
        idempotencyKey.current,
        {
          dataset_version_id: datasetVersionId,
          engine: selectedEngine.key,
          executor: selectedEngine.executor,
          recipe: {
            model,
            task: "detect",
            epochs,
            image_size: imageSize,
            batch_size: batchSize,
            seed,
          },
        },
      );
      idempotencyKey.current = null;
      await refreshProjectState(workspace, project);
      setNotice(run.reused ? "已恢复上次提交的训练任务" : "训练任务已进入队列");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "训练任务提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitAcceptance(event: FormEvent) {
    event.preventDefault();
    if (
      !workspace
      || !project
      || !acceptanceModelVersionId
      || !acceptanceDatasetVersionId
      || !activePolicy
    ) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    acceptanceIdempotencyKey.current ??= crypto.randomUUID();
    try {
      const run = await catalogApi.createAcceptanceRun(
        workspace.id,
        project.id,
        acceptanceModelVersionId,
        acceptanceIdempotencyKey.current,
        {
          dataset_version_id: acceptanceDatasetVersionId,
          image_size: acceptanceImageSize,
          batch_size: acceptanceBatchSize,
        },
      );
      acceptanceIdempotencyKey.current = null;
      await refreshProjectState(workspace, project);
      setNotice(run.reused ? "已恢复上次提交的检查任务" : "独立数据检查已进入队列");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "模型检查提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function cancelRun(run: TrainingRun) {
    if (!workspace || !project) return;
    setBusy(true);
    setError(null);
    try {
      await catalogApi.cancelTrainingRun(workspace.id, run.id);
      await refreshProjectState(workspace, project);
      setNotice("已提交取消请求");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "取消请求失败");
    } finally {
      setBusy(false);
    }
  }

  async function dispatchRun(run: TrainingRun) {
    if (!workspace || !project) return;
    setBusy(true);
    setError(null);
    try {
      await catalogApi.dispatchTrainingRun(workspace.id, run.id);
      await refreshProjectState(workspace, project);
      setNotice("训练任务已重新入队");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重新入队失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <section className="panel training-loading" aria-live="polite">
        <LoaderCircle size={19} className="spinner" />
        <span>正在读取数据版本与训练状态…</span>
      </section>
    );
  }

  if (!workspace || !project) {
    return (
      <section className="panel training-prerequisite">
        <AlertCircle size={20} />
        <span className="eyebrow">缺少前置数据</span>
        <h2>请先创建工作区和项目</h2>
        <Link className="primary-button" href="/studio/data?createProject=1">创建项目</Link>
      </section>
    );
  }

  return (
    <section className="training-workbench">
      {error ? (
        <div className="workbench-message error-message" role="alert">
          <AlertCircle size={15} />
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)}>关闭</button>
        </div>
      ) : null}
      {notice ? (
        <div className="workbench-message notice-message" role="status">
          <Check size={14} />
          <span>{notice}</span>
        </div>
      ) : null}

      <section className="training-object-summary" aria-label="训练项目摘要">
        <div className="training-object-summary-copy">
          <span className="eyebrow">训练与模型</span>
          <h2>训练任务</h2>
          <p>从冻结数据版本启动训练，完成后生成可追溯的模型版本。</p>
        </div>
        <div className="training-object-summary-stats">
          <div><span>数据版本</span><strong>{versionOptions.length}</strong></div>
          <div><span>训练任务</span><strong>{runs.length}</strong></div>
          <div><span>模型版本</span><strong>{modelVersions.length}</strong></div>
          <div><span>运行中</span><strong>{runs.filter((run) => activeStatuses.has(run.status)).length}</strong></div>
        </div>
        <Link className="secondary-button compact" href={`/studio/data?project=${project.id}`}><Database size={14} />查看数据</Link>
      </section>

      <div className="training-primary-grid">
        <form className="panel training-config-card" id="new-training" onSubmit={(event) => void submitTraining(event)}>
          <div className="training-card-heading">
            <span className="training-card-icon"><FlaskConical size={17} /></span>
            <div>
              <h2>新建训练</h2>
            </div>
          </div>

          {versionOptions.length ? (
            <div className="training-form-grid">
              <label className="training-field training-field-wide">
                <span>数据集版本</span>
                <select value={datasetVersionId} onChange={(event) => setDatasetVersionId(event.target.value)}>
                  {versionOptions.map(({ dataset, version }) => (
                    <option value={version.id} key={version.id}>
                      {dataset.name} · ds_v{version.version_number} · {version.asset_count} 个资产
                    </option>
                  ))}
                </select>
              </label>
              <label className="training-field">
                <span>训练引擎</span>
                <select
                  value={engineKey}
                  onChange={(event) => {
                    const nextEngine = engines.find((engine) => engine.key === event.target.value);
                    setEngineKey(event.target.value);
                    if (nextEngine) setModel(nextEngine.defaults.model);
                  }}
                >
                  {engines.map((engine) => <option value={engine.key} key={engine.key}>{engine.label}</option>)}
                </select>
              </label>
              <label className="training-field">
                <span>基础模型</span>
                <select value={model} onChange={(event) => setModel(event.target.value)}>
                  {(selectedEngine?.models ?? []).map((item) => <option value={item} key={item}>{item}</option>)}
                </select>
              </label>
              <label className="training-field"><span>训练轮次</span><input type="number" min="1" max="500" value={epochs} onChange={(event) => setEpochs(Number(event.target.value))} /></label>
              <label className="training-field"><span>图像尺寸</span><input type="number" min="320" max="1536" step="32" value={imageSize} onChange={(event) => setImageSize(Number(event.target.value))} /></label>
              <label className="training-field"><span>批量大小</span><input type="number" min="1" max="256" value={batchSize} onChange={(event) => setBatchSize(Number(event.target.value))} /></label>
              <label className="training-field"><span>随机种子</span><input type="number" min="0" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></label>
            </div>
          ) : (
            <div className="training-inline-empty">
              <Database size={18} />
              <div><strong>尚无可训练的数据版本</strong><span>先导入资产并冻结数据版本。</span></div>
              <Link href={`/studio/data?project=${project.id}`}>前往数据</Link>
            </div>
          )}

          <div className="training-submit-row">
            <span><ShieldCheck size={14} />SenseMu 提供训练环境 · 费用功能尚未开通</span>
            <button className="primary-button" type="submit" disabled={busy || !datasetVersionId}>
              {busy ? <LoaderCircle size={14} className="spinner" /> : <Play size={14} fill="currentColor" />}
              提交训练
            </button>
          </div>
        </form>

        <article className="panel training-runs-card">
          <div className="training-card-heading">
            <span className="training-card-icon"><Timer size={17} /></span>
            <div><h2>运行记录</h2></div>
            <button type="button" aria-label="刷新训练队列" onClick={() => void refreshProjectState(workspace, project)}><RefreshCw size={14} /></button>
          </div>
          {runs.length ? (
            <div className="training-run-list">
              {runs.map((run) => (
                <div className="training-run-row" key={run.id}>
                  <div className="training-run-topline">
                    <span className={`run-state-chip ${run.status}`}>{statusLabels[run.status] ?? run.status}</span>
                    <small>{formatTime(run.created_at)}</small>
                  </div>
                  <strong>{String(run.recipe.model ?? run.engine)}</strong>
                  <span>数据版本 ds_v{versionOptions.find(({ version }) => version.id === run.dataset_version_id)?.version.version_number ?? "—"} · {String(run.recipe.epochs ?? "—")} 轮 · 平台训练</span>
                  {run.error_message ? (
                    <p className="training-run-error"><AlertCircle size={12} />{run.error_message}</p>
                  ) : null}
                  <div className="training-run-progress"><span style={{ width: `${run.progress}%` }} /></div>
                  <div className="training-run-footer">
                    <code>{run.id.slice(0, 8)}</code>
                    <div className="training-run-actions">
                      <Link className="training-run-detail-link" href={`/studio/training/runs/${run.id}?project=${project.id}`}>详情<ArrowUpRight size={11} /></Link>
                      {run.status === "queued" ? (
                        <button className="dispatch-action" type="button" disabled={busy} onClick={() => void dispatchRun(run)}><RefreshCw size={12} />重新入队</button>
                      ) : null}
                      {activeStatuses.has(run.status) && run.status !== "cancel_requested" ? (
                        <button type="button" disabled={busy} onClick={() => void cancelRun(run)}><Ban size={12} />取消</button>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="training-runs-empty"><Cpu size={19} /><p>尚无训练任务，首次提交后会在此追踪。</p></div>
          )}
        </article>
      </div>

      <form
        id="acceptance-evaluation"
        className="panel acceptance-card"
        onSubmit={(event) => void submitAcceptance(event)}
      >
        <div className="training-card-heading">
          <span className="training-card-icon"><TestTubeDiagonal size={17} /></span>
          <div>
            <span className="eyebrow">发布前检查</span>
            <h2>独立数据检查</h2>
          </div>
          {activePolicy ? (
            <span className="acceptance-policy-chip">检查 v{activePolicy.version_number}</span>
          ) : null}
        </div>
        <p className="acceptance-intro">
          使用未参与训练的数据版本检查真实效果；通过当前发布检查后，模型才可发布。
        </p>

        {modelVersions.length && acceptanceOptions.length && activePolicy ? (
          <div className="acceptance-layout">
            <div className="acceptance-form-grid">
              <label className="training-field">
                <span>候选模型</span>
                <select
                  value={acceptanceModelVersionId}
                  onChange={(event) => setAcceptanceModelVersionId(event.target.value)}
                >
                  {modelVersions.map((version) => (
                    <option value={version.id} key={version.id}>
                      {version.model_name} · v{version.version_number} · {modelStatusLabels[version.status] ?? version.status}
                    </option>
                  ))}
                </select>
              </label>
              <label className="training-field">
                <span>独立数据版本</span>
                <select
                  value={acceptanceDatasetVersionId}
                  onChange={(event) => setAcceptanceDatasetVersionId(event.target.value)}
                >
                  {acceptanceOptions.map(({ dataset, version }) => (
                    <option value={version.id} key={version.id}>
                      {dataset.name} · ds_v{version.version_number} · {version.asset_count} 个资产
                    </option>
                  ))}
                </select>
              </label>
              <label className="training-field">
                <span>图像尺寸</span>
                <input
                  type="number"
                  min="320"
                  max="1536"
                  step="32"
                  value={acceptanceImageSize}
                  onChange={(event) => setAcceptanceImageSize(Number(event.target.value))}
                />
              </label>
              <label className="training-field">
                <span>批量大小</span>
                <input
                  type="number"
                  min="1"
                  max="256"
                  value={acceptanceBatchSize}
                  onChange={(event) => setAcceptanceBatchSize(Number(event.target.value))}
                />
              </label>
              <button
                className="primary-button acceptance-submit"
                type="submit"
                disabled={busy || !acceptanceDatasetVersionId}
              >
                {busy ? <LoaderCircle size={14} className="spinner" /> : <BadgeCheck size={14} />}
                开始检查
              </button>
            </div>

            <div className="acceptance-run-list">
              {acceptanceRuns.length ? acceptanceRuns.slice(0, 4).map((run) => {
                const result = evaluations.find(
                  (evaluation) => evaluation.source === "acceptance-dataset"
                    && evaluation.model_version_id === String(run.recipe.model_version_id)
                    && evaluation.dataset_version_id === run.dataset_version_id
                    && evaluation.policy_id === String(run.recipe.policy_id),
                );
                return (
                  <div className="acceptance-run-row" key={run.id}>
                    <span className={`run-state-chip ${run.status}`}>
                      {result
                        ? result.verdict === "approved" ? "检查通过" : "检查未通过"
                        : statusLabels[run.status] ?? run.status}
                    </span>
                    <div>
                      <strong>
                        {modelVersions.find(
                          (version) => version.id === String(run.recipe.model_version_id),
                        )?.model_name ?? "模型检查"}
                      </strong>
                      <small>数据版本 {run.dataset_version_id.slice(0, 8)} · {formatTime(run.created_at)}</small>
                    </div>
                    <span>{result ? `${result.policy_name} v${result.policy_version}` : `${run.progress}%`}</span>
                  </div>
                );
              }) : (
                <div className="acceptance-empty">
                  <ShieldCheck size={18} />
                  <span>尚无检查任务</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="training-inline-empty acceptance-prerequisite">
            <AlertCircle size={18} />
            <div>
              <strong>暂时无法开始检查</strong>
              <span>
                {!activePolicy
                  ? "请先在发布与调用中设置发布检查。"
                  : !modelVersions.length
                    ? "请先完成一次训练并登记模型版本。"
                    : "请准备一个未参与训练的冻结数据版本。"}
              </span>
            </div>
            <Link href={activePolicy ? `/studio/data?project=${project.id}` : `/services?project=${project.id}&view=publish#release-check`}>去准备</Link>
          </div>
        )}
      </form>

      <article className="panel model-versions-card">
        <div className="training-card-heading">
          <span className="training-card-icon"><Box size={17} /></span>
          <div><h2>模型版本</h2></div>
          <span className="model-count">{modelVersions.length}</span>
        </div>
        {modelVersions.length ? (
          <div className="model-version-list">
            {modelVersions.map((version) => (
              <div className="model-version-row" key={version.id}>
                <span><Cpu size={15} /></span>
                <div><strong>{version.model_name} · v{version.version_number}</strong><small>{modelStatusLabels[version.status] ?? version.status}</small></div>
                <code>{version.run_id.slice(0, 8)}</code>
                <span className="model-version-status">
                  {version.status === "approved" ? <BadgeCheck size={13} /> : <Check size={13} />}
                  {version.status === "approved" ? "可发布" : "已登记"}
                </span>
                <Link className="model-version-detail-link" href={`/studio/training/models/${version.id}?project=${project.id}`} aria-label={`查看${version.model_name}详情`}><ArrowUpRight size={13} /></Link>
              </div>
            ))}
          </div>
        ) : (
          <div className="model-version-empty">
            <Cpu size={20} />
            <div><strong>尚无模型版本</strong><p>Docker 执行器完成训练并回传产物后，才会在这里生成真实版本。</p></div>
          </div>
        )}
      </article>

      <ModelComparisonPanel models={modelVersions} />
    </section>
  );
}
