import type { CatalogPreview as CatalogPreviewData } from "../../lib/catalog-mock-data";
import type { CSSProperties } from "react";

type CatalogPreviewProps = {
  preview: CatalogPreviewData;
  kind: "algorithm" | "data";
  large?: boolean;
};

const sceneImages: Partial<Record<CatalogPreviewData["scene"], { url: string; aspectRatio: number }>> = {
  "road-surface": { url: "/catalog-road-inspection.jpg", aspectRatio: 1600 / 2400 },
  "road-safety": { url: "/catalog-road-inspection.jpg", aspectRatio: 1600 / 2400 },
  "road-slope": { url: "/catalog-road-inspection.jpg", aspectRatio: 1600 / 2400 },
  "road-environment": { url: "/catalog-urban-street.jpg", aspectRatio: 1600 / 1067 },
  tunnel: { url: "/catalog-road-inspection.jpg", aspectRatio: 1600 / 2400 },
  bridge: { url: "/catalog-construction-site.jpg", aspectRatio: 1600 / 1067 },
  "urban-illegal": { url: "/catalog-urban-buildings.jpg", aspectRatio: 1600 / 1067 },
  "urban-sanitation": { url: "/catalog-urban-street.jpg", aspectRatio: 1600 / 1067 },
  "urban-construction-waste": { url: "/catalog-construction-site.jpg", aspectRatio: 1600 / 1067 },
  "urban-site": { url: "/catalog-construction-site.jpg", aspectRatio: 1600 / 1067 },
  "urban-advertising": { url: "/catalog-urban-buildings.jpg", aspectRatio: 1600 / 1067 },
  "urban-municipal": { url: "/catalog-urban-street.jpg", aspectRatio: 1600 / 1067 },
  "urban-water": { url: "/catalog-waterway.jpg", aspectRatio: 1600 / 1068 },
  "urban-ecology": { url: "/catalog-waterway.jpg", aspectRatio: 1600 / 1068 },
  "urban-fire": { url: "/catalog-construction-site.jpg", aspectRatio: 1600 / 1067 },
  "urban-crowd": { url: "/catalog-urban-street.jpg", aspectRatio: 1600 / 1067 },
  "urban-traffic": { url: "/catalog-urban-traffic.jpg", aspectRatio: 1600 / 1067 },
  "urban-greening": { url: "/catalog-urban-street.jpg", aspectRatio: 1600 / 1067 },
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

export function CatalogPreview({ preview, kind, large = false }: CatalogPreviewProps) {
  const frameRatio = large ? 4 / 3 : 16 / 9;
  const sceneImage = getCatalogSceneImage(preview.scene);
  const sourceRatio = Math.min(4, Math.max(0.25, preview.aspect_ratio ?? sceneImage?.aspectRatio ?? 1));
  const mediaStyle: CSSProperties = { width: "100%", height: "100%" };

  const imageUrl = preview.image_url ?? sceneImage?.url;
  if (imageUrl) {
    mediaStyle.backgroundImage = `url("${imageUrl}")`;
    mediaStyle.backgroundPosition = "center";
    mediaStyle.backgroundSize = "cover";
  }

  function boxStyle(box: CatalogPreviewData["boxes"][number]): CSSProperties {
    return getCoverBoxStyle(box, sourceRatio, frameRatio);
  }

  return (
    <div
      className={`catalog-preview${large ? " is-large" : ""}`}
      role="img"
      aria-label={preview.alt}
    >
      <span className="catalog-preview-kind">{kind === "algorithm" ? "效果样例" : "标注样例"}</span>
      <div className={`catalog-preview-media scene-${preview.scene}`} style={mediaStyle} aria-hidden="true">
        {preview.boxes.map((box, index) => (
          <span
            className="catalog-preview-box"
            key={`${box.label}-${index}`}
            style={boxStyle(box)}
          >
            <small>{box.label}{box.confidence ? ` ${box.confidence}` : ""}</small>
          </span>
        ))}
      </div>
    </div>
  );
}
