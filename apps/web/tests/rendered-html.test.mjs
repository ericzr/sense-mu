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

test("server-renders the SenseMu product shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.equal(response.headers.get("cache-control"), "no-store, no-cache, must-revalidate");
  assert.match(response.headers.get("x-sensemu-release") ?? "", /^(?:[0-9a-f]{7,12}|unknown)$/);

  const html = await response.text();
  assert.match(html, /<title>SenseMu · 视觉 AI 工作平台<\/title>/i);
  assert.match(html, /<h1>工作台<\/h1>/);
  assert.match(html, /新建项目/);
  assert.match(html, /训练项目/);
  assert.match(html, /最近活动/);
  assert.match(html, /算法市场/);
  assert.match(html, /数据市场/);
  assert.match(html, /我的/);
  assert.match(html, /aria-label="主导航"/);
  assert.doesNotMatch(html, /navigation-label[^>]*>工作</);
  assert.match(html, /workbench-home-link[^>]*>.*概览/s);
  assert.match(html, /navigation-label[^>]*>市场</);
  assert.match(html, /navigation-label[^>]*>账户</);
  assert.match(html, /aria-label="工作台对象"/);
  assert.match(html, /数据与标注/);
  assert.match(html, /aria-label="新建数据集"/);
  assert.match(html, /aria-label="新建项目"/);
  assert.match(html, /aria-label="工作台快捷入口"/);
  assert.match(html, /aria-label="收起侧栏"/);
  assert.match(html, /aria-label="打开主菜单"/);
  assert.match(html, /aria-label="关闭主菜单"/);
  assert.match(html, /src="\/sensemu-logo-wide\.svg"/);
  assert.match(html, /src="\/sensemu-logo-mark\.svg"/);
  assert.match(html, /role="slider"[^>]*aria-label="调整侧栏宽度"/);
  assert.match(html, /sensemu-sidebar-width/);
  assert.doesNotMatch(html, /workspace-switcher/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/);
});

test("health endpoint identifies the exact build release", async () => {
  const response = await render("/__sensemu/health");
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");

  const health = await response.json();
  assert.equal(health.status, "ok");
  assert.match(health.release, /^(?:[0-9a-f]{7,12}|unknown)$/);
  assert.notEqual(health.release, "aa0136f");
});

test("server-renders the Studio project route", async () => {
  const response = await render("/studio");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>项目概览 · SenseMu<\/title>/i);
  assert.match(html, /正在读取项目状态/);
  assert.doesNotMatch(html, /当前闭环|可复现配置|生产门禁|可信提示/);
  assert.match(html, /workbench-home-link/);
  assert.match(html, /项目详情/);
  assert.doesNotMatch(html, /PROJECT PIPELINE|QUALITY SIGNAL|DATASET VERSION|TRAINING RECIPE/);
});

test("server-renders the data workbench route", async () => {
  const response = await render("/studio/data");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>数据与标注 · SenseMu<\/title>/i);
  assert.match(html, /数据与标注/);
  assert.match(html, /正在读取工作区/);
  assert.doesNotMatch(html, /aria-label="项目导航"/);
});

test("server-renders the annotation editor route", async () => {
  const response = await render("/studio/data/annotate?task=ppe-video-gate-a");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>数据标注 · SenseMu<\/title>/i);
  assert.match(html, /返回标注任务/);
  assert.match(html, /正在读取任务/);
  assert.doesNotMatch(html, /先试跑 8 张/);
});

test("server-renders the training workbench route", async () => {
  const response = await render("/studio/training");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>训练任务 · SenseMu<\/title>/i);
  assert.doesNotMatch(html, /aria-label="项目导航"/);
  assert.match(html, /正在读取数据版本与训练状态/);
});

test("server-renders a standalone training run detail route", async () => {
  const response = await render("/studio/training/runs/mock-run-id");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>训练任务详情 · SenseMu<\/title>/i);
  assert.match(html, /正在读取详情/);
});

test("server-renders a standalone model detail route", async () => {
  const response = await render("/studio/training/models/mock-model-id");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>模型详情 · SenseMu<\/title>/i);
  assert.match(html, /正在读取详情/);
});

test("server-renders the project publishing and inference route", async () => {
  const response = await render("/services");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>发布与调用 · SenseMu<\/title>/i);
  assert.match(html, /正在读取发布条件/);
  assert.match(html, /发布控制面/);
});

