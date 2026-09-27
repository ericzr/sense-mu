#!/usr/bin/env node

import { fileURLToPath } from "node:url";

/** Verify the deployed public web surface without browser tooling. */

const DEFAULT_ROUTES = [
  "/",
  "/studio",
  "/studio/data",
  "/studio/training",
  "/services",
  "/marketplace",
  "/me",
];

function normalizeBaseUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "https:") throw new Error("SENSEMU_PRODUCTION_URL must use https");
  url.pathname = url.pathname.replace(/\/+$/, "");
  url.search = "";
  url.hash = "";
  return url;
}

function expectedRelease(value) {
  if (!value) return null;
  if (!/^[0-9a-f]{7,64}$/i.test(value)) throw new Error("SENSEMU_EXPECTED_RELEASE must be a Git SHA or SHA prefix");
  return value.toLowerCase();
}

function joinUrl(base, pathname) {
  return new URL(pathname.replace(/^\/+/, ""), base);
}

async function get(fetchImpl, url, timeoutMs) {
  return fetchImpl(url, {
    method: "GET",
    redirect: "manual",
    signal: AbortSignal.timeout(timeoutMs),
    headers: { accept: "application/json, text/html" },
  });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

export async function runPreflight({
  baseUrl,
  expectedRelease: expectedReleaseValue = null,
  allowPreview = false,
  timeoutMs = 15_000,
  routes = DEFAULT_ROUTES,
  fetchImpl = fetch,
} = {}) {
  const base = normalizeBaseUrl(baseUrl);
  const expected = expectedRelease(expectedReleaseValue);
  const healthResponse = await get(fetchImpl, joinUrl(base, "/__sensemu/health"), timeoutMs);
  assert(healthResponse.status === 200, `health probe returned HTTP ${healthResponse.status}`);

  let health;
  try {
    health = await healthResponse.json();
  } catch {
    throw new Error("health probe did not return JSON");
  }
  assert(health?.status === "ok", "health probe status is not ok");
  assert(health.runtime === "cloudflare-worker", "health probe is not a Cloudflare Worker");
  assert(health.bindings?.assets === true, "Worker assets binding is unavailable");
  assert(health.bindings?.images === true, "Worker images binding is unavailable");
  assert(typeof health.release === "string" && health.release.length >= 7, "health probe has no release");
  if (expected) assert(health.release.toLowerCase().startsWith(expected), `release ${health.release} does not match ${expected}`);
  if (!allowPreview) assert(health.preview === false, "deployment is still in preview mode");

  for (const route of routes) {
    const response = await get(fetchImpl, joinUrl(base, route), timeoutMs);
    assert(response.status >= 200 && response.status < 300, `${route} returned HTTP ${response.status}`);
    assert(response.headers.get("x-sensemu-worker") === "sense-mu", `${route} is not served by SenseMu Worker`);
  }
  return { release: health.release, preview: health.preview === true, routes: [...routes] };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const baseUrl = process.env.SENSEMU_PRODUCTION_URL;
  if (!baseUrl) {
    console.error("Missing SENSEMU_PRODUCTION_URL, for example https://cs.sensemu.com");
    process.exitCode = 2;
  } else {
    runPreflight({
      baseUrl,
      expectedRelease: process.env.SENSEMU_EXPECTED_RELEASE,
      allowPreview: process.env.SENSEMU_ALLOW_PREVIEW === "true",
    })
      .then((result) => {
        console.log(`SenseMu preflight passed: release=${result.release} preview=${result.preview ? "true" : "false"}`);
        console.log(`Routes checked: ${result.routes.join(", ")}`);
      })
      .catch((error) => {
        console.error(`SenseMu preflight failed: ${error instanceof Error ? error.message : String(error)}`);
        process.exitCode = 1;
      });
  }
}
