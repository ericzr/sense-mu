"use client";

import { ArrowLeft, BadgeCheck, Check, LoaderCircle, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { formatAlgorithmPrice, taskLabels } from "../marketplace-workbench";
import {
  decorateAlgorithmListing,
  findMockAlgorithm,
  type AlgorithmCatalogItem,
} from "../../../lib/catalog-mock-data";
import { catalogApi, type Workspace } from "../../../lib/catalog-api";
import { AlgorithmLiveDemo } from "./algorithm-live-demo";

export function AlgorithmDetailWorkbench({ listingId, previewMode }: { listingId: string; previewMode: boolean }) {
  const initialListing = previewMode ? findMockAlgorithm(listingId) : null;
  const [listing, setListing] = useState<AlgorithmCatalogItem | null>(initialListing);
  const [loading, setLoading] = useState(!initialListing);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [busy, setBusy] = useState(false);
  const [purchased, setPurchased] = useState(false);

  useEffect(() => {
    void catalogApi.listWorkspaces()
      .then(async (nextWorkspaces) => {
        setWorkspaces(nextWorkspaces);
        const selected = nextWorkspaces[0]?.id ?? "";
        setWorkspaceId(selected);
        if (!initialListing && selected) {
          const realListing = (await catalogApi.listMarketplaceListings(selected)).find((item) => item.id === listingId);
          setListing(realListing ? decorateAlgorithmListing(realListing) : null);
        }
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "算法详情加载失败"))
      .finally(() => setLoading(false));
  }, [initialListing, listingId]);

  async function buy() {
    if (!listing || !workspaceId) return;
    setBusy(true);
    setError(null);
    try {
      if (listing.is_mock && previewMode) {
        setPurchased(true);
        setNotice("示例购买流程已完成；接入支付后将创建真实 API 授权。");
      } else if (!listing.is_mock) {
        const checkout = await catalogApi.subscribeMarketplaceListing(workspaceId, listing.id);
        setPurchased(checkout.status === "active");
        setNotice(checkout.status === "active" ? "购买成功，请到“我的”领取 API 密钥。" : "订单已创建，请到“我的”查看。");
      } else {
        throw new Error("演示商品不能在正式环境购买");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "购买失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <main className="product-page"><div className="storefront-empty"><LoaderCircle className="spinner" size={20} />正在加载算法详情</div></main>;
  }

  if (!listing) {
    return (
      <main className="product-page catalog-detail-page">
        <Link className="catalog-back-link" href="/marketplace"><ArrowLeft size={15} />返回算法市场</Link>
        <div className="catalog-detail-empty"><h1>没有找到这个算法</h1><p>商品可能已下架或链接无效。</p></div>
      </main>
    );
  }

  const codeSample = `curl -X POST "https://api.sensemu.cn${listing.endpoint_url}" \\
  -H "Authorization: Bearer $SENSEMU_API_KEY" \\
  -F "image=@sample.jpg"`;

  return (
    <main className="product-page catalog-detail-page">
      <Link className="catalog-back-link" href="/marketplace"><ArrowLeft size={15} />算法市场</Link>

      <section className="catalog-detail-hero is-copy-only">
        <div className="catalog-detail-intro">
          <div className="catalog-detail-kicker">
            <span>{taskLabels[listing.task_type] ?? listing.category}</span>
            <span className="verified-label"><BadgeCheck size={14} /> 已验证</span>
          </div>
          <h1>{listing.title}</h1>
          <p>{listing.summary}</p>
          <div className="storefront-tags">
            {listing.capability_verified_scenes.map((scene) => <span key={scene}>{scene}</span>)}
          </div>
          <div className="catalog-detail-provider"><span>提供方</span><strong>{listing.provider_name}</strong><small>更新于 {listing.updated_label}</small></div>
        </div>
      </section>

      {error ? <p className="inline-notice is-error" role="alert">{error}</p> : null}
      {notice ? <p className="inline-notice" role="status">{notice}</p> : null}

      <AlgorithmLiveDemo listing={listing} />

      <div className="catalog-detail-layout">
        <div className="catalog-detail-main">
          <section className="catalog-detail-section">
            <h2>效果与规格</h2>
            <div className="catalog-metric-grid">
              {listing.metrics.map((metric) => <div key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong></div>)}
              <div><span>响应 P95</span><strong>{listing.latency_p95}</strong></div>
            </div>
            <dl className="catalog-fact-list">
              <div><dt>模型</dt><dd>{listing.model_architecture}</dd></div>
              <div><dt>输入尺寸</dt><dd>{listing.input_size}</dd></div>
              <div><dt>评测依据</dt><dd>{listing.evaluation_basis}</dd></div>
              <div><dt>返回格式</dt><dd>{listing.capability_output_contract ?? "detections.v1"}</dd></div>
            </dl>
          </section>

          <section className="catalog-detail-section">
            <h2>适用边界</h2>
            <div className="catalog-boundary-grid">
              <div><h3>已验证场景</h3>{listing.capability_verified_scenes.map((item) => <p key={item}><Check size={14} />{item}</p>)}</div>
              <div><h3>不建议直接使用</h3>{listing.capability_unsupported_conditions.map((item) => <p key={item}>{item}</p>)}</div>
            </div>
          </section>

          <section className="catalog-detail-section">
            <h2>识别类别</h2>
            <div className="catalog-class-list">
              {(listing.classes.length ? listing.classes : ["以接口返回为准"]).map((item) => <span key={item}>{item}</span>)}
            </div>
          </section>

          <section className="catalog-detail-section">
            <h2>接入方式</h2>
            <p className="catalog-section-lead">购买后领取 API 密钥，使用图片文件发起请求。默认不留存输入图片。</p>
            <pre className="catalog-code"><code>{codeSample}</code></pre>
          </section>
        </div>

        <aside className="catalog-purchase-card">
          <span>API 调用</span>
          <strong>{formatAlgorithmPrice(listing.price_per_1000_cents)}</strong>
          <small>每月包含 {listing.monthly_quota_units.toLocaleString("zh-CN")} 次调用</small>
          <ul>
            <li><ShieldCheck size={15} />共享 API 服务</li>
            <li><ShieldCheck size={15} />输入图片默认不留存</li>
            <li><ShieldCheck size={15} />按成功调用计费</li>
          </ul>
          {workspaces.length > 1 ? (
            <label><span>购买到</span><select value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)}>{workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></label>
          ) : null}
          {purchased ? (
            <Link className="primary-button" href="/me?view=consumer">打开我的 API</Link>
          ) : workspaces.length ? (
            <button className="primary-button" type="button" disabled={busy} onClick={() => void buy()}>{busy ? "处理中" : "购买 API"}</button>
          ) : (
            <Link className="primary-button" href="/settings">先创建工作区</Link>
          )}
          <p>{listing.is_mock ? "示例商品用于敲定页面与购买流程，不产生真实费用。" : "购买即表示同意商品调用与计费规则。"}</p>
        </aside>
      </div>
    </main>
  );
}
