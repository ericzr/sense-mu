export type WebAuthMode = "development" | "oidc";

export type WebAuthConfig = {
  mode: WebAuthMode;
  configured: boolean;
  authorizationEndpoint: string | null;
  clientId: string | null;
  redirectUri: string | null;
  loginUrl: string | null;
  scope: string;
  missing: string[];
};

const PUBLIC_AUTH_FIELDS = [
  ["NEXT_PUBLIC_SENSEMU_OIDC_AUTHORIZATION_ENDPOINT", "authorization endpoint"],
  ["NEXT_PUBLIC_SENSEMU_OIDC_CLIENT_ID", "client ID"],
  ["NEXT_PUBLIC_SENSEMU_OIDC_REDIRECT_URI", "redirect URI"],
] as const;

function readUrl(value: string | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.hostname !== "localhost") return null;
    return url.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}

function readLoginUrl(value: string | undefined): string | null {
  if (!value) return null;
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  return readUrl(value);
}

function safeReturnTo(value: string): string {
  if (!value.startsWith("/") || value.startsWith("//")) return "/";
  try {
    const url = new URL(value, "https://sensemu.local");
    if (url.origin !== "https://sensemu.local") return "/";
    return `${url.pathname}${url.search}`;
  } catch {
    return "/";
  }
}

export function getAuthLoginHref(loginUrl: string | null, returnTo: string): string | null {
  if (!loginUrl) return null;
  const safePath = safeReturnTo(returnTo);
  try {
    const url = new URL(loginUrl, "https://sensemu.local");
    url.searchParams.set("return_to", safePath);
    if (loginUrl.startsWith("/") && !loginUrl.startsWith("//")) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
    return url.toString();
  } catch {
    return loginUrl;
  }
}

export function getWebAuthConfig(): WebAuthConfig {
  const mode = process.env.NEXT_PUBLIC_SENSEMU_AUTH_MODE === "development"
    ? "development"
    : "oidc";
  const values = {
    NEXT_PUBLIC_SENSEMU_OIDC_AUTHORIZATION_ENDPOINT:
      readUrl(process.env.NEXT_PUBLIC_SENSEMU_OIDC_AUTHORIZATION_ENDPOINT),
    NEXT_PUBLIC_SENSEMU_OIDC_CLIENT_ID: process.env.NEXT_PUBLIC_SENSEMU_OIDC_CLIENT_ID || null,
    NEXT_PUBLIC_SENSEMU_OIDC_REDIRECT_URI:
      readUrl(process.env.NEXT_PUBLIC_SENSEMU_OIDC_REDIRECT_URI),
    NEXT_PUBLIC_SENSEMU_AUTH_LOGIN_URL:
      readLoginUrl(process.env.NEXT_PUBLIC_SENSEMU_AUTH_LOGIN_URL),
  };
  const missing = mode === "oidc"
    ? PUBLIC_AUTH_FIELDS
      .filter(([key]) => !values[key])
      .map(([, label]) => label)
    : [];

  return {
    mode,
    configured: mode === "development" || missing.length === 0,
    authorizationEndpoint: values.NEXT_PUBLIC_SENSEMU_OIDC_AUTHORIZATION_ENDPOINT,
    clientId: values.NEXT_PUBLIC_SENSEMU_OIDC_CLIENT_ID,
    redirectUri: values.NEXT_PUBLIC_SENSEMU_OIDC_REDIRECT_URI,
    loginUrl: values.NEXT_PUBLIC_SENSEMU_AUTH_LOGIN_URL,
    scope: process.env.NEXT_PUBLIC_SENSEMU_OIDC_SCOPE || "openid profile email",
    missing,
  };
}
