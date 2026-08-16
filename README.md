# SenseMu

SenseMu 是一个面向视觉 AI 的端到端工作平台：在同一个可追溯闭环中完成数据管理、训练、评测、发布、推理与算法交易。

项目交接入口：

- 产品功能与边界：[`docs/PRODUCT_FUNCTIONS.md`](docs/PRODUCT_FUNCTIONS.md)
- 后端接口与鉴权：[`docs/API_GUIDE.md`](docs/API_GUIDE.md)
- 架构与代码审计：[`docs/CODE_AUDIT_2026-08-16.md`](docs/CODE_AUDIT_2026-08-16.md)
- 当前状态与优先级：[`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)

当前仓库是第一版工程骨架，保持五个运行时边界：

- `apps/web`：React 19 + TypeScript + Tailwind CSS 4 + vinext 产品端
- `apps/api`：FastAPI 模块化单体，承载核心业务 API
- `apps/worker`：Celery 异步任务进程，承载导入、处理、训练编排和计量
- `apps/inference-gateway`：独立 FastAPI 进程，承载鉴权、路由、限流与推理协议
- `apps/inference-runtime`：隔离的 Ultralytics 进程，承载模型缓存与真实预测

PostgreSQL 是业务事实源，Redis 承载队列与短期状态，S3 兼容存储承载数据、模型和评测产物。首版不拆微服务，不引入 Kubernetes。

## 目录

```text
sense-mu/
├── apps/
│   ├── web/
│   ├── api/
│   ├── worker/
│   ├── inference-gateway/
│   └── inference-runtime/
├── packages/
│   └── contracts/
├── infra/
│   └── compose/
└── docs/
    └── adr/
```

## 本地启动

不安装 Docker 也可以先体验数据主链路。在仓库根目录分别启动 API 和 Web：

```bash
make local-api
make web-dev
```

`local-api` 会自动迁移本地 SQLite，并将上传文件放到已忽略的 `.local-data/`。打开 `http://localhost:3000/studio/data` 即可创建工作区、项目和数据集，直传图片、设置数据划分、导入 YOLO 标注并冻结不可变数据版本；在 `http://localhost:3000/studio/training` 可用冻结版本提交幂等、可追溯的训练任务。这条路径仅用于本地开发；生产仍使用 PostgreSQL 和 S3/MinIO。

要实际执行训练，还需启动 Docker Desktop、Redis 和训练 Worker：

```bash
docker compose -f infra/compose/compose.yml up -d redis
make local-worker
```

Worker 会消费训练、视频抽帧和维护队列，本地命令同时启动轻量定时调度器。视频抽帧需要 Worker 宿主机安装 `ffmpeg` 与 `ffprobe`；原始视频仅作为来源文件保存，生成的图片才会进入标注、划分和版本冻结。数据预检要求至少包含训练集、独立验证集、连续的类别定义和每张图片的 YOLO 标注；不满足时任务会记录真实失败原因，不会进入伪训练。执行过程中 Worker 每 15 秒续期租约；超过 120 秒没有心跳的训练任务会安全回收并重新排队，连续失联 3 次后停止自动重试。

完整基础设施需要 Node.js 22.13+ 与 Docker：

```bash
cd apps/web
npm install
npm run dev
```

后端需要 Python 3.12+。使用一个根目录虚拟环境即可：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e apps/api -e apps/worker -e apps/inference-gateway -e 'apps/inference-runtime[runtime]'
cp .env.example .env
make api-dev
```

启动 PostgreSQL、Redis、MinIO 等本地依赖：

```bash
make infra-up
```

接口存活检查：`GET http://localhost:8000/health/live`。`GET http://localhost:8080/health/ready` 会同时探测核心 API 和推理运行时，并返回模型缓存、活动请求与可用容量；运行时自身状态位于 `GET http://localhost:8090/health/ready`。

本地真实推理需要另开两个终端：

```bash
make runtime-dev
make gateway-dev
```

项目内的“发布与推理”页面可以查看端到端运行状态、主动预热已发布模型，并上传一张 JPEG、PNG 或 WebP 图片执行真实调用。预热只填充模型缓存，不登记调用量；推理仅在成功后计量。默认 CPU 运行时同时处理 1 个请求，容量满时快速返回 `429` 和重试提示。运行时没有启动、模型文件不存在、超时或 Ultralytics 未安装时都会返回明确错误，不会生成模拟结果。

启动 PostgreSQL 后执行迁移：

```bash
make db-migrate
```

完整本地检查：`make check`。数据库主链模型与 Alembic 迁移位于 `apps/api/src/sensemu_api/db` 和 `apps/api/migrations`。

## 当前边界

当前已经落地一组连续、可追溯的真实竖切：

- `Asset → DatasetVersion`：租户隔离的数据库查询、预签名直传合同、SHA-256 与文件大小校验、去重资产登记、训练/验证/测试划分、YOLO 标注格式与类别校验，以及包含全部训练输入的不可变 manifest。
- `DatasetVersion → Run → ModelVersion`：只接受已冻结数据版本，通过 Ultralytics 引擎适配器校验配置，使用幂等键避免重复任务，持久化 `Run` 和追加式 `RunEvent`，并写入不可变 `job-spec.json`。Worker 使用带心跳、超时回收和最大尝试次数的执行租约防止重复或永久卡死，由 Docker 运行 Ultralytics，回传真实进度、错误和产物；API 在产物已上传后原子登记不可变 `ModelVersion`。
- `ModelVersion → Training validation signal`：项目门禁策略按版本追加且只保留一个当前版本；训练完成后使用真实训练验证指标生成早期质量信号，也支持新策略下重评。该信号不再直接授予生产发布资格。
- `Independent DatasetVersion → Acceptance Run → Gate verdict`：验收任务必须选择未参与该模型训练、类别定义完全一致的冻结数据版本。Worker 在断网 Docker 运行时中加载真实模型并执行 Ultralytics 验收推理，固化模型、数据、门禁、运行镜像、实际指标和逐条结果到不可变 `report.json`。只有当前门禁下的独立验收记录可以把模型收敛为可发布。
- `Acceptance-approved ModelVersion → Deployment → Inference Gateway → UsageRecord`：只有通过当前独立验收门禁的模型才能发布；发布规格固化模型与验收依据，API 密钥只显示一次且数据库只保存摘要。独立推理网关按工作区和端点解析服务、校验密钥、转发到配置的运行时，并按请求编号幂等记录成功处理的图像数。
- `Production Deployment → CapabilitySpec`：供应方从已发布的生产服务固化可交付能力版本，服务端锁定模型、独立验收依据和输出协议，并把问题定义、输入限制、适用边界、交付方式与内容哈希写入不可变 JSON 契约。修订只能绑定新服务版本创建新的能力版本。
- `CapabilitySpec → Template WorkflowSpec`：首期仅支持 PPE 违规事件到 Webhook 的固定模板，服务端校验事件必须来自能力契约，固定能力调用、去重窗口和输出步骤，并保存能力内容哈希与工作流版本快照。
- `VisionEvent → WebhookDelivery`：受保护的内部事件契约按工作流和幂等键持久化业务事实，并创建唯一投递记录。Worker 使用稳定 JSON 和 HMAC-SHA256 签名调用客户 Webhook，失败按退避策略重试、超时占用会被定时回收；“发布与推理”页保留近期投递状态、尝试次数和错误摘要。
- `CapabilitySpec → MarketplaceListing`：算法商品必须显式引用一个已发布能力版本，服务端据此锁定生产服务、模型、独立验收依据和输入输出边界。审核批准会再次校验契约与生产服务；公开目录展示能力版本、输出协议、已验证场景和不适用条件，无法映射到能力契约的历史商品不会继续公开。
- `Inference Gateway → Ultralytics Runtime → detections.v1`：运行时只接受内部凭据和受限参数，从平台对象存储或受限 Base64 图片读取输入，按模型版本缓存权重并输出稳定的目标检测结构；不抓取任意互联网 URL，也不在响应中回显图片内容。运行时提供受鉴权的模型预热和实例级容量保护；网关分别约束控制面、运行时与计量超时，并聚合端到端就绪状态。
- `Production Deployment → Listing Submission → Platform Review`：只有已发布的目标检测生产服务可以提交市场审核。商品在平台批准前处于待审核状态，不出现在公开目录、不允许购买；拒绝后供应方可修订同一商品再提交，审核事实始终追加保存。
- `Published Listing → Pending Order`：只有平台批准的算法商品会公开给其他工作区。买方首先创建固化价格和额度的待支付订单；此时不起算 30 天有效期、不激活额度、不生成调用密钥。同一待支付订单重复操作会返回既有支付意图，不重复下单；供应方不能购买自己的商品。
- `Verified Payment → Entitlement → Claim-once Key`：支付适配器验签后通过受保护的内部契约提交归一化事件。只有金额、币种与幂等性校验通过的收款会激活 30 天额度；管理员随后一次性领取密钥，数据库只保存前缀和摘要。价格为零的订单明确标记免付费并直接激活；全额退款立即清除密钥并撤销后续调用资格。
- `Entitlement → Quota Reservation → Usage Accrual`：网关在推理前原子预留额度，成功后在同一事务确认用量和供应方收入计提，运行失败则释放；重复请求编号不重复扣额或入账。Worker 自动回收失联遗留预留，市场页分开展示订单、收款状态、成功用量和待结算收入。
- `OIDC Identity → UserAccount → WorkspaceMembership → Role Gate`：核心 API 以签发方和用户主体标识稳定映射账号，不使用可变邮箱作为授权主键。`X-Workspace-ID` 只用于选择工作区，每次请求都必须在服务端校验活跃成员关系。查看者可读，成员可执行日常数据和训练操作，管理员才能发布服务、轮换密钥或购买市场授权。本地开发模式保留单用户自动授权，但在非开发环境会强制失败关闭。
- `Project Training/Deployment → My Compute & Hosting`：训练任务只从项目“训练”创建，在线服务只从项目“发布与调用”创建；供应方在“我的”统一查看跨项目任务和服务并跳回详情。费用合同未落地前明确显示尚未开通，不伪造算力档位、价格或余额。
- `Workspace Invitation → Verified Email → Membership → Access Audit`：管理员可邀请普通成员，只有所有者可以授予管理员角色。邀请凭据只显示一次且数据库只保存摘要；接受者必须使用身份提供方明确验证、并与目标一致的邮箱。角色调整、邀请接受/撤销和成员停用均写入只追加的权限审计，所有者和当前操作者受到防误操作保护。
- `Frozen DatasetVersion → Provenance Card → Delivery Spec → Data Marketplace`：供应方只能从自有冻结版本发布数据卡，必须声明来源、采集方式、覆盖、限制、隐私处理、许可证与用途权限，并确认拥有分发权。每张新数据卡会写入不可变交付规范快照和内容哈希，明确为“授权后导入买方工作区、无对象存储直链”；首阶段拒绝含个人数据，公开目录不泄露内部 manifest 或对象地址，正式下载、购买和授权仍保持关闭。
- `Provider Workspace → Listings → Sales → Earnings`：供应方中心聚合算法商品、数据卡、客户授权、成功用量、供应方销售订单以及支付、退款和待结算收入事实。公开档案与主体认证、收款配置和平台审核状态分离；未接入的认证、结算和提现能力始终显示未开始或未开放，不以商品或收入记录伪造准入完成。

生产环境需将 `SENSEMU_AUTH_MODE` 设为 `oidc`，并配置精确的签发方、受众和 JWKS 地址。成员邀请还要求身份提供方在令牌中明确给出已验证邮箱。当前已完成 API 的凭据验证和成员授权边界，但尚未选定最终身份提供方或实现面向公网的登录界面。

产品仍保持模块化单体，未引入集群调度、通用工作流引擎、自研标注器或多个数据库。算法市场已将提交审核、公开发现、下单、验签收款、授权激活、密钥领取和全额退款撤权串成真实时序，但尚未选定或接入具体收款渠道。下一步为首个 PPE 模板接入具备明确事件条件、去重键和回放测试的推理网关解释器；在确定目标市场、签约主体和支付渠道后才实现首个真实收款适配器，不在核心平台中硬编码某一家渠道。
