"use client";

import { ArrowLeft, BadgeCheck, Check, LoaderCircle, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { dataTaskLabels, getDatasetListingCounts, licenseLabels } from "../data-market-workbench";
import { decorateDataListing, findMockData, type DataCatalogItem } from "../../../lib/catalog-mock-data";
import { catalogApi } from "../../../lib/catalog-api";

export function DataDetailWorkbench({ listingId, previewMode }: { listingId: string; previewMode: boolean }) {
  const initialListing = previewMode ? findMockData(listingId) : null;
  const [listing, setListing] = useState<DataCatalogItem | null>(initialListing);
  const [loading, setLoading] = useState(!initialListing);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialListing) return;
    void catalogApi.listPublicDataMarketListings()
      .then((publicListings) => {
        const realListing = publicListings.find((item) => item.id === listingId);
        setListing(realListing ? decorateDataListing(realListing) : null);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "数据集详情加载失败"))
      .finally(() => setLoading(false));
  }, [initialListing, listingId]);

  if (loading) {
    return <main className="product-page"><div className="storefront-empty"><LoaderCircle className="spinner" size={20} />正在加载数据集详情</div></main>;
  }

  if (!listing) {
    return (
      <main className="product-page catalog-detail-page">
        <Link className="catalog-back-link" href="/data-market"><ArrowLeft size={15} />返回数据市场</Link>
        <div className="catalog-detail-empty"><h1>没有找到这个数据集</h1><p>商品可能已下架或链接无效。</p></div>
      </main>
    );
  }

  const quality = listing.quality_report;
  const classes = Object.values(listing.class_map);
  const counts = getDatasetListingCounts(listing);
  const maxAnnotations = Math.max(...(quality?.class_distribution.map((item) => item.annotation_count) ?? [1]));

  return (
    <main className="product-page catalog-detail-page">
      <Link className="catalog-back-link" href="/data-market"><ArrowLeft size={15} />数据市场</Link>

      <section className="catalog-detail-hero is-copy-only">
        <div className="catalog-detail-intro">
          <div className="catalog-detail-kicker">
            <span>{dataTaskLabels[listing.task_type] ?? listing.task_type}</span>
            <span className="verified-label"><BadgeCheck size={14} /> 信息完整</span>
          </div>
          <h1>{listing.title}</h1>
          <p>{listing.summary}</p>
          <div className="storefront-tags">
            <span>{counts.images.toLocaleString("zh-CN")} 张图片</span>
            <span>{counts.annotatedImages === null ? "标注量待公布" : `${counts.annotatedImages.toLocaleString("zh-CN")} 张已标注`}</span>
            <span>{classes.length} 个类别</span>
            <span>{listing.annotation_type}</span>
          </div>
          <div className="catalog-detail-provider"><span>提供方</span><strong>{listing.provider_name}</strong><small>更新于 {listing.updated_label}</small></div>
        </div>
      </section>

      {error ? <p className="inline-notice is-error" role="alert">{error}</p> : null}

      <div className="catalog-detail-layout">
        <div className="catalog-detail-main">
          <section className="catalog-detail-section">
            <h2>数据概览</h2>
            <div className="catalog-metric-grid">
              <div><span>图片</span><strong>{counts.images.toLocaleString("zh-CN")}</strong></div>
              <div><span>已标注图片</span><strong>{counts.annotatedImages?.toLocaleString("zh-CN") ?? "待公布"}</strong></div>
              <div><span>标注实例</span><strong>{counts.annotations?.toLocaleString("zh-CN") ?? "待公布"}</strong></div>
              <div><span>类别</span><strong>{classes.length}</strong></div>
            </div>
            {quality ? (
              <dl className="catalog-fact-list">
                <div><dt>标注覆盖</dt><dd>{quality.annotation_coverage_percent}%</dd></div>
                <div><dt>图像尺寸</dt><dd>{listing.image_size_summary}</dd></div>
                <div><dt>训练集</dt><dd>{quality.split_counts.train.toLocaleString("zh-CN")}</dd></div>
                <div><dt>验证集</dt><dd>{quality.split_counts.valid.toLocaleString("zh-CN")}</dd></div>
                <div><dt>测试集</dt><dd>{quality.split_counts.test.toLocaleString("zh-CN")}</dd></div>
                <div><dt>版本</dt><dd>v{listing.dataset_version_number}</dd></div>
              </dl>
            ) : null}
          </section>

          <section className="catalog-detail-section">
            <h2>类别分布</h2>
            <div className="catalog-distribution-list">
              {(quality?.class_distribution ?? classes.map((name, index) => ({ class_name: name, annotation_count: classes.length - index }))).map((item) => (
                <div key={item.class_name}>
                  <span>{item.class_name}</span>
                  <div><i style={{ width: `${Math.max(8, item.annotation_count / maxAnnotations * 100)}%` }} /></div>
                  <strong>{quality ? item.annotation_count.toLocaleString("zh-CN") : "—"}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="catalog-detail-section">
            <h2>来源与质量</h2>
            <dl className="catalog-story-list">
              <div><dt>数据来源</dt><dd>{listing.source_summary}</dd></div>
              <div><dt>采集与标注</dt><dd>{listing.collection_method}</dd></div>
              <div><dt>覆盖范围</dt><dd>{listing.coverage_summary}</dd></div>
              <div><dt>已知限制</dt><dd>{listing.known_limitations}</dd></div>
              <div><dt>隐私处理</dt><dd>{listing.privacy_treatment}</dd></div>
            </dl>
            {quality?.advisories.length ? <p className="catalog-advisory">质量提示：{quality.advisories.join("；")}</p> : null}
          </section>
        </div>

        <aside className="catalog-purchase-card">
          <span>数据版本</span>
          <strong>{listing.price_label}</strong>
          <small>{licenseLabels[listing.license_code] ?? listing.license_code}</small>
          <ul>
            <li><ShieldCheck size={15} />{listing.allow_model_training ? "可用于模型训练" : "不可用于模型训练"}</li>
            <li><ShieldCheck size={15} />{listing.allow_commercial_use ? "可用于商业项目" : "仅限非商业使用"}</li>
            <li><ShieldCheck size={15} />{listing.allow_redistribution ? "允许再次分发" : "不可再次分发"}</li>
          </ul>
          <button className="primary-button" type="button" disabled>购买即将开放</button>
          <p>当前先敲定商品信息与授权边界；支付和数据交付将在下一阶段接入。</p>
          <div className="catalog-license-note"><Check size={14} /><span>购买前可再次核对完整许可条款</span></div>
        </aside>
      </div>
    </main>
  );
}
