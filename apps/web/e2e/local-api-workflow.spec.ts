import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const sampleImagePath = fileURLToPath(
  new URL("../public/catalog-vision-samples.png", import.meta.url),
);

async function drawBox(page: Page) {
  await page.getByRole("button", { name: "矩形框", exact: true }).click();
  const layer = page.getByLabel(/添加「目标」矩形框/);
  const bounds = await layer.boundingBox();
  if (!bounds) throw new Error("标注画布不可用");
  await page.mouse.move(bounds.x + bounds.width * 0.32, bounds.y + bounds.height * 0.3);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width * 0.58, bounds.y + bounds.height * 0.7, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole("button", { name: "目标标注" })).toBeVisible();
}

test("真实数据写入可完成标注、冻结和训练提交", async ({ page }) => {
  await page.goto("/studio/data?createProject=1");

  await expect(page.getByRole("heading", { name: "创建第一个工作区" })).toBeVisible();
  await page.getByLabel("工作区名称").fill("SenseMu E2E");
  await page.getByRole("button", { name: "创建并继续" }).click();

  await expect(page.getByRole("heading", { name: "创建视觉项目" })).toBeVisible();
  await page.getByLabel("项目名称").fill("PPE E2E 项目");
  await page.getByRole("button", { name: "创建并继续" }).click();

  await expect(page.getByRole("heading", { name: "创建数据集" })).toBeVisible();
  await page.getByLabel("数据集名称").fill("PPE E2E 数据集");
  await page.getByRole("button", { name: "创建并继续" }).click();
  await expect(page.getByRole("heading", { name: "PPE E2E 数据集" })).toBeVisible();

  const image = await readFile(sampleImagePath);
  await page.locator('input[type="file"][accept*="image/jpeg"]').setInputFiles([
    { name: "train.png", mimeType: "image/png", buffer: image },
    { name: "valid.png", mimeType: "image/png", buffer: Buffer.concat([image, Buffer.from("valid")]) },
  ]);
  await expect(page.getByRole("status")).toContainText("2 个资产已导入");

  const splitSelectors = page.getByRole("combobox", { name: "数据划分" });
  await expect(splitSelectors).toHaveCount(2);
  await splitSelectors.nth(0).selectOption("train");
  await expect(page.getByRole("status")).toContainText("已设为训练集");
  await splitSelectors.nth(1).selectOption("valid");
  await expect(page.getByRole("status")).toContainText("已设为验证集");

  await page.getByRole("button", { name: /类别与统计/ }).click();
  await page.getByPlaceholder("安全帽\n反光衣").fill("目标");
  await page.getByRole("button", { name: "保存类别" }).click();
  await expect(page.getByRole("status")).toContainText("类别定义已保存");

  await page.getByRole("button", { name: /标注任务/ }).click();
  await page.getByRole("button", { name: "新建任务" }).click();
  const taskDialog = page.getByRole("dialog", { name: "新建标注任务" });
  await taskDialog.getByLabel("任务名称").fill("PPE E2E 标注");
  await taskDialog.getByLabel("素材范围").selectOption("all");
  await taskDialog.getByRole("button", { name: "创建任务" }).click();
  await expect(page.getByRole("status")).toContainText("手动标注任务已创建");

  await page.getByRole("link", { name: "继续" }).click();
  await expect(page.getByLabel("标注画布")).toBeVisible();
  await expect(page.getByAltText("当前素材")).toBeVisible();

  await drawBox(page);
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator(".editor-history-actions span")).toHaveText("已保存当前标注");

  const firstImageSource = await page.getByAltText("当前素材").getAttribute("src");
  await page.getByRole("button", { name: "下一张" }).click();
  await expect.poll(() => page.getByAltText("当前素材").getAttribute("src")).not.toBe(firstImageSource);
  await drawBox(page);
  await page.getByRole("button", { name: "提交检查" }).click();
  await expect(page.getByRole("button", { name: "完成检查" })).toBeVisible();
  await page.getByRole("button", { name: "完成检查" }).click();
  await expect(page.getByRole("button", { name: "已完成" })).toBeVisible();

  await page.getByRole("link", { name: "返回标注任务" }).click();
  const freezeButton = page.getByRole("button", { name: "冻结新版本" });
  await expect(freezeButton).toBeEnabled();
  await freezeButton.click();
  await expect(page.getByRole("status")).toContainText("ds_v1 已冻结");

  await page.getByRole("link", { name: /开始训练/ }).click();
  await expect(page.getByRole("heading", { name: "新建训练" })).toBeVisible();
  await page.getByRole("button", { name: "提交训练" }).click();
  await expect(page.getByRole("status")).toContainText("训练任务已进入队列");
  await expect(page.getByText("排队中", { exact: true })).toBeVisible();
});
