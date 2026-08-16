import { getOverview } from "../lib/api";
import { ProductShell } from "./components/product-shell";
import { WorkbenchOverview } from "./workbench-overview";

export default async function Home() {
  const overview = await getOverview();

  return (
    <ProductShell active="overview">
      <main className="product-page workbench-page">
        <WorkbenchOverview initialOverview={overview} />
      </main>
    </ProductShell>
  );
}
