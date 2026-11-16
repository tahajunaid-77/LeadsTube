import { route } from "@/lib/route";
import { testEmailLogin } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const POST = route(() => testEmailLogin());
