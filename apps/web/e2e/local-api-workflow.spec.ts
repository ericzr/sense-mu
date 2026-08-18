import { expect, test, type Page } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const sampleImagePath = fileURLToPath(
  new URL("../public/catalog-vision-samples.png", import.meta.url),
);
const coreApiUrl = `http://127.0.0.1:${process.env.SENSEMU_E2E_API_PORT ?? "8001"}/api/v1`;

type CoreRequestOptions = Parameters<Page["request"]["fetch"]>[1];
type WorkspaceRecord = { id: string };
type ProjectRecord = { id: string; name: string };
type RunRecord = { id: string; artifact_prefix: string | null };
type ModelVersionRecord = { id: string };
type DatasetRecord = { id: string };
type DatasetVersionRecord = { id: string };
type AssetRecord = { id: string };
type UploadIntent = { upload_url: string; object_key: string; headers: Record<string, string> };
type DeploymentRecord = { id: string; api_key_prefix: string | null; api_key?: string };

async function coreApi<T>(
  page: Page,
  path: string,
  options?: CoreRequestOptions,
): Promise<T> {
  const response = await page.request.fetch(`${coreApiUrl}${path}`, options);
  if (!response.ok()) {
    throw new Error(
      `Core API ${options?.method ?? "GET"} ${path} failed (${response.status()}): ${await response.text()}`,
    );
  }
  return response.json() as Promise<T>;
}

test("身份服务不可用时显示可恢复的会话状态", async ({ page }) => {
  await page.route("**/api/v1/identity/me", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "OIDC 身份验证尚未完成配置" }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("身份服务暂不可用", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "重新检查" })).toBeVisible();
});

test("工作台资源失败时保留明确状态而不误报为空", async ({ page }) => {
  await page.route("**/api/v1/workspaces", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "工作区服务暂不可用" }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("资源暂不可用", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "重新加载工作台资源" })).toBeVisible();
});

function sha256(payload: Buffer): string {
  return createHash("sha256").update(payload).digest("hex");
}

async function uploadToIntent(page: Page, intent: UploadIntent, payload: Buffer) {
  const response = await page.request.put(intent.upload_url, {
    headers: intent.headers,
    data: payload,
  });
  if (!response.ok()) {
    throw new Error(`本地对象上传失败 (${response.status()}): ${await response.text()}`);
  }
}

async function createAcceptanceDataset(
  page: Page,
  workspaceId: string,
  projectId: string,
  image: Buffer,
): Promise<DatasetVersionRecord> {
  const workspaceHeaders = { "X-Workspace-ID": workspaceId };
  const dataset = await coreApi<DatasetRecord>(page, `/projects/${projectId}/datasets`, {
    method: "POST",
    headers: workspaceHeaders,
    data: { name: "PPE E2E 独立验收集" },
  });

  for (const [split, suffix] of [["train", "acceptance-train"], ["valid", "acceptance-valid"]] as const) {
    const assetPayload = Buffer.concat([image, Buffer.from(suffix)]);
    const assetChecksum = sha256(assetPayload);
    const uploadIntent = await coreApi<UploadIntent>(page, `/datasets/${dataset.id}/uploads`, {
      method: "POST",
      headers: workspaceHeaders,
      data: {
        filename: `ppe-${split}.png`,
        content_type: "image/png",
        byte_size: assetPayload.length,
        checksum_sha256: assetChecksum,
      },
    });
    await uploadToIntent(page, uploadIntent, assetPayload);
    const asset = await coreApi<AssetRecord>(page, `/datasets/${dataset.id}/assets`, {
      method: "POST",
      headers: workspaceHeaders,
      data: {
        object_key: uploadIntent.object_key,
        media_type: "image/png",
        checksum_sha256: assetChecksum,
        byte_size: assetPayload.length,
        width: 640,
        height: 480,
      },
    });
    await coreApi<AssetRecord>(page, `/datasets/${dataset.id}/items/${asset.id}`, {
      method: "PATCH",
      headers: workspaceHeaders,
      data: { split },
    });

    const annotationPayload = Buffer.from("0 0.5 0.5 0.25 0.25\n");
    const annotationChecksum = sha256(annotationPayload);
    const annotationIntent = await coreApi<UploadIntent>(
      page,
      `/datasets/${dataset.id}/items/${asset.id}/annotation-uploads`,
      {
        method: "POST",
        headers: workspaceHeaders,
        data: {
          filename: `ppe-${split}.txt`,
          byte_size: annotationPayload.length,
          checksum_sha256: annotationChecksum,
        },
      },
    );
    await uploadToIntent(page, annotationIntent, annotationPayload);
    await coreApi<AssetRecord>(page, `/datasets/${dataset.id}/items/${asset.id}/annotation`, {
      method: "POST",
      headers: workspaceHeaders,
      data: {
        object_key: annotationIntent.object_key,
        byte_size: annotationPayload.length,
        checksum_sha256: annotationChecksum,
      },
    });
  }

  return coreApi<DatasetVersionRecord>(page, `/datasets/${dataset.id}/versions:freeze`, {
    method: "POST",
    headers: workspaceHeaders,
    data: { class_map: { 0: "目标" } },
  });
}

