/**
 * /ai-search-authority/score → /ai-buyer-trust-test alias.
 *
 * The brief documented the public quiz path as
 * /ai-search-authority/score. The canonical surface lives at
 * /ai-buyer-trust-test (matches the package slug); this route exists so
 * any social link, doc, or backend reference to /score lands the user on
 * the live quiz instead of a 404.
 */

import { redirect } from "next/navigation";

export const dynamic = "force-static";

export default function AiSearchAuthorityScoreAlias(): never {
  redirect("/ai-buyer-trust-test");
}
