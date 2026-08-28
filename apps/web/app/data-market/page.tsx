import type { Metadata } from "next";
import { ProductShell } from "../components/product-shell";
import { DataMarketWorkbench } from "./data-market-workbench";

export const metadata: Metadata = {
  title: "数据市场 · SenseMu",
  description: "发现具备来源、许可、质量和用途边界的训练数据资产。",
};

export default function DataMarketPage() {
  const previewMode = process.env.SENSEMU_PREVIEW_MODE === "true";
  return (
    <ProductShell active="data-market">
      <DataMarketWorkbench previewMode={previewMode} />
    </ProductShell>
  );
}
