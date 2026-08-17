let accessToken: string | null = null;

/**
 * The web client only keeps an access token in memory. Refresh tokens belong
 * in a server-side BFF session and must never be written to browser storage.
 */
export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string): void {
  accessToken = token.trim() || null;
}

export function clearAccessToken(): void {
  accessToken = null;
}
