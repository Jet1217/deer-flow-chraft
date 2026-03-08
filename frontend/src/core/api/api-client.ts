"use client";

import { Client as LangGraphClient } from "@langchain/langgraph-sdk/client";

import { getLangGraphBaseURL } from "../config";
import { getAuthHeaders } from "./token";

let _singleton: LangGraphClient | null = null;
export function getAPIClient(isMock?: boolean): LangGraphClient {
  _singleton ??= new LangGraphClient({
    apiUrl: getLangGraphBaseURL(isMock),
    defaultHeaders: getAuthHeaders(),
  });
  return _singleton;
}

export function resetAPIClient(): void {
  _singleton = null;
}
