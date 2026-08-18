# ADR-0037：OIDC 与 BFF 会话边界

## 背景

SenseMu Core API 已完成 OIDC JWT 校验、`UserAccount` 映射和工作区角色校验。Web 端也能区分身份服务不可用、会话失效和权限不足，但正式登录仍依赖首发身份供应商和受信的 BFF。

如果把授权码交换、refresh token 或供应商 client secret 放进 Web bundle，会扩大泄露面，也无法可靠处理退出、令牌轮换和会话撤销。反过来，如果 Web 只显示“需要登录”而没有入口，用户又无法恢复失效会话。

## 决策

- Web 只提供配置驱动的 `NEXT_PUBLIC_SENSEMU_AUTH_LOGIN_URL` 登录入口，默认建议使用同源 `/auth/login`。
- BFF 负责 OIDC Authorization Code + PKCE 的 state、nonce、code verifier、授权回调和 token exchange。
- refresh token、client secret、OIDC provider session 和 BFF session cookie 只存在服务端；浏览器不写入 `localStorage` 或 `sessionStorage`。
- BFF 向 Web 提供短期 access token 的受信注入方式，或由 BFF 代理 Core API；最终采用哪一种由部署形态决定，但 Core API 始终只信任标准 `Authorization: Bearer <OIDC JWT>`。
- Core API 不信任 Web 或 Sites 的访客头；每次请求仍按 `issuer + subject` 映射账号，并用 `X-Workspace-ID` 复核成员关系和最低角色。
- Web 收到 Core API `401` 时清除内存 access token 并显示登录入口；`403` 显示权限不足；`5xx/503` 显示服务不可用和重试，不自动退出账号。
- 退出必须先由 BFF 撤销或清理服务端会话，再跳转到身份供应商的 end-session（若供应商支持）；不能只清除浏览器内存状态。

## 最小 BFF 合同

| 动作 | 责任 | 约束 |
|---|---|---|
| `GET /auth/login?return_to=/...` | 创建 state/nonce/PKCE 并跳转供应商 | `return_to` 只接受同源相对路径，禁止开放重定向 |
| `GET /auth/callback?code=...&state=...` | 校验 state、交换 code、建立安全会话 | 拒绝重复使用 state；失败不落库 token |
| `GET /auth/session` | 返回当前会话的非敏感身份摘要 | 不返回 refresh token 或 client secret |
| `POST /auth/logout` | 清理 BFF 会话并执行 provider logout | 幂等；失败也清除本地会话 |
| Core API 请求 | BFF 或 Web 注入短期 access token | 不使用 Sites 访客头替代 JWT |

## 安全不变量

1. state、nonce 和 code verifier 必须与浏览器会话绑定并一次性使用。
2. 回调必须校验 issuer、audience、签名、过期时间和授权码交换结果；Core API 再次校验 JWT，不把 BFF 结果当作永久信任。
3. 会话 cookie 必须 `HttpOnly`、`Secure`（本地 HTTPS 例外）、`SameSite=Lax/Strict`，并设置明确过期时间和轮换策略。
4. 日志中不得出现授权码、access token、refresh token、完整 cookie 或原始 `return_to`。
5. 用户停用、工作区移除和角色变更在 Core API 立即生效，不等待 Web 会话过期。

## 接入顺序

1. 确定首发身份供应商、issuer、audience、JWKS、授权端点、token 端点和 end-session 端点。
2. 实现 BFF 登录、回调、会话和退出，并为 state 重放、错误回调、过期 refresh token 和权限撤销补 E2E。
3. 配置 Web 的 `NEXT_PUBLIC_SENSEMU_AUTH_LOGIN_URL`，验证失效会话可恢复，且演示模式不调用真实身份提供方。
4. 在 staging 使用真实 OIDC 租户完成邀请、成员角色变更、停用和跨工作区访问验收，再开放 production。

## 未决事项

- 尚未选择首发身份供应商和 BFF 部署位置。
- 尚未决定 Web 采用短期 token 内存注入还是由 BFF 代理 Core API；两者都必须遵守上述安全不变量。
- 在这些外部条件确定前，不实现供应商特定的 token endpoint、refresh 逻辑或退出 URL。
