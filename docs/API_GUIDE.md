# SenseMu 后端接口指南

- 更新日期：2026-08-25
- Core API 版本：`0.1.0`
- 基础前缀：`/api/v1`

本文是给后端开发同事的接口地图，强调调用方、授权方式和业务顺序。首次接入请先阅读 `docs/DEVELOPER_HANDOFF.md` 的正式地址、架构边界和 P0/P1 优先级。字段级请求/响应以运行中的 OpenAPI 为唯一准确信源：

- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`
- OpenAPI JSON：`http://localhost:8000/openapi.json`
- 仓库快照：`apps/api/openapi.json`，由 `make api-openapi` 从 FastAPI 应用生成，`make api-openapi-check` 用于 CI 漂移检查
- 前端生成类型：`apps/web/lib/generated/core-api.ts`；请求封装仍位于 `apps/web/lib/catalog-api.ts`

## 1. 本地服务地址

| 服务 | 地址 | 调用方 |
|---|---|---|
| Core API | `http://localhost:8000` | Web、Worker、推理网关、支付/审核适配器 |
| Inference Gateway | `http://localhost:8080` | Web 和算法 API 客户 |
| Inference Runtime | `http://localhost:8090` | 仅推理网关和受信任务 |

开发时执行：

```bash
make local-api
make web-dev
```

需要异步训练或抽帧时再启动 Redis、Worker 和相应运行时。完整命令见根目录 `README.md`。

## 2. 鉴权与通用请求头

### 2.1 浏览器到 Core API

| 请求头 | 是否必需 | 说明 |
|---|---|---|
| `Authorization: Bearer <OIDC JWT>` | 生产必需 | 确认用户身份；开发模式允许省略 |
| `X-Workspace-ID: <uuid>` | 大多数工作区接口必需 | 选择租户，服务端仍会复核成员关系 |
| `Idempotency-Key: <8-120 chars>` | 创建训练、验收、批处理等操作必需 | 重试时复用同一个值 |
| `Content-Type: application/json` | 有 JSON body 时必需 | 上传文件使用预签名或本地上传地址，不走大 JSON |

角色规则：`GET/HEAD/OPTIONS` 至少 viewer，普通写操作至少 member，发布、购买、密钥轮换和供应方资料通常至少 admin。owner 另外负责管理员角色。

浏览器跨域访问只允许配置的 `SENSEMU_WEB_ORIGIN`，预检支持当前接口实际使用的 `GET / POST / PUT / PATCH / DELETE / OPTIONS`。新增方法或请求头时必须同步更新 CORS 配置和回归测试。

Web 端的正式身份接入必须由 OIDC 授权码 + PKCE 和服务端 BFF（或等价的受信令牌交换层）完成。浏览器只携带短期 access token；refresh token、client secret 和 token 交换逻辑不得进入 Web bundle，也不得放入 `localStorage` 或 `sessionStorage`。当前 Web 客户端已经统一注入内存中的短期 token，并将 `401` 标记为会话失效、`403` 标记为权限不足、`5xx` 标记为服务不可用；在没有真实身份提供方配置时，工作台会显示明确的配置提示，不会伪造登录成功。

Web 配置契约（`apps/web/.env.example`）：

| 变量 | 作用 |
|---|---|
| `NEXT_PUBLIC_SENSEMU_AUTH_MODE` | `development` 或 `oidc`；生产必须是 `oidc` |
| `NEXT_PUBLIC_SENSEMU_OIDC_AUTHORIZATION_ENDPOINT` | OIDC 授权端点，只允许 HTTPS（本地可用 localhost） |
| `NEXT_PUBLIC_SENSEMU_OIDC_CLIENT_ID` | Web 公共客户端 ID，不是 client secret |
| `NEXT_PUBLIC_SENSEMU_OIDC_REDIRECT_URI` | 授权回调地址，必须预先在身份提供方登记 |
| `NEXT_PUBLIC_SENSEMU_AUTH_LOGIN_URL` | BFF 登录入口；建议使用同源 `/auth/login`，由 BFF 负责 PKCE、回调、会话 cookie 和跳回原页面 |
| `NEXT_PUBLIC_SENSEMU_OIDC_SCOPE` | 默认 `openid profile email` |

