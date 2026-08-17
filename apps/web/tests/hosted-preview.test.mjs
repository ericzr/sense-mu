import assert from "node:assert/strict";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders a consistent hosted demo overview", async () => {
  const response = await render();
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<h1>工作台<\/h1>/);
  assert.match(html, /工地安全穿戴数据/);
  assert.match(html, /12 个素材/);
  assert.match(html, /金属表面缺陷数据/);
  assert.match(html, /8 个素材/);
  assert.match(html, /3 个版本/);
  assert.doesNotMatch(html, /1,248 个素材|594 个素材/);
});
