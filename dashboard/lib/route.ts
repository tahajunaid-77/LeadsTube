// Wraps an API handler: JSON in/out, friendly errors, and only this dashboard may call write routes.
import { NextResponse } from "next/server";

export type Body = Record<string, any>;
export type Handler = (req: { body: Body; url: URL }) => unknown | Promise<unknown>;

export function json(data: unknown, status = 200) {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

export function route(handler: Handler) {
  return async (request: Request) => {
    try {
      if (request.method !== "GET") {
        const origin = request.headers.get("origin");
        if (origin && origin !== new URL(request.url).origin) return json({ error: "Forbidden" }, 403);
      }
      let body: Body = {};
      if (request.method === "POST") {
        const text = await request.text();
        if (text.length > 2_000_000) return json({ error: "Request too large" }, 413);
        body = text ? JSON.parse(text) : {};
      }
      return json(await handler({ body, url: new URL(request.url) }));
    } catch (err) {
      const e = err as { status?: number; message?: string };
      if (!e.status) console.error(err);
      return json({ error: e.message || "Something went wrong" }, e.status || 500);
    }
  };
}
