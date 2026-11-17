import { route } from "@/lib/route";
import { smartleadCampaigns } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const GET = route(() => smartleadCampaigns());
