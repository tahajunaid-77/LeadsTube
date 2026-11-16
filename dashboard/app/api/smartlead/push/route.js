import { route } from "@/lib/route";
import { smartleadPush } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const POST = route(({ body }) => smartleadPush(body));
