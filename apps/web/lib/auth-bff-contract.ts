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

type BffConfig = {
  configured: boolean;
  missing: string[];
};

const REQUIRED_SERVER_SETTINGS = [
  ["SENSEMU_BFF_ENABLED", "BFF enablement"],
  ["SENSEMU_OIDC_ISSUER", "OIDC issuer"],
  ["SENSEMU_OIDC_CLIENT_ID", "OIDC client ID"],
  ["SENSEMU_OIDC_AUTHORIZATION_ENDPOINT", "OIDC authorization endpoint"],
  ["SENSEMU_OIDC_TOKEN_ENDPOINT", "OIDC token endpoint"],
  ["SENSEMU_OIDC_REDIRECT_URI", "OIDC redirect URI"],
  ["SENSEMU_SESSION_SECRET", "session secret"],
] as const;

function serverSetting(name: string): string | undefined {
  return process.env[name]?.trim() || undefined;
}

export function getBffConfig(): BffConfig {
  const missing = REQUIRED_SERVER_SETTINGS
    .filter(([name]) => !serverSetting(name))
    .map(([, label]) => label);
  if (serverSetting("SENSEMU_BFF_ENABLED") !== "true" && !missing.includes("BFF enablement")) {
    missing.push("BFF enablement");
  }

  return {
    configured: missing.length === 0 && serverSetting("SENSEMU_BFF_ENABLED") === "true",
    missing,
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
  return new Response(
    JSON.stringify({
      error: "auth_unavailable",
      detail: "同源身份 BFF 尚未完成配置，当前不会建立登录会话",
      missing: getBffConfig().missing,
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
