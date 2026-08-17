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

  test("算法市场筛选不会破坏商品发现", async ({ page }) => {
    await page.goto("/marketplace");
    await expect(page.getByRole("heading", { name: "算法市场" })).toBeVisible();
    await expect(page.getByRole("link", { name: "查看工地安全穿戴检测" })).toBeVisible();

    await page.getByPlaceholder("搜索算法或使用场景").fill("安全穿戴");
    await expect(page.getByRole("link", { name: "查看工地安全穿戴检测" })).toBeVisible();

    await page.getByPlaceholder("搜索算法或使用场景").fill("不存在的算法");
    await expect(page.getByText("没有找到符合条件的算法", { exact: true })).toBeVisible();
  });
});