以上变量仅描述浏览器侧的公开授权参数。正式上线还必须配置 BFF 的服务端 issuer、audience、JWKS、token exchange 和安全会话 cookie；在这些配置完成前，不能把 Sites 的 `oai-authenticated-user-*` 访客头直接转换成 Core API 的 Bearer JWT。

### 2.2 内部接口

内部接口不向浏览器开放：

| 调用方 | 凭据头 |
|---|---|
| Worker | `X-SenseMu-Worker-Token` |
| Inference Gateway → Core API | `X-SenseMu-Gateway-Token` |
| Payment adapter | `X-SenseMu-Payment-Adapter-Token` |
| Platform review adapter | `X-SenseMu-Platform-Review-Token` |
| Gateway → Runtime | `X-SenseMu-Runtime-Token` |

所有生产凭据必须由部署平台注入并轮换，不能使用 `.env.example` 中的本地默认值。

四个后端进程会在启动或首次创建配置时执行失败关闭校验：

- Core API 使用 `SENSEMU_ENVIRONMENT`；Worker 同样继承该变量。
- 推理网关使用 `SENSEMU_GATEWAY_ENVIRONMENT`，推理运行时使用 `SENSEMU_RUNTIME_ENVIRONMENT`。
- `staging/production` 禁止 `*-local-only`、少于 32 字符的内部凭据和 `local://` 对象存储。
- Core API 在 `staging/production` 必须使用 `SENSEMU_AUTH_MODE=oidc`，并完整配置 issuer、audience 和 JWKS URL。
- Worker 在 `staging/production` 禁止 `SENSEMU_DOCKER_ALLOW_CROSS_ARCHITECTURE=true`。

部署清单必须显式设置对应环境变量；如果遗漏环境标识，进程会按开发模式运行，因此发布流水线还应把环境标识设为必填项。

### 2.3 错误格式

Core API 当前遵循 FastAPI 默认格式：

```json
{"detail": "当前成员角色无权执行该操作"}
```

推理网关和运行时对机器可处理错误使用结构化 detail：

```json
{"detail": {"code": "RUNTIME_BUSY", "message": "运行时繁忙"}}
```

常用状态码：`400/409` 状态冲突，`401` 凭据无效，`403` 无权限，`404` 对象不存在或不属于当前工作区，`422` 参数或数据不满足约束，`429` 容量忙，`502/504` 下游不可用或超时。

### 2.4 异步任务提交语义

训练、独立验收、批量推理、视频抽帧和 Webhook 投递都采用“先持久化、后派发”顺序：接口会先提交任务/投递记录及不可变任务规格，再安排后台消息。恢复失联租约的接口也必须先提交重新入队状态，再触发下一次派发。

因此 Worker 或投递器收到消息后可以直接按 ID 读取记录；如果消息系统暂时不可用，记录仍会保留在 `queued` / `pending`，运行告警会暴露积压，再按对应任务族的维护或显式重新派发策略恢复。调用方重试创建请求时必须复用原 `Idempotency-Key`，不能通过新建重复任务来“补偿”派发失败。

## 3. Core API 功能索引

