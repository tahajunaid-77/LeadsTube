import { route } from "@/lib/route";
import { emailState } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const GET = route(() => emailState());
