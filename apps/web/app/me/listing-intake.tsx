"use client";

import { ArrowRight, Boxes, Cpu, LoaderCircle, X } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useState } from "react";
import {
  catalogApi,
  type CapabilitySpec,
  type DataMarketListingCreate,
  type Dataset,
  type DatasetVersion,
  type Project,
} from "../../lib/catalog-api";

type ListingKind = "algorithm" | "data";
type AlgorithmCandidate = CapabilitySpec & { project: Project };
type DataCandidate = DatasetVersion & { dataset: Dataset; project: Project };

type DataForm = Omit<DataMarketListingCreate, "rights_confirmed">;

const initialDataForm: DataForm = {
  title: "",
  summary: "",
  source_summary: "",
  collection_method: "",
  coverage_summary: "",
  known_limitations: "",
  license_code: "CC-BY-4.0",
  custom_license_terms: null,
  allow_commercial_use: false,
  allow_model_training: false,
  allow_derivative_models: false,
  allow_redistribution: false,
  contains_personal_data: false,
  privacy_treatment: "",
};

function candidateLabel(candidate: AlgorithmCandidate): string {
  return `${candidate.project.name} · ${candidate.display_name} v${candidate.version_number}`;
}

function dataCandidateLabel(candidate: DataCandidate): string {
  return `${candidate.project.name} · ${candidate.dataset.name} v${candidate.version_number}`;
}

function initialDataFormFor(candidate: DataCandidate): DataForm {
  return {
    ...initialDataForm,
    title: `${candidate.dataset.name} v${candidate.version_number}`,
    summary: candidate.dataset.description ?? "",
  };
}