### 3.1 健康、身份和工作台

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/health/live` | 进程存活，不代表依赖可用 |
| GET | `/health/ready` | 实查数据库和对象存储 |
| GET | `/health/operational` | 训练、Webhook、额度预留等运行告警摘要 |
| GET | `/api/v1/identity/me` | 当前身份与工作区成员关系 |
| GET | `/api/v1/overview` | 工作台资源统计和最近活动 |

### 3.2 工作区与协作

| 方法 | 路径 | 作用 |
|---|---|---|
| POST / GET | `/api/v1/workspaces` | 创建或列出工作区 |
| GET | `/api/v1/workspace-members` | 列出成员 |
| PATCH | `/api/v1/workspace-members/{membership_id}` | 调整成员角色 |
| POST | `/api/v1/workspace-members/{membership_id}:suspend` | 停用成员 |
| POST / GET | `/api/v1/workspace-invitations` | 创建或列出邀请 |
| POST | `/api/v1/workspace-invitations:accept` | 使用一次性令牌接受邀请 |
| POST | `/api/v1/workspace-invitations/{invitation_id}:revoke` | 撤销邀请 |
| GET | `/api/v1/workspace-access-events` | 查看只追加的权限审计 |

### 3.3 项目、数据集和素材

| 方法 | 路径 | 作用 |
|---|---|---|
| POST / GET | `/api/v1/projects` | 创建或列出项目 |
| POST | `/api/v1/projects/{project_id}:pause` | 暂停新任务创建 |
| POST | `/api/v1/projects/{project_id}:resume` | 恢复项目 |
| POST | `/api/v1/projects/{project_id}:archive` | 归档项目；存在运行中的训练/处理、未完成标注任务、进行中的视频抽帧或已发布在线服务时返回 `409` |
| POST / GET | `/api/v1/projects/{project_id}/datasets` | 创建或列出数据集 |
| PATCH | `/api/v1/datasets/{dataset_id}/classes` | 保存类别表 |
| DELETE | `/api/v1/datasets/{dataset_id}` | 删除没有受保护依赖的数据集 |
| POST | `/api/v1/datasets/{dataset_id}/uploads` | 创建素材上传意图 |
| POST / GET | `/api/v1/datasets/{dataset_id}/assets` | 登记或列出素材 |
| GET | `/api/v1/datasets/{dataset_id}/assets/{asset_id}/content` | 通过权限边界读取图片 |
| PATCH | `/api/v1/datasets/{dataset_id}/items/{asset_id}` | 更新划分等素材属性 |
| GET | `/api/v1/datasets/{dataset_id}/source-videos` | 列出视频来源文件 |

上传顺序是“创建上传意图 → 客户端直传对象存储 → 登记素材”。API 不接收大文件本体；本地开发的 `/api/v1/dev-storage/{key}` 只是 LocalStorage 适配器入口。

### 3.4 视频抽帧和标注任务

| 方法 | 路径 | 作用 |
|---|---|---|
| POST / GET | `/api/v1/datasets/{dataset_id}/video-extractions` | 创建或列出抽帧任务 |
| GET | `/api/v1/video-extractions/{job_id}` | 获取任务状态 |
| POST | `/api/v1/video-extractions/{job_id}:cancel` | 取消仍可取消的任务 |
| PUT | `/api/v1/datasets/{dataset_id}/video-extractions/{job_id}/annotation-task` | 从该批实际输出幂等创建标注任务 |
| POST / GET | `/api/v1/datasets/{dataset_id}/annotation-tasks` | 创建或列出标注任务 |
| GET / PATCH | `/api/v1/datasets/{dataset_id}/annotation-tasks/{task_id}` | 读取任务或更新状态 |
| GET | `/api/v1/datasets/{dataset_id}/annotation-tasks/{task_id}/assets` | 获取固定任务素材快照 |
| GET | `/api/v1/datasets/{dataset_id}/annotation-tasks/{task_id}/yolo-package` | 导出带清单的标注 ZIP；始终包含 YOLO，图片尺寸完整时同时包含标准 COCO |
| POST | `/api/v1/datasets/{dataset_id}/annotation-tasks/{task_id}/yolo-import-uploads` | 创建标注任务包上传意图 |
| POST | `/api/v1/datasets/{dataset_id}/annotation-tasks/{task_id}/yolo-import` | 校验并导入 YOLO 或 COCO 结果；旧路径名保持兼容 |
| POST / GET | `/api/v1/datasets/{dataset_id}/items/{asset_id}/annotation` | 登记或读取单图 YOLO 标注 |

任务状态不能仅由前端文案决定。完成检查前，服务端会复核任务素材是否全部有合法标注。

### 3.5 数据版本、训练和模型

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/v1/datasets/{dataset_id}/versions:freeze` | 生成不可变数据版本 |
| GET | `/api/v1/datasets/{dataset_id}/versions` | 列出版本 |
| GET | `/api/v1/dataset-versions/{version_id}/quality-report` | 获取冻结时质量快照 |
| GET | `/api/v1/training/engines` | 列出允许的训练引擎 |
| POST / GET | `/api/v1/projects/{project_id}/training-runs` | 创建或列出训练任务 |
| GET | `/api/v1/training-runs/{run_id}` | 获取任务状态 |
| GET | `/api/v1/training-runs/{run_id}/events` | 追加式事件时间线 |
| POST | `/api/v1/training-runs/{run_id}:cancel` | 取消任务 |
| POST | `/api/v1/training-runs/{run_id}:dispatch` | 重新分发可执行任务 |
| GET | `/api/v1/training-runs/{run_id}/report` | 读取受限 `results.csv` 报告 |
| GET | `/api/v1/training-runs/{run_id}/class-metrics` | 读取类别指标 |
| GET | `/api/v1/training-runs/{run_id}/visualizations/{visualization}` | 读取白名单 PNG 可视化 |
| GET | `/api/v1/projects/{project_id}/model-versions` | 列出不可变模型版本 |

