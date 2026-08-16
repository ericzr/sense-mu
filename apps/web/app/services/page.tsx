import type { Metadata } from "next";
import { ProductShell } from "../components/product-shell";
import { ServicesWorkbench } from "./services-workbench";

export const metadata: Metadata = {
  title: "发布与调用 · SenseMu",
  description: "将通过检查的模型发布为在线服务并管理调用。",
};

export default function ServicesPage() {
  return (
    <ProductShell active="studio">
      <ServicesWorkbench />
    </ProductShell>
  );
}
