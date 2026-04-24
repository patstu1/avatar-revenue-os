# Revenue Playbook — AI Avatar Revenue OS
**From dev-mode today → $1M+ MRR in 12 months → ceiling break after**

Analyst: Claude · Date: 2026-04-22 · Target folder: `/Users/pstuart/Desktop/revproof/`

---

## North Star

| Milestone | When | MRR | ARR | Trigger |
|---|---|---|---|---|
| M0 — First live dollar | Week 1 | any | any | Live Stripe + DNS + one closed sale |
| M1 — Predictable pipeline | Month 2 | $25K | $300K | 10 paying accounts on one brand |
| M2 — Engine compounding | Month 4 | $100K | $1.2M | Analytics wired, attribution real |
| M3 — Multi-brand runway | Month 6 | $300K | $3.6M | 3 brands live, 3 revenue streams each |
| M4 — Ceiling approach | Month 9 | $800K | $9.6M | All 12 revenue streams firing |
| M5 — Ceiling hit | Month 12 | $1.2M+ | $14M+ | Productized services saturated |
| M6 — Break ceiling | Month 18 | $2M+ | $25M+ | Terraform multi-node or Platform-SaaS GTM |

**Guiding principle:** every action in this playbook is ordered by *dollars per hour of your time*. Do not reorder.

---

## Phase 0 — Deploy (48 hours)

Goal: live production stack, real Stripe, real domain, real money can flow.

### 0.1 Fix `.env` for production

File: `/Users/pstuart/Desktop/revproof/.env`

```bash
# CHANGE THESE
API_ENV=production                                        # was: development
API_SECRET_KEY=<64-char random, e.g. openssl rand -hex 32> # was: dev-secret-key-not-for-production-abc123
POSTGRES_PASSWORD=<rotate to 32-char random>              # was: avataros_dev_2026
NEXT_PUBLIC_API_URL=https://api.proofhook.com              # was: http://localhost:8001
STRIPE_API_KEY=sk_live_...                                 # was: sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_... (new from live webhooks)   # was: test webhook secret
LOG_LEVEL=info                                             # was: debug
SENTRY_DSN=https://...ingest.sentry.io/...                 # was: empty

# DECIDE
DOMAIN=proofhook.com  # or app.nvironments.com — pick one, drop the other
```

Regenerate `API_SECRET_KEY` now — the current value will invalidate every JWT when rotated, which is fine because there are no prod users yet.

### 0.2 Resolve domain mismatch

`.env` says `proofhook.com`, `SYSTEM_ANALYSIS.md` says `app.nvironments.com`. Pick one. `proofhook.com` is consistent with the Brevo SMTP alias `hello@proofhook.com` and the Outlook inbox `hello@proofhook.com`, so that's the natural choice. Drop `nvironments.com` or redirect it.

Point A records for `proofhook.com` and `api.proofhook.com` at the Hetzner box IP. Caddy will auto-issue Let's Encrypt certs on first hit.

### 0.3 Set up live Stripe

1. In Stripe dashboard, switch to live mode.
2. Create six products matching the offer pages:
   - AI-UGC Starter — $1,500/mo recurring
   - Growth Content Pack — $2,500/mo recurring
   - Beauty Content Pack — $2,500/mo recurring
   - Performance Creative Pack — $2,500/mo recurring (confirm price)
   - Launch Sprint — $5,000 one-time
   - Full Creative Retainer — $7,500/mo recurring
3. Copy the six `price_...` IDs into `.env`:
   ```
   STRIPE_PRICE_STARTER_MONTHLY=price_...
   STRIPE_PRICE_STARTER_ANNUAL=price_...  (offer 2 months free if they pay annually)
   STRIPE_PRICE_PROFESSIONAL_MONTHLY=price_...
   STRIPE_PRICE_PROFESSIONAL_ANNUAL=price_...
   STRIPE_PRICE_BUSINESS_MONTHLY=price_...
   STRIPE_PRICE_BUSINESS_ANNUAL=price_...
   ```
4. Add a webhook endpoint at `https://api.proofhook.com/api/v1/webhooks/stripe` subscribed to: `checkout.session.completed`, `invoice.paid`, `customer.subscription.created/updated/deleted`, `charge.refunded`, `charge.dispute.created`.
5. Copy the live webhook signing secret into `STRIPE_WEBHOOK_SECRET`.

