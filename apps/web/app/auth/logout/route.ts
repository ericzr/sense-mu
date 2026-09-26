import { clearBffSessionResponse } from "../../../lib/auth-bff-contract";

export async function POST(): Promise<Response> {
  // Clearing the local session is safe and idempotent even before a provider
  // logout endpoint is selected. A configured BFF should revoke upstream
  // state before returning the same response.
  return clearBffSessionResponse();
}
