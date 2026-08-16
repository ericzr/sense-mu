import type { Metadata } from "next";
import { ProductShell } from "../../../../components/product-shell";
import { ProjectChrome } from "../../../project-chrome";
import { TrainingArtifactDetail } from "../../artifact-detail";

export const metadata: Metadata = {
  title: "模型详情 · SenseMu",
  description: "查看模型指标、训练来源、检查与发布状态。",
};

export default async function ModelDetailPage({ params }: { params: Promise<{ modelId: string }> }) {
  const { modelId } = await params;
  return (
    <ProductShell active="studio">
      <main className="studio-main training-detail-page">
        <ProjectChrome active="training" />
        <TrainingArtifactDetail artifactId={modelId} kind="model" />
      </main>
    </ProductShell>
  );
}