async function completeTrainingRun(
  page: Page,
  workspaceId: string,
  run: RunRecord,
): Promise<ModelVersionRecord> {
  if (!run.artifact_prefix) throw new Error("训练任务缺少产物路径");
  const headers = {
    "X-Workspace-ID": workspaceId,
    "X-SenseMu-Worker-Token": "sensemu-worker-local-only",
  };
  const attemptId = randomUUID();
  const occurredAt = new Date().toISOString();
  await coreApi(page, `/internal/training-runs/${run.id}/execution:claim`, {
    method: "POST",
    headers,
    data: { attempt_id: attemptId, worker_id: "local-e2e-worker" },
  });
  await coreApi(page, `/internal/training-runs/${run.id}/events`, {
    method: "POST",
    headers,
    data: {
      attempt_id: attemptId,
      event_id: randomUUID(),
      event_type: "job.started",
      occurred_at: occurredAt,
    },
  });
  return coreApi<ModelVersionRecord>(page, `/internal/training-runs/${run.id}/complete`, {
    method: "POST",
    headers,
    data: {
      attempt_id: attemptId,
      event_id: randomUUID(),
      model_name: "PPE E2E 模型",
      artifact_uri: `local://${run.artifact_prefix}/model/best.pt`,
      metrics: { "metrics/mAP50(B)": 0.91 },
      occurred_at: occurredAt,
    },
  });
}

async function completeAcceptanceRun(page: Page, workspaceId: string, run: RunRecord) {
  const headers = {
    "X-Workspace-ID": workspaceId,
    "X-SenseMu-Worker-Token": "sensemu-worker-local-only",
  };
  const attemptId = randomUUID();
  const occurredAt = new Date().toISOString();
  await coreApi(page, `/internal/training-runs/${run.id}/execution:claim`, {
    method: "POST",
    headers,
    data: { attempt_id: attemptId, worker_id: "local-e2e-worker" },
  });
  await coreApi(page, `/internal/training-runs/${run.id}/events`, {
    method: "POST",
    headers,
    data: {
      attempt_id: attemptId,
      event_id: randomUUID(),
      event_type: "job.started",
      occurred_at: occurredAt,
    },
  });
  await coreApi(page, `/internal/acceptance-runs/${run.id}/complete`, {
    method: "POST",
    headers,
    data: {
      attempt_id: attemptId,
      event_id: randomUUID(),
      metrics: { "metrics/mAP50(B)": 0.9 },
      evaluated_asset_count: 2,
      runtime_image: "ultralytics@sha256:local-e2e",
      occurred_at: occurredAt,
    },
  });
}

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

