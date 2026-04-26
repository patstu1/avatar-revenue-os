/**
 * Public robots.txt — keeps Googlebot, Bingbot, OAI-SearchBot, and GPTBot
 * explicitly allowed so the ProofHook marketing surface remains eligible
 * for indexing by Google, Bing, Bing Copilot, ChatGPT Search, and AI
 * referral systems that piggyback on those crawlers. /dashboard, /login,
 * and the API are disallowed because they're operator-internal.
 */

import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/proofhook-packages";

const PRIVATE_PATHS = ["/dashboard/", "/login", "/api/"];

const ALLOWED_AGENTS = [
  "Googlebot",
  "Bingbot",
  "OAI-SearchBot",
  "GPTBot",
  "PerplexityBot",
  "ClaudeBot",
  "CCBot",
  "Applebot",
  "DuckDuckBot",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      ...ALLOWED_AGENTS.map((agent) => ({
        userAgent: agent,
        allow: "/",
        disallow: PRIVATE_PATHS,
      })),
      // Default catch-all — allow root, disallow operator-internal paths.
      {
        userAgent: "*",
        allow: "/",
        disallow: PRIVATE_PATHS,
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
