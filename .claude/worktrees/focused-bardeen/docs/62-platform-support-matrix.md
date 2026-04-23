# Platform Support Matrix

## Support Levels

| Level | Meaning |
|-------|---------|
| **Buffer-automated** | Content published via Buffer API when BUFFER_API_KEY is set |
| **ESP-automated** | Content delivered via email service when SMTP_HOST is set |
| **Manual / Recommendation-only** | System recommends content + format but operator publishes manually |
| **Blocked by credentials** | Automated path exists but credentials not configured |
| **Blocked by missing client** | No automated publish client exists for this platform |

## Full Platform Matrix

| Platform | Priority | Publish Mode | Buffer | Execution Truth | Credential | Blocker |
|----------|----------|-------------|--------|----------------|------------|---------|
| Instagram | P0 | buffer | Yes | live_when_configured | BUFFER_API_KEY | — |
| TikTok | P0 | buffer | Yes | live_when_configured | BUFFER_API_KEY | — |
| YouTube | P0 | buffer | Yes | live_when_configured | BUFFER_API_KEY | — |
| X / Twitter | P0 | buffer | Yes | live_when_configured | BUFFER_API_KEY | — |
| Blog / Website | P0 | manual | No | recommendation_only | — | no_cms_client |
| Facebook | P1 | buffer | Yes | live_when_configured | BUFFER_API_KEY | — |
| Pinterest | P1 | buffer | Yes | live_when_configured | BUFFER_API_KEY | — |
| Reddit | P1 | manual | No | recommendation_only | — | no_direct_publish_client |
| LinkedIn | P1 | buffer | Yes | live_when_configured | BUFFER_API_KEY | — |
| Threads | P2 | buffer | Yes | live_when_configured | BUFFER_API_KEY | — |
| Snapchat | P2 | manual | No | recommendation_only | — | no_direct_publish_client |
| Email Newsletter | P2 | esp_service | No | live_when_configured | SMTP_HOST | blocked_without_esp |
| SEO Authority | P2 | manual | No | recommendation_only | — | no_cms_client |
| Telegram | P3 | manual | No | recommendation_only | — | no_direct_publish_client |
| Discord | P3 | manual | No | recommendation_only | — | no_direct_publish_client |
| Medium | P3 | manual | No | recommendation_only | — | no_direct_publish_client |
| Substack | P3 | manual | No | recommendation_only | — | no_direct_publish_client |

## How Each Non-Buffer Platform Works

### Blog / SEO Authority
System generates content recommendations, selects content form, and prepares the asset. Operator publishes via their CMS (WordPress, Ghost, etc.). No automated CMS client.

### Reddit
System recommends posts with optimal format (text-led, proof, carousel). Operator posts manually — Reddit has strict anti-bot policies making automated posting risky.

### Email Newsletter
Automated via the existing live execution ESP layer. When SMTP_HOST and SMTP_FROM_EMAIL are set, emails are sent through aiosmtplib. Sequences, nurture flows, and transactional emails are all supported.

### Telegram / Discord
System recommends content and format. Operator posts to channels/servers manually. Future: Telegram Bot API and Discord webhook clients can be added to enable direct posting.

### Medium / Substack
System generates long-form content, selects format, prepares the article. Operator publishes manually. Future: Medium API and Substack API clients can be added.

### Snapchat
System recommends ephemeral content. Operator posts manually. Low priority — limited monetization suitability.