test("真实数据写入可完成标注、训练、独立验收与安全发布", async ({ page }) => {
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

  const [workspace] = await coreApi<WorkspaceRecord[]>(page, "/workspaces");
  const projects = await coreApi<ProjectRecord[]>(page, "/projects", {
    headers: { "X-Workspace-ID": workspace.id },
  });
  const project = projects.find((item) => item.name === "PPE E2E 项目");
  if (!project) throw new Error("未找到 E2E 项目");
  const [trainingRun] = await coreApi<RunRecord[]>(
    page,
    `/projects/${project.id}/training-runs`,
    { headers: { "X-Workspace-ID": workspace.id } },
  );
  if (!trainingRun) throw new Error("未找到 E2E 训练任务");

  await page.goto(`/services?project=${project.id}&view=publish`);
  await page.getByRole("button", { name: "设置发布检查" }).click();
  await page.getByLabel("检查名称").fill("PPE E2E 发布检查");
  await page.getByLabel("最低要求").fill("0.8");
  await page.getByRole("button", { name: "启用" }).click();
  await expect(page.getByRole("status")).toContainText("发布检查 v1 已启用");

  const modelVersion = await completeTrainingRun(page, workspace.id, trainingRun);
  const acceptanceDatasetVersion = await createAcceptanceDataset(
    page,
    workspace.id,
    project.id,
    image,
  );
  const acceptanceRun = await coreApi<RunRecord>(
    page,
    `/projects/${project.id}/model-versions/${modelVersion.id}/acceptance-runs`,
    {
      method: "POST",
      headers: {
        "X-Workspace-ID": workspace.id,
        "Idempotency-Key": `acceptance-${randomUUID()}`,
      },
      data: { dataset_version_id: acceptanceDatasetVersion.id },
    },
  );
  await completeAcceptanceRun(page, workspace.id, acceptanceRun);

  await page.reload();
  await expect(page.getByRole("heading", { name: "发布服务" })).toBeVisible();
  await page.getByLabel("服务名称").fill("PPE E2E 在线服务");
  await page.getByLabel("服务地址").fill("ppe-e2e-service");
  await page.getByRole("button", { name: "发布服务" }).click();
  await expect(page.getByRole("status")).toContainText("服务已发布，请立即保存首次显示的 API 密钥");

  const secretPanel = page.locator(".deployment-secret");
  await expect(secretPanel).toBeVisible();
  const originalApiKey = await secretPanel.locator("code").innerText();
  expect(originalApiKey).toMatch(/^smu_live_/);
  await page.getByRole("button", { name: "我已保存" }).click();
  await expect(secretPanel).toBeHidden();

  await page.reload();
  await expect(page.getByRole("heading", { name: "保存 API 密钥" })).toBeHidden();
  await expect(page.locator(".deployment-row").filter({ hasText: "PPE E2E 在线服务" })).toBeVisible();
  const [deployment] = await coreApi<DeploymentRecord[]>(
    page,
    `/projects/${project.id}/deployments`,
    { headers: { "X-Workspace-ID": workspace.id } },
  );
  expect(deployment).toBeDefined();
  expect(deployment.api_key_prefix).toBeTruthy();
  expect(deployment).not.toHaveProperty("api_key");

  await page.getByTitle("轮换 API 密钥").click();
  await expect(secretPanel).toBeVisible();
  const rotatedApiKey = await secretPanel.locator("code").innerText();
  expect(rotatedApiKey).toMatch(/^smu_live_/);
  expect(rotatedApiKey).not.toBe(originalApiKey);
});

test("刷新失败时保留已加载的工作台资源快照", async ({ page }) => {
  const suffix = randomUUID().slice(0, 8);
  const [workspace] = await coreApi<WorkspaceRecord[]>(page, "/workspaces");
  if (!workspace) throw new Error("未找到默认工作区");
  const project = await coreApi<ProjectRecord>(page, "/projects", {
    method: "POST",
    headers: { "X-Workspace-ID": workspace.id },
    data: {
      slug: `resource-snapshot-project-${suffix}`,
      name: "资源快照项目",
      task_type: "object-detection",
    },
  });

  await page.goto("/studio");
  const projectResource = page.getByTitle(project.name);
  await expect(projectResource).toBeVisible();

  await page.route("**/api/v1/workspaces", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "工作区服务暂不可用" }),
    });
  });
  await page.getByRole("button", { name: "刷新工作台资源" }).click();

  await expect(page.getByText("资源暂不可用", { exact: true })).toBeVisible();
  await expect(projectResource).toBeVisible();
});

