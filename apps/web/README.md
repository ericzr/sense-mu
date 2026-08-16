# SenseMu Web

SenseMu 产品端，基于 React 19、TypeScript、Tailwind CSS 4 和 vinext。

## 开发

```bash
npm install
cp .env.example .env.local
npm run dev
```

默认地址是 `http://localhost:3000`。`SENSEMU_API_URL` 指向核心 FastAPI 服务；未配置或服务暂时不可用时，首页使用与 API 同形的本地数据，保证设计与前端开发不被阻断。

## 命令

- `npm run dev`：启动本地开发服务
- `npm run build`：构建生产产物
- `npm test`：生产构建后验证总览与 Studio 的 SSR 输出
- `npm run typecheck`：检查 TypeScript 与 Cloudflare Worker 类型
- `npm run lint`：执行 ESLint

业务数据不直连 D1，所有写入经过 SenseMu API，以 PostgreSQL 为唯一事实源。`.openai/hosting.json` 和 Sites Vite 插件仅负责 Web 产物的本地预览与托管适配。
