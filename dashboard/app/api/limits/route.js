import { route } from "@/lib/route";
import { limits } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const GET = route(({ url }) => limits(url.searchParams.has("refresh")));
