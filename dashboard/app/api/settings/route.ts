import { route } from "@/lib/route";
import { publicSettings, saveSettings } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const GET = route(() => publicSettings());
export const POST = route(({ body }) => saveSettings(body));
