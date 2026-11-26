import { NextRequest, NextResponse } from "next/server";
import {
  getBackendBaseUrl,
  getBackendHeaders,
  isWorkerConfigured,
  proxyJsonResponse,
} from "@/lib/backendProxy";
import { validateTaskMessage } from "@/lib/validation";

export async function POST(request: NextRequest) {
  let body: { message?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON request body." }, { status: 400 });
  }

  const rawMessage = typeof body.message === "string" ? body.message : "";
  const validation = validateTaskMessage(rawMessage);
  if (!validation.valid) {
    return NextResponse.json(
      { detail: validation.error || "Invalid task message." },
      { status: 422 }
    );
  }

  if (!isWorkerConfigured()) {
    return NextResponse.json(
      {
        detail:
          "Python Playwright worker is not configured yet. Set PYTHON_WORKER_URL and BACKEND_API_KEY in Vercel Environment Variables.",
      },
      { status: 503 }
    );
  }

  try {
    const upstream = await fetch(`${getBackendBaseUrl()}/api/tasks`, {
      method: "POST",
      headers: getBackendHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ message: rawMessage }),
      cache: "no-store",
    });
    return proxyJsonResponse(upstream);
  } catch {
    return NextResponse.json(
      { detail: "Automation worker is unavailable. Please ensure the backend service is running." },
      { status: 503 }
    );
  }
}
