import {
  bffBadRequestResponse,
  bffUnavailableResponse,
  getBffConfig,
  safeBffReturnTo,
} from "../../../lib/auth-bff-contract";

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const returnTo = url.searchParams.get("return_to") ?? "/";
  const safePath = safeBffReturnTo(returnTo);
  if (safePath === "/" && returnTo !== "/") {
    return bffBadRequestResponse("return_to 必须是同源相对路径");
  }

  // The actual authorization redirect belongs here once the provider is
  // selected. Never redirect to a guessed endpoint or create a fake session.
  if (!getBffConfig().configured) return bffUnavailableResponse();
  return bffUnavailableResponse();
}