### 3.6 评测、验收和发布

| 方法 | 路径 | 作用 |
|---|---|---|
| POST / GET | `/api/v1/projects/{project_id}/evaluation-policies` | 创建或列出版本化门禁 |
| POST | `/api/v1/model-versions/{model_version_id}:evaluate` | 用训练指标生成早期信号 |
| POST | `/api/v1/projects/{project_id}/model-versions/{model_version_id}/acceptance-runs` | 在独立数据版本上验收 |
| GET | `/api/v1/projects/{project_id}/acceptance-runs` | 列出验收任务 |
| GET | `/api/v1/projects/{project_id}/evaluations` | 列出评测结论 |
| POST / GET | `/api/v1/projects/{project_id}/deployments` | 发布或列出服务 |
| POST | `/api/v1/deployments/{deployment_id}:enable` | 启用服务 |
| POST | `/api/v1/deployments/{deployment_id}:disable` | 停用服务 |
| POST | `/api/v1/deployments/{deployment_id}:rotate-key` | 轮换并一次性返回密钥 |

发布接口必须复核“当前门禁 + 独立验收 + 模型版本”，不能仅相信前端传入的可发布状态。

### 3.7 能力契约、批处理和业务事件

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/v1/deployments/{deployment_id}/capability-spec` | 从生产服务固化能力契约 |
| GET | `/api/v1/projects/{project_id}/capability-specs` | 列出能力版本 |
| POST / GET | `/api/v1/projects/{project_id}/workflow-specs` | 创建或列出固定模板工作流 |
| GET | `/api/v1/projects/{project_id}/vision-events` | 列出业务事件 |
| GET | `/api/v1/projects/{project_id}/vision-events/{event_id}/replay` | 回放不含原图的命中依据 |
| POST / GET | `/api/v1/projects/{project_id}/batch-inference-runs` | 创建或列出批量推理 |
| GET | `/api/v1/batch-inference-runs/{run_id}/output` | 下载无原始地址的 NDJSON/报告 |

### 3.8 算法市场、数据市场和供应方

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/v1/capability-specs/{capability_spec_id}/marketplace-listing` | 从能力契约创建算法商品 |
| GET | `/api/v1/marketplace/listings` | 买方可发现商品 |
| GET | `/api/v1/marketplace/submissions` | 供应方查看审核状态 |
| POST | `/api/v1/marketplace/listings/{listing_id}/subscriptions` | 创建订阅/待支付订单 |
| GET | `/api/v1/marketplace/subscriptions` | 列出买方授权 |
| POST | `/api/v1/marketplace/subscriptions/{subscription_id}:claim-key` | 一次性领取密钥 |
| POST | `/api/v1/marketplace/subscriptions/{subscription_id}:rotate-key` | 轮换买方密钥 |
| GET | `/api/v1/marketplace/usage-records` | 成功调用记录 |
| GET | `/api/v1/marketplace/billing` | 订单、支付和收入事实 |
| POST | `/api/v1/dataset-versions/{dataset_version_id}/data-listing` | 从冻结版本发布数据卡 |
| GET | `/api/v1/data-market/listings` | 列出公开数据卡 |
| GET | `/api/v1/data-market/listings/{listing_id}/delivery-spec` | 读取交付规范 |
| GET | `/api/v1/provider/dashboard` | 供应方聚合看板 |
| GET / PATCH | `/api/v1/provider/profile` | 读取或更新供应方资料 |

