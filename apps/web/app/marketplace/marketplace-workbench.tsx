"use client";

import { ArrowUpRight, BadgeCheck, LoaderCircle, Search, ShoppingBag } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CatalogFilterMenu } from "../components/catalog-filter-menu";
import { CatalogPreview } from "../components/catalog-preview";
import {
  mergeAlgorithmListings,
  MOCK_ALGORITHM_LISTINGS,
  type AlgorithmCatalogItem,
} from "../../lib/catalog-mock-data";
import {
  catalogApi,
  type MarketplaceSubscription,
  type Workspace,
} from "../../lib/catalog-api";

export const taskLabels: Record<string, string> = {
  "object-detection": "目标检测",
  classification: "图像分类",
  segmentation: "图像分割",
  pose: "姿态估计",
  ocr: "文字识别",
};

export function formatAlgorithmPrice(cents: number): string {
  if (cents === 0) return "免费";
  return `${new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 2,
  }).format(cents / 100)} / 千次`;
}

function getListingEnvironments(listing: AlgorithmCatalogItem): string[] {
  const text = listing.capability_verified_scenes.join(" ");
  return [
    /固定|高位|俯拍|正面|机位/.test(text) ? "固定机位" : null,
    /室内|仓库|厂房|产线|货架|传送带|温室|圈舍/.test(text) ? "室内" : null,
    /工地|城市路口|道路|林区|林道|田间|果园|牧场/.test(text) ? "室外" : null,
    /夜景|夜间|白天与|自然光/.test(text) ? "昼夜" : null,
  ].filter((item): item is string => Boolean(item));
}

