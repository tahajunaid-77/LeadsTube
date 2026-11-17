import { route } from "@/lib/route";
import { setContacted, HttpError } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const POST = route(({ body }) => {
  const links = Array.isArray(body.links) ? body.links : [body.link];
  if (!links.length || links.some(l => typeof l !== "string" || !l.startsWith("https://www.youtube.com/"))) throw new HttpError(400, "Bad link");
  return setContacted(links, !!body.contacted).then(state => ({ ok: true, count: Object.keys(state).length }));
});
