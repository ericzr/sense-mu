import {
  bffBadRequestResponse,
  bffUnavailableResponse,
  getBffConfig,
} from "../../../lib/auth-bff-contract";

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const error = url.searchParams.get("error");

  if (error || !code || !state) {
    return bffBadRequestResponse("OIDC 回调缺少一次性 code 或 state");
  }

  // State/nonce/PKCE validation and code exchange are intentionally not
  // inferred from query parameters. A configured BFF implementation must
  // replace this fail-closed branch with server-side session-bound checks.
  if (!getBffConfig().configured) return bffUnavailableResponse();
  return bffUnavailableResponse();
}
