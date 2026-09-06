"use client";

import { RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { useState } from "react";
import type { CatalogPreview as CatalogPreviewData } from "../../lib/catalog-mock-data";
import { CatalogPreview, getCatalogSceneImage } from "./catalog-preview";

export function CatalogZoomPreview({ preview, kind }: { preview: CatalogPreviewData; kind: "algorithm" | "data" }) {
  const [zoom, setZoom] = useState(1);
  const percent = Math.round(zoom * 100);
  const source = getCatalogSceneImage(preview.scene);

  return (
    <section className="catalog-zoom-preview" aria-labelledby="catalog-zoom-preview-title">
      <header>
        <div>
          <h2 id="catalog-zoom-preview-title">{kind === "data" ? "标注样例" : "效果样例"}</h2>
          <p>默认完整显示原图，可在 100%–140% 范围内查看细节。</p>
        </div>
        <div className="catalog-zoom-controls">
          <ZoomOut size={14} aria-hidden="true" />
          <input
            aria-label="示例图片缩放"
            type="range"
            min="1"
            max="1.4"
            step="0.05"
            value={zoom}
            onChange={(event) => setZoom(Number(event.target.value))}
          />
          <ZoomIn size={14} aria-hidden="true" />
          <output>{percent}%</output>
          <button type="button" disabled={zoom === 1} onClick={() => setZoom(1)} aria-label="恢复图片为完整显示">
            <RotateCcw size={13} aria-hidden="true" />复位
          </button>
        </div>
      </header>
      <CatalogPreview preview={preview} kind={kind} large zoom={zoom} />
      {source ? (
        <p className="catalog-preview-attribution">
          <span>真实公开样本</span>
          <a href={source.sourceUrl} target="_blank" rel="noreferrer">{source.dataset} · {source.sample} · {source.license}</a>
          <small>框线与中文类别为 Mock 演示，不是原始标注或模型输出。</small>
        </p>
      ) : null}
    </section>
  );
}
