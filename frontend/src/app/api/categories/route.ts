import { NextResponse } from "next/server";
import { getBackendBaseUrl, getBackendHeaders, proxyJsonResponse } from "@/lib/backendProxy";

export async function GET() {
  try {
    const upstream = await fetch(`${getBackendBaseUrl()}/api/categories`, {
      headers: getBackendHeaders(),
      cache: "no-store",
    });
    return proxyJsonResponse(upstream);
  } catch {
    return NextResponse.json(
      { detail: "Could not load live categories from automation worker." },
      { status: 503 }
    );
  }
}
