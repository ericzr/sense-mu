# SenseMu 后端协同开发手册

- 更新日期：2026-08-25
- 适用对象：后端、Worker、推理、基础设施、前端和测试协作者
- 当前阶段：公开演示 + 后端真实闭环开发

这份文档是新协作者的单一入口。产品范围看 `PRODUCT_FUNCTIONS.md`，字段级接口以 `apps/api/openapi.json` 为准，架构取舍看 `docs/adr/`，当前优先级看 `PROJECT_STATUS.md`。

## 1. 正式地址

| 用途 | 地址 | 说明 |
|---|---|---|
| 源码仓库 | https://github.com/ericzr/sense-mu | `main` 是 Cloudflare 生产构建来源 |
| SenseMu 预览/演示 | https://cs.sensemu.com/ | 当前公开访问入口，使用 Cloudflare Worker 承载 |
| Worker 健康探针 | https://cs.sensemu.com/__sensemu/health | 应返回 `runtime=cloudflare-worker`、`preview=true` 和绑定状态 |
| Cloudflare 服务控制台 | https://dash.cloudflare.com/23f50cb8b259344e75d53dc6a741abd2/workers/services/view/sense-mu/production | 需要 Cloudflare 账号权限 |
| GitHub 文档入口 | https://github.com/ericzr/sense-mu/tree/main/docs | 只承载文档，不承载完整工作台 |

`chatgpt.site`、临时 `workers.dev` 和旧 GitHub Pages 地址都不是产品验收入口。遇到线上问题先检查健康探针和 Cloudflare 部署详情，再判断是否是业务代码问题。

## 2. 产品一句话与核心对象

SenseMu 是计算机视觉能力的生产、交付和交易平台：用户把素材变成可追溯的数据版本，再变成经过独立验收的模型、可调用服务和可交易能力。

核心对象的事实顺序不可跳过：

```text
Workspace → Project → Dataset → Asset → AnnotationTask → DatasetVersion
→ TrainingRun → ModelVersion → AcceptanceRun → Deployment
→ CapabilitySpec → MarketplaceListing → Entitlement → UsageRecord
```

四个一级产品页面：

- 工作台：生产方管理数据、训练、模型、发布和调用。
- 算法市场：需求方发现和订阅已审核的算法能力。
- 数据市场：需求方发现有来源、许可和质量边界的数据卡。
- 我的：生产方管理商品和销售，需求方管理订单、授权和用量。

当前首个垂直场景是工业安全目标检测（PPE）。林业、农业和缺陷检测数据/算法是演示与扩展场景，不代表已经有对应的真实推理服务。

## 3. 当前真实边界

### 已可验证

- 数据集、素材、YOLO 标注、训练/验证/测试划分和不可变数据版本。
- 标注任务、任务包导出/导入、视频文件抽帧任务及任务恢复边界。
- 训练任务、租约、事件、模型产物、报告和独立验收门禁的控制面。
- 发布、服务启停、一次性密钥、图像推理网关和成功用量计量的本地真实闭环。
- 算法商品审核、能力契约、数据卡来源/许可/交付规范的控制面。

### 公开演示中的限制

- `cs.sensemu.com` 明确运行在 `SENSEMU_PREVIEW_MODE=true`，页面数据为只读演示数据。
- 当前没有连接生产 Core API、训练集群、对象存储和推理服务器；演示页面不会伪造训练或推理成功。
- 多模态大模型、实时视频流、真实支付、KYC/KYB、结算提现和数据购买交付保持未开放。
- 需要验证真实写入时使用 `test:e2e:local` 和隔离 API，不要把公开演示站当作后端集成环境。

## 4. 系统架构

| 边界 | 默认端口 | 职责 | 不负责 |
|---|---:|---|---|
| `apps/web` | 3000 | React/Vinext 页面、交互、调用 API | 不保存业务事实，不持有内部凭据 |
| `apps/api` | 8000 | FastAPI 核心业务、权限、数据库事实和 OpenAPI | 不执行 GPU 训练或直接推理 |
| `apps/worker` | 无公网端口 | 训练、验收、抽帧、批推理、维护和 Webhook | 不提供浏览器 API |
| `apps/inference-gateway` | 8080 | API Key、限流、额度预留、计量和稳定推理协议 | 不保存模型权重 |
| `apps/inference-runtime` | 8090 | 受限模型缓存和 Ultralytics 预测 | 不对浏览器或公网开放 |

生产依赖边界：PostgreSQL 是业务事实源，Redis 只承载队列与短期状态，S3 兼容存储承载素材、模型和报告。首期采用模块化单体，不拆微服务，不引入 Kubernetes。

关键调用顺序：

```text
Browser → same-origin BFF → Core API
Core API → persist task → queue/Worker
Worker → restricted Runtime or Ultralytics container → artifact callback
Browser/API client → Inference Gateway → Runtime
```

所有异步任务遵循“先持久化、后派发”。旧租约、旧 Worker 或重复请求不得覆盖新的执行尝试。

## 5. 身份与会话决策

首期采用“同源 BFF + 托管身份供应商”。

