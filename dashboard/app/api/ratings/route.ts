import { route } from "@/lib/route";
import { setRatings, HttpError } from "@/lib/backend";

export const dynamic = "force-dynamic";
// { links: [...], rating: "good" | "medium" | "low" | null }  (null removes the rating)
export const POST = route(({ body }) => {
  const links = Array.isArray(body.links) ? body.links : [body.link];
  if (!links.length || links.some(l => typeof l !== "string" || !l.startsWith("https://www.youtube.com/"))) throw new HttpError(400, "Bad link");
  return setRatings(links, body.rating ?? null);
});
