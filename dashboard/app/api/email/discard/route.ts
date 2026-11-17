import { route } from "@/lib/route";
import { discardDraft } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const POST = route(({ body }) => discardDraft(body));
