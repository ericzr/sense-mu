# Cloudflare 部署手册

SenseMu 的产品端不是纯静态站点，而是基于 Vinext 的服务端渲染应用，并包含 Cloudflare Worker 运行时和同源 API 边界。生产部署应使用 Cloudflare Workers（Cloudflare 控制台目前将相关入口归在 Workers & Pages 下），不能把 `dist/` 当成普通静态目录上传到 GitHub Pages。

## 推荐连接

- 源码：`https://github.com/ericzr/sense-mu`
- 生产分支：`main`
- 构建目录：`apps/web`
- Node.js：仓库 `.nvmrc` 指定的 24.19.0
- 构建命令：`npm ci && npm run build`
- 部署目标：Cloudflare Workers / Vinext Worker

Cloudflare 控制台中的服务名可以与仓库名一致，但服务名不是公开访问地址。部署完成后，应在该服务的生产部署详情或 Domains & Routes 中复制实际的 `workers.dev`、`pages.dev` 或自定义域名作为验收地址，不要根据名称猜测域名。

### Workers Builds 配置

在 `sense-mu` 服务的 Settings → Build 中使用以下值。这里的根目录是仓库根目录下的路径，不要填写 `docs`，也不要把它当成静态 Pages 站点发布：

```text
Root directory: /apps/web
Build command: npm ci && npm run build
Deploy command: npx wrangler deploy --config wrangler.jsonc
Production branch: main
```

`workers_dev: true` 已写入应用配置，确保部署继续提供 `workers.dev` 访问地址；如果部署详情仍没有 `workers.dev` 域名，说明 Cloudflare 服务的域名开关或账户级 Workers 访问被关闭，需要在控制台的 Domains & Routes 中重新启用或绑定自定义域名。

保存设置后，重新触发一次 `main` 构建。成功的部署详情应显示为可执行 Worker；如果设置页仍提示“仅静态资源”，说明旧部署尚未被新构建替换。`wrangler.jsonc` 随应用源码维护 Worker 入口、`ASSETS` 静态资源绑定和 `IMAGES` 图像绑定，避免构建产物路径变化导致线上运行时失效。`docs/` 只用于 GitHub Pages 的文档入口，不能作为 SenseMu 工作台的生产输出目录。

## 环境边界

### 公开演示环境

没有 Core API、数据库、对象存储和推理服务器时，可以使用：

```text
SENSEMU_PREVIEW_MODE=true
NEXT_PUBLIC_SENSEMU_PREVIEW_MODE=true
```

该模式只读，页面必须显示“演示数据”，写入动作必须明确提示未连接真实服务；它不代表训练、推理或支付已经完成。

### 生产环境

生产部署必须关闭演示模式，并配置真实后端：

```text
SENSEMU_PREVIEW_MODE=false
NEXT_PUBLIC_SENSEMU_PREVIEW_MODE=false
SENSEMU_API_URL=<同源 BFF 或 Core API 地址>
NEXT_PUBLIC_SENSEMU_AUTH_MODE=oidc
NEXT_PUBLIC_SENSEMU_AUTH_LOGIN_URL=<BFF 登录入口>
```

OIDC 的 issuer、audience、JWKS、授权码交换、刷新令牌和安全会话 cookie 只允许在 BFF/服务端配置，不能放入浏览器变量。身份供应商确定前，不要把演示站当成真实登录环境。

## 构建与验收

每次发布前，应在与 Cloudflare 相同的 Node 主版本下执行：

```bash
cd apps/web
npm ci
npm run typecheck
npm run lint
npm run api:types:check
npm test
```

发布后用 Cloudflare 生产域名检查以下路径：

```text
/
/studio
/studio/data
/studio/training
/services
/marketplace
/me
```

先检查部署探针，再打开页面：

```text
/__sensemu/health
```

探针必须返回 JSON，且包含 `"runtime":"cloudflare-worker"`、`"bindings":{"assets":true,"images":true}` 和当前 `release`。如果返回 GitHub Pages 的 HTML、404 或没有 `x-sensemu-worker` 响应头，说明生产域名仍指向旧静态部署；这时不要继续排查前端路由，应在 Workers Builds 将根目录改为 `/apps/web` 并重新部署 `main`。

重点确认：服务端页面返回 200、刷新深路径不回退到 404、演示数据标识与环境一致、API 失败显示为明确状态、没有把完整密钥或对象存储地址渲染到页面。

## 回滚与版本核对

1. 先记录 GitHub `main` 的 commit SHA。
2. 在 Cloudflare 生产部署详情确认构建使用相同 SHA。
3. 出现问题时优先回滚到上一份已验证的生产部署，不直接修改线上变量掩盖构建问题。
4. 回滚后重新检查上述深路径和核心 API 状态。

GitHub Actions 当前负责质量检查；Cloudflare 面板负责部署。后续如果要改为 GitHub 自动部署，应使用 Cloudflare API Token、Account ID 和明确的生产环境保护规则，并将部署动作限制在已通过质量检查的 `main` 提交上。

## 不应继续使用的地址

`chatgpt.site` 是旧的 Sites 预览地址，不是当前 Cloudflare 服务的正式入口。它出现 Cloudflare 边缘拦截时，不应通过修改业务代码解决，也不应继续放在产品或 GitHub 入口中。
