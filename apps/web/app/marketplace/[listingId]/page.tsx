import type { Metadata } from "next";
import { ProductShell } from "../../components/product-shell";
import { AlgorithmDetailWorkbench } from "./algorithm-detail-workbench";

export const metadata: Metadata = {
  title: "算法详情 · SenseMu",
  description: "查看算法效果、适用边界、接口规格和调用价格。",
};

export default async function AlgorithmDetailPage({ params }: { params: Promise<{ listingId: string }> }) {
  const { listingId } = await params;
  return (
    <ProductShell active="algorithm-market">
      <AlgorithmDetailWorkbench listingId={listingId} />
    </ProductShell>
  );
}
