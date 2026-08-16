import type { Metadata } from "next";
import { ProductShell } from "../../../../components/product-shell";
import { ProjectChrome } from "../../../project-chrome";
import { TrainingArtifactDetail } from "../../artifact-detail";

export const metadata: Metadata = {
  title: "训练任务详情 · SenseMu",
  description: "查看训练任务状态、参数与产物。",
};

export default async function TrainingRunDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return (
    <ProductShell active="studio">
      <main className="studio-main training-detail-page">
        <ProjectChrome active="training" />
        <TrainingArtifactDetail artifactId={runId} kind="run" />
      </main>
    </ProductShell>
  );
}
