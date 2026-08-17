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
- `npm run typecheck`：检查 TypeScript 与 Cloudflare Worker 类型
- `npm run lint`：执行 ESLint

业务数据不直连 D1，所有写入经过 SenseMu API，以 PostgreSQL 为唯一事实源。`.openai/hosting.json` 和 Sites Vite 插件仅负责 Web 产物的本地预览与托管适配。
