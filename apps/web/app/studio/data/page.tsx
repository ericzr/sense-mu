import type { Metadata } from "next";
import { ProductShell } from "../../components/product-shell";
import { DataWorkbench } from "./data-workbench";

export const metadata: Metadata = {
  title: "数据与标注 · SenseMu",
  description: "创建数据集、导入视觉资产并生成不可变数据版本。",
};

export default function DataPage() {
  return (
    <ProductShell active="studio">
      <main className="studio-main data-page">
        <DataWorkbench />
      </main>
    </ProductShell>
  );
}
