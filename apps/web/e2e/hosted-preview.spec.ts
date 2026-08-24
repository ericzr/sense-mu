import { expect, test } from "@playwright/test";

const ppeProject = "demo-project-ppe";
const ppeDataset = "demo-dataset-ppe";

test.describe("托管演示站", () => {
  test("数据、标注编辑与窄屏反馈保持可用", async ({ page }) => {
    await page.goto(`/studio/data?project=${ppeProject}&dataset=${ppeDataset}&view=annotation`);

    await expect(page.getByText("演示数据", { exact: true })).toBeVisible();
    await expect(page.getByText("需要登录", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "工地安全穿戴数据" })).toBeVisible();
    await expect(page.getByText("安全穿戴样本复核", { exact: true })).toBeVisible();

    await page.getByRole("link", { name: "检查" }).click();
    await expect(page.getByLabel("标注画布")).toBeVisible();
    await expect(page.getByRole("button", { name: "保存", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "保存", exact: true }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "当前为演示数据，新增与修改不会保存" }),
    ).toBeVisible();
  });

  test("训练报告和实时分析边界与演示数据一致", async ({ page }) => {
    await page.goto(`/studio/training?project=${ppeProject}`);
    await expect(page.getByRole("heading", { name: "训练任务" })).toBeVisible();
    await expect(page.getByText("模型对比", { exact: true })).toBeVisible();

    await page.goto(`/studio/training/runs/demo-run-ppe-v2?project=${ppeProject}`);
    await expect(page.getByText("训练曲线", { exact: true })).toBeVisible();
    await expect(page.getByLabel(/训练曲线/)).toBeVisible();

    await page.goto(`/services?project=${ppeProject}&view=live&deployment=demo-deployment-ppe`);
    await expect(page.getByRole("heading", { name: "实时分析" })).toBeVisible();
    await expect(page.getByRole("button", { name: /多模态大模型/ })).toBeDisabled();
    await expect(page.getByRole("button", { name: /实时视频流/ })).toBeDisabled();
  });

  test("展开侧栏时实时分析会在窄内容区收敛", async ({ page }) => {
    await page.setViewportSize({ width: 702, height: 900 });
    await page.goto(`/services?project=${ppeProject}&view=live&deployment=demo-deployment-ppe`);

    const analysis = page.locator("#live-analysis");
    await expect(analysis.getByRole("heading", { name: "实时分析" })).toBeVisible();
    await expect(analysis.locator(".inference-tester-heading")).toHaveCSS("flex-direction", "column");
    const optionColumns = await analysis.locator(".live-analysis-option-group > div").first().evaluate(
      (element) => getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length,
    );
    expect(optionColumns).toBe(1);
    await expect(analysis.getByRole("button", { name: /视觉小模型/ })).toBeVisible();
    await expect(analysis.getByRole("button", { name: /多模态大模型/ })).toBeVisible();
  });

  test("算法市场筛选不会破坏商品发现", async ({ page }) => {
    await page.goto("/marketplace");
    await expect(page.getByRole("heading", { name: "算法市场" })).toBeVisible();
    await expect(page.getByRole("link", { name: "查看工地安全穿戴检测" })).toBeVisible();

    await page.getByPlaceholder("搜索算法或使用场景").fill("安全穿戴");
    await expect(page.getByRole("link", { name: "查看工地安全穿戴检测" })).toBeVisible();

    await page.getByPlaceholder("搜索算法或使用场景").fill("林木健康");
    await expect(page.getByRole("link", { name: "查看林木健康巡检" })).toBeVisible();

    await page.getByPlaceholder("搜索算法或使用场景").fill("果园果实");
    await expect(page.getByRole("link", { name: "查看果园果实计数" })).toBeVisible();

    await page.getByPlaceholder("搜索算法或使用场景").fill("不存在的算法");
    await expect(page.getByText("没有找到符合条件的算法", { exact: true })).toBeVisible();
  });

  test("数据市场包含林业与农业数据集", async ({ page }) => {
    await page.goto("/data-market");
    await expect(page.getByRole("heading", { name: "数据市场" })).toBeVisible();
    await expect(page.getByRole("link", { name: "查看林区树木健康数据集" })).toBeVisible();

    await page.getByPlaceholder("搜索数据集或类别").fill("农产品分选");
    await expect(page.getByRole("link", { name: "查看农产品分选数据集" })).toBeVisible();

    await page.getByPlaceholder("搜索数据集或类别").fill("果园果实");
    await expect(page.getByRole("link", { name: "查看果园果实计数数据集" })).toBeVisible();
  });

  test("我的页面提供真实资产上架入口并保留演示写入边界", async ({ page }) => {
    await page.goto("/me?view=producer");
    await expect(page.getByRole("heading", { name: "上架", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "提交审核", exact: true }).click();
    await expect(page.getByRole("combobox", { name: "可上架能力" })).toBeVisible();
    await page.getByRole("button", { name: "关闭上架表单" }).click();

    await page.getByRole("button", { name: "创建数据卡", exact: true }).click();
    await expect(page.getByRole("combobox", { name: "可上架数据版本" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "我确认拥有发布及声明上述授权范围的权利" })).toBeVisible();
  });
});
