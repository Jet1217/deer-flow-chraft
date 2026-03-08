import { getAuthHeaders } from "./token";
import { getBackendBaseURL } from "../config";

export interface AuthMe {
  user_id: string;
  is_user_scoped: boolean;
}

/**
 * Fetch current auth context from the backend.
 * - user_id: "default" when auth is disabled or no valid token; otherwise the authenticated user id.
 * - is_user_scoped: true when agents/skills/memory are isolated per user (valid token with non-default user).
 * Returns null on 401 (not authenticated when AUTH_ENABLED=true).
 */
export async function getAuthMe(): Promise<AuthMe | null> {
  const res = await fetch(`${getBackendBaseURL()}/api/auth/me`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return null;
  return res.json() as Promise<AuthMe>;
}
