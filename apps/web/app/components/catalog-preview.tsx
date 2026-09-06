/* eslint-disable @next/next/no-img-element -- Catalog previews preserve source pixels and annotation coordinates across local, remote, and data URL images. */
import type { CatalogPreview as CatalogPreviewData } from "../../lib/catalog-mock-data";
import type { CSSProperties } from "react";

type CatalogPreviewProps = {
  preview: CatalogPreviewData;
  kind: "algorithm" | "data";
  large?: boolean;
  zoom?: number;
};

type PreviewStyle = CSSProperties & { "--catalog-image"?: string };

const sceneImages: Partial<Record<CatalogPreviewData["scene"], { url: string; aspectRatio: number }>> = {
  "road-surface": { url: "/catalog-real-road-surface.png", aspectRatio: 352 / 288 },
  "road-safety": { url: "/catalog-real-road-safety.jpg", aspectRatio: 640 / 427 },
  "road-slope": { url: "/catalog-real-road-slope.jpg", aspectRatio: 640 / 480 },
  "road-environment": { url: "/catalog-real-road-environment.png", aspectRatio: 352 / 288 },
  tunnel: { url: "/catalog-real-tunnel.jpg", aspectRatio: 480 / 640 },
  bridge: { url: "/catalog-real-bridge.jpg", aspectRatio: 640 / 480 },
  "urban-illegal": { url: "/catalog-real-urban-illegal.jpg", aspectRatio: 640 / 427 },
  "urban-sanitation": { url: "/catalog-real-urban-sanitation.jpg", aspectRatio: 640 / 480 },
  "urban-construction-waste": { url: "/catalog-real-urban-construction-waste.jpg", aspectRatio: 640 / 480 },
  "urban-site": { url: "/catalog-real-urban-site.jpg", aspectRatio: 640 / 482 },
  "urban-advertising": { url: "/catalog-real-urban-advertising.jpg", aspectRatio: 640 / 480 },
  "urban-municipal": { url: "/catalog-real-urban-municipal.jpg", aspectRatio: 640 / 480 },
  "urban-water": { url: "/catalog-real-urban-water.jpg", aspectRatio: 480 / 640 },
  "urban-ecology": { url: "/catalog-real-urban-ecology.jpg", aspectRatio: 640 / 480 },
  "urban-fire": { url: "/catalog-real-urban-fire.jpg", aspectRatio: 640 / 480 },
  "urban-crowd": { url: "/catalog-real-urban-crowd.jpg", aspectRatio: 640 / 427 },
  "urban-traffic": { url: "/catalog-real-urban-traffic.jpg", aspectRatio: 640 / 480 },
  "urban-greening": { url: "/catalog-real-urban-greening.jpg", aspectRatio: 640 / 427 },
};

export function getCatalogSceneImage(scene: CatalogPreviewData["scene"]) {
  return sceneImages[scene] ?? null;
}

export function getCoverBoxStyle(
  box: CatalogPreviewData["boxes"][number],
  sourceRatio: number,
  frameRatio: number,
): CSSProperties {
  let x = box.x;
  let y = box.y;
  let width = box.width;
  let height = box.height;
  if (sourceRatio < frameRatio) {
    const visibleHeight = sourceRatio / frameRatio;
    const cropTop = (1 - visibleHeight) / 2;
    y = (box.y / 100 - cropTop) / visibleHeight * 100;
    height = box.height / visibleHeight;
  } else if (sourceRatio > frameRatio) {
    const visibleWidth = frameRatio / sourceRatio;
    const cropLeft = (1 - visibleWidth) / 2;
    x = (box.x / 100 - cropLeft) / visibleWidth * 100;
    width = box.width / visibleWidth;
  }
  return { left: `${x}%`, top: `${y}%`, width: `${width}%`, height: `${height}%` };
}

export function getContainedFrameStyle(sourceRatio: number, frameRatio: number, zoom = 1): CSSProperties {
  const boundedZoom = Math.min(1.4, Math.max(1, zoom));
  const size = sourceRatio < frameRatio
    ? { width: `${sourceRatio / frameRatio * 100}%`, height: "100%" }
    : { width: "100%", height: `${frameRatio / sourceRatio * 100}%` };
  return {
    ...size,
    transform: `translate(-50%, -50%) scale(${boundedZoom})`,
  };
}

function directBoxStyle(box: CatalogPreviewData["boxes"][number]): CSSProperties {
  return { left: `${box.x}%`, top: `${box.y}%`, width: `${box.width}%`, height: `${box.height}%` };
}

export function CatalogPreview({ preview, kind, large = false, zoom = 1 }: CatalogPreviewProps) {
  const frameRatio = large ? 4 / 3 : 16 / 9;
  const sceneImage = getCatalogSceneImage(preview.scene);
  const sourceRatio = Math.min(4, Math.max(0.25, preview.aspect_ratio ?? sceneImage?.aspectRatio ?? 1));
  const imageUrl = preview.image_url ?? sceneImage?.url;
  const previewStyle: PreviewStyle | undefined = imageUrl
    ? { "--catalog-image": `url("${imageUrl}")` }
    : undefined;

  return (
    <div
      className={`catalog-preview${large ? " is-large" : ""}${imageUrl ? " has-image" : ""}`}
      style={previewStyle}
      role="img"
      aria-label={preview.alt}
    >
      <span className="catalog-preview-kind">{kind === "algorithm" ? "效果样例" : "标注样例"}</span>
      {imageUrl ? (
        <>
          <span className="catalog-preview-backdrop" aria-hidden="true" />
          <div
            className="catalog-preview-media is-contained"
            style={getContainedFrameStyle(sourceRatio, frameRatio, zoom)}
            aria-hidden="true"
          >
            <img src={imageUrl} alt="" />
            {preview.boxes.map((box, index) => (
              <span
                className="catalog-preview-box"
                key={`${box.label}-${index}`}
                style={directBoxStyle(box)}
              >
                <small>{box.label}{box.confidence ? ` ${box.confidence}` : ""}</small>
              </span>
            ))}
          </div>
        </>
      ) : (
        <div
          className={`catalog-preview-media is-contained is-legacy scene-${preview.scene}`}
          style={getContainedFrameStyle(frameRatio, frameRatio, zoom)}
          aria-hidden="true"
        >
          {preview.boxes.map((box, index) => (
            <span
              className="catalog-preview-box"
              key={`${box.label}-${index}`}
              style={getCoverBoxStyle(box, sourceRatio, frameRatio)}
            >
              <small>{box.label}{box.confidence ? ` ${box.confidence}` : ""}</small>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