- Web 只跳转到同源 `/auth/login?return_to=...`，不直接交换授权码。
- BFF 负责 OIDC Authorization Code + PKCE 的 state、nonce、回调、token exchange、刷新和退出。
- refresh token、client secret、OIDC 会话和安全 cookie 只存在 BFF 服务端。
- Core API 仍校验标准 `Authorization: Bearer <OIDC JWT>`，并按 `X-Workspace-ID` 复核成员关系和最低角色。
- `return_to` 只能是同源相对路径，禁止开放重定向。
- 托管身份供应商尚未最终选型；在选型前不实现供应商特定 SDK 或 token endpoint。

详细安全不变量见 `docs/adr/0037-oidc-bff-session-boundary.md`。

## 6. 本地协作启动

环境要求：Node.js `24.19.0`、Python `3.12+`、Docker Desktop（真实训练/基础设施需要）。

```bash
git clone https://github.com/ericzr/sense-mu.git
cd sense-mu
nvm use
python3 -m venv .venv
source .venv/bin/activate
pip install -e apps/api -e apps/worker -e apps/inference-gateway -e 'apps/inference-runtime[runtime]'
cp .env.example .env
make infra-up
make api-dev
```

另开终端启动 Web：

```bash
cd apps/web
npm ci
npm run dev
```

常用检查：

```bash
make api-test
make api-lint
make api-openapi-check
cd apps/web && npm run typecheck && npm run lint && npm test
```

真实写入浏览器回归使用 `cd apps/web && npm run test:e2e:local`。公开演示回归使用 `npm run test:e2e`，两者不能互相替代。

## 7. 接口协作规则

1. 字段级请求和响应以 `apps/api/openapi.json` 为准；后端 schema 变化后先运行 `make api-openapi`，再更新 Web 生成类型。
2. 所有工作区对象在服务端校验归属，不能只相信 URL 中的 ID 或浏览器传入的工作区头。
3. 创建训练、验收、批推理、视频抽帧和支付意图必须支持 `Idempotency-Key`，重试必须复用原值。
4. 写操作按角色限制：viewer 只读，member 执行日常生产操作，admin/owner 管理发布、购买、密钥和成员。
5. `401` 表示身份失效，`403` 表示权限不足，`409` 表示业务保护条件，`429` 表示容量忙，`502/504` 表示下游不可用或超时。
6. API 不接收大文件本体；使用上传意图、直传对象存储、再登记素材的顺序。
7. 密钥只在创建/轮换响应中显示一次，数据库保存摘要；日志不得记录完整密钥、token、cookie 或对象存储直链。
8. 不为未接入的模型、支付、视频流或质量指标生成成功结果；必须返回明确的 unavailable/not-configured 语义。

接口总表和调用时序见 `docs/API_GUIDE.md`。

## 8. 后端协同优先级

服务器上线前的可执行验收矩阵见 `docs/PRE_SERVER_ACCEPTANCE.md`。其中“已由代码和自动化证明”不等于生产设施已验证；身份、PostgreSQL、对象存储、Redis、GPU、告警和恢复演练必须在真实环境留证。

### P0：让真实后端可被安全接入

- 确定托管身份供应商和 BFF 部署位置，完成登录、回调、会话、退出和权限撤销 E2E。
- 配置 staging 的 PostgreSQL、S3、Redis、Worker、网关和 Runtime，并关闭演示模式。
- 将 Cloudflare Web 的 `SENSEMU_API_URL` 指向同源 BFF/Core API，完成深链刷新、CORS、超时和健康探针验收。
- 为训练、验收、推理、Webhook 和对象存储补齐生产日志、指标、告警和 trace/request ID。

### P1：打通第一个可交付能力

- 用 PPE 目标检测完成真实训练 → 独立验收 → 发布 → 图像推理 → 用量计量闭环。
- 固化 `CapabilitySpec` 和算法市场审核后的真实订阅/授权边界。
- 选择支付渠道后实现一个渠道适配器，保持核心订单和支付事件渠道无关。

### P2：扩展感知能力

- 多模态模型适配器：凭据隔离、协议转换、超时、重试、审计和计量。
- 实时视频流：采样、断流恢复、租约、事件去重和网络白名单。
- 数据市场购买、授权后交付、KYC/KYB、结算与提现。

## 9. 交付标准

每个后端功能合并前必须同时具备：

- OpenAPI 快照和生成类型没有漂移。
- 工作区权限、幂等、错误语义和审计记录有测试。
- 异步任务有租约、超时、恢复和旧尝试回写保护。
- 敏感值不进浏览器 bundle、数据库明文或日志。
- 演示模式、真实本地 API 和 staging 的行为边界写入文档。
- `make check`、相关 API 测试和 Web 回归通过，并在 PR 描述中记录验证命令。

## 10. 协作约定

- 默认从 `main` 拉分支，提交保持单一目的；不要提交 `.local-data`、`.env`、构建目录或真实密钥。
- 产品行为变更先更新 `PRODUCT_FUNCTIONS.md`；接口变更先更新 OpenAPI 和 `API_GUIDE.md`；架构取舍新增 ADR。
- 任何“暂未接入”能力必须先定义边界和失败语义，再接具体供应商或基础设施。
- 线上问题先记录部署 SHA、`/__sensemu/health`、Core API ready 状态和相关 request ID，再修改代码。
