import { NextRequest, NextResponse } from "next/server";

/**
 * When MUTINY_API_TOKEN is set on the web process, inject Authorization for
 * same-origin /api/* rewrites (including EventSource). The browser never sees
 * the token. Auth remains server-side on the FastAPI Hosted API (M-PR7).
 */
export function middleware(request: NextRequest) {
  const token = process.env.MUTINY_API_TOKEN?.trim();
  if (!token || !request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.next();
  }
  const headers = new Headers(request.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return NextResponse.next({
    request: { headers },
  });
}

export const config = {
  matcher: "/api/:path*",
};
