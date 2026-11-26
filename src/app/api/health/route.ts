import { NextResponse } from "next/server";
import { getBackendBaseUrl, getBackendHeaders, isWorkerConfigured } from "@/lib/backendProxy";

export async function GET() {
  if (!isWorkerConfigured()) {
    return NextResponse.json(
      {
        status: "offline",
        worker_configured: false,
        detail: "Set PYTHON_WORKER_URL in Vercel Environment Variables to connect the Python Playwright worker.",
      },
      { status: 503 }
    );
  }

  try {
    const upstream = await fetch(`${getBackendBaseUrl()}/api/health`, {
      headers: getBackendHeaders(),
      cache: "no-store",
    });
    const data = await upstream.json();
    return NextResponse.json({ ...data, worker_configured: true }, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { status: "offline", worker_configured: true, detail: "Automation worker is unreachable." },
      { status: 503 }
    );
  }
}
