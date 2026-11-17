import { route } from "@/lib/route";
import { saveDraft } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const POST = route(({ body }) => saveDraft(body));
