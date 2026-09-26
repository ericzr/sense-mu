import { bffUnavailableResponse } from "../../../lib/auth-bff-contract";

export async function GET(): Promise<Response> {
  // Do not expose cookies, tokens, or guessed identity data when the BFF is
  // not configured. The caller can render a recoverable unavailable state.
  return bffUnavailableResponse();
}