### 0.4 Confirm Buffer is wired

Buffer is the only publishing channel proven real in the audit. Go to the Hetzner VPS (`root@5.78.187.31`), check `/opt/avatar-revenue-os/.env` on the server for `BUFFER_API_KEY` — the dev `.env` in your working folder has it blank with a comment saying it's managed elsewhere. If the prod file is also blank, get a Buffer API token from `buffer.com/developers/api` and set it now. Without this, zero posts ship.

### 0.5 Deploy

```bash
ssh root@5.78.187.31
cd /opt/avatar-revenue-os
git pull
# edit .env with values from 0.1-0.4
./deploy.sh
```

`deploy.sh` is a 6-step process with rollback tagging. It will tag current images `:rollback`, run the migrate container, rolling-restart api/web/worker/scheduler/caddy, and hit `/healthz` 15 × 3s to verify.

### 0.6 Smoke test

```bash
# From anywhere
curl https://api.proofhook.com/healthz
curl https://proofhook.com/  # should return Next.js root
curl https://proofhook.com/offers/aesthetic-theory/full-creative-retainer  # renders offer page

# On the server
docker exec aro-api python scripts/verify_production.py
docker exec aro-api python scripts/compounding_proof.py  # 28/28 should pass
docker exec aro-api python scripts/monetization_proof.py # 54/54 should pass
```

Fail any of these → stop, fix, don't proceed.

### 0.7 Send yourself through Stripe

Open `https://proofhook.com/offers/aesthetic-theory/launch-sprint` in a real browser. Pay $5,000 with your personal card. Confirm:
1. Stripe charged you live
2. `revenue_ledger` table has the row (check via `/dashboard/revenue`)
3. Webhook fired (Stripe dashboard shows 200)
4. `/dashboard/monetization` reflects the new entry

Refund yourself. Now you've proven end-to-end.

**Phase 0 done when:** you can take money from a real customer on at least one offer page.

---

## Phase 1 — First $1 (Week 1)

Goal: one paying customer who isn't you. Everything else is noise.

### 1.1 Pick your beachhead brand

`aesthetic-theory` is the most-built (3 of 6 offer pages are fully custom, not `PackagePage` templates). Beauty/skincare DTC has short sales cycles and clear ICP ($50K+/mo revenue for the core pack, $200K+/mo for the retainer). Go here first. Park `body-theory` and `tool-signal` — do NOT spread attention across three brands in Week 1.

### 1.2 Your one offer to sell