test("server-renders the algorithm marketplace route", async () => {
  const response = await render("/marketplace");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>算法市场 · SenseMu<\/title>/i);
  assert.match(html, /搜索算法或使用场景/);
  assert.match(html, /工地安全穿戴检测/);
  assert.match(html, /林木健康巡检/);
  assert.match(html, /森林烟火早期识别/);
  assert.match(html, /农产品分选识别/);
  assert.match(html, /果园果实计数/);
  assert.match(html, /蜂箱巡检与计数/);
  assert.match(html, /href="\/marketplace\/mock-alg-ppe"/);
  assert.match(html, /href="\/marketplace\/mock-alg-forest-health"/);
  assert.match(html, /href="\/marketplace\/mock-alg-produce-sort"/);
  assert.match(html, /catalog-preview-media scene-ppe/);
  assert.match(html, /精确率/);
  assert.match(html, /YOLO26s/);
  assert.match(html, /全部场景/);
  assert.match(html, /aria-label="工作台对象"/);
  assert.match(html, /数据与标注/);
  assert.match(html, /训练/);
  assert.match(html, /发布/);
  assert.match(html, /aria-label="工作台快捷入口"/);
  assert.doesNotMatch(html, /storefront-detail/);
  assert.match(html, /href="\/marketplace"[^>]*aria-current="page"/);
});

test("server-renders a standalone algorithm detail route", async () => {
  const response = await render("/marketplace/mock-alg-ppe");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>算法详情 · SenseMu<\/title>/i);
  assert.match(html, /工地安全穿戴检测/);
  assert.match(html, /效果与规格/);
  assert.match(html, /在线体验/);
  assert.match(html, /运行识别/);
  assert.match(html, /上传图片/);
  assert.match(html, /置信度/);
  assert.match(html, /适用边界/);
  assert.match(html, /接入方式/);
  assert.match(html, /先创建工作区/);
  assert.doesNotMatch(html, /catalog-preview is-large/);
});

test("server-renders a forestry algorithm detail route", async () => {
  const response = await render("/marketplace/mock-alg-forest-health");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>算法详情 · SenseMu<\/title>/i);
  assert.match(html, /林木健康巡检/);
  assert.match(html, /疑似枯死树/);
  assert.match(html, /林区航拍/);
  assert.match(html, /catalog-forest\.jpg/);
});

test("server-renders the workspace settings route", async () => {
  const response = await render("/settings");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>工作区设置 · SenseMu<\/title>/i);
  assert.match(html, /成员与权限/);
  assert.match(html, /正在读取成员与权限记录/);
  assert.match(html, /href="\/me"[^>]*aria-current="page"/);
});

test("server-renders the trusted data marketplace route", async () => {
  const response = await render("/data-market");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>数据市场 · SenseMu<\/title>/i);
  assert.match(html, /搜索数据集或类别/);
  assert.match(html, /工地安全穿戴数据集/);
  assert.match(html, /林区树木健康数据集/);
  assert.match(html, /农产品分选数据集/);
  assert.match(html, /果园果实计数数据集/);
  assert.match(html, /蜂场巡检数据集/);
  assert.match(html, /href="\/data-market\/mock-data-ppe"/);
  assert.match(html, /href="\/data-market\/mock-data-forest-health"/);
  assert.match(html, /href="\/data-market\/mock-data-produce"/);
  assert.match(html, /catalog-preview-media scene-ppe/);
  assert.match(html, /标注实例/);
  assert.match(html, /标注覆盖/);
  assert.match(html, /全部筛选/);
  assert.doesNotMatch(html, /storefront-detail/);
  assert.match(html, /href="\/data-market"[^>]*aria-current="page"/);
});

test("server-renders a standalone data detail route", async () => {
  const response = await render("/data-market/mock-data-ppe");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>数据集详情 · SenseMu<\/title>/i);
  assert.match(html, /工地安全穿戴数据集/);
  assert.match(html, /数据概览/);
  assert.match(html, /已标注图片/);
  assert.match(html, /标注实例/);
  assert.match(html, /类别分布/);
  assert.match(html, /来源与质量/);
  assert.match(html, /购买即将开放/);
  assert.doesNotMatch(html, /catalog-preview is-large/);
});

test("server-renders a forestry data detail route", async () => {
  const response = await render("/data-market/mock-data-forest-health");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>数据集详情 · SenseMu<\/title>/i);
  assert.match(html, /林区树木健康数据集/);
  assert.match(html, /疑似枯死树/);
  assert.match(html, /林区航拍/);
});

test("redirects the old provider route into My", async () => {
  const response = await render("/providers");
  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"), "/me?view=producer");
});

test("server-renders My with selling and buying views", async () => {
  const response = await render("/me");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<title>我的 · SenseMu<\/title>/i);
  assert.match(html, /创作与销售/);
  assert.match(html, /购买与使用/);
  assert.match(html, /正在加载/);
  assert.match(html, /href="\/me"[^>]*aria-current="page"/);
});
