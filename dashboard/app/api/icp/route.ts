import { route } from "@/lib/route";
import { getIcp, saveIcp } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const GET = route(() => getIcp());
// { text } saves ICP.md (all section titles must stay); { undo: true } restores the previous version
export const POST = route(({ body }) => saveIcp(body));
