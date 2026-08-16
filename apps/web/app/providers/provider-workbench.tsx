"use client";

import {
  AlertCircle,
  BadgeCheck,
  Boxes,
  Building2,
  Check,
  CircleDollarSign,
  ClipboardList,
  Cpu,
  FileClock,
  Landmark,
  LoaderCircle,
  ReceiptText,
  Save,
  ShieldCheck,
  X,
} from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";
import {
  catalogApi,
  type ProviderDashboard,
  type ProviderProfileUpdate,
  type Workspace,
} from "../../lib/catalog-api";

const emptyDashboard: ProviderDashboard = {
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

const regions = ["中国大陆", "中国香港", "亚太", "欧洲", "北美", "全球"];

const paymentLabels: Record<string, string> = {
  not_collected: "未收款",
  paid: "已收款",
  partially_refunded: "部分退款",
  refunded: "已退款",
};

const listingReviewLabels: Record<string, string> = {
  pending_review: "等待平台审核",
  published: "已在公开目录发布",
  rejected: "审核未通过",
};

function formatYuan(value: number, digits = 2): string {
  return value.toLocaleString("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function ProviderWorkbench() {
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [dashboard, setDashboard] = useState<ProviderDashboard>(emptyDashboard);
  const [publicName, setPublicName] = useState("");
  const [summary, setSummary] = useState("");
  const [providerType, setProviderType] = useState<"organization" | "individual">("organization");
  const [supportEmail, setSupportEmail] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [serviceRegions, setServiceRegions] = useState<string[]>(["中国大陆"]);
  const [supportCommitment, setSupportCommitment] = useState("");

  const selectedWorkspace = workspaces.find((workspace) => workspace.id === workspaceId);
  const canManage = selectedWorkspace?.role === "owner" || selectedWorkspace?.role === "admin";

  function syncProfile(nextDashboard: ProviderDashboard, fallbackName: string) {
    const profile = nextDashboard.profile;
    setPublicName(profile?.public_name ?? fallbackName);
    setSummary(profile?.summary ?? "");
    setProviderType(profile?.provider_type ?? "organization");
    setSupportEmail(profile?.support_email ?? "");
    setWebsiteUrl(profile?.website_url ?? "");
    setServiceRegions(profile?.service_regions ?? ["中国大陆"]);
    setSupportCommitment(profile?.support_commitment ?? "");
  }

  async function loadDashboard(workspace: Workspace) {
    if (workspace.role !== "owner" && workspace.role !== "admin") {
      setDashboard(emptyDashboard);
      syncProfile(emptyDashboard, workspace.name);
      return;
    }
    const nextDashboard = await catalogApi.getProviderDashboard(workspace.id);
    setDashboard(nextDashboard);
    syncProfile(nextDashboard, workspace.name);
  }

  useEffect(() => {
    void catalogApi
      .listWorkspaces()
      .then(async (nextWorkspaces) => {
        setWorkspaces(nextWorkspaces);
        const selected =
          nextWorkspaces.find(
            (workspace) => workspace.role === "owner" || workspace.role === "admin",
          ) ?? nextWorkspaces[0];
        setWorkspaceId(selected?.id ?? "");
        if (selected) await loadDashboard(selected);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "供应方中心加载失败"))
      .finally(() => setLoading(false));
  }, []);

  async function changeWorkspace(nextWorkspaceId: string) {
    const workspace = workspaces.find((item) => item.id === nextWorkspaceId);
    if (!workspace) return;
    setWorkspaceId(nextWorkspaceId);
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      await loadDashboard(workspace);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工作区切换失败");
    } finally {
      setLoading(false);
    }
  }

  function toggleRegion(region: string) {
    setServiceRegions((current) =>
      current.includes(region)
        ? current.filter((item) => item !== region)
        : [...current, region],
    );
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    if (!workspaceId || serviceRegions.length === 0) return;
    const payload: ProviderProfileUpdate = {
      public_name: publicName,
      summary,
      provider_type: providerType,
      support_email: supportEmail,
      website_url: websiteUrl.trim() || null,
      service_regions: serviceRegions,
      support_commitment: supportCommitment,
    };
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await catalogApi.updateProviderProfile(workspaceId, payload);
      if (selectedWorkspace) await loadDashboard(selectedWorkspace);
      setNotice("供应方档案已保存；实名、收款与平台审核状态没有被自动改变");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "供应方档案保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="provider-main">
      <section className="provider-heading">
        <div>
          <span className="eyebrow">供给运营</span>
          <h1>供应方中心</h1>
          <p>从可交付资产到销售与收入事实，保持一条可核对的链路。</p>
        </div>
        <label className="provider-workspace-select">
          <span>供应工作区</span>
          <select value={workspaceId} onChange={(event) => void changeWorkspace(event.target.value)}>
            {workspaces.map((workspace) => <option value={workspace.id} key={workspace.id}>{workspace.name}</option>)}
          </select>
        </label>
      </section>

      {error ? <div className="provider-message is-error" role="alert"><AlertCircle size={16} /><span>{error}</span><button type="button" aria-label="关闭错误提示" onClick={() => setError(null)}><X size={15} /></button></div> : null}
      {notice ? <div className="provider-message" role="status"><Check size={16} /><span>{notice}</span><button type="button" aria-label="关闭状态提示" onClick={() => setNotice(null)}><X size={15} /></button></div> : null}

      {loading ? (
        <section className="provider-loading"><LoaderCircle className="spin" size={20} />正在读取供应方资产与账本</section>
      ) : !workspaceId ? (
        <section className="provider-empty">请先创建工作区。</section>
      ) : !canManage ? (
        <section className="provider-empty"><ShieldCheck size={24} /><strong>当前角色不能查看供应方账本</strong><span>只有工作区管理员和所有者可以管理公开档案、销售与收入。</span></section>
      ) : (
        <>
          <section className="provider-kpis">
            <article><span className="provider-kpi-icon soft-blue"><Cpu size={18} /></span><div><small>算法商品</small><strong>{dashboard.algorithm_listing_count}</strong><em>{dashboard.active_customer_grants} 份有效客户授权</em></div></article>
            <article><span className="provider-kpi-icon soft-purple"><Boxes size={18} /></span><div><small>公开数据卡</small><strong>{dashboard.data_listing_count}</strong><em>仍未开放付费交付</em></div></article>
            <article><span className="provider-kpi-icon soft-sand"><ReceiptText size={18} /></span><div><small>销售授权上限</small><strong>{formatYuan(dashboard.authorized_sales_yuan)}</strong><em>实收 {formatYuan(dashboard.paid_sales_yuan)}</em></div></article>
            <article><span className="provider-kpi-icon soft-green"><Landmark size={18} /></span><div><small>待结算收入</small><strong>{formatYuan(dashboard.unsettled_earnings_yuan, 4)}</strong><em>{dashboard.successful_units.toLocaleString("zh-CN")} 次成功计量</em></div></article>
          </section>

          <section className="provider-readiness">
            <div><span className="provider-section-icon"><ClipboardList size={18} /></span><div><h2>准入状态</h2><p>系统只展示真实完成度，不自动通过外部审核。</p></div></div>
            <div className="provider-readiness-steps">
              <span className={dashboard.profile ? "is-complete" : ""}>{dashboard.profile ? <Check size={13} /> : <FileClock size={13} />}公开档案 · {dashboard.profile ? "已完成" : "待填写"}</span>
              <span><FileClock size={13} />主体认证 · 未开始</span>
              <span><FileClock size={13} />收款配置 · 未开始</span>
              <span><FileClock size={13} />平台审核 · 未提交</span>
            </div>
          </section>

          <div className="provider-grid">
            <form className="provider-panel provider-profile" onSubmit={(event) => void saveProfile(event)}>
              <header><div><span className="provider-section-icon soft-purple"><Building2 size={18} /></span><div><h2>公开档案</h2><p>面向客户的供应方身份与支持承诺</p></div></div></header>
              <div className="provider-profile-fields">
                <label><span>公开名称</span><input value={publicName} required minLength={2} onChange={(event) => setPublicName(event.target.value)} /></label>
                <label><span>供应方类型</span><select value={providerType} onChange={(event) => setProviderType(event.target.value as "organization" | "individual")}><option value="organization">企业或团队</option><option value="individual">个人开发者</option></select></label>
                <label><span>支持邮箱</span><input type="email" value={supportEmail} required onChange={(event) => setSupportEmail(event.target.value)} /></label>
                <label><span>网站</span><input type="url" value={websiteUrl} placeholder="https://" onChange={(event) => setWebsiteUrl(event.target.value)} /></label>
                <label className="is-wide"><span>能力说明</span><textarea value={summary} required minLength={12} onChange={(event) => setSummary(event.target.value)} /></label>
                <fieldset className="is-wide"><legend>服务区域</legend><div>{regions.map((region) => <label key={region}><input type="checkbox" checked={serviceRegions.includes(region)} onChange={() => toggleRegion(region)} />{region}</label>)}</div></fieldset>
                <label className="is-wide"><span>支持承诺</span><textarea value={supportCommitment} required minLength={8} onChange={(event) => setSupportCommitment(event.target.value)} /></label>
              </div>
              <button className="primary-button" type="submit" disabled={busy || serviceRegions.length === 0}>{busy ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}保存档案</button>
            </form>

            <aside className="provider-panel provider-boundaries">
              <header><div><span className="provider-section-icon soft-sand"><ShieldCheck size={18} /></span><div><h2>商业边界</h2><p>尚未接入的能力保持关闭</p></div></div></header>
              <div className="provider-boundary-list">
                <article><span><BadgeCheck size={16} /></span><div><strong>主体认证</strong><p>需要后续接入企业或个人认证服务。</p></div><em>未开始</em></article>
                <article><span><CircleDollarSign size={16} /></span><div><strong>收款账户</strong><p>支付渠道与结算主体尚未确定。</p></div><em>未开始</em></article>
                <article><span><Landmark size={16} /></span><div><strong>提现与结算</strong><p>账本仅记录待结算收入，不提供虚假提现。</p></div><em>未开放</em></article>
              </div>
            </aside>

            <section className="provider-panel provider-assets">
              <header><div><span className="provider-section-icon soft-blue"><Cpu size={18} /></span><div><h2>算法商品</h2><p>提交后需通过平台审核才会公开</p></div></div><Link href="/marketplace">提交商品</Link></header>
              {dashboard.algorithm_listings.length ? <div className="provider-asset-list">{dashboard.algorithm_listings.map((listing) => <article key={listing.id}><span className="provider-asset-mark"><Cpu size={16} /></span><div><strong>{listing.title}</strong><small>{listing.category} · {formatYuan(listing.price_per_1000_cents / 100)} / 千张</small>{listing.review_note ? <small>审核说明：{listing.review_note}</small> : null}</div><div><strong>{listing.successful_units.toLocaleString("zh-CN")}</strong><small>成功计量</small></div><span>{listingReviewLabels[listing.status] ?? listing.status}</span></article>)}</div> : <div className="provider-list-empty"><Cpu size={20} />尚无提交的算法商品</div>}
            </section>

            <section className="provider-panel provider-assets">
              <header><div><span className="provider-section-icon soft-purple"><Boxes size={18} /></span><div><h2>数据卡</h2><p>仅展示可信发现层资产</p></div></div><Link href="/data-market">管理数据卡</Link></header>
              {dashboard.data_listings.length ? <div className="provider-asset-list">{dashboard.data_listings.map((listing) => <article key={listing.id}><span className="provider-asset-mark"><Boxes size={16} /></span><div><strong>{listing.title}</strong><small>{listing.dataset_name} · 第 {listing.dataset_version_number} 版</small></div><div><strong>{listing.asset_count.toLocaleString("zh-CN")}</strong><small>样本</small></div><span>{listing.license_code}</span></article>)}</div> : <div className="provider-list-empty"><Boxes size={20} />尚无公开数据卡</div>}
            </section>

            <section className="provider-panel provider-ledger">
              <header><div><span className="provider-section-icon soft-sand"><ReceiptText size={18} /></span><div><h2>销售订单</h2><p>授权金额不等于已收款</p></div></div><span>{dashboard.sales.length}</span></header>
              {dashboard.sales.length ? <div className="provider-ledger-list">{dashboard.sales.map((sale) => <article key={sale.id}><div><strong>{sale.listing_title}</strong><small>{sale.buyer_name} · {formatDate(sale.created_at)}</small><code>{sale.order_number}</code></div><div><strong>{formatYuan(sale.authorization_amount_yuan)}</strong><small>{paymentLabels[sale.payment_status] ?? sale.payment_status}</small>{sale.refunded_amount_yuan ? <em>已退 {formatYuan(sale.refunded_amount_yuan)}</em> : null}</div></article>)}</div> : <div className="provider-list-empty"><ReceiptText size={20} />尚无供应方销售订单</div>}
            </section>

            <section className="provider-panel provider-ledger">
              <header><div><span className="provider-section-icon soft-green"><Landmark size={18} /></span><div><h2>收入计提</h2><p>只由成功调用生成，尚未结算</p></div></div><span>{dashboard.earnings.length}</span></header>
              {dashboard.earnings.length ? <div className="provider-ledger-list">{dashboard.earnings.map((earning) => <article key={earning.id}><div><strong>{earning.listing_title}</strong><small>{earning.buyer_name} · {formatDate(earning.occurred_at)}</small><code>{earning.request_id}</code></div><div><strong>{formatYuan(earning.amount_yuan, 4)}</strong><small>未结算</small></div></article>)}</div> : <div className="provider-list-empty"><Landmark size={20} />尚无成功调用收入</div>}
            </section>
          </div>
        </>
      )}
    </main>
  );
}
