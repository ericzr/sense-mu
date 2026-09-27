import assert from "node:assert/strict";
import test from "node:test";

import { runPreflight } from "../scripts/production-preflight.mjs";

function mockFetch({ preview = false, release = "abcdef1234567", routeStatus = 200 } = {}) {
  return async (input) => {
    const url = new URL(input);
    if (url.pathname === "/__sensemu/health") {
      return new Response(JSON.stringify({
        status: "ok",
        runtime: "cloudflare-worker",
        release,
        preview,
        bindings: { assets: true, images: true },
      }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("ok", {
      status: routeStatus,
      headers: { "x-sensemu-worker": "sense-mu" },
    });
  };
}

test("production preflight checks the Worker and all public routes", async () => {
  const result = await runPreflight({
    baseUrl: "https://preview.example.test",
    expectedRelease: "abcdef1",
    fetchImpl: mockFetch(),
  });
  assert.equal(result.release, "abcdef1234567");
  assert.deepEqual(result.routes, ["/", "/studio", "/studio/data", "/studio/training", "/services", "/marketplace", "/me"]);
});

test("production preflight rejects preview deployments unless explicitly allowed", async () => {
  await assert.rejects(
    runPreflight({ baseUrl: "https://preview.example.test", fetchImpl: mockFetch({ preview: true }) }),
    /still in preview mode/,
  );
  const result = await runPreflight({
    baseUrl: "https://preview.example.test",
    allowPreview: true,
    fetchImpl: mockFetch({ preview: true }),
  });
  assert.equal(result.preview, true);
});

test("production preflight rejects stale releases and failed routes", async () => {
  await assert.rejects(
    runPreflight({ baseUrl: "https://preview.example.test", expectedRelease: "deadbee", fetchImpl: mockFetch() }),
    /does not match deadbee/,
  );
  await assert.rejects(
    runPreflight({ baseUrl: "https://preview.example.test", fetchImpl: mockFetch({ routeStatus: 503 }) }),
    /returned HTTP 503/,
  );
});

