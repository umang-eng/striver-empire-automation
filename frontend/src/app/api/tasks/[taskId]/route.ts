import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl, getBackendHeaders, proxyJsonResponse } from "@/lib/backendProxy";

type RouteContext = { params: Promise<{ taskId: string }> };

export async function GET(_request: NextRequest, context: RouteContext) {
  const { taskId } = await context.params;
  try {
    const upstream = await fetch(`${getBackendBaseUrl()}/api/tasks/${encodeURIComponent(taskId)}`, {
      headers: getBackendHeaders(),
      cache: "no-store",
    });
    return proxyJsonResponse(upstream);
  } catch {
    return NextResponse.json({ detail: "Automation worker unreachable." }, { status: 503 });
  }
}

export async function DELETE(_request: NextRequest, context: RouteContext) {
  const { taskId } = await context.params;
  try {
    const upstream = await fetch(`${getBackendBaseUrl()}/api/tasks/${encodeURIComponent(taskId)}`, {
      method: "DELETE",
      headers: getBackendHeaders(),
      cache: "no-store",
    });
    return proxyJsonResponse(upstream);
  } catch {
    return NextResponse.json({ detail: "Automation worker unreachable." }, { status: 503 });
  }
}
