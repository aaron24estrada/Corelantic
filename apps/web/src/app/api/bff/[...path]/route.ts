import { type NextRequest, NextResponse } from "next/server";

import { env } from "@/lib/env";

// The BFF boundary: the browser's only door to the private API. Client-side calls hit
// same-origin /api/bff/* and are forwarded server-to-server, with the internal secret
// injected here so it never reaches the browser. Once auth lands (docs O-4), the
// caller's identity is resolved and enforced here too, before anything is forwarded.

async function proxy(
  request: NextRequest,
  path: string[],
): Promise<NextResponse> {
  const target = `${env.apiBaseUrl}/${path.join("/")}${request.nextUrl.search}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (env.internalApiKey) headers.set("x-internal-api-key", env.internalApiKey);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const response = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.text() : undefined,
  });

  return new NextResponse(response.body, {
    status: response.status,
    headers: {
      "content-type":
        response.headers.get("content-type") ?? "application/json",
    },
  });
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(
  request: NextRequest,
  context: Context,
): Promise<NextResponse> {
  return proxy(request, (await context.params).path);
}

export async function POST(
  request: NextRequest,
  context: Context,
): Promise<NextResponse> {
  return proxy(request, (await context.params).path);
}
