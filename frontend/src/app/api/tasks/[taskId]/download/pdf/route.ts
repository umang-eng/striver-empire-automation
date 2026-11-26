import { NextRequest, NextResponse } from "next/server";
import { getBackendBaseUrl, getBackendHeaders } from "@/lib/backendProxy";

type RouteContext = { params: Promise<{ taskId: string }> };

export async function GET(_request: NextRequest, context: RouteContext) {
  const { taskId } = await context.params;
  try {
    const upstream = await fetch(
      `${getBackendBaseUrl()}/api/tasks/${encodeURIComponent(taskId)}/download/pdf`,
      {
        headers: getBackendHeaders(),
        cache: "no-store",
      }
    );
    if (!upstream.ok) {
      const text = await upstream.text();
      return new NextResponse(text, { status: upstream.status });
    }
    const buffer = await upstream.arrayBuffer();
    const disposition =
      upstream.headers.get("Content-Disposition") || `attachment; filename="${taskId}.pdf"`;

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": disposition,
        "Cache-Control": "private, no-store",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Could not download PDF file." }, { status: 503 });
  }
}
