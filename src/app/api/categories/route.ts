import { NextResponse } from "next/server";
import { getBackendBaseUrl, getBackendHeaders, isWorkerConfigured, proxyJsonResponse } from "@/lib/backendProxy";
import { DEFAULT_CATEGORY_GROUPS } from "@/lib/defaultCategories";

export async function GET() {
  if (!isWorkerConfigured()) {
    return NextResponse.json({
      groups: DEFAULT_CATEGORY_GROUPS,
      site: "https://striverempire.com",
      source: "static-fallback",
    });
  }

  try {
    const upstream = await fetch(`${getBackendBaseUrl()}/api/categories`, {
      headers: getBackendHeaders(),
      cache: "no-store",
    });
    if (upstream.ok) {
      return proxyJsonResponse(upstream);
    }
  } catch {
    // Fall back to static catalog so category suggestions remain functional
  }

  return NextResponse.json({
    groups: DEFAULT_CATEGORY_GROUPS,
    site: "https://striverempire.com",
    source: "static-fallback",
  });
}
