import { route } from "@/lib/route";
import { startJob, jobStatus } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const GET = route(() => jobStatus());
export const POST = route(({ body }) => startJob({ mode: body.mode === "emails" ? "emails" : "search",
  target: body.target, countries: body.countries, days: body.days, keywords: body.keywords, fitGoal: body.fitGoal }));
