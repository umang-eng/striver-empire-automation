import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl, getBackendHeaders } from "@/lib/backendProxy";

type RouteContext = { params: Promise<{ taskId: string }> };

export async function GET(_request: NextRequest, context: RouteContext) {
  const { taskId } = await context.params;
  try {
    const upstream = await fetch(
      `${getBackendBaseUrl()}/api/tasks/${encodeURIComponent(taskId)}/events`,
      {
        headers: getBackendHeaders({ Accept: "text/event-stream" }),
        cache: "no-store",
      }
    );

    if (!upstream.ok || !upstream.body) {
      return NextResponse.json({ detail: "Stream unavailable." }, { status: upstream.status || 502 });
    }

    return new NextResponse(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Automation worker unreachable." }, { status: 503 });
  }
}
