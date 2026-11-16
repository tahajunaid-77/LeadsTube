import { route } from "@/lib/route";
import { sendEmail } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const POST = route(({ body }) => sendEmail(body));
