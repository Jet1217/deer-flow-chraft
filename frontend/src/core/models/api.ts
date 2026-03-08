import { getAuthHeaders } from "../api/token";
import { getBackendBaseURL } from "../config";

import type { Model } from "./types";

export async function loadModels() {
  const res = await fetch(`${getBackendBaseURL()}/api/models`, {
    headers: getAuthHeaders(),
  });
  const { models } = (await res.json()) as { models: Model[] };
  return models;
}
