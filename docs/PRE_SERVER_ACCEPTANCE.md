# SenseMu 服务器上线前验收门禁

- 更新日期：2026-08-28
- 适用版本：`main`
- 目的：在算力服务器、对象存储和生产数据库上线前，区分代码已经证明的能力与必须在真实基础设施上验证的风险。

## 结论

当前仓库可以作为“无真实服务器的产品与业务逻辑验收基线”，不能宣称已经具备生产上线条件。演示站只读、Mock 数据和真实业务事实已经分界；正式上线仍被身份、数据设施、算力和观测门禁阻塞。

## 已由代码和自动化证明

| 领域 | 证据 | 结果 |
|---|---|---|
| API 与状态机 | API 单元/集成测试 | 95 项通过 |
| 数据生产 | 上传意图、标注任务、YOLO/COCO 交换、审核、冻结版本 | 服务端门禁和权限测试通过 |
| 训练与验收 | 幂等键、租约、超时、旧尝试拒绝、独立验收 | 服务端和 Worker 测试通过 |
| 发布与调用 | 评测通过后发布、一次性密钥、网关额度预留与成功计量 | 代码路径和本地闭环已覆盖 |
| 批量推理 | 固定数据版本、部署、产物前缀和执行令牌 | 结果登记边界已覆盖 |
| Webhook | 签名、重试、租约恢复、HTTPS 和 DNS 目标校验 | API/Worker 回归通过 |
| 前端 | 渲染、类型、Lint、OpenAPI 类型、托管预览 E2E | 渲染 18 项、托管预览 3 项通过 |
| 依赖 | `npm audit --omit=dev --audit-level=high`（官方 registry） | 0 vulnerabilities |
| 演示边界 | 仅 `SENSEMU_PREVIEW_MODE=true` 展示 Mock 商品/数据集 | 正式渲染回归确认不会泄漏 |

## P0：服务器上线前必须完成

### 身份与入口

- 选定托管 OIDC 供应商和 BFF 部署位置。
- 实现 Authorization Code + PKCE 的 state/nonce、回调、刷新、退出和撤销。
- 只在 BFF 保存 refresh token、client secret 和会话 cookie；浏览器不交换 token。
- 用真实账号验证 `401`、`403`、权限收回、深链返回和跨工作区访问拒绝。

### 数据设施

- PostgreSQL：迁移到 head，验证备份、恢复、连接池、滚动升级和唯一约束冲突恢复。
- S3 兼容存储：启用加密、版本控制、生命周期、最小权限、CORS 和大文件失败重试；验证对象丢失时的可解释错误。
- Redis：区分队列与短期状态，验证持久化、重启、积压告警、重复投递和故障恢复。
- 所有生产服务必须注入 `SENSEMU_ENVIRONMENT=production` 和独立密钥；禁止本机依赖和 `local://`。

### 算力与推理

- 在目标 Linux x86/GPU 节点复现：冻结版本 → 训练 → 独立验收 → 发布 → 图像推理 → 成功计量。
- 训练镜像使用不可变 `@sha256:<digest>`；记录 CUDA、驱动、GPU 型号和 Ultralytics 版本。
- 记录训练耗时、P50/P95 延迟、并发上限、队列等待、超时、取消和 Worker 失联恢复。
- 网关和 Runtime 只允许内部网络访问；公网只暴露网关，验证额度不足、运行时繁忙和下游超时不计费。

### 观测与运维

- 统一 request ID、run ID、attempt ID 和 deployment ID；日志不得包含 token、完整 API key、Cookie 或对象直链。
- 为 API、队列、Worker、网关、Runtime、对象存储和 Webhook 配置健康探针、延迟/错误/积压告警。
- 完成一次发布回滚和一次数据库/对象存储恢复演练，并保存结果和 RPO/RTO。

## P1：首批客户前完成

- 真实支付渠道的签名、金额/币种校验、幂等事件、退款和授权撤销。
- 算法市场公开目录与买方工作区解耦：访客可发现，购买和密钥领取仍要求管理员工作区。
- 真实标注工具交接和大任务异步导出，不继续扩展通用自研标注器。
- 按真实吞吐优化批量推理产物和交付格式；不得与公网在线推理计费路径混用。

## 明确关闭或暂不承诺

- 多模态大模型、实时视频流、数据市场购买/复制交付、KYC/KYB、提现和正式结算在依赖与合同确定前保持 `待接入/未开放`。
- 公开演示环境不连接真实推理服务器，不生成虚假推理、训练指标、验收或账务事实。

## 验收命令

```bash
make api-test
make api-lint
make api-openapi-check
make python-check
cd apps/web && npm run typecheck && npm run lint && npm test
cd apps/web && npm run test:e2e:local
cd apps/web && npm run test:e2e
curl -fsS https://cs.sensemu.com/__sensemu/health
```

服务器未就绪前，最后四项中的真实 API E2E、GPU 闭环、恢复演练和线上告警只能标记为“待真实环境证据”，不能以本地 Mock 结果替代。
