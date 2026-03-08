"use client";

import { useState } from "react";

import { resetAPIClient } from "@/core/api/api-client";
import { clearToken, getToken, setToken } from "@/core/api/token";
import { getBackendBaseURL, getLangGraphBaseURL } from "@/core/config";

interface TestResult {
  name: string;
  status: "idle" | "loading" | "ok" | "error";
  data?: unknown;
  error?: string;
}

export default function AuthTestPage() {
  const [tokenInput, setTokenInput] = useState(getToken() ?? "");
  const [currentToken, setCurrentToken] = useState(getToken());
  const [results, setResults] = useState<TestResult[]>([]);

  function applyToken() {
    if (tokenInput.trim()) {
      setToken(tokenInput.trim());
    } else {
      clearToken();
    }
    resetAPIClient();
    setCurrentToken(getToken());
    setResults([]);
  }

  function clearAll() {
    clearToken();
    resetAPIClient();
    setTokenInput("");
    setCurrentToken(null);
    setResults([]);
  }

  function setResult(name: string, update: Partial<TestResult>) {
    setResults((prev) => {
      const idx = prev.findIndex((r) => r.name === name);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], ...update };
        return next;
      }
      return [...prev, { name, status: "idle", ...update }];
    });
  }

  function authHeaders(): Record<string, string> {
    const token = getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function runTest(
    name: string,
    url: string,
    options?: RequestInit,
  ) {
    setResult(name, { status: "loading" });
    try {
      const res = await fetch(url, {
        ...options,
        headers: { ...authHeaders(), ...(options?.headers ?? {}) },
      });
      const data = await res.json().catch(() => res.statusText);
      if (res.ok) {
        setResult(name, { status: "ok", data });
      } else {
        setResult(name, { status: "error", error: JSON.stringify(data) });
      }
    } catch (e) {
      setResult(name, { status: "error", error: String(e) });
    }
  }

  async function runAllTests() {
    const base = getBackendBaseURL();
    const lg = getLangGraphBaseURL();
    await runTest("GET /api/auth/me", `${base}/api/auth/me`);
    await runTest("GET /api/memory", `${base}/api/memory`);
    await runTest("GET /api/models", `${base}/api/models`);
    await runTest("GET /api/agents", `${base}/api/agents`);
    await runTest("GET /api/skills", `${base}/api/skills`);
    await runTest(
      "POST /threads (LangGraph)",
      `${lg}/threads`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
    );
    await runTest(
      "POST /threads/search (LangGraph)",
      `${lg}/threads/search`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
    );
  }

  const statusColor: Record<string, string> = {
    idle: "text-gray-400",
    loading: "text-yellow-400",
    ok: "text-green-400",
    error: "text-red-400",
  };

  const statusIcon: Record<string, string> = {
    idle: "○",
    loading: "⟳",
    ok: "✓",
    error: "✗",
  };

  // Decode JWT payload for display (no verification, just parsing)
  function decodePayload(token: string): string {
    try {
      const parts = token.split(".");
      if (parts.length !== 3) return "invalid format";
      const payload = JSON.parse(atob(parts[1]!));
      return JSON.stringify(payload, null, 2);
    } catch {
      return "failed to decode";
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 p-8 font-mono text-sm text-gray-100">
      <h1 className="mb-6 text-xl font-bold text-white">Auth Test Page</h1>

      {/* Token Input */}
      <section className="mb-6 rounded-lg border border-gray-700 p-4">
        <h2 className="mb-3 font-semibold text-gray-300">JWT Token</h2>
        <textarea
          className="mb-3 w-full rounded border border-gray-600 bg-gray-900 p-2 text-xs text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
          rows={3}
          placeholder="Paste Bearer token here (without 'Bearer ' prefix)..."
          value={tokenInput}
          onChange={(e) => setTokenInput(e.target.value)}
        />
        <div className="flex gap-2">
          <button
            className="rounded bg-blue-600 px-4 py-1.5 text-white hover:bg-blue-700"
            onClick={applyToken}
          >
            Apply Token
          </button>
          <button
            className="rounded bg-gray-700 px-4 py-1.5 text-gray-200 hover:bg-gray-600"
            onClick={clearAll}
          >
            Clear (logout)
          </button>
        </div>

        {currentToken && (
          <div className="mt-3 rounded border border-gray-700 bg-gray-900 p-3">
            <p className="mb-1 text-xs text-gray-400">Current token payload:</p>
            <pre className="text-xs text-green-300">{decodePayload(currentToken)}</pre>
          </div>
        )}
        {!currentToken && (
          <p className="mt-3 text-xs text-yellow-400">No token set — requests will be unauthenticated</p>
        )}
      </section>

      {/* Run Tests */}
      <section className="mb-6 rounded-lg border border-gray-700 p-4">
        <h2 className="mb-3 font-semibold text-gray-300">API Tests</h2>
        <button
          className="rounded bg-green-700 px-4 py-1.5 text-white hover:bg-green-600"
          onClick={runAllTests}
        >
          Run All Tests
        </button>

        {results.length > 0 && (
          <div className="mt-4 space-y-3">
            {results.map((r) => (
              <div key={r.name} className="rounded border border-gray-700 bg-gray-900 p-3">
                <div className="flex items-center gap-2">
                  <span className={statusColor[r.status]}>{statusIcon[r.status]}</span>
                  <span className="font-semibold text-gray-200">{r.name}</span>
                  <span className={`text-xs ${statusColor[r.status]}`}>{r.status}</span>
                </div>
                {r.status === "error" && (
                  <pre className="mt-2 text-xs text-red-300">{r.error}</pre>
                )}
                {r.status === "ok" && (
                  <pre className="mt-2 max-h-40 overflow-auto text-xs text-gray-300">
                    {JSON.stringify(r.data, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Quick Token Generator */}
      <section className="rounded-lg border border-gray-700 p-4">
        <h2 className="mb-2 font-semibold text-gray-300">Quick Test Tokens</h2>
        <p className="mb-3 text-xs text-gray-500">
          These tokens are signed with the current <code className="text-yellow-300">JWT_SECRET_KEY</code> from .env.
        </p>
        <div className="space-y-2">
          {[
            { user: "alice", token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsImV4cCI6MTgwNDM0NjAwNX0.aXdAVtdJLKVFIBdrZ8HL7hvHeX8MoF0lffufXuUDs48" },
            { user: "bob", token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJib2IiLCJleHAiOjE4MDQzNDYwMDV9.-iLb4xCoruQi_VyEp4SpGqZJm8an8m5NAcEoHXtpG1s" },
          ].map(({ user, token }) => (
            <div key={user} className="flex items-center gap-3">
              <button
                className="rounded bg-gray-700 px-3 py-1 text-xs text-gray-200 hover:bg-gray-600"
                onClick={() => {
                  setTokenInput(token);
                  setToken(token);
                  resetAPIClient();
                  setCurrentToken(token);
                  setResults([]);
                }}
              >
                Use {user}
              </button>
              <span className="truncate text-xs text-gray-500">{token.slice(0, 40)}...</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
