import type { Metadata } from "next";
import { ProductShell } from "../components/product-shell";
import { MeWorkbench } from "./me-workbench";

export const metadata: Metadata = {
  title: "我的 · SenseMu",
  description: "管理我的商品、订单、API 和用量。",
};

export default async function MePage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string }>;
}) {
  const { view } = await searchParams;
  return (
    <ProductShell active="me">
      <MeWorkbench initialView={view === "consumer" ? "consumer" : "producer"} />
    </ProductShell>
  );
}
