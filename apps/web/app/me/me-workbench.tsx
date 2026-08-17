"use client";

import {
  ArrowRight,
  Boxes,
  Copy,
  Cpu,
  KeyRound,
  LoaderCircle,
  PackageCheck,
  RefreshCw,
  Settings,
  ShieldCheck,
  ShoppingBag,
  WalletCards,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ListingIntake } from "./listing-intake";
import {
  catalogApi,
  type Deployment,
  type MarketplaceBilling,
  type MarketplaceSubscription,
  type MarketplaceSubscriptionSecret,
  type MarketplaceUsageRecord,
  type Project,
  type ProviderDashboard,
  type TrainingRun,
  type Workspace,
} from "../../lib/catalog-api";

type View = "producer" | "consumer";
type ComputeView = "training" | "services";
type ProjectTrainingRun = TrainingRun & { project: Project };

const emptyProvider: ProviderDashboard = {
  profile: null,
  algorithm_listing_count: 0,
  data_listing_count: 0,
  active_customer_grants: 0,
  successful_units: 0,
  authorized_sales_yuan: 0,
  paid_sales_yuan: 0,
  refunded_sales_yuan: 0,
  unsettled_earnings_yuan: 0,
  algorithm_listings: [],
  data_listings: [],
  sales: [],
  earnings: [],
};

const emptyBilling: MarketplaceBilling = {
  authorization_ceiling_yuan: 0,
  unsettled_earnings_yuan: 0,
  orders: [],
  earnings: [],
};

function formatMoney(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "numeric", day: "numeric" }).format(new Date(value));
}

const listingStatus: Record<string, string> = {
  published: "已上架",
  pending_review: "审核中",
  rejected: "需修改",
};

const orderStatus: Record<string, string> = {
  pending_payment: "待支付",
  active: "已生效",
  cancelled: "已取消",
  refunded: "已退款",
  paid: "已支付",
  waived: "无需支付",
  not_collected: "待支付",
};

const trainingStatus: Record<string, string> = {
  queued: "排队中",
  preparing: "准备中",
  running: "运行中",
  cancel_requested: "正在取消",
  cancelled: "已取消",
  succeeded: "已完成",
  failed: "已失败",
};

const deploymentStatus: Record<string, string> = {
  published: "运行中",
  disabled: "已停用",
  draft: "未发布",
};

