import type { Metadata } from "next";
import { ProductShell } from "../../components/product-shell";
import { ProjectChrome } from "../project-chrome";
import { TrainingWorkbench } from "./training-workbench";

export const metadata: Metadata = {
  title: "训练任务 · SenseMu",
  description: "从不可变数据版本创建可追溯的视觉模型训练任务。",
};

export default function TrainingPage() {
  return (
    <ProductShell active="studio">
      <main className="studio-main training-page">
        <ProjectChrome active="training" />
        <TrainingWorkbench />
      </main>
    </ProductShell>
  );
}
