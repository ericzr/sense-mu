# SenseMu 正式上线执行手册

- 适用版本：`main`
- 适用环境：`staging`、`production`
- 本手册是执行顺序和证据要求，不替代部署平台的密钥管理文档。

## 0. 上线准入

只有以下条件全部满足，才允许把公网流量切到新版本：

- [ ] 已选定 OIDC 供应商和同源 BFF 部署位置，并登记回调、退出和允许来源。
- [ ] Web BFF 预检为 `ready`，并且 `SENSEMU_BFF_IMPLEMENTATION_READY=true` 只在 provider-specific 实现和 staging E2E 完成后设置。
- [ ] 生产环境变量由密钥管理系统注入；仓库、镜像和日志中没有 client secret、refresh token、API key 或 Cookie。
- [ ] PostgreSQL、S3 兼容对象存储、Redis 的连接信息和备份策略已登记。
- [ ] 训练镜像使用不可变 `@sha256:<digest>`，并记录 CUDA、驱动和 GPU 型号。
- [ ] 已完成一次 staging 的训练到推理闭环和一次失败恢复演练。
- [ ] 已配置 API、队列、Worker、网关、Runtime、Webhook 的告警接收人。

## 1. 发布前冻结

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
```

将提交 SHA、构建产物 digest、数据库迁移 head 和变更说明写入发布记录。发布记录不得使用“最新”“当前”等不可复现描述。

## 2. 配置检查

生产必须设置：

- `SENSEMU_ENVIRONMENT=production`
- `SENSEMU_AUTH_MODE=oidc`
- OIDC issuer、audience、JWKS URL
- PostgreSQL、S3、Redis 连接和独立密钥
- Worker、网关和 Runtime 的内部服务凭据
- Web 的同源 BFF 登录入口

生产禁止：

- `development` 身份模式
- `local://` 对象存储
- `*-local-only` 凭据、短于 32 字符的内部密钥
- 将 refresh token、client secret 放入浏览器变量或 Web Storage

## 3. 数据库与对象存储

1. 对生产数据库创建带时间戳的备份，并记录备份校验结果。
2. 在维护窗口执行迁移到 head；迁移失败时停止发布，不跳过版本。
3. 验证对象存储加密、版本控制、生命周期、CORS 和最小权限。
4. 使用一份非敏感测试对象验证上传、读取、删除保护和对象缺失时的可解释错误。
5. 记录恢复所需时间，形成 RPO/RTO 证据。

## 4. 流量门禁

部署后必须先检查存活和就绪：

```bash
curl -fsS https://<api-host>/health
curl -fsS https://<api-host>/health/ready
```

`/health/ready` 必须同时通过 PostgreSQL、对象存储和 Redis。任一依赖失败必须返回 `503`，部署平台不得导入流量。切流前保存响应中的版本、依赖状态和时间戳。

## 5. 业务闭环验收

使用专用 staging 工作区和最小权限账号，按顺序记录每一步的 request ID、run ID 和 deployment ID：

```text
创建项目
→ 创建数据集
→ 上传并登记素材
→ 标注、审核、冻结数据版本
→ 入队训练
→ 独立数据验收
→ 发布模型
→ 图像推理
→ 成功计量
```

同时验证：重复请求幂等、额度不足不计费、运行时超时不计费、旧 attempt 不能覆盖新 attempt、工作区成员隔离、密钥只显示一次。

## 6. GPU 与队列证据

- [ ] 记录节点架构、GPU 型号、驱动、CUDA、镜像 digest。
- [ ] 记录训练耗时、队列等待、P50/P95 推理延迟和并发上限。
- [ ] 验证取消、超时、Worker 失联、Redis 重启、重复投递和恢复。
- [ ] 确认公网只能访问网关，Worker 和 Runtime 仅允许内部网络访问。

## 7. 回滚

回滚必须指向已验证的提交 SHA 和镜像 digest，不使用重新构建的浮动标签：

1. 停止继续导入流量并保留现版本日志。
2. 切换到上一份已验收的 Web/API/Worker/Runtime 组合。
3. 若涉及不可逆迁移，先执行兼容性回滚方案，不直接降级数据库 schema。
4. 重新检查 `/health/ready` 和最小业务闭环。
5. 记录触发原因、影响范围、恢复时间和后续修复责任人。

## 8. 证据归档

每次发布至少归档：提交 SHA、镜像 digest、迁移版本、健康检查响应、闭环结果、告警截图、备份校验、RPO/RTO、回滚结果。没有证据的项目标记为“未验收”，不得写成“已上线”。

身份供应商的选择和 BFF 端点合同见 `docs/adr/0037-oidc-bff-session-boundary.md`；完整阻断项清单见 `docs/PRE_SERVER_ACCEPTANCE.md`。
