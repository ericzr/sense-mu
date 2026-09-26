/**
 * Provider-neutral server boundary for the first-party authentication BFF.
 *
 * This module deliberately does not perform an OIDC token exchange. Until the
 * production provider and deployment binding are selected, the routes must
 * fail closed instead of pretending that a browser or Sites identity is a
 * Core API session.
 */

import { safeReturnTo } from "./auth-config";

export const BFF_SESSION_COOKIE = "__Host-sensemu_session";

const RESERVED_AUTH_PATHS = new Set([
  "/auth/login",
  "/auth/callback",
  "/auth/session",
  "/auth/logout",
]);

export type BffConfigurationState = "disabled" | "incomplete" | "unsafe" | "blocked" | "ready";

export type BffConfig = {
  configured: boolean;
  implementationReady: boolean;
  state: BffConfigurationState;
  missing: string[];
  invalid: string[];
};

const REQUIRED_SERVER_SETTINGS = [
  ["SENSEMU_BFF_ENABLED", "BFF enablement"],
  ["SENSEMU_BFF_IMPLEMENTATION_READY", "BFF implementation readiness"],
  ["SENSEMU_OIDC_ISSUER", "OIDC issuer"],
  ["SENSEMU_OIDC_CLIENT_ID", "OIDC client ID"],
  ["SENSEMU_OIDC_AUTHORIZATION_ENDPOINT", "OIDC authorization endpoint"],
  ["SENSEMU_OIDC_TOKEN_ENDPOINT", "OIDC token endpoint"],
  ["SENSEMU_OIDC_REDIRECT_URI", "OIDC redirect URI"],
  ["SENSEMU_SESSION_STORE", "session store"],
  ["SENSEMU_SESSION_SECRET", "session secret"],
] as const;

const ALLOWED_SESSION_STORES = new Set(["redis", "kv", "d1", "managed"]);

function serverUrl(name: string): URL | null {
  const value = serverSetting(name);
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.hostname !== "localhost") return null;
    if (url.username || url.password || url.hash) return null;
    return url;
  } catch {
    return null;
  }
}

function hasStrongSessionSecret(value: string | undefined): boolean {
  if (!value) return false;
  const normalized = value.toLowerCase();
  if (normalized.includes("local-only") || normalized.includes("change-me")) return false;
  return new TextEncoder().encode(value).byteLength >= 32;
}

function serverSetting(name: string): string | undefined {
  return process.env[name]?.trim() || undefined;
}

export function getBffConfig(): BffConfig {
  const missing = REQUIRED_SERVER_SETTINGS
    .filter(([name]) => !serverSetting(name))
    .map(([, label]) => label);
  const invalid: string[] = [];
  const enabled = serverSetting("SENSEMU_BFF_ENABLED") === "true";
  const implementationReady = serverSetting("SENSEMU_BFF_IMPLEMENTATION_READY") === "true";
  const sessionStore = serverSetting("SENSEMU_SESSION_STORE");

  if (!enabled && !missing.includes("BFF enablement")) missing.push("BFF enablement");
  if (!implementationReady && !missing.includes("BFF implementation readiness")) {
    missing.push("BFF implementation readiness");
  }
  if (sessionStore && !ALLOWED_SESSION_STORES.has(sessionStore)) {
    invalid.push("session store");
  }

  for (const name of [
    "SENSEMU_OIDC_ISSUER",
    "SENSEMU_OIDC_AUTHORIZATION_ENDPOINT",
    "SENSEMU_OIDC_TOKEN_ENDPOINT",
    "SENSEMU_OIDC_REDIRECT_URI",
  ]) {
    if (serverSetting(name) && !serverUrl(name)) invalid.push(name);
  }

  const redirectUri = serverUrl("SENSEMU_OIDC_REDIRECT_URI");
  if (redirectUri && (redirectUri.pathname !== "/auth/callback" || redirectUri.search || redirectUri.hash)) {
    invalid.push("OIDC redirect URI path");
  }
  if (serverSetting("SENSEMU_SESSION_SECRET") && !hasStrongSessionSecret(serverSetting("SENSEMU_SESSION_SECRET"))) {
    invalid.push("session secret");
  }

  const state: BffConfigurationState = !enabled
    ? "disabled"
    : invalid.length > 0
      ? "unsafe"
      : missing.length > 0
        ? implementationReady ? "incomplete" : "blocked"
        : "ready";

  return {
    configured: state === "ready",
    implementationReady,
    state,
    missing,
    invalid,
  };
}

export function safeBffReturnTo(value: string): string {
  const safePath = safeReturnTo(value);
  let pathname: string;
  try {
    pathname = new URL(safePath, "https://sensemu.local").pathname;
  } catch {
    return "/";
  }
  return RESERVED_AUTH_PATHS.has(pathname) ? "/" : safePath;
}

function noStoreHeaders(): Headers {
  return new Headers({
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
  });
}

export function bffUnavailableResponse(): Response {
  const headers = noStoreHeaders();
  const config = getBffConfig();
  return new Response(
    JSON.stringify({
      error: "auth_unavailable",
      detail: "同源身份 BFF 尚未完成配置，当前不会建立登录会话",
      configuration_state: config.state,
      missing: config.missing,
      invalid: config.invalid,
    }),
    { status: 503, headers },
  );
}

export function bffBadRequestResponse(detail: string): Response {
  const headers = noStoreHeaders();
  return new Response(JSON.stringify({ error: "invalid_auth_request", detail }), {
    status: 400,
    headers,
  });
}

export function clearBffSessionResponse(): Response {
  const headers = noStoreHeaders();
  headers.set(
    "set-cookie",
    `${BFF_SESSION_COOKIE}=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax`,
  );
  return new Response(null, { status: 204, headers });
}
