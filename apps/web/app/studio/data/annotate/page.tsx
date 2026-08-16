import type { Metadata } from "next";
import { ProductShell } from "../../../components/product-shell";
import { AnnotationEditor } from "./annotation-editor";

export const metadata: Metadata = {
  title: "数据标注 · SenseMu",
  description: "手动标注、智能预标注与结果检查。",
};

export default function AnnotationPage() {
  return (
    <ProductShell active="studio">
      <AnnotationEditor />
    </ProductShell>
  );
}
