import type { Metadata } from "next";
import { ProductShell } from "../components/product-shell";
import { MarketplaceWorkbench } from "./marketplace-workbench";

export const metadata: Metadata = {
  title: "算法市场 · SenseMu",
  description: "查找、比较和购买可直接调用的视觉算法。",
};

export default function MarketplacePage() {
  return (
    <ProductShell active="algorithm-market">
      <MarketplaceWorkbench />
    </ProductShell>
  );
}