平台审核、支付归一化事件、日级对账、额度预留与确认等 `/api/v1/internal/*` 路径只供受信适配器和网关调用，不属于浏览器 API。

## 4. 公网推理网关

| 方法 | 路径 | 请求头 | 说明 |
|---|---|---|---|
| GET | `/health/live` | 无 | 进程存活 |
| GET | `/health/ready` | 无 | 同时探测 Core API 与 Runtime |
| GET | `/inference/v1/runtimes` | 无 | 当前稳定协议和运行时配置摘要 |
| POST | `/inference/v1/workspaces/{workspace_slug}/endpoints/{endpoint_slug}:prewarm` | `X-API-Key`, 可选 `X-Request-ID` | 预热模型，不计量 |
| POST | `/inference/v1/workspaces/{workspace_slug}/endpoints/{endpoint_slug}:predict` | `X-API-Key`, 可选 `X-Request-ID` | 1-4 张图片的真实预测，成功后计量 |

预测输入当前只允许受限对象引用或 Base64 图片，不抓取任意互联网 URL。稳定输出协议为 `detections.v1`。相同 `X-Request-ID` 用于幂等用量处理，不应在业务重试时生成新值。

## 5. 内部推理运行时

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health/live` | 进程存活 |
| GET | `/health/ready` | 模型缓存、容量和是否接收请求 |
| POST | `/v1/models:prewarm` | 使用 `X-SenseMu-Runtime-Token` 预热模型 |
| POST | `/v1/predict` | 使用内部模型地址执行 `detections.v1` |

运行时只接受网关提供的不可变模型版本和对象存储地址。不要从 Web 直接调用，也不要把 Runtime Token 返回给浏览器。

## 6. 关键业务时序

### 6.1 数据到训练

`Workspace → Project → Dataset → Upload intent → Asset → Annotation task → Review → Frozen DatasetVersion → Training Run → ModelVersion`

### 6.2 模型到上线

`ModelVersion → Independent Acceptance Run → Gate verdict → Deployment → Prewarm → Predict → UsageRecord`

### 6.3 算法商品到计费

`Production Deployment → CapabilitySpec → Listing review → Pending order → Verified payment → Entitlement/key → Quota reservation → Successful usage → Provider earning`

任何接口调整都要保留这些顺序和不可变边界。

## 7. 接口变更检查清单

- 是否明确调用方是浏览器、Worker、网关还是内部适配器？
- 是否带工作区边界并在服务端校验对象归属？
- 写操作的最低角色是否正确？
- 重试会不会重复创建任务、扣额度或写收入？
- 一次性密钥是否只在创建/轮换响应出现？
- 异步回写是否验证当前执行租约或尝试令牌？
- 是否避免返回对象存储地址、原始输入和内部错误堆栈？
- OpenAPI、前端类型、测试和本文是否同步更新？
