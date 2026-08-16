import type { Metadata } from "next";
import { ProductShell } from "../components/product-shell";
import { StudioOverview } from "./studio-overview";

export const metadata: Metadata = {
  title: "项目概览 · SenseMu",
  description: "SenseMu 视觉 AI 项目概览。",
};

export default function StudioPage() {
  return (
    <ProductShell active="studio">
      <StudioOverview />
    </ProductShell>
  );
}
