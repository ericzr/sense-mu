/** Cloudflare Worker entry point for the SenseMu web application. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

declare const __SENSEMU_BUILD_RELEASE__: string;

interface Env {
  ASSETS?: Fetcher;
  DB?: D1Database;
  IMAGES?: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
  SENSEMU_PREVIEW_MODE?: string;
  NEXT_PUBLIC_SENSEMU_PREVIEW_MODE?: string;
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const assets = env.ASSETS;

    if (url.pathname === "/__sensemu/health") {
      return new Response(
        JSON.stringify({
          service: "sensemu-web",
          runtime: "cloudflare-worker",
          status: "ok",
          release: __SENSEMU_BUILD_RELEASE__,
          preview: env.SENSEMU_PREVIEW_MODE === "true",
          bindings: {
            assets: Boolean(assets),
            images: Boolean(env.IMAGES),
          },
        }),
        {
          headers: {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
            "x-sensemu-worker": "sense-mu",
          },
        },
      );
    }

    if (url.pathname === "/_vinext/image" && assets) {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      return handleImageOptimization(request, {
        fetchAsset: (path) => assets.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          if (!env.IMAGES) return new Response(body);
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
    }

    try {
      const response = await handler.fetch(request, env, ctx);
      const headers = new Headers(response.headers);
      const contentType = headers.get("content-type") ?? "";
      const isDocumentResponse =
        contentType.includes("text/html") ||
        contentType.includes("text/x-component") ||
        request.headers.get("rsc") === "1";

      headers.set("x-sensemu-worker", "sense-mu");
      headers.set("x-sensemu-release", __SENSEMU_BUILD_RELEASE__);
      headers.set("x-sensemu-preview-mode", env.SENSEMU_PREVIEW_MODE === "true" ? "true" : "false");
      if (isDocumentResponse) {
        headers.set("cache-control", "no-store, no-cache, must-revalidate");
        headers.set("pragma", "no-cache");
        headers.set("expires", "0");
      }
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    } catch (error) {
      console.error("SenseMu request failed", error);
      return new Response("SenseMu 暂时无法处理请求，请稍后重试。", {
        status: 503,
        headers: {
          "content-type": "text/plain; charset=utf-8",
          "cache-control": "no-store",
          "x-sensemu-worker": "sense-mu",
        },
      });
    }
  },
};

export default worker;
