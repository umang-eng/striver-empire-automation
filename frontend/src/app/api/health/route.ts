import { NextResponse } from "next/server";
import { getBackendBaseUrl, getBackendHeaders } from "@/lib/backendProxy";

export async function GET() {
  try {
    const upstream = await fetch(`${getBackendBaseUrl()}/api/health`, {
      headers: getBackendHeaders(),
      cache: "no-store",
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json(
      { status: "offline", detail: "Automation worker is unreachable." },
      { status: 503 }
    );
  }
}
