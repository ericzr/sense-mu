import type { Metadata } from "next";
import { ProductShell } from "../../components/product-shell";
import { DataDetailWorkbench } from "./data-detail-workbench";

export const metadata: Metadata = {
  title: "数据集详情 · SenseMu",
  description: "查看数据样例、规模、类别、质量、来源和授权边界。",
};

export default async function DataDetailPage({ params }: { params: Promise<{ listingId: string }> }) {
  const { listingId } = await params;
  return (
    <ProductShell active="data-market">
      <DataDetailWorkbench listingId={listingId} />
    </ProductShell>
  );
}