export function MarketplaceWorkbench({ previewMode }: { previewMode: boolean }) {
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [listings, setListings] = useState<AlgorithmCatalogItem[]>(previewMode ? MOCK_ALGORITHM_LISTINGS : []);
  const [subscriptions, setSubscriptions] = useState<MarketplaceSubscription[]>([]);
  const [mockPurchasedIds, setMockPurchasedIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("全部");
  const [scene, setScene] = useState("全部场景");
  const [environment, setEnvironment] = useState("全部环境");
  const [checkoutListing, setCheckoutListing] = useState<AlgorithmCatalogItem | null>(null);

  const loadWorkspace = useCallback(async (nextWorkspaceId: string) => {
    const [nextListings, nextSubscriptions] = await Promise.all([
      catalogApi.listMarketplaceListings(nextWorkspaceId),
      catalogApi.listMarketplaceSubscriptions(nextWorkspaceId),
    ]);
    setListings(mergeAlgorithmListings(nextListings, previewMode));
    setSubscriptions(nextSubscriptions);
  }, [previewMode]);

  useEffect(() => {
    void catalogApi.listWorkspaces()
      .then(async (nextWorkspaces) => {
        setWorkspaces(nextWorkspaces);
        const selected = nextWorkspaces[0]?.id ?? "";
        setWorkspaceId(selected);
        if (selected) await loadWorkspace(selected);
      })
      .catch((reason) => {
        setListings(previewMode ? MOCK_ALGORITHM_LISTINGS : []);
        const message = reason instanceof Error ? reason.message : "服务暂不可用";
        setError(previewMode ? `${message}；当前显示示例商品。` : message);
      })
      .finally(() => setLoading(false));
  }, [loadWorkspace, previewMode]);

  const categories = useMemo(
    () => ["全部", ...Array.from(new Set(listings.map((listing) => taskLabels[listing.task_type] ?? listing.category)))],
    [listings],
  );
  const scenes = useMemo(
    () => ["全部场景", ...Array.from(new Set(listings.map((listing) => listing.category)))],
    [listings],
  );
  const environments = useMemo(
    () => ["全部环境", ...Array.from(new Set(listings.flatMap(getListingEnvironments)))],
    [listings],
  );
  const subscriptionByListingId = useMemo(
    () => new Map(subscriptions.map((subscription) => [subscription.listing_id, subscription])),
    [subscriptions],
  );
  const filteredListings = listings.filter((listing) => {
    const normalized = query.trim().toLowerCase();
    const listingCategory = taskLabels[listing.task_type] ?? listing.category;
    return (category === "全部" || category === listingCategory)
      && (scene === "全部场景" || scene === listing.category)
      && (environment === "全部环境" || getListingEnvironments(listing).includes(environment))
      && (!normalized || `${listing.title} ${listing.summary} ${listing.provider_name} ${listing.category} ${listing.model_architecture} ${listing.input_size} ${listing.capability_verified_scenes.join(" ")} ${listing.classes.join(" ")}`.toLowerCase().includes(normalized));
  });

  async function selectPurchaseWorkspace(nextWorkspaceId: string) {
    setWorkspaceId(nextWorkspaceId);
    setError(null);
    try {
      await loadWorkspace(nextWorkspaceId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工作区切换失败");
    }
  }

  async function buy(listing: AlgorithmCatalogItem) {
    if (!workspaceId) return;
    setBusyId(listing.id);
    setError(null);
    setNotice(null);
    try {
      if (listing.is_mock && previewMode) {
        setMockPurchasedIds((current) => [...new Set([...current, listing.id])]);
        setCheckoutListing(null);
        setNotice("示例购买流程已完成；接入支付后将创建真实 API 授权。");
        return;
      }
      if (listing.is_mock) throw new Error("演示商品不能在正式环境购买");
      const checkout = await catalogApi.subscribeMarketplaceListing(workspaceId, listing.id);
      await loadWorkspace(workspaceId);
      setCheckoutListing(null);
      setNotice(checkout.status === "active"
        ? "购买成功，请到“我的”领取 API 密钥。"
        : "订单已创建，请到“我的”查看。"
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "购买失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className="product-page storefront-page">
      <header className="product-page-header">
        <h1>算法市场</h1>
      </header>

      <div className="storefront-tools">
        <label className="storefront-search">
          <Search size={16} aria-hidden="true" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索算法或使用场景" />
        </label>
        <div className="storefront-filters" aria-label="算法类型">
          {categories.map((item) => (
            <button className={category === item ? "is-active" : ""} type="button" key={item} onClick={() => setCategory(item)}>{item}</button>
          ))}
        </div>
        <CatalogFilterMenu
          title="筛选应用场景"
          defaultLabel="全部场景"
          groups={[
            { id: "industry", label: "行业场景", value: scene, allValue: "全部场景", options: scenes, onChange: setScene },
            { id: "environment", label: "采集环境", value: environment, allValue: "全部环境", options: environments, onChange: setEnvironment },
          ]}
        />
      </div>

      {error ? <p className="inline-notice is-error" role="alert">{error}</p> : null}
      {notice ? <p className="inline-notice" role="status">{notice}</p> : null}

      {checkoutListing ? (
        <div className="purchase-dialog-backdrop">
          <button className="purchase-dialog-dismiss" type="button" aria-label="关闭购买窗口" onClick={() => setCheckoutListing(null)} />
          <section className="purchase-dialog" role="dialog" aria-modal="true" aria-labelledby="purchase-dialog-title">
            <h2 id="purchase-dialog-title">购买 {checkoutListing.title}</h2>
            <label>
              <span>购买到工作区</span>
              <select value={workspaceId} onChange={(event) => void selectPurchaseWorkspace(event.target.value)}>
                {workspaces.map((workspace) => <option value={workspace.id} key={workspace.id}>{workspace.name}</option>)}
              </select>
            </label>
            <p className="purchase-dialog-note">每月 {checkoutListing.monthly_quota_units.toLocaleString("zh-CN")} 次调用，{formatAlgorithmPrice(checkoutListing.price_per_1000_cents)}。</p>
            <div>
              <button className="text-button compact" type="button" onClick={() => setCheckoutListing(null)}>取消</button>
              <button className="primary-button compact" type="button" disabled={busyId === checkoutListing.id} onClick={() => void buy(checkoutListing)}>
                {busyId === checkoutListing.id ? "处理中" : "确认购买"}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {loading && listings.length === 0 ? (
        <div className="storefront-empty"><LoaderCircle className="spinner" size={20} /><span>正在加载</span></div>
      ) : filteredListings.length ? (
        <section className="storefront-grid" aria-label="算法商品">
          {filteredListings.map((listing) => {
            const subscription = subscriptionByListingId.get(listing.id);
            const purchased = subscription?.status === "active" || mockPurchasedIds.includes(listing.id);
            const pending = subscription?.status === "pending_payment";
            const secondaryMetric = listing.metrics.find((metric) => metric.label === "召回率" || metric.label === "精确率") ?? listing.metrics[1];
            return (
              <article className="storefront-card" key={listing.id}>
                <Link className="storefront-card-link" href={`/marketplace/${listing.id}`} aria-label={`查看${listing.title}`}>
                  <CatalogPreview preview={listing.preview} kind="algorithm" />
                  <div className="storefront-card-topline">
                    <span>{taskLabels[listing.task_type] ?? listing.category}</span>
                    <span className="verified-label"><BadgeCheck size={14} /> 已验证</span>
                  </div>
                  <h2>{listing.title}</h2>
                  <p>{listing.summary}</p>
                  <div className="storefront-card-tags" aria-label="算法标签">
                    <span>{listing.category}</span>
                    <span>{listing.model_architecture}</span>
                  </div>
                  <div className="storefront-card-evidence">
                    <span><small>{listing.metrics[0].label}</small><strong>{listing.metrics[0].value}</strong></span>
                    <span><small>{secondaryMetric.label}</small><strong>{secondaryMetric.value}</strong></span>
                    <span><small>响应 P95</small><strong>{listing.latency_p95}</strong></span>
                  </div>
                </Link>
                <div className="storefront-card-footer">
                  <div><strong>{formatAlgorithmPrice(listing.price_per_1000_cents)}</strong><small>{listing.provider_name}</small></div>
                  <div className="storefront-card-actions">
                    <Link className="text-button compact" href={`/marketplace/${listing.id}`}>详情 <ArrowUpRight size={14} /></Link>
                    {purchased || pending ? (
                      <Link className="secondary-button compact" href="/me?view=consumer">{purchased ? "已购买" : "查看订单"}</Link>
                    ) : !workspaces.length ? (
                      <Link className="secondary-button compact" href="/settings">创建工作区</Link>
                    ) : (
                      <button className="primary-button compact" type="button" disabled={busyId === listing.id} onClick={() => workspaces.length > 1 ? setCheckoutListing(listing) : void buy(listing)}>
                        {busyId === listing.id ? "处理中" : "购买 API"}
                      </button>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        <div className="storefront-empty"><ShoppingBag size={20} /><span>没有找到符合条件的算法</span></div>
      )}
    </main>
  );
}
