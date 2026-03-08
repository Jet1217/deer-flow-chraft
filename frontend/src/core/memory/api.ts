import { getAuthHeaders } from "../api/token";
import { getBackendBaseURL } from "../config";

import type { UserMemory } from "./types";

export async function loadMemory() {
  const memory = await fetch(`${getBackendBaseURL()}/api/memory`, {
    headers: getAuthHeaders(),
  });
  const json = await memory.json();
  return json as UserMemory;
}