test("权限拒绝时清除已加载的工作台资源快照", async ({ page }) => {
  const suffix = randomUUID().slice(0, 8);
  const [workspace] = await coreApi<WorkspaceRecord[]>(page, "/workspaces");
  if (!workspace) throw new Error("未找到默认工作区");
  const project = await coreApi<ProjectRecord>(page, "/projects", {
    method: "POST",
    headers: { "X-Workspace-ID": workspace.id },
    data: {
      slug: `resource-permission-${suffix}`,
      name: "权限边界项目",
      task_type: "object-detection",
    },
  });

  await page.goto("/studio");
  const projectResource = page.getByTitle(project.name);
  await expect(projectResource).toBeVisible();

  await page.route("**/api/v1/workspaces", async (route) => {
    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({ detail: "当前账号已不再拥有该工作区的访问权限" }),
    });
  });
  await page.getByRole("button", { name: "刷新工作台资源" }).click();

  await expect(page.getByText("工作台访问权限已变更", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "重新检查工作台权限" })).toBeVisible();
  await expect(projectResource).toBeHidden();
});

test("新的刷新请求不会被旧响应覆盖", async ({ page }) => {
  const suffix = randomUUID().slice(0, 8);
  const [workspace] = await coreApi<WorkspaceRecord[]>(page, "/workspaces");
  if (!workspace) throw new Error("未找到默认工作区");
  const project = await coreApi<ProjectRecord>(page, "/projects", {
    method: "POST",
    headers: { "X-Workspace-ID": workspace.id },
    data: {
      slug: `resource-race-${suffix}`,
      name: "刷新竞态项目",
      task_type: "object-detection",
    },
  });

  await page.goto("/studio");
  const projectResource = page.getByTitle(project.name);
  await expect(projectResource).toBeVisible();

  let firstRequest = true;
  let releaseFirstRequest!: () => void;
  let notifyFirstRequestStarted!: () => void;
  const firstRequestStarted = new Promise<void>((resolve) => {
    notifyFirstRequestStarted = resolve;
  });
  const firstRequestReleased = new Promise<void>((resolve) => {
    releaseFirstRequest = resolve;
  });
  await page.route("**/api/v1/workspaces", async (route) => {
    if (!firstRequest) {
      await route.continue();
      return;
    }
    firstRequest = false;
    notifyFirstRequestStarted();
    await firstRequestReleased;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "工作区服务暂不可用" }),
    });
  });

  await page.getByRole("button", { name: "刷新工作台资源" }).click();
  await firstRequestStarted;
  const secondResponse = page.waitForResponse((response) => (
    response.url().includes("/api/v1/workspaces") && response.ok()
  ));
  await page.getByRole("button", { name: "刷新工作台资源" }).click();
  await secondResponse;
  await expect(projectResource).toBeVisible();

  const staleFailureResponse = page.waitForResponse((response) => (
    response.url().includes("/api/v1/workspaces") && response.status() === 503
  ));
  releaseFirstRequest();
  await staleFailureResponse;
  await expect(page.getByText("资源暂不可用", { exact: true })).toBeHidden();
  await expect(projectResource).toBeVisible();
});

test("工作台资源服务恢复后可重新加载", async ({ page }) => {
  const suffix = randomUUID().slice(0, 8);
  const [workspace] = await coreApi<WorkspaceRecord[]>(page, "/workspaces");
  if (!workspace) throw new Error("未找到默认工作区");
  const project = await coreApi<ProjectRecord>(page, "/projects", {
    method: "POST",
    headers: { "X-Workspace-ID": workspace.id },
    data: {
      slug: `resource-recovery-${suffix}`,
      name: "服务恢复项目",
      task_type: "object-detection",
    },
  });

  let firstRequest = true;
  await page.route("**/api/v1/workspaces", async (route) => {
    if (!firstRequest) {
      await route.continue();
      return;
    }
    firstRequest = false;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "工作区服务暂不可用" }),
    });
  });

  await page.goto("/");
  const projectResource = page.getByTitle(project.name);
  await expect(page.getByText("资源暂不可用", { exact: true })).toBeVisible();
  await expect(projectResource).toBeHidden();

  await page.getByRole("button", { name: "重新加载工作台资源" }).click();
  await expect(page.getByText("资源暂不可用", { exact: true })).toBeHidden();

  await page.getByRole("button", { name: /^训练/ }).click();
  await expect(projectResource).toBeVisible();
});
