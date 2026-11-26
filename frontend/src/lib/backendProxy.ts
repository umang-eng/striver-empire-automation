import { NextResponse } from "next/server";

export function getBackendBaseUrl(): string {
  return (process.env.PYTHON_WORKER_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
}

export function getBackendHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  const apiKey = (process.env.BACKEND_API_KEY || "").trim();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

export async function proxyJsonResponse(upstream: Response): Promise<NextResponse> {
  const text = await upstream.text();
  let data: unknown = { detail: "Unexpected backend response." };
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: upstream.ok ? "OK" : "Backend service error." };
  }
  return NextResponse.json(data, { status: upstream.status });
}
