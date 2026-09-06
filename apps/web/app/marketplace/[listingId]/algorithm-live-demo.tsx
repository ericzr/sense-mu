"use client";

/* eslint-disable @next/next/no-img-element -- The demo supports local data URL uploads that cannot use the optimized image pipeline. */

import {
  Check,
  Image as ImageIcon,
  LoaderCircle,
  Play,
  RotateCcw,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { type ChangeEvent, type CSSProperties, type SyntheticEvent, useMemo, useState } from "react";
import { getCatalogSceneImage, getContainedFrameStyle, getCoverBoxStyle } from "../../components/catalog-preview";
import type { AlgorithmCatalogItem } from "../../../lib/catalog-mock-data";

type DemoSource = "sample" | "upload";
type DemoCanvasStyle = CSSProperties & { "--algorithm-demo-image"?: string };

function directBoxStyle(box: AlgorithmCatalogItem["preview"]["boxes"][number]): CSSProperties {
  return { left: `${box.x}%`, top: `${box.y}%`, width: `${box.width}%`, height: `${box.height}%` };
}

export function AlgorithmLiveDemo({ listing }: { listing: AlgorithmCatalogItem }) {
  const [source, setSource] = useState<DemoSource>("sample");
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [uploadedName, setUploadedName] = useState("");
  const [confidence, setConfidence] = useState(0.25);
  const [running, setRunning] = useState(false);
  const [hasResult, setHasResult] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [uploadedAspectRatio, setUploadedAspectRatio] = useState<number | null>(null);

  const visibleBoxes = useMemo(
    () => listing.preview.boxes.filter((box) => Number(box.confidence ?? 1) >= confidence),
    [confidence, listing.preview.boxes],
  );
  const sceneImage = getCatalogSceneImage(listing.preview.scene);
  const sampleSourceRatio = Math.min(4, Math.max(0.25, listing.preview.aspect_ratio ?? sceneImage?.aspectRatio ?? 1));
  const demoFrameRatio = 16 / 10;
  const directSampleImage = listing.preview.image_url ?? sceneImage?.url;
  const activeImage = uploadedImage ?? directSampleImage;
  const activeSourceRatio = uploadedImage ? (uploadedAspectRatio ?? sampleSourceRatio) : sampleSourceRatio;
  const canvasStyle: DemoCanvasStyle | undefined = activeImage
    ? { "--algorithm-demo-image": `url("${activeImage}")` }
    : undefined;

  function chooseSample() {
    setSource("sample");
    setUploadedImage(null);
    setUploadedName("");
    setHasResult(false);
    setMessage(null);
    setZoom(1);
  }

  function chooseUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setMessage("请选择图片文件");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setMessage("图片不能超过 10 MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setSource("upload");
      setUploadedImage(String(reader.result));
      setUploadedName(file.name);
      setUploadedAspectRatio(null);
      setHasResult(false);
      setMessage(null);
      setZoom(1);
    };
    reader.readAsDataURL(file);
    event.target.value = "";
  }

  function runDemo() {
    setRunning(true);
    setHasResult(false);
    setMessage(null);
    window.setTimeout(() => {
      setRunning(false);
      setHasResult(true);
      setMessage(listing.is_mock ? "已生成体验结果；当前为商品效果演示。" : "识别完成");
    }, 620);
  }

  function resetDemo() {
    setHasResult(false);
    setMessage(null);
  }

  function captureUploadedRatio(event: SyntheticEvent<HTMLImageElement>) {
    if (!uploadedImage) return;
    const image = event.currentTarget;
    if (image.naturalWidth && image.naturalHeight) {
      setUploadedAspectRatio(image.naturalWidth / image.naturalHeight);
    }
  }

  return (
    <section className="algorithm-live-demo" aria-labelledby="algorithm-live-demo-title">
      <div className="algorithm-demo-heading">
        <div>
          <span>购买前体验</span>
          <h2 id="algorithm-live-demo-title">在线体验</h2>
          <p>选择示例或上传一张图片，直接查看识别结果。</p>
        </div>
        <span className="algorithm-demo-model"><i aria-hidden="true" />{listing.model_architecture}</span>
      </div>

      <div className="algorithm-demo-layout">
        <div className="algorithm-demo-stage">
          <div className="algorithm-demo-stagebar">
            <span><ImageIcon size={14} />{source === "sample" ? "商品示例" : uploadedName}</span>
            {hasResult ? <button type="button" onClick={resetDemo}><RotateCcw size={13} />重置结果</button> : <small>输入图片仅用于本次体验</small>}
          </div>

          <div
            className={`algorithm-demo-canvas scene-${listing.preview.scene}${source === "upload" ? " is-upload" : ""}${activeImage ? " has-image" : ""}`}
            style={canvasStyle}
            role="img"
            aria-label={source === "sample" ? listing.preview.alt : `待识别图片 ${uploadedName}`}
          >
            {activeImage ? (
              <>
                <span className="algorithm-demo-backdrop" aria-hidden="true" />
                <div className="algorithm-demo-image-frame" style={getContainedFrameStyle(activeSourceRatio, demoFrameRatio, zoom)} aria-hidden="true">
                  <img src={activeImage} alt="" onLoad={captureUploadedRatio} />
                  {hasResult ? visibleBoxes.map((box, index) => (
                    <span className="algorithm-demo-box" key={`${box.label}-${index}`} style={directBoxStyle(box)}>
                      <small>{box.label} {box.confidence}</small>
                    </span>
                  )) : null}
                </div>
              </>
            ) : (
              <div
                className={`algorithm-demo-image-frame is-legacy scene-${listing.preview.scene}`}
                style={getContainedFrameStyle(demoFrameRatio, demoFrameRatio, zoom)}
                aria-hidden="true"
              >
                {hasResult ? visibleBoxes.map((box, index) => (
                  <span
                    className="algorithm-demo-box"
                    key={`${box.label}-${index}`}
                    style={getCoverBoxStyle(box, sampleSourceRatio, demoFrameRatio)}
                  >
                    <small>{box.label} {box.confidence}</small>
                  </span>
                )) : null}
              </div>
            )}
            {running ? (
              <span className="algorithm-demo-running"><LoaderCircle size={21} className="spinner" />正在识别</span>
            ) : null}
            {!hasResult && !running ? <span className="algorithm-demo-ready">点击“运行识别”查看效果</span> : null}
          </div>

          <div className="algorithm-demo-resultbar" aria-live="polite">
            {hasResult ? (
              <>
                <span><Check size={14} />识别完成</span>
                <strong>{visibleBoxes.length} 个目标</strong>
                <small>{listing.latency_p95.replace("P95", "")} · 置信度 ≥ {confidence.toFixed(2)}</small>
              </>
            ) : <small>{message ?? "支持 JPEG、PNG、WebP，最大 10 MB"}</small>}
          </div>
          {source === "sample" && sceneImage ? (
            <p className="algorithm-demo-sample-origin">
              <span>真实公开样本</span>
              <a href={sceneImage.sourceUrl} target="_blank" rel="noreferrer">{sceneImage.dataset} · {sceneImage.license}</a>
              <small>识别框仅为 Mock 演示。</small>
            </p>
          ) : null}
        </div>

        <aside className="algorithm-demo-controls">
          <div className="algorithm-demo-control-heading"><strong>输入图片</strong><small>选择一种方式</small></div>
          <div className="algorithm-demo-source-grid">
            <button type="button" className={source === "sample" ? "is-active" : ""} onClick={chooseSample}>
              <span
                className={`algorithm-demo-thumb scene-${listing.preview.scene}`}
                style={{ backgroundImage: `url(${listing.preview.image_url ?? sceneImage?.url ?? "/catalog-vision-samples.png"})`, backgroundPosition: "center", backgroundSize: "cover" }}
              />
              <span><strong>商品示例</strong><small>立即体验</small></span>
              {source === "sample" ? <Check size={13} /> : null}
            </button>
            <label className={source === "upload" ? "is-active" : ""}>
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseUpload} />
              <UploadCloud size={17} />
              <span><strong>上传图片</strong><small>仅在本地预览</small></span>
            </label>
          </div>

          <label className="algorithm-demo-confidence">
            <span><strong>图像缩放</strong><b>{Math.round(zoom * 100)}%</b></span>
            <input aria-label="体验图片缩放" type="range" min="1" max="1.4" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} />
            <small>100% 完整显示；放大时可查看局部细节。</small>
          </label>

          <label className="algorithm-demo-confidence">
            <span><strong>置信度</strong><b>{confidence.toFixed(2)}</b></span>
            <input type="range" min="0.05" max="0.95" step="0.05" value={confidence} onChange={(event) => setConfidence(Number(event.target.value))} />
            <small>数值越高，结果越严格。</small>
          </label>

          <div className="algorithm-demo-privacy"><ShieldCheck size={15} /><span><strong>体验图片不留存</strong><small>当前页面不会把上传图片保存到素材库。</small></span></div>

          {message ? <p className="algorithm-demo-message" role="status">{message}</p> : null}
          <button className="primary-button algorithm-demo-run" type="button" disabled={running} onClick={runDemo}>
            {running ? <LoaderCircle size={15} className="spinner" /> : <Play size={15} />}
            {running ? "正在识别" : "运行识别"}
          </button>
          {listing.is_mock ? <p className="algorithm-demo-disclaimer">当前为商品效果演示；真实调用结果以正式 API 为准。</p> : null}
        </aside>
      </div>
    </section>
  );
}