export function MeWorkbench({ initialView }: { initialView: View }) {
  const [view, setView] = useState<View>(initialView);
  const [computeView, setComputeView] = useState<ComputeView>("training");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [provider, setProvider] = useState<ProviderDashboard>(emptyProvider);
  const [subscriptions, setSubscriptions] = useState<MarketplaceSubscription[]>([]);
  const [usage, setUsage] = useState<MarketplaceUsageRecord[]>([]);
  const [billing, setBilling] = useState<MarketplaceBilling>(emptyBilling);
  const [trainingRuns, setTrainingRuns] = useState<ProjectTrainingRun[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [secret, setSecret] = useState<MarketplaceSubscriptionSecret | null>(null);

  async function loadWorkspace(
    nextWorkspaceId: string,
    role?: Workspace["role"],
  ) {
    const canManageProvider = role === "owner" || role === "admin";
    const [nextProvider, nextSubscriptions, nextUsage, nextBilling, projects] = await Promise.all([
      canManageProvider
        ? catalogApi.getProviderDashboard(nextWorkspaceId)
        : Promise.resolve(emptyProvider),
      catalogApi.listMarketplaceSubscriptions(nextWorkspaceId),
      catalogApi.listMarketplaceUsageRecords(nextWorkspaceId),
      catalogApi.getMarketplaceBilling(nextWorkspaceId),
      catalogApi.listProjects(nextWorkspaceId),
    ]);
    const [deploymentGroups, trainingRunGroups] = await Promise.all([
      Promise.all(projects.map((project) => catalogApi.listDeployments(nextWorkspaceId, project.id))),
      Promise.all(projects.map(async (project) => {
        const runs = await catalogApi.listTrainingRuns(nextWorkspaceId, project.id);
        return runs.map((run) => ({ ...run, project }));
      })),
    ]);
    setProvider(nextProvider);
    setSubscriptions(nextSubscriptions);
    setUsage(nextUsage);
    setBilling(nextBilling);
    setTrainingRuns(trainingRunGroups.flat().sort((left, right) => right.created_at.localeCompare(left.created_at)));
    setDeployments(deploymentGroups.flat());
  }

  useEffect(() => {
    void catalogApi.listWorkspaces()
      .then(async (nextWorkspaces) => {
        setWorkspaces(nextWorkspaces);
        const selected = nextWorkspaces[0];
        setWorkspaceId(selected?.id ?? "");
        if (selected) await loadWorkspace(selected.id, selected.role);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "内容加载失败"))
      .finally(() => setLoading(false));
  }, []);

  function changeView(nextView: View) {
    setView(nextView);
    window.history.replaceState(null, "", `/me?view=${nextView}`);
  }

  async function changeWorkspace(nextWorkspaceId: string) {
    const nextWorkspace = workspaces.find((workspace) => workspace.id === nextWorkspaceId);
    setWorkspaceId(nextWorkspaceId);
    setLoading(true);
    setError(null);
    setSecret(null);
    try {
      await loadWorkspace(nextWorkspaceId, nextWorkspace?.role);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工作区切换失败");
    } finally {
      setLoading(false);
    }
  }

  async function showKey(subscription: MarketplaceSubscription, rotate = false) {
    if (!workspaceId) return;
    setBusyId(subscription.id);
    setError(null);
    setNotice(null);
    try {
      const nextSecret = rotate
        ? await catalogApi.rotateMarketplaceSubscriptionKey(workspaceId, subscription.id)
        : await catalogApi.claimMarketplaceSubscriptionKey(workspaceId, subscription.id);
      setSecret(nextSecret);
      await loadWorkspace(workspaceId);
      setNotice(rotate ? "新密钥已生成，旧密钥已失效。" : "密钥仅显示一次，请立即保存。")
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "密钥操作失败");
    } finally {
      setBusyId(null);
    }
  }

  async function copyKey() {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret.api_key);
      setNotice("密钥已复制。")
    } catch {
      setError("复制失败，请手动选择密钥。")
    }
  }

  const activeSubscriptions = subscriptions.filter((item) => item.status === "active");
  const remainingUnits = activeSubscriptions.reduce((sum, item) => sum + item.remaining_units, 0);
  const canManageProvider = workspaces.some(
    (workspace) =>
      workspace.id === workspaceId && (workspace.role === "owner" || workspace.role === "admin"),
  );

  return (
    <main className="product-page me-page">
      <header className="product-page-header">
        <h1>我的</h1>
        {workspaces.length > 1 ? (
          <label className="workspace-context-selector">
            <span>当前工作区</span>
            <select value={workspaceId} onChange={(event) => void changeWorkspace(event.target.value)}>
              {workspaces.map((workspace) => <option value={workspace.id} key={workspace.id}>{workspace.name}</option>)}
            </select>
          </label>
        ) : null}
      </header>

      <div className="role-switch" role="tablist" aria-label="查看我的内容">
        <button className={view === "producer" ? "is-active" : ""} type="button" role="tab" aria-selected={view === "producer"} onClick={() => changeView("producer")}>创作与销售</button>
        <button className={view === "consumer" ? "is-active" : ""} type="button" role="tab" aria-selected={view === "consumer"} onClick={() => changeView("consumer")}>购买与使用</button>
      </div>

      {error ? <p className="inline-notice is-error" role="alert">{error}</p> : null}
      {notice ? <p className="inline-notice" role="status">{notice}</p> : null}
      {loading ? <div className="storefront-empty"><LoaderCircle className="spinner" size={20} /><span>正在加载</span></div> : null}

      {!loading && view === "producer" ? (
        <div className="me-content">
          <section className="me-summary-grid" aria-label="创作与销售概览">
            <article><WalletCards size={17} /><span>钱包</span><strong>—</strong><small>尚未开通</small></article>
            <article><ShoppingBag size={17} /><span>在售商品</span><strong>{provider.algorithm_listing_count + provider.data_listing_count}</strong><small>算法与数据</small></article>
            <article><PackageCheck size={17} /><span>销售额</span><strong>{formatMoney(provider.paid_sales_yuan)}</strong><small>{provider.sales.length} 个订单</small></article>
            <article><Boxes size={17} /><span>待结算</span><strong>{formatMoney(provider.unsettled_earnings_yuan)}</strong><small>按实际调用计算</small></article>
          </section>

          {canManageProvider ? <ListingIntake workspaceId={workspaceId} onSubmitted={() => loadWorkspace(
            workspaceId,
            workspaces.find((workspace) => workspace.id === workspaceId)?.role,
          )} /> : (
            <section className="me-permission-note">
              <ShieldCheck size={17} />
              <span>管理员可管理商品、销售订单和结算信息。</span>
              <Link href="/studio">继续生产 <ArrowRight size={13} /></Link>
            </section>
          )}

          <section className="me-section">
            <div className="me-section-heading"><h2>我的商品</h2><span>{provider.algorithm_listing_count + provider.data_listing_count} 个</span></div>
            <div className="me-product-grid">
              {[...provider.algorithm_listings.map((item) => ({ id: item.id, title: item.title, type: "算法", detail: `${formatMoney(item.price_per_1000_cents / 100)} / 千次`, status: item.status })),
                ...provider.data_listings.map((item) => ({ id: item.id, title: item.title, type: "数据", detail: `${item.asset_count.toLocaleString("zh-CN")} 个文件`, status: item.status }))]
                .map((item) => {
                  const href = item.status === "published"
                    ? item.type === "算法" ? `/marketplace/${item.id}` : `/data-market/${item.id}`
                    : null;
                  const content = <><span>{item.type}</span><strong>{item.title}</strong><small>{item.detail}</small><em>{listingStatus[item.status] ?? item.status}</em></>;
                  return href ? <Link className="me-product-card-link" key={`${item.type}-${item.id}`} href={href}>{content}</Link> : <article key={`${item.type}-${item.id}`}>{content}</article>;
                })}
              {!provider.algorithm_listings.length && !provider.data_listings.length ? <div className="me-empty">还没有上架商品</div> : null}
            </div>
          </section>

          <section className="me-section">
            <div className="me-section-heading"><h2>销售订单</h2><span>{provider.sales.length} 个</span></div>
            <div className="me-table">
              {provider.sales.map((sale) => <article key={sale.id}><div><strong>{sale.listing_title}</strong><small>{sale.buyer_name} · {sale.order_number}</small></div><span>{orderStatus[sale.payment_status] ?? sale.payment_status}</span><strong>{formatMoney(sale.paid_amount_yuan)}</strong></article>)}
              {!provider.sales.length ? <div className="me-empty">还没有销售订单</div> : null}
            </div>
          </section>

          <section className="me-section compute-hosting-section">
            <div className="me-section-heading"><h2>算力与托管</h2><span>费用功能尚未开通</span></div>
            <div className="compute-hosting-tabs" role="tablist" aria-label="查看算力与托管">
              <button className={computeView === "training" ? "is-active" : ""} type="button" role="tab" aria-selected={computeView === "training"} onClick={() => setComputeView("training")}>
                训练任务 <span>{trainingRuns.length}</span>
              </button>
              <button className={computeView === "services" ? "is-active" : ""} type="button" role="tab" aria-selected={computeView === "services"} onClick={() => setComputeView("services")}>
                在线服务 <span>{deployments.length}</span>
              </button>
            </div>
            {computeView === "training" ? (
              <div className="me-table compute-hosting-table" role="tabpanel">
                {trainingRuns.map((run) => <article key={run.id}>
                  <div><strong>{String(run.recipe.model ?? run.engine)}</strong><small>{run.project.name} · {String(run.recipe.epochs ?? "—")} 轮 · {run.progress}%</small></div>
                  <span>{trainingStatus[run.status] ?? run.status}</span>
                  <Link href={`/studio/training/runs/${run.id}?project=${run.project_id}`}>查看<ArrowRight size={12} /></Link>
                </article>)}
                {!trainingRuns.length ? <div className="me-empty"><Cpu size={17} /><span>还没有训练任务</span></div> : null}
              </div>
            ) : (
              <div className="me-table compute-hosting-table" role="tabpanel">
                {deployments.map((deployment) => <article key={deployment.id}>
                  <div><strong>{deployment.name}</strong><small>{deployment.model_name} v{deployment.model_version_number} · {deployment.request_count.toLocaleString("zh-CN")} 次调用</small></div>
                  <span>{deploymentStatus[deployment.status] ?? deployment.status}</span>
                  <Link href={`/services?project=${deployment.project_id}`}>查看<ArrowRight size={12} /></Link>
                </article>)}
                {!deployments.length ? <div className="me-empty"><Boxes size={17} /><span>还没有在线服务</span></div> : null}
              </div>
            )}
          </section>

          <Link className="settings-entry" href="/settings"><Settings size={17} /><span><strong>账户与设置</strong><small>成员、权限和账户设置</small></span><ArrowRight size={16} /></Link>
        </div>
      ) : null}

      {!loading && view === "consumer" ? (
        <div className="me-content">
          <section className="me-summary-grid" aria-label="购买与使用概览">
            <article><WalletCards size={17} /><span>钱包</span><strong>—</strong><small>尚未开通</small></article>
            <article><KeyRound size={17} /><span>已购 API</span><strong>{activeSubscriptions.length}</strong><small>当前可用</small></article>
            <article><Boxes size={17} /><span>剩余额度</span><strong>{remainingUnits.toLocaleString("zh-CN")}</strong><small>次调用</small></article>
            <article><ShoppingBag size={17} /><span>订单</span><strong>{billing.orders.length}</strong><small>{formatMoney(billing.authorization_ceiling_yuan)}</small></article>
          </section>

          {secret ? <section className="api-key-reveal"><div><span>API 密钥</span><code>{secret.api_key}</code></div><button className="secondary-button compact" type="button" onClick={() => void copyKey()}><Copy size={13} />复制</button></section> : null}

          <section className="me-section">
            <div className="me-section-heading"><h2>我的 API</h2><Link href="/marketplace">去算法市场</Link></div>
            <div className="me-api-grid">
              {subscriptions.map((subscription) => <article key={subscription.id}>
                <div><span>{subscription.status === "active" ? "可用" : orderStatus[subscription.status] ?? subscription.status}</span><strong>{subscription.listing_title}</strong><small>{subscription.provider_name}</small></div>
                <dl><div><dt>剩余额度</dt><dd>{subscription.remaining_units.toLocaleString("zh-CN")}</dd></div><div><dt>到期日</dt><dd>{formatDate(subscription.expires_at)}</dd></div></dl>
                <code>{subscription.endpoint_url}</code>
                {subscription.status === "active" ? <div className="me-api-actions">
                  {!subscription.credential_claimed_at ? <button className="primary-button compact" type="button" disabled={busyId === subscription.id} onClick={() => void showKey(subscription)}>领取密钥</button> : null}
                  {subscription.credential_claimed_at ? <button className="secondary-button compact" type="button" disabled={busyId === subscription.id} onClick={() => void showKey(subscription, true)}><RefreshCw size={13} />更换密钥</button> : null}
                </div> : null}
              </article>)}
              {!subscriptions.length ? <div className="me-empty">还没有购买 API</div> : null}
            </div>
          </section>

          <section className="me-section">
            <div className="me-section-heading"><h2>购买订单</h2><span>{billing.orders.length} 个</span></div>
            <div className="me-table">
              {billing.orders.map((order) => <article key={order.id}><div><strong>{order.listing_title}</strong><small>{order.provider_name} · {order.order_number}</small></div><span>{orderStatus[order.payment_status] ?? orderStatus[order.status] ?? order.status}</span><strong>{formatMoney(order.authorization_amount_yuan)}</strong></article>)}
              {!billing.orders.length ? <div className="me-empty">还没有购买订单</div> : null}
            </div>
          </section>

          <section className="me-section">
            <div className="me-section-heading"><h2>最近使用</h2><span>{usage.length} 条</span></div>
            <div className="me-table">
              {usage.slice(0, 12).map((record) => <article key={record.id}><div><strong>{record.listing_title}</strong><small>{formatDate(record.occurred_at)}</small></div><span>{record.billable_units} 次</span><strong>{formatMoney(record.estimated_cost_yuan)}</strong></article>)}
              {!usage.length ? <div className="me-empty">还没有 API 使用记录</div> : null}
            </div>
          </section>

          <section className="me-section data-access-section">
            <div className="me-section-heading"><h2>数据授权</h2><Link href="/data-market">浏览数据市场</Link></div>
            <div><span>数据购买和交付尚未开放</span><small>当前可查看数据卡、许可与适用范围。</small></div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
