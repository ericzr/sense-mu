# SenseMu Web

SenseMu 产品端，基于 React 19、TypeScript、Tailwind CSS 4 和 vinext。

## 开发

```bash
npm install
cp .env.example .env.local
npm run dev
```

默认地址是 `http://localhost:3000`。`SENSEMU_API_URL` 指向核心 FastAPI 服务。托管演示站通过 `SENSEMU_PREVIEW_MODE=true` 使用与 API 同形的只读演示数据；页面会显示“演示数据”标识，新增和修改不会保存，也不代表真实训练结果。正式环境必须配置真实 API，并保持演示模式关闭。

## 命令

- `npm run dev`：启动本地开发服务
- `npm run build`：构建生产产物
- `npm test`：生产构建后验证总览与 Studio 的 SSR 输出
- `npm run test:e2e`：以演示数据启动本地生产构建，并执行 Playwright 浏览器回归
- `npm run typecheck`：检查 TypeScript 与 Cloudflare Worker 类型
- `npm run lint`：执行 ESLint

`test:e2e` 默认使用本机 Chrome；CI 使用 Playwright Chromium，并需在任务中先执行 `npx playwright install --with-deps chromium`。该套件覆盖数据与标注、训练报告、实时分析边界和市场筛选，同时确认托管演示站不会持久化写操作。上传、冻结版本、训练创建、发布与一次性密钥展示必须连接本地 Core API 与隔离测试数据库后再做写入验收，不能由只读演示站替代。

业务数据不直连 D1，所有写入经过 SenseMu API，以 PostgreSQL 为唯一事实源。`.openai/hosting.json` 和 Sites Vite 插件仅负责 Web 产物的本地预览与托管适配。
