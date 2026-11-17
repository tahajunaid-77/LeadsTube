import { route } from "@/lib/route";
import { getCopy, saveCopy } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const GET = route(() => getCopy());
export const POST = route(({ body }) => saveCopy(body));
