import { route } from "@/lib/route";
import { stopJob } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const POST = route(() => stopJob());