Not six. One. **Launch Sprint at $5,000 one-time.** Reasons:
- Lowest commitment friction (no "am I locked in for a year")
- Fastest delivery (you can produce and ship in days, not a month)
- Most credible proof-of-value (we do a thing, you see it, you buy retainer)
- Funds the retainer funnel (sprint buyers are the closer's warmest retainer leads)

Sell the sprint. Upsell sprint-buyers to retainer after the sprint ships.

### 1.3 Outbound (the only acquisition channel Week 1)

Apollo.io → export 500 DTC beauty brands doing $50K+/mo in the US/UK. Use the already-wired `scripts/import_apollo_contacts.py` to load them.

```bash
docker exec aro-api python scripts/import_apollo_contacts.py ~/contacts.csv
```

Set up a three-touch sequence via the wired Brevo SMTP:
- Day 1: 90-word cold with one loom showing an AI-generated ad for a competitor of theirs.
- Day 3: one-line follow-up, ask for reply only.
- Day 7: breakup "closing your file, last chance" + new angle.

Send 50/day from `hello@proofhook.com`. Open rate target 40%, reply rate 5%, booked-call rate 1–2%. Expect 5–10 booked calls in week one off 250 sends.

### 1.4 Close the sprint

Demo = one pre-built video showing what their brand looks like through the system. `cinema_studio_worker` already does this. 20-minute Zoom. Close at $5,000 half up front, half on delivery. Stripe invoice link → same ledger.

### 1.5 Operating cadence Week 1

- Morning: 50 outbound sends, check overnight replies.
- Midday: 2–3 discovery calls.
- Afternoon: produce 1 sprint that's been sold (the system does the work; you review, QA, publish).
- Evening: check `/dashboard/revenue`, `/dashboard/jobs`, `/dashboard/buffer-status` for errors. Log anything broken as a GitHub issue.

**Phase 1 done when:** one non-you human has paid $5,000 and received delivered sprint assets.

---

## Phase 2 — Engine online (Weeks 2–4)

Goal: close the high-severity audit gaps so the 17 revenue engines have real data to run against. Each one multiplies your next-dollar efficiency.

Per `REALITY_AUDIT.md` the high-severity gaps are: QA hardcoded, performance data collection missing, brain decisions don't auto-execute, autonomous loop doesn't orchestrate. Order of attack:

### 2.1 Platform analytics ingestion — #1 priority

This is the single biggest unlock. Until it lands, engines E14 (leak), E15 (portfolio), E16 (compounding), and E17 (durability) run against empty tables.

Get tokens:
- **YouTube Data API v3** — OAuth flow. Set `YOUTUBE_API_KEY` + `YOUTUBE_OAUTH_TOKEN`.
- **TikTok Business API** — apply, ~3–5 day approval. Set `TIKTOK_ACCESS_TOKEN`.
- **Instagram Graph API** — needs Meta Business verification. Set `INSTAGRAM_ACCESS_TOKEN`.

Build the missing clients. Per audit: "models exist, clients don't." Create:
- `packages/clients/youtube_analytics.py`
- `packages/clients/tiktok_analytics.py`
- `packages/clients/instagram_analytics.py`

Wire each into `workers/analytics_ingestion_worker/tasks.py`. The 30-minute Beat schedule is already there (`analytics_worker.tasks.ingest_performance`) — it just needs real clients to call.

Test: produce one piece of content, publish via Buffer, wait 24h, confirm `PerformanceMetric` rows exist for that `content_item_id`.

### 2.2 Real QA scoring

File: `apps/api/services/content_pipeline_service.py`, function `run_qa()`. Currently passes `originality_score=0.7, compliance_score=0.85` hardcoded.

Replace with real calls:
- Originality: embed content with OpenAI `text-embedding-3-small`, compare against `ContentItem` history via pgvector. Return cosine distance → originality score.
- Compliance: Claude API call with brand guidelines + content → structured score.
- Hook strength: Claude scored against E1 creator fit archetype signals.

Without this, E9 (margin rankings) and E14 (leak) under-fire, and you suppress winning content.

### 2.3 Wire second + third publishing channels

`publishing_worker` uses Buffer only. Clients for Publer + Ayrshare exist but aren't called. Add fallback order:
1. Buffer primary
2. Ayrshare secondary (already has key in `.env`)
3. Publer tertiary

One-line routing change in `workers/publishing_worker/tasks.py`. This is an insurance policy — Buffer rate-limits kill throughput at scale.

### 2.4 Brain decision auto-dispatch

`BrainDecision` rows are written but no worker reads them. Create `workers/brain_worker/tasks.py::dispatch_brain_decisions` that:
1. Selects `BrainDecision` rows with `confidence >= 0.7` and `executed_at IS NULL`.
2. Converts each to an `OperatorAction` via `intelligence_bridge.py`.
3. Marks executed.

Add to Beat schedule every 15 minutes. This turns Brain Phases C+D from observational to operational — audit explicitly flags this as the "reclassify honestly" demand.

### 2.5 SerpAPI trend discovery

Get SerpAPI key → `SERPAPI_KEY`. The `niche_research_worker` and E2 opportunity detection read from trend signals. Without this, ideation is "manual seed only." With it, the content firehose self-directs at rising keywords and E12 (experiment opportunities) produces real test candidates.

### 2.6 Running outbound while you wire

Don't pause sales for engineering. Each day in Phase 2:
- 50 cold sends continuing
- 2–4 discovery calls
- Close 1–2 sprints/week average

Target end of Month 1: 4–8 sprint buyers paid ($20K–$40K banked), of whom 1–2 convert to retainer ($7,500 MRR × 1–2 = $7,500–$15,000 MRR).

**Phase 2 done when:** (a) platform analytics write real rows for real content, (b) QA produces real scores, (c) Brain decisions dispatch automatically, (d) you have ≥5 paid clients.

---

## Phase 3 — Compounding (Months 2–3)

Goal: the system starts producing dollars without you in the loop. You become the sales + approval layer, not the operator.

### 3.1 Wire affiliate networks

Keys scaffolded in `.env.example`: `IMPACT`, `SHAREASALE`, `CLICKBANK`. ClickBank key is already live in `.env`. Get Impact + ShareASale accounts (instant approval for most).

`affiliate_intel_worker` and `affiliate_placement_engine` will then:
- Auto-insert affiliate links into content
- Track commissions via webhook
- Write to ledger as `affiliate_commission`
- Attribute via `causal_attribution_service`

Expected contribution: $5K–$15K MRR/brand by month 3 from organic traffic on published content alone.

### 3.2 Sponsor outreach automation

`sponsor_autonomy` and `sponsor-sales` engines scaffolded. Enable them. Set guardrails:
- Only reach out to brands matching ICP fit score ≥ 0.7
- Cap: 10 sponsor emails/day/brand (deliverability)
- Minimum deal: $2,000

Expected: 2–4 sponsor deals/month/brand by month 3, $5K–$25K per deal. Add $10K–$100K MRR.

### 3.3 Turn on Cinema Studio long-form

`cinema_studio_worker` is a full pipeline for character-driven long-form avatar content. Currently likely idle. Long-form (YouTube 3–10 min) has 8–10× the RPM of short-form AND is owned-channel (not rented algorithms). Turn it on.

One scene per day, per brand. Costs ~$3–8 in provider spend per scene at hero tier.

### 3.4 Launch brand #2: `body-theory`

Replicate the aesthetic-theory outbound playbook with a fitness/wellness ICP. All offer pages already built (thin template versions — flesh them out to match `full-creative-retainer`'s depth). New Apollo list of 500 fitness DTC brands. Same 50/day cadence.

Do NOT do this before aesthetic-theory is consistently closing 4+ sprints/month. Avoid context-switch debt.

### 3.5 Hiring (the first real question)

By month 3 you're the bottleneck. Two roles, in order:
1. **SDR** — takes outbound off your plate. $45K base + commission. They handle the 50 sends + discovery qualification. You only take qualified calls.
2. **Account manager / delivery QA** — takes post-sale QA off your plate. $55K base. They review system-generated deliverables, handle client Slack.

These free you to do strategy + closing + engine wiring, which is the $/hr-highest work.

**Phase 3 done when:** $100K+ MRR, 3+ revenue source types active, 2 brands live, you have one hire.

---

## Phase 4 — Scale (Months 4–6)

Goal: fill the productized-services ceiling. Saturate 3 brands.

### 4.1 Brand #3: `tool-signal`

B2B SaaS/dev tools ICP. Longer sales cycles but larger deals ($7,500 retainer is a no-brainer for a Series A SaaS). Replicate playbook.

### 4.2 Capital allocator engine

`capital_allocator_worker` routes provider spend across hero/standard/bulk tiers based on ROI. Tune the weights once you have 3 months of attribution data. Expected efficiency gain: 15–25% margin improvement at same revenue.

### 4.3 Offer ladders + productization (E11)

Engine E11 already recommends entry→core→upsell packaging. Act on it. For each brand:
- Entry: $297 "content audit" (new, not built yet) — top-of-funnel, self-serve
- Mid: $1,500–$2,500 productized packs (already built)
- Premium: $7,500–$15,000 retainer (already built at $7,500 — add a `premium-plus` at $15K for $1M+/mo brands)
- Continuity: $500/mo "creative membership" (new) — post-retainer churn catcher

Adding the $297 entry doubles top-of-funnel volume. Adding the $15K tier adds 20% to ARPU on the top 10% of accounts.

### 4.4 Recurring revenue density (E10, E15)

Engine E15 (portfolio allocation) tells you which accounts are hero/growth/maintain/pause. Prune the bottom quintile aggressively — low-margin accounts consume delivery capacity that compounds much faster on hero accounts.

### 4.5 Referral program

`referral` engine in Expansion Pack 2 phase C. Activate. 20% recurring commission for referrers for 12 months. Clients refer clients — this is the lowest-CAC channel by far.

### 4.6 Hiring continues

Month 5 adds: second SDR, second delivery AM, part-time engineer for engine wiring. By end of month 6 you're running a 5-person team at $300K MRR.

**Phase 4 done when:** $300K+ MRR, 3 brands live, 5+ revenue streams contributing, ≥100 paying accounts.

---

## Phase 5 — Ceiling approach (Months 7–12)

Goal: saturate all 12 revenue source types on the single VPS. Hit ~$1M MRR.

### 5.1 Creator revenue streams

`creator_revenue_worker` handles 6 streams: UGC services, consulting, premium access, merch, licensing, data products. Each is a separate offer page build.

Priority order by $/hour:
1. **Data products** — anonymized industry benchmarks by vertical, $499–$2,499/report, sold quarterly. You already have the data in the ledger from 100+ accounts. Highest margin (98%+).
2. **Licensing** — license brand-safe ad creative to enterprise. $5K–$25K/license. Already-produced assets → zero marginal cost.
3. **Premium access** — $99/mo community + template library. Scales without delivery load.
4. **Consulting** — $500/hr. Limited by your time, but high hourly.
5. **UGC services** — labor-intensive, consider last.
6. **Merch** — low margin, not worth the cycles.

Expected added MRR: $50K–$200K across the top three.

### 5.2 Ad revenue on owned channels

Long-form YouTube content (Cinema Studio) monetizes directly at $2–$8 RPM. At 1M views/mo/brand × 3 brands = $6K–$24K MRR. Bonus: views compound with the library.

### 5.3 Product sales (DTC under your brand)

Optional. If any brand has obvious product-market fit (supplements for body-theory, tools/courses for tool-signal), Shopify webhook is wired. Launch one product per brand. Use the content engine to sell it. Skip if it's distraction.

### 5.4 Enterprise tier

Build a `$25K/mo enterprise retainer` offer. Same delivery, 2× the volume + dedicated Slack + quarterly strategy session. Sell 4–8 of these by month 12. $100K–$200K MRR from 8 accounts is the fastest path to $1M MRR.

### 5.5 Operational excellence

At $500K+ MRR, the failure modes are operational, not strategic:
- Set `quality_governor_service` thresholds harder (false-positive suppression beats false-negative publish)
- Tighten `OperatorAction` confidence threshold from 0.6 to 0.75 (fewer, higher-quality autonomous actions)
- Stand up a staging environment (currently only dev + prod)
- Implement the Integration Manager per `NEXT_SESSION_SPEC.md` — manual env-var provider config breaks at 10+ connected platforms
- Rotate all API keys quarterly
- Fix `.backups/` and `celerybeat-schedule` hygiene (both should be in `.gitignore`)

**Phase 5 done when:** $1M+ MRR, 10+ revenue streams live, ≥300 paying accounts across 3 brands.

---

## Phase 6 — Break the ceiling (Months 13–18+)

At $1.2M+ MRR you're hitting the single-VPS wall. Three paths, pick one (not all):

### Path A — Multi-node infrastructure
Use the placeholder `infrastructure/terraform/`. Migrate to 3-node Postgres HA + horizontally-scaled API + worker pools per tenant. Budget: $40–80K in infra work + $3–8K/mo infra cost. Unlocks the next 3–5× of revenue on the same business model.

### Path B — Platform-as-SaaS
The Starter/Professional/Business Stripe tiers in `.env.example` imply this. Productize the platform, rent it to other creator orgs at $500–$5,000/mo. You own the rails, they drive their own cars. Budget: 3–6 months product work (billing, onboarding, tenant isolation audit, docs). Uncapped by architecture, capped only by GTM.

### Path C — 4th and 5th brands
Easiest by far. Same playbook, new verticals. Every additional brand adds ~$300–500K MRR at saturation. But at 5+ brands you'll hit VPS limits anyway, so this is a stopgap for Path A.

**Recommendation:** Path A first (buys you 3–5×), then Path B once stable (uncaps you).

---

## Daily operating cadence (after Phase 1)

Morning (90 min):
1. `/dashboard/revenue` — MRR, ARR, refund rate, dispute rate
2. `/dashboard/jobs` — failed jobs, backlog, retry queue
3. `/dashboard/buffer-status` — publishing queue health
4. `/dashboard/experiment-decisions` — any experiments concluded overnight
5. Respond to overnight inbound in `hello@proofhook.com`
6. Dispatch any `OperatorAction`s with confidence 0.5–0.7 that need your approval

Midday (3–4 hr):
- Discovery calls + closes (highest $/hr)
- Engine wiring or bug fixing (next-highest)

End of day (30 min):
- Review `/dashboard/kill-ledger` — what got suppressed today, is it correct?
- Review `/dashboard/revenue-leaks` — what did E14 detect today?
- Note one thing to automate next week

## Weekly cadence

Monday: set goals for week (sprints sold, retainers closed)
Wednesday: mid-week pipeline review
Friday: numbers review — MRR movement, churn, delivery on-time rate, provider spend

## Monthly cadence

Day 1: board/self-review meeting against milestones above
Day 15: cost audit — every provider's spend vs. revenue attributed to its tier
Day 30: retention review — which accounts are at-risk per E17 durability scoring

---

## KPIs to watch (the real ones)

| KPI | How to get it | Target |
|---|---|---|
| MRR | `/dashboard/revenue` | +25% MoM months 1–6, +15% MoM 7–12 |
| ARPU | MRR / active accounts | $2,000 → $3,500 by month 12 |
| Gross margin | 1 - (provider spend / revenue) | ≥75% (hero tier) |
| Churn (logo) | cancelled / starting | <5%/mo |
| Churn (revenue) | net revenue change excluding new | positive (net retention) |
| Sprint→retainer conversion | retainers closed / sprints shipped | ≥25% |
| Delivery on-time % | completed by SLA / total | ≥95% |
| E14 leak detection value | attributed $ to recovery actions | >$10K/mo by month 4 |

---

## Kill criteria (when to stop or pivot)

- **Month 2, <2 paying customers**: your ICP is wrong or your outbound copy is wrong. Do not ship more code. Do 50 customer discovery calls.
- **Month 4, <$25K MRR**: the aesthetic-theory brand is not working. Try tool-signal instead or pivot to SaaS (Path B) early.
- **Month 6, gross margin <60%**: provider spend is out of control. Force all routing to bulk/standard tier until margin recovers. Hero tier is a premium, not a default.
- **Month 9, churn >8%/mo**: delivery quality is failing. Pause all new sales for 30 days, fix QA + delivery, resume.
- **Month 12, <$500K MRR**: you're not on track for ceiling. Decide: double down on sales (hire, spend on ads) OR pivot to Platform-SaaS (Path B).

---

## What NOT to do

- Do not build a new feature if there's unwired audit gap above it in priority. Finish the stack.
- Do not spread across 3 brands before the first one is consistent.
- Do not hire before $50K MRR. You'll burn runway.
- Do not take outside capital before $100K MRR — dilution at pre-revenue pricing is a bad trade.
- Do not chase enterprise-only before product-market fit in mid-market.
- Do not let provider spend exceed 30% of revenue at any point. Set a hard budget cap per-org.
- Do not ignore `REALITY_AUDIT.md` "HIGH severity" items once you're past $50K MRR. Every one of them is limiting your ceiling.

---

## First 14 days — literal day-by-day

| Day | Action |
|---|---|
| 1 | Rotate secrets in `.env`, resolve domain, DNS A records |
| 2 | Live Stripe setup + webhook, deploy to Hetzner, smoke test |
| 3 | Pay yourself through live checkout, confirm end-to-end |
| 4 | Apollo list of 500 DTC beauty brands, load via script |
| 5 | Write 3-touch cold sequence, A/B test 2 hooks in Brevo |
| 6 | Start sending 50/day from `hello@proofhook.com` |
| 7 | First discovery calls (2–3 booked from week's sends) |
| 8 | Close first sprint. First real $5,000. |
| 9 | Deliver sprint #1 assets. Record delivery as proof for #2. |
| 10 | Start YouTube API integration (Phase 2.1 begins) |
| 11 | Continue sends + delivery. Second close target. |
| 12 | Ship YouTube analytics client to prod. |
| 13 | Start TikTok + Instagram analytics clients in parallel. |
| 14 | End of week 2 review: 2 closes, 1 analytics client live, outbound cadence holding. |

---

## One-line summary

Deploy → sell one offer on one brand via cold outbound → wire analytics → compound into three brands + three hires → saturate productized services at ~$14M ARR → unlock next tier via Terraform or Platform-SaaS. Stay ruthlessly sequenced. The code is further than the operations. Fix operations.

---

*End of playbook.*