export function ListingIntake({
  workspaceId,
  onSubmitted,
}: {
  workspaceId: string;
  onSubmitted: () => Promise<void>;
}) {
  const [kind, setKind] = useState<ListingKind | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [algorithmCandidates, setAlgorithmCandidates] = useState<AlgorithmCandidate[]>([]);
  const [dataCandidates, setDataCandidates] = useState<DataCandidate[]>([]);
  const [algorithmCapabilityId, setAlgorithmCapabilityId] = useState("");
  const [algorithmTitle, setAlgorithmTitle] = useState("");
  const [algorithmSummary, setAlgorithmSummary] = useState("");
  const [algorithmPrice, setAlgorithmPrice] = useState("16.8");
  const [algorithmQuota, setAlgorithmQuota] = useState("20000");
  const [datasetVersionId, setDatasetVersionId] = useState("");
  const [dataForm, setDataForm] = useState<DataForm>(initialDataForm);
  const [rightsConfirmed, setRightsConfirmed] = useState(false);

  const selectedAlgorithm = algorithmCandidates.find((item) => item.id === algorithmCapabilityId) ?? null;
  const selectedData = dataCandidates.find((item) => item.id === datasetVersionId) ?? null;

  function chooseAlgorithm(candidateId: string) {
    const candidate = algorithmCandidates.find((item) => item.id === candidateId);
    setAlgorithmCapabilityId(candidateId);
    if (!candidate) return;
    setAlgorithmTitle(candidate.display_name);
    setAlgorithmSummary(candidate.problem_definition);
  }

  function chooseData(candidateId: string) {
    const candidate = dataCandidates.find((item) => item.id === candidateId);
    setDatasetVersionId(candidateId);
    if (!candidate) return;
    setDataForm(initialDataFormFor(candidate));
    setRightsConfirmed(false);
  }

  async function loadCandidates() {
    setLoading(true);
    setError(null);
    try {
      const projects = await catalogApi.listProjects(workspaceId);
      const [capabilityGroups, datasetGroups, submissions, publicDataListings] = await Promise.all([
        Promise.all(
          projects.map(async (project) =>
            (await catalogApi.listCapabilitySpecs(workspaceId, project.id)).map((spec) => ({
              ...spec,
              project,
            })),
          ),
        ),
        Promise.all(
          projects.map(async (project) =>
            (await catalogApi.listDatasets(workspaceId, project.id)).map((dataset) => ({
              dataset,
              project,
            })),
          ),
        ),
        catalogApi.listMarketplaceSubmissions(workspaceId),
        catalogApi.listDataMarketListings(workspaceId),
      ]);
      const submittedCapabilities = new Set(
        submissions.map((listing) => listing.capability_spec_id).filter((id): id is string => Boolean(id)),
      );
      const listedDataVersions = new Set(publicDataListings.map((listing) => listing.dataset_version_id));
      const datasets = datasetGroups.flat();
      const versionGroups = await Promise.all(
        datasets.map(async ({ dataset, project }) =>
          (await catalogApi.listVersions(workspaceId, dataset.id))
            .filter((version) => version.status === "frozen")
            .map((version) => ({ ...version, dataset, project })),
        ),
      );
      const nextAlgorithmCandidates = capabilityGroups.flat().filter(
        (candidate) => !submittedCapabilities.has(candidate.id),
      );
      const nextDataCandidates = versionGroups.flat().filter(
        (candidate) => !listedDataVersions.has(candidate.id),
      );
      setAlgorithmCandidates(nextAlgorithmCandidates);
      setDataCandidates(nextDataCandidates);
      const firstAlgorithmCandidate = nextAlgorithmCandidates[0];
      if (firstAlgorithmCandidate) {
        setAlgorithmCapabilityId(firstAlgorithmCandidate.id);
        setAlgorithmTitle(firstAlgorithmCandidate.display_name);
        setAlgorithmSummary(firstAlgorithmCandidate.problem_definition);
      }
      const firstDataCandidate = nextDataCandidates[0];
      if (firstDataCandidate) {
        setDatasetVersionId(firstDataCandidate.id);
        setDataForm(initialDataFormFor(firstDataCandidate));
        setRightsConfirmed(false);
      }
      setLoaded(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "可上架资产加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function open(kindToOpen: ListingKind) {
    setKind(kindToOpen);
    setNotice(null);
    setError(null);
    if (!loaded) await loadCandidates();
  }

  async function submitAlgorithm(event: FormEvent) {
    event.preventDefault();
    if (!selectedAlgorithm) return;
    const pricePerThousand = Number(algorithmPrice);
    const quota = Number(algorithmQuota);
    const priceCents = Math.round(pricePerThousand * 100);
    if (!Number.isFinite(pricePerThousand) || priceCents < 0 || !Number.isInteger(quota) || quota < 10) {
      setError("请填写有效的单价和每月额度");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await catalogApi.createMarketplaceListing(workspaceId, selectedAlgorithm.id, {
        title: algorithmTitle.trim(),
        summary: algorithmSummary.trim(),
        price_per_1000_cents: priceCents,
        monthly_quota_units: quota,
      });
      await onSubmitted();
      setNotice("算法商品已提交审核，审核通过后才会在算法市场公开。");
      setKind(null);
      setLoaded(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "算法商品提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitData(event: FormEvent) {
    event.preventDefault();
    if (!selectedData || !rightsConfirmed) return;
    setBusy(true);
    setError(null);
    try {
      await catalogApi.createDataMarketListing(workspaceId, selectedData.id, {
        ...dataForm,
        title: dataForm.title.trim(),
        summary: dataForm.summary.trim(),
        source_summary: dataForm.source_summary.trim(),
        collection_method: dataForm.collection_method.trim(),
        coverage_summary: dataForm.coverage_summary.trim(),
        known_limitations: dataForm.known_limitations.trim(),
        custom_license_terms: dataForm.custom_license_terms?.trim() || null,
        privacy_treatment: dataForm.privacy_treatment.trim(),
        rights_confirmed: true,
      });
      await onSubmitted();
      setNotice("数据卡已公开；数据购买和交付将在商业能力开通后提供。");
      setKind(null);
      setLoaded(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "数据卡提交失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="me-section listing-intake" aria-label="上架商品">
      <div className="me-section-heading"><h2>上架</h2><span>从已固化资产开始</span></div>
      {error ? <p className="inline-notice is-error listing-intake-notice" role="alert">{error}</p> : null}
      {notice ? <p className="inline-notice listing-intake-notice" role="status">{notice}</p> : null}
      {kind === null ? (
        <div className="selling-choice-grid">
          <article>
            <span className="selling-choice-icon"><Cpu size={18} /></span>
            <div><strong>算法商品</strong><small>选择已固化的能力版本</small></div>
            <button className="secondary-button compact" type="button" onClick={() => void open("algorithm")}>提交审核 <ArrowRight size={13} /></button>
          </article>
          <article>
            <span className="selling-choice-icon is-data"><Boxes size={18} /></span>
            <div><strong>数据卡</strong><small>选择已冻结的数据版本</small></div>
            <button className="secondary-button compact" type="button" onClick={() => void open("data")}>创建数据卡 <ArrowRight size={13} /></button>
          </article>
        </div>
      ) : (
        <div className="listing-intake-content">
          <header>
            <div><strong>{kind === "algorithm" ? "提交算法商品" : "创建数据卡"}</strong><small>{kind === "algorithm" ? "仅支持已固化的生产服务能力" : "仅支持已冻结且尚未公开的版本"}</small></div>
            <button className="icon-button" type="button" onClick={() => setKind(null)} aria-label="关闭上架表单" title="关闭"><X size={16} /></button>
          </header>
          {loading ? <div className="me-empty"><LoaderCircle className="spinner" size={18} /><span>正在读取可上架资产</span></div> : null}
          {!loading && kind === "algorithm" && !algorithmCandidates.length ? (
            <div className="listing-intake-empty"><Cpu size={18} /><span>还没有可提交的算法能力</span><Link href="/services?view=publish">前往发布服务 <ArrowRight size={13} /></Link></div>
          ) : null}
          {!loading && kind === "data" && !dataCandidates.length ? (
            <div className="listing-intake-empty"><Boxes size={18} /><span>还没有可创建数据卡的冻结版本</span><Link href="/studio/data">前往数据与标注 <ArrowRight size={13} /></Link></div>
          ) : null}
          {!loading && kind === "algorithm" && selectedAlgorithm ? (
            <form className="listing-intake-form" onSubmit={(event) => void submitAlgorithm(event)}>
              <label className="is-wide"><span>能力版本</span><select aria-label="可上架能力" value={algorithmCapabilityId} onChange={(event) => chooseAlgorithm(event.target.value)}>{algorithmCandidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidateLabel(candidate)}</option>)}</select></label>
              <label><span>商品名称</span><input value={algorithmTitle} minLength={2} maxLength={180} required onChange={(event) => setAlgorithmTitle(event.target.value)} /></label>
              <label><span>每千次调用价格（元）</span><input value={algorithmPrice} inputMode="decimal" required onChange={(event) => setAlgorithmPrice(event.target.value)} /></label>
              <label className="is-wide"><span>商品说明</span><textarea value={algorithmSummary} minLength={8} maxLength={1000} required onChange={(event) => setAlgorithmSummary(event.target.value)} /></label>
              <label><span>每月调用额度</span><input value={algorithmQuota} inputMode="numeric" required onChange={(event) => setAlgorithmQuota(event.target.value)} /></label>
              <div className="listing-intake-actions"><button className="primary-button" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spinner" size={15} /> : null}提交审核</button></div>
            </form>
          ) : null}
          {!loading && kind === "data" && selectedData ? (
            <form className="listing-intake-form" onSubmit={(event) => void submitData(event)}>
              <label className="is-wide"><span>冻结版本</span><select aria-label="可上架数据版本" value={datasetVersionId} onChange={(event) => chooseData(event.target.value)}>{dataCandidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{dataCandidateLabel(candidate)}</option>)}</select></label>
              <label><span>数据卡名称</span><input value={dataForm.title} minLength={2} maxLength={180} required onChange={(event) => setDataForm((current) => ({ ...current, title: event.target.value }))} /></label>
              <label><span>许可</span><select value={dataForm.license_code} onChange={(event) => setDataForm((current) => ({ ...current, license_code: event.target.value as DataForm["license_code"], custom_license_terms: event.target.value === "CUSTOM-COMMERCIAL" ? current.custom_license_terms : null }))}><option value="CC0-1.0">CC0</option><option value="CC-BY-4.0">CC BY 4.0</option><option value="ODC-BY-1.0">ODC BY 1.0</option><option value="CUSTOM-COMMERCIAL">自定义商业许可</option></select></label>
              <label className="is-wide"><span>数据说明</span><textarea value={dataForm.summary} minLength={12} maxLength={1200} required onChange={(event) => setDataForm((current) => ({ ...current, summary: event.target.value }))} /></label>
              <label><span>来源说明</span><textarea value={dataForm.source_summary} minLength={12} maxLength={2000} required onChange={(event) => setDataForm((current) => ({ ...current, source_summary: event.target.value }))} /></label>
              <label><span>采集方式</span><textarea value={dataForm.collection_method} minLength={8} maxLength={2000} required onChange={(event) => setDataForm((current) => ({ ...current, collection_method: event.target.value }))} /></label>
              <label><span>覆盖范围</span><textarea value={dataForm.coverage_summary} minLength={8} maxLength={2000} required onChange={(event) => setDataForm((current) => ({ ...current, coverage_summary: event.target.value }))} /></label>
              <label><span>已知限制</span><textarea value={dataForm.known_limitations} minLength={8} maxLength={2000} required onChange={(event) => setDataForm((current) => ({ ...current, known_limitations: event.target.value }))} /></label>
              {dataForm.license_code === "CUSTOM-COMMERCIAL" ? <label className="is-wide"><span>完整授权条款</span><textarea value={dataForm.custom_license_terms ?? ""} minLength={1} maxLength={4000} required onChange={(event) => setDataForm((current) => ({ ...current, custom_license_terms: event.target.value }))} /></label> : null}
              <label className="is-wide"><span>隐私处理</span><textarea value={dataForm.privacy_treatment} minLength={4} maxLength={2000} required onChange={(event) => setDataForm((current) => ({ ...current, privacy_treatment: event.target.value }))} /></label>
              <fieldset className="listing-rights-field is-wide"><legend>允许用途</legend><label><input type="checkbox" checked={dataForm.allow_commercial_use} onChange={(event) => setDataForm((current) => ({ ...current, allow_commercial_use: event.target.checked }))} />商业使用</label><label><input type="checkbox" checked={dataForm.allow_model_training} onChange={(event) => setDataForm((current) => ({ ...current, allow_model_training: event.target.checked }))} />模型训练</label><label><input type="checkbox" checked={dataForm.allow_derivative_models} onChange={(event) => setDataForm((current) => ({ ...current, allow_derivative_models: event.target.checked }))} />衍生模型</label><label><input type="checkbox" checked={dataForm.allow_redistribution} onChange={(event) => setDataForm((current) => ({ ...current, allow_redistribution: event.target.checked }))} />再分发</label><label><input type="checkbox" checked={dataForm.contains_personal_data} onChange={(event) => setDataForm((current) => ({ ...current, contains_personal_data: event.target.checked }))} />包含个人信息</label></fieldset>
              <label className="listing-confirmation is-wide"><input type="checkbox" checked={rightsConfirmed} required onChange={(event) => setRightsConfirmed(event.target.checked)} />我确认拥有发布及声明上述授权范围的权利</label>
              <div className="listing-intake-actions"><button className="primary-button" type="submit" disabled={busy || !rightsConfirmed}>{busy ? <LoaderCircle className="spinner" size={15} /> : null}创建数据卡</button></div>
            </form>
          ) : null}
        </div>
      )}
    </section>
  );
}
