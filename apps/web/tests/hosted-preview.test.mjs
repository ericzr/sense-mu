import assert from "node:assert/strict";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders a consistent hosted demo overview", async () => {
  const response = await render();
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<html[^>]*data-sensemu-preview="true"/);
  assert.match(html, /<h1>工作台<\/h1>/);
  assert.match(html, /工地安全穿戴数据/);
  assert.match(html, /12 个素材/);
  assert.match(html, /金属表面缺陷数据/);
  assert.match(html, /8 个素材/);
  assert.match(html, /3 个版本/);
  assert.doesNotMatch(html, /1,248 个素材|594 个素材/);
});

test("hosted preview keeps the algorithm catalog and demo detail available", async () => {
  const catalogResponse = await render("/marketplace");
  assert.equal(catalogResponse.status, 200);
  const catalogHtml = await catalogResponse.text();
  assert.match(catalogHtml, /工地安全穿戴检测/);
  assert.match(catalogHtml, /林木健康巡检/);
  assert.match(catalogHtml, /路面病害识别/);
  assert.match(catalogHtml, /桥梁设施病害识别/);
  assert.match(catalogHtml, /违法建设识别/);
  assert.match(catalogHtml, /园林绿化问题识别/);
  assert.match(catalogHtml, /href="\/marketplace\/mock-alg-ppe"/);

  const detailResponse = await render("/marketplace/mock-alg-ppe");
  assert.equal(detailResponse.status, 200);
  const detailHtml = await detailResponse.text();
  assert.match(detailHtml, /工地安全穿戴检测/);
  assert.match(detailHtml, /在线体验/);
  assert.match(detailHtml, /适用边界/);
});

test("hosted preview exposes road and urban algorithm details", async () => {
  const roadResponse = await render("/marketplace/mock-alg-road-surface");
  assert.equal(roadResponse.status, 200);
  const roadHtml = await roadResponse.text();
  assert.match(roadHtml, /路面病害识别/);
  assert.match(roadHtml, /横向裂缝/);
  assert.match(roadHtml, /待真实服务/);

  const urbanResponse = await render("/marketplace/mock-alg-urban-illegal");
  assert.equal(urbanResponse.status, 200);
  const urbanHtml = await urbanResponse.text();
  assert.match(urbanHtml, /违法建设识别/);
  assert.match(urbanHtml, /楼顶新增搭建/);
  assert.match(urbanHtml, /适用边界/);
});

test("hosted preview keeps the data catalog and demo detail available", async () => {
  const catalogResponse = await render("/data-market");
  assert.equal(catalogResponse.status, 200);
  const catalogHtml = await catalogResponse.text();
  assert.match(catalogHtml, /工地安全穿戴数据集/);
  assert.match(catalogHtml, /林区树木健康数据集/);
  assert.match(catalogHtml, /路面病害识别数据集/);
  assert.match(catalogHtml, /交安设施识别数据集/);
  assert.match(catalogHtml, /隧道设施异常数据集/);
  assert.match(catalogHtml, /桥梁设施病害数据集/);
  assert.match(catalogHtml, /违法建设识别数据集/);
  assert.match(catalogHtml, /市容环境问题数据集/);
  assert.match(catalogHtml, /火情与安全隐患数据集/);
  assert.match(catalogHtml, /园林绿化问题数据集/);
  assert.match(catalogHtml, /href="\/data-market\/mock-data-ppe"/);

  const detailResponse = await render("/data-market/mock-data-ppe");
  assert.equal(detailResponse.status, 200);
  const detailHtml = await detailResponse.text();
  assert.match(detailHtml, /工地安全穿戴数据集/);
  assert.match(detailHtml, /数据概览/);
  assert.match(detailHtml, /来源与质量/);
});

test("hosted preview exposes road engineering dataset details", async () => {
  const detailResponse = await render("/data-market/mock-data-road-surface");
  assert.equal(detailResponse.status, 200);
  const detailHtml = await detailResponse.text();
  assert.match(detailHtml, /路面病害识别数据集/);
  assert.match(detailHtml, /横向裂缝/);
  assert.match(detailHtml, /修补不良/);

  const bridgeResponse = await render("/data-market/mock-data-bridge");
  assert.equal(bridgeResponse.status, 200);
  const bridgeHtml = await bridgeResponse.text();
  assert.match(bridgeHtml, /桥梁设施病害数据集/);
  assert.match(bridgeHtml, /伸缩缝错位/);
  assert.match(bridgeHtml, /支座脱空/);
});

test("hosted preview exposes urban governance dataset details", async () => {
  const detailResponse = await render("/data-market/mock-data-urban-illegal");
  assert.equal(detailResponse.status, 200);
  const detailHtml = await detailResponse.text();
  assert.match(detailHtml, /违法建设识别数据集/);
  assert.match(detailHtml, /楼顶新增搭建/);
  assert.match(detailHtml, /疑似违建围挡/);

  const waterResponse = await render("/data-market/mock-data-urban-water");
  assert.equal(waterResponse.status, 200);
  const waterHtml = await waterResponse.text();
  assert.match(waterHtml, /河道与水域污染数据集/);
  assert.match(waterHtml, /污水直排/);
  assert.match(waterHtml, /禁钓区垂钓/);
});
