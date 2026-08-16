import type { Metadata } from "next";
import { ProductShell } from "../components/product-shell";
import { WorkspaceSettings } from "./workspace-settings";

export const metadata: Metadata = {
  title: "工作区设置 · SenseMu",
  description: "管理工作区成员、邀请与权限审计。",
};

export default function SettingsPage() {
  return (
    <ProductShell active="settings">
      <WorkspaceSettings />
    </ProductShell>
  );
}
