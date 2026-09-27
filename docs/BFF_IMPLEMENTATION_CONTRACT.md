# SenseMu 同源身份 BFF 实现契约

这份文档是 Web 与后端协同实现正式登录前的边界合同。当前 Web 已提供 `/auth/*` 的 fail-closed 占位路由：身份供应商、服务端会话或实现就绪标记未配置时，登录、回调和会话查询返回 `503`，不会伪造登录成功；退出始终幂等清理本地会话 Cookie。

## 业务边界

| 路由 | 方法 | 成功语义 | 未配置/失败语义 |
| --- | --- | --- | --- |
| `/auth/login?return_to=/...` | `GET` | 创建 state、nonce、PKCE，跳转到托管身份供应商 | `400`（开放重定向或非法参数）/ `503`（BFF 未配置） |
| `/auth/callback?code=...&state=...` | `GET` | 校验一次性 state、nonce、授权码并建立服务端会话，然后回到安全的 `return_to` | `400`（缺参数、provider error、重复 state）/ `503`（BFF 未配置） |
| `/auth/session` | `GET` | 返回非敏感身份摘要和会话过期时间 | `401`（无会话）/ `503`（BFF 不可用） |
| `/auth/logout` | `POST` | 先清理服务端会话，再按供应商能力执行上游退出 | `204` 且仍清理本地 Cookie；退出必须幂等 |

所有 JSON 错误响应都必须设置 `Cache-Control: no-store`。错误响应只能包含稳定的错误码和用户可读说明，不得回显 `code`、`state`、`return_to` 原值、Cookie 或 token。

## 服务端配置

以下配置只允许存在于 BFF 运行时，不得使用 `NEXT_PUBLIC_` 前缀，也不得进入浏览器 bundle：

| 变量 | 用途 |
| --- | --- |
| `SENSEMU_BFF_ENABLED=true` | 显式打开 BFF，缺失时必须 fail closed |
| `SENSEMU_BFF_IMPLEMENTATION_READY=true` | 只有 provider-specific callback、会话存储和 staging E2E 完成后才能打开；仅填写 OIDC 地址不会解除 fail closed |
| `SENSEMU_OIDC_ISSUER` | 供应商 issuer，用于发现和 JWT 校验 |
| `SENSEMU_OIDC_CLIENT_ID` | OIDC client id |
| `SENSEMU_OIDC_AUTHORIZATION_ENDPOINT` | 授权端点 |
| `SENSEMU_OIDC_TOKEN_ENDPOINT` | 授权码交换端点 |
| `SENSEMU_OIDC_REDIRECT_URI` | 同源 `/auth/callback` 地址 |
| `SENSEMU_SESSION_STORE` | 服务端会话存储类型：`redis`、`kv`、`d1` 或托管会话；禁止使用进程内存 |
| `SENSEMU_SESSION_SECRET` | 服务端会话签名/加密密钥 |

首期可使用 Redis、D1 或供应商托管会话存储，但必须满足同样的会话不变量。不要把 refresh token 放入 D1 明文、浏览器 Cookie、`localStorage` 或 `sessionStorage`。

### 配置预检状态

Web BFF 在运行时对服务端配置执行预检，错误只返回不敏感的状态和字段名称：

- `disabled`：`SENSEMU_BFF_ENABLED` 未显式打开。
- `incomplete`：已打开但缺少身份端点、会话存储或密钥。
- `unsafe`：端点不是 HTTPS（本地 localhost 除外）、回调路径不是 `/auth/callback`、会话存储类型不支持，或密钥短于 32 字节/仍是本地占位值。
- `blocked`：配置基本完整，但 `SENSEMU_BFF_IMPLEMENTATION_READY` 仍为 `false`，表示供应商专属实现或 staging 验收尚未完成。
- `ready`：所有配置预检通过；这只表示可以进入真实实现联调，不替代登录、成员权限和退出 E2E。

`SENSEMU_BFF_IMPLEMENTATION_READY` 是独立的上线保险丝。没有它，即使误把 OIDC 地址和密钥注入部署环境，路由仍然返回 `503`，不会半启用一个没有 state/nonce/PKCE 和会话存储的登录流程。

## 安全不变量

1. `state`、`nonce`、`code_verifier` 必须随机生成、与浏览器会话绑定、一次性消费，并设置短过期时间。
2. `return_to` 只接受以 `/` 开头且不是 `//` 的同源相对路径；认证保留路径不能作为回跳目标。
3. 回调必须校验 issuer、audience、签名、`exp`、`nonce`、授权码交换结果和 PKCE verifier。Core API 仍独立校验 Bearer JWT 与工作区成员关系。
4. 会话 Cookie 使用 `__Host-sensemu_session`、`HttpOnly`、`Secure`、`Path=/`、`SameSite=Lax`（需要更严格 CSRF 边界时使用 `Strict`），并设置明确过期时间。
5. 日志不得输出授权码、state、nonce、code verifier、access token、refresh token、完整 Cookie 或原始 `return_to`。
6. Core API 的 `401`、账号停用、工作区移除和角色变化必须即时生效；不能仅依赖 Web 会话过期。

## 与 Web 的协作方式

Web 端只把 `/auth/login` 当作登录入口，并根据 Core API 的 `401/403/5xx` 分别展示“需要登录”“权限不足”“服务暂不可用”。Web 不应自行拼接供应商 URL，也不应读取服务端 Cookie 内容。

后端接入真实供应商时，替换 `apps/web/app/auth/{login,callback,session,logout}/route.ts` 中的 fail-closed 分支即可，保留路由、状态码、Cookie 属性和日志约束。若 BFF 采用代理模式，浏览器继续请求同源 `/api/*`，由 BFF 在服务端注入短期 Bearer JWT；若采用短期内存注入，也不得把 refresh token 暴露到 Web。

## 联调验收

- 未配置 BFF：登录和回调不会跳转到猜测的供应商地址，均返回 `503`；会话响应不包含 token 字段。
- 恶意 `return_to=https://evil.example` 或 `//evil.example`：返回 `400`，响应不回显恶意地址。
- 缺少 `code/state`、重复 state、过期 state、nonce 不匹配、PKCE 不匹配：均拒绝且不落库 token。
- 退出重复调用：均返回 `204`，并清理 `__Host-sensemu_session`。
- 真实 OIDC staging：登录、邀请、成员角色变更、停用、跨工作区访问和上游退出全部完成 E2E 后，才打开 production BFF。
