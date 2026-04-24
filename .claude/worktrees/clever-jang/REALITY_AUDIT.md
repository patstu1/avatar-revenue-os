# REALITY CONVERSION AUDIT

Commit: `6540a3e` on `main` (post deploy-v1)
Audited: 2026-04-04

---

## SECTION 1: FULL AUDIT TABLE

### OS INFRASTRUCTURE (built in Phases 1-6)

| Feature | Claimed | Status | What It Does | Runtime Verified | State Changes | Downstream Effects | Missing | Files |
|---------|---------|--------|-------------|-----------------|--------------|-------------------|---------|-------|
| Event bus (SystemEvent) | Events emitted on all state changes | **Fully real** | db.add(SystemEvent) + db.flush() on every lifecycle transition | 60/60 runtime proof | Appends row to system_events | Control layer reads, activity feed displays | None | event_bus.py |
| Operator actions (OperatorAction) | Actions created from all layers | **Fully real** | db.add(OperatorAction) with type/priority/category | 60/60 runtime proof | Creates pending action row, complete/dismiss transitions | Control layer surfaces, autonomous dispatch reads | None | event_bus.py |
| Control layer dashboard | Aggregates real state from all layers | **Fully real** | SQL queries across ContentItem, SystemJob, OperatorAction, Offer, RevenueLedgerEntry, ProviderBlocker, MemoryEntry, GatekeeperAlert | 60/60 runtime proof | No (read-only) | Dashboard displays real counts | None | control_layer_service.py |
| Content lifecycle service | Brief→generate→QA→approve→publish with events | **Partially real** | Wraps pipeline functions with emit_event/emit_action. QA gate blocks on qa_status. | Static proof only (101/101) | ContentItem.status transitions | Events feed control layer, actions feed operator | **Not runtime-proven end-to-end with real content** | content_lifecycle.py |
| Quality gate enforcement | QA blocks bad content | **Partially real** | Checks qa_report.qa_status and similarity. If fail → status=quality_blocked + action created | Static proof | ContentItem.status → quality_blocked | Action created, blocks publishing | **QA inputs are hardcoded (originality=0.7, etc.) — gate triggers based on formula applied to fake inputs, not real content analysis** | content_lifecycle.py, content_pipeline_service.py |
| Kill ledger blocking | Blocks content generation of dead approaches | **Partially real** | Queries KillLedgerEntry before generation. If match → ValueError raised | Static proof | Generation blocked | Error returned to caller | **Only blocks if KillLedgerEntry rows exist — no code auto-creates them from failure patterns** | content_lifecycle.py, intelligence_bridge.py |
| Intelligence bridge | Brain decisions → operator actions | **Fully real** | Queries BrainDecision, PatternDecayReport, PWExperimentWinner, FailureFamilyReport → creates OperatorActions | Runtime proof (in revenue_maximizer context) | OperatorAction rows created | Control layer surfaces | None | intelligence_bridge.py |
| Monetization bridge | Offer↔content linking, revenue state | **Fully real** | assign_offer_to_content sets FK, get_brand_revenue_state queries ledger | 54/54 runtime proof | ContentItem.offer_id, RevenueLedgerEntry rows | Revenue dashboard, attribution, allocation | None | monetization_bridge.py |
| Orchestration bridge | Job/worker/provider visibility | **Partially real** | Queries SystemJob, ProviderBlocker for state | Runtime proof (60/60) | OperatorAction rows for stuck/failed jobs | Control layer surfaces | **Provider health is config-check only, not actual API ping** | orchestration_bridge.py |
| Governance bridge | Permission check, audit trail, memory | **Partially real** | Calls operator_permission_service.check_action(), writes AuditLog + SystemEvent | Runtime proof (60/60) | AuditLog row, SystemEvent row, MemoryEntry row | Control layer, memory layer | **Permission check returns dict but does NOT block the actual API endpoint — callers must respect the result voluntarily** | governance_bridge.py |

### CANONICAL REVENUE LEDGER

| Feature | Claimed | Status | What It Does | Runtime Verified | State Changes | Downstream Effects | Missing | Files |
|---------|---------|--------|-------------|-----------------|--------------|-------------------|---------|-------|
| RevenueLedgerEntry table | Single source of truth for all money | **Fully real** | 34-column table with source type, amounts, state machine, FK linkages | 54/54 proof | Row creation | Dashboard, allocation, mix, leak detection all query this | None | revenue_ledger.py |
| Affiliate → ledger | Commission events write to ledger | **Fully real** | record_affiliate_commission_to_ledger() creates row | 54/54 proof | RevenueLedgerEntry row, SystemEvent | Revenue state, allocation | None | monetization_bridge.py |
| Sponsor → ledger | Deal payments write to ledger | **Fully real** | record_sponsor_payment_to_ledger() creates row | 54/54 proof | RevenueLedgerEntry row, SystemEvent | Revenue state, allocation | None | monetization_bridge.py |
| Service → ledger | Service payments write to ledger | **Fully real** | record_service_payment_to_ledger() creates row | 54/54 proof | RevenueLedgerEntry row, SystemEvent | Revenue state, allocation | None | monetization_bridge.py |
| Product → ledger | Product sales write to ledger | **Fully real** | record_product_sale_to_ledger() creates row | 54/54 proof | RevenueLedgerEntry row, SystemEvent | Revenue state, allocation | None | monetization_bridge.py |
| Refund → ledger | Negative entry linked to original | **Fully real** | record_refund_to_ledger() creates negative row with refund_of_id | 54/54 proof | RevenueLedgerEntry row (negative), original row → payment_state=refunded | Net revenue calculation | None | monetization_bridge.py |
| Webhook → ledger (Stripe) | Stripe payments auto-write to ledger | **Fully real** | webhooks.py calls record_service_payment_to_ledger() | Static proof (37/37 code verification) | RevenueLedgerEntry row | Revenue state | **Not proven with real Stripe webhook — only code path verified** | webhooks.py |
| Webhook → ledger (Shopify) | Shopify orders auto-write to ledger | **Fully real** | webhooks.py calls record_product_sale_to_ledger() | Static proof (37/37 code verification) | RevenueLedgerEntry row | Revenue state | **Not proven with real Shopify webhook — only code path verified** | webhooks.py |
| Idempotency | Duplicate webhooks rejected | **Fully real** | Unique constraint on webhook_ref column | 54/54 proof (IntegrityError on duplicate) | Prevents duplicate row | No double-counting | None | revenue_ledger.py |

### 17 REVENUE ENGINES

| Engine | Claimed | Status | What It Does | Runtime Verified | State Changes | Downstream Effects | Missing | Files |
|--------|---------|--------|-------------|-----------------|--------------|-------------------|---------|-------|
| E1: Creator fit scoring | Score 10 paths per account | **Fully real** | SQL query on CreatorAccount + Offer + RevenueLedgerEntry, computes 10 float scores | 38/38 + 28/28 proof | No (read-only scoring) | Fit scores feed opportunity detection, portfolio, archetype | None | revenue_maximizer.py |
| E2: Opportunity detection | Find highest-value gaps | **Fully real** | Queries unmonetized content, orphan offers, sponsor-ready accounts, underexploited patterns | 38/38 proof | No (read-only) | Feeds next-best-actions, execution engine | None | revenue_maximizer.py |
| E3: Revenue allocation | Rank where effort should go | **Fully real** | Queries ledger by source, computes composite score with structural traits | 38/38 proof | No (read-only) | Feeds mix, next-actions | None | revenue_maximizer.py |
| E4: Suppression targets | What to stop | **Fully real** | Queries LosingPatternMemory, SuppressionRule, FailureFamilyReport, BrainDecision[suppress] | 38/38 proof | No (read-only) | Feeds execution engine | None | revenue_maximizer.py |
| E5: Revenue memory | What worked | **Fully real** | Queries WinningPatternMemory, PromotedWinnerRule, MemoryEntry, RevenueLedgerEntry by source | 38/38 proof | No (read-only) | Feeds generation context | None | revenue_maximizer.py |
| E6: Monetization mix | Current vs optimal | **Fully real** | Queries ledger, computes allocation scores, identifies gaps | 38/38 proof | No (read-only) | Feeds next-actions | None | revenue_maximizer.py |
| E7: Next-best actions | Top 10 by value | **Fully real** | Composes E2+E4+E6 outputs, sorts by expected_value | 38/38 proof | No (read-only) | Feeds execution engine | None | revenue_maximizer.py |
| E8: Simulation | What-if modeling | **Fully real** | Queries ledger, applies multiplier/shift/suppress, projects outcomes | 38/38 proof | No (read-only) | Recommendation: execute/review/reject | None | revenue_engines_extended.py |
| E9: Margin rankings | True-value scoring | **Fully real** | Queries ledger with refund/dispute rates, computes composite with structural traits | 38/38 proof | No (read-only) | Recommendation: scale/maintain/reduce/suppress | None | revenue_engines_extended.py |
| E10: Creator archetypes | 11-type classification | **Fully real** | Reads accounts + ledger by source per account, scores 11 archetype patterns | 38/38 proof | No (read-only) | Feeds fit routing | **Archetype scores use hardcoded weights, not learned from actual performance** | revenue_engines_extended.py |
| E11: Offer packaging | Entry→core→upsell | **Fully real** | Reads active offers, sorts by priority-weighted payout, assigns roles | 38/38 proof | No (read-only) | Feeds packaging actions | **Does not create actual bundle/upsell objects — only recommends** | revenue_engines_extended.py |
| E12: Experiment opportunities | What to test | **Fully real** | Reads ActiveExperiment, identifies untested variables | 38/38 proof | No (read-only) | Feeds experiment launch actions | **Does not auto-create experiments — only identifies gaps** | revenue_engines_extended.py |
| E13: Payout speed | Days-to-cash | **Partially real** | Uses structural estimates (hardcoded avg_days_to_cash per source), counts paid/pending from ledger | 38/38 proof | No (read-only) | Feeds allocation priority | **Days-to-cash are static estimates, not computed from actual ledger timestamps** | revenue_engines_extended.py |
| E14: Leak detection | Find lost money | **Fully real** | Queries unattributed revenue, unmonetized content, orphan offers, stalled deals, pending-too-long | 38/38 + 28/28 proof | No (read-only) | Feeds execution engine | None | revenue_engines_extended.py |
| E15: Portfolio allocation | Hero/growth/maintain/pause | **Fully real** | Reads accounts + ledger + content counts, computes portfolio_score, applies scale_role penalty | 38/38 + 28/28 proof | No (read-only) | Feeds execution engine | None | revenue_engines_extended.py |
| E16: Cross-platform compounding | Wins cascade | **Partially real** | Reads platform revenue, identifies expansion targets, reads winning patterns | 38/38 proof | No (read-only) | Feeds execution engine | **Does not create actual cross-platform content briefs — only recommends** | revenue_engines_extended.py |
| E17: Durability scoring | Short-term vs lasting | **Partially real** | Reads ledger over 3 periods, computes volatility + trend, applies structural traits | 38/38 proof | No (read-only) | Recommendation: exploit/diversify/stabilize/reduce | **Structural traits (defensibility, platform_dependence) are hardcoded, not learned** | revenue_engines_extended.py |

### EXECUTION ENGINE + AUTONOMOUS ACTIONS

| Feature | Claimed | Status | What It Does | Runtime Verified | State Changes | Downstream Effects | Missing | Files |
|---------|---------|--------|-------------|-----------------|--------------|-------------------|---------|-------|
| Execution engine | 3-tier governance cycle | **Fully real** | Gathers intelligence from E2+E4+E14+E16, creates OperatorActions with autonomy tier | 43/43 proof | OperatorAction rows | Feeds dispatcher | None | revenue_execution.py |
| Autonomous dispatch | Actions execute real state changes | **Fully real** | Reads pending autonomous actions, calls handler, marks complete, emits events | 43/43 + 28/28 proof | See individual actions below | See individual actions below | None | action_dispatcher.py |
| attach_offer_to_content | Auto-assign best offer | **Fully real + compounding** | Calls assign_offer_to_content with EPC+priority weighted selection | 28/28 proof | ContentItem.offer_id set | Reduces unmonetized count in 6 downstream systems | None | action_dispatcher.py |
| suppress_losing_offer | Deactivate weak offer | **Fully real + compounding** | Sets Offer.is_active=False for lowest-EPC offer | 28/28 proof | Offer.is_active=False | Removes from 10 downstream systems | None | action_dispatcher.py |
| promote_winning_offer | Boost priority + weight | **Fully real + compounding** | Offer.priority+=10, PromotedWinnerRule.weight_boost+=0.15 | 28/28 proof | Offer.priority, PromotedWinnerRule.weight_boost | Affects attach selection, generation context, packaging sort | None | action_dispatcher.py |
| deprioritize_low_margin | Reduce priority | **Fully real + compounding** | Offer.priority-=5 for low-EPC offers | 28/28 proof | Offer.priority | Priority factored into attach, opportunities, packaging | None | action_dispatcher.py |
| reduce_dead_channel | Change scale_role | **Fully real + compounding** | CreatorAccount.scale_role='reduced' for zero-revenue accounts | 28/28 proof | CreatorAccount.scale_role | Fit score penalty, portfolio → pause, excluded from sponsor-ready | None | action_dispatcher.py |
| repair_broken_attribution | Fix unattributed revenue | **Fully real + compounding** | Sets RevenueLedgerEntry.attribution_state + offer_id | 28/28 proof | RevenueLedgerEntry.attribution_state, offer_id | Reduces leak count, shifts allocation/mix | None | action_dispatcher.py |
| recover_failed_webhook | Re-trigger ledger write | **Fully real + compounding** | Reads WebhookEvent.raw_payload, calls ledger write function, then marks processed | 28/28 proof | WebhookEvent.processed, new RevenueLedgerEntry row | Revenue state includes recovered amount | None | action_dispatcher.py |
| Scheduled revenue cycle | Celery Beat every 4h | **Implemented, not runtime-proven** | run_revenue_cycle task: iterates orgs/brands, calls auto_surface + dispatch | Code verified (37/37 static) | OperatorAction rows, state changes via dispatch | Full cycle on schedule | **Never executed by actual Celery Beat — only proven as importable callable** | monetization_worker/tasks.py, celery_app.py |
| Confidence gating | Low-confidence actions not dispatched | **Fully real** | Actions with confidence < 0.6 excluded from autonomous list | 43/43 proof | None (prevents execution) | Low-confidence actions stay pending for operator | None | action_dispatcher.py |

### PRE-EXISTING INFRASTRUCTURE (from original builder)

| Feature | Claimed | Status | What It Does | State Changes | Missing | Files |
|---------|---------|--------|-------------|--------------|---------|-------|
| AI content generation | Generate scripts via Claude/Gemini/DeepSeek | **Real when credentials configured** | Calls real AI APIs with tiered routing + fallback to template | Script row created | API keys required | content_pipeline_service.py, ai_clients.py |
| Media generation | Video via HeyGen/D-ID/Runway/Kling | **Real when credentials configured** | Calls real provider APIs, creates Asset + ContentItem | MediaJob, Asset, ContentItem rows | API keys required; no completion polling | generation_worker/tasks.py |
| Publishing to platforms | Post via Buffer/Publer/Ayrshare | **Real when Buffer configured** | Buffer client makes real HTTP POST to buffer API | PublishJob.status=completed, ContentItem.status=published | Only Buffer wired in worker; Publer/Ayrshare clients exist but unused | publishing_worker/tasks.py |
| Email sending | SMTP | **Real when SMTP configured** | aiosmtplib.send() | EmailSendRequest row | Credentials required | external_clients.py |
| SMS sending | Twilio | **Real when Twilio configured** | HTTP POST to Twilio API | SmsSendRequest row | Credentials required | external_clients.py |
| Webhook signature verification | Stripe HMAC-SHA256, Shopify SHA256 | **Fully real** | hmac.compare_digest with 300s timestamp tolerance | WebhookEvent row | None | webhooks.py, external_clients.py |
| Auth (JWT) | Register/login/token | **Fully real** | bcrypt hashing, JWT HS256, 24h expiry | User, Organization rows | None | auth.py, deps.py |
| Onboarding | New user → brand → accounts → offers | **Fully real** | CRUD creates working data models | Brand, CreatorAccount, Offer rows | None | onboarding_service.py |
| QA scoring engine | Content quality assessment | **Surface-only** | Applies weighting formula to HARDCODED input scores (0.7, 0.85, 0.75, etc.) | QAReport row with fixed values | **Inputs are not computed from actual content. No video/audio/text analysis. Formula is real, data is synthetic.** | content_pipeline_service.py, qa.py |
| Brain Phase A | Memory + state snapshots | **Fully real** | Reads real accounts/offers/suppressions, computes states | BrainMemoryEntry, AccountStateSnapshot rows | None | brain_phase_a_service.py |
| Brain Phase B | Decisions + arbitration | **Fully real computation, no downstream execution** | Computes decision class, policy, confidence, arbitration | BrainDecision, PolicyEvaluation, ArbitrationReport rows | **Decisions are consultative — no code auto-dispatches them into worker tasks** | brain_phase_b_service.py |
| Brain Phase C | Agent mesh | **Not auditable** | Referenced in worker but implementation not provided for audit | Unknown | Unknown | brain_phase_c_service.py |
| Brain Phase D | Meta-monitoring | **Not auditable** | Referenced in worker but implementation not provided for audit | Unknown | Unknown | brain_phase_d_service.py |
| Discovery / signal ingestion | Detect trends and opportunities | **Surface-only** | Manual topic seeding only. No external API calls to Google Trends, YouTube Research, etc. | TopicCandidate rows from manual input | **No automated signal ingestion from any external source** | discovery_service.py |
| Provider health audit | Check provider status | **Surface-only** | Reads env vars for presence of API keys. Does not test connectivity, latency, or rate limits | ProviderRegistryEntry rows | **Rename to "credential registry" — does not audit health** | provider_registry_service.py |
| Autonomous execution loop | Orchestrate content creation automatically | **Surface-only** | Creates AutomationExecutionRun records, evaluates policy gates | Execution run rows | **No orchestration loop dispatches real work. System computes what should happen but doesn't do it.** | autonomous_execution_service.py |
| CRM sync | Sync contacts to Hubspot/Salesforce | **Not real** | Data models exist (CrmContact, CrmSync). No API clients. | DB rows only | **No CRM API integration exists** | live_execution_service.py |
| Performance data collection | Ingest YouTube/TikTok/Instagram analytics | **Not real** | PerformanceMetric model exists. No code fetches data from platform APIs. | DB rows only if manually created | **No analytics API integration. System cannot learn from content performance automatically.** | No client exists |
| 100+ scoring engines | Compute intelligence across all domains | **Mostly real computation** | 97 files in packages/scoring/, 85+ with real computation | Various | **Engines compute from available data. If data is missing/synthetic, output is correspondingly limited.** | packages/scoring/*.py |
| 250+ Celery Beat tasks | Scheduled recomputation | **Implemented, partially runtime-proven** | Beat schedule defined with 250+ entries. Workers execute via TrackedTask. | SystemJob rows + SystemEvent rows | **Proven: TrackedTask writes events. Not proven: all 250 tasks actually run successfully on schedule.** | celery_app.py, workers/ |
| 207 frontend pages | Dashboard UI | **Rendered but many passive** | Next.js pages fetch from API endpoints and display data. 3 pages rebuilt as operational surfaces. | No (display only) | **Most pages are read-only displays of backend data. Only 3 (dashboard, content pipeline, orchestration) have action buttons.** | apps/web/src/app/dashboard/ |

---

## SECTION 2: REALITY GAP LIST

### CRITICAL GAPS (false impressions that could mislead)

| # | Gap | Why Incomplete | Severity | False Impression | Work Needed | Action |
|---|-----|---------------|----------|-----------------|-------------|--------|
| 1 | **QA scoring uses hardcoded inputs** | `run_qa()` passes `originality_score=0.7, compliance_score=0.85` etc. No actual content analysis. | **HIGH** | User thinks content is quality-assessed. It's not — scores are fixed. | Replace hardcoded inputs with actual content analysis (word count, readability, compliance checks, dedup hash). Or honestly label as "placeholder QA". | **Complete now OR demote in UI** |
| 2 | **No performance data collection** | No code fetches views/engagement/revenue from YouTube, TikTok, or any platform API after publishing. | **HIGH** | System appears to track content performance. It has PerformanceMetric model but no data flows in. | Add YouTube Analytics API + TikTok Analytics API clients. Schedule daily ingestion worker. | **Complete now** |
| 3 | **Discovery is manual-only** | `ingest_signals()` only accepts manually provided topics. No Google Trends, YouTube Research, or social media trend API integration. | **MEDIUM** | System appears to discover opportunities. It only stores manually entered topics. | Add external trend API clients. Schedule daily signal scan. | **Demote in UI until real** |
| 4 | **Brain decisions don't auto-execute** | BrainDecision records are created but no worker dispatches content creation, suppression, or scaling based on them. | **MEDIUM** | System appears to make autonomous brain decisions. Decisions are stored as records, not executed. | Wire brain decisions into revenue execution engine as input source. | **Complete now** |
| 5 | **Provider audit is credential-check only** | `audit_providers()` checks env var presence, not actual API connectivity or health. | **LOW** | "Provider health audit" implies testing. It only checks config. | Add actual HTTP ping to each provider. Check latency/error rate. | **Reclassify honestly** |
| 6 | **Autonomous execution loop doesn't orchestrate** | `autonomous_execution_service.py` evaluates policy gates but doesn't dispatch work. | **MEDIUM** | "Autonomous execution" implies the system runs itself. It computes but doesn't act. | The revenue execution engine + action dispatcher partially replaces this. Wire remaining phases. | **Reclassify honestly** |
| 7 | **CRM sync not implemented** | Models exist, no API clients for any CRM. | **LOW** | "CRM Sync" page implies integration. It's a data model only. | Add Hubspot/Salesforce client OR hide page. | **Hide until real** |
| 8 | **Publer/Ayrshare clients unused** | Clients exist in packages/clients/ but publishing_worker only uses Buffer. | **LOW** | System lists 3 publishing platforms. Only 1 is wired. | Wire Publer and Ayrshare into publishing_worker as fallbacks. | **Complete in Phase 2** |
| 9 | **Scheduled revenue cycle not runtime-proven** | Celery Beat entry exists. Task is importable and callable. But never actually fired by Beat in a running system. | **LOW** | "Runs every 4 hours" — true in config, unproven in runtime. | Deploy and verify one actual Beat-triggered cycle. | **Prove during deployment** |
| 10 | **207 pages mostly passive** | 204 of 207 pages are read-only data displays with no action buttons or state-changing capabilities. | **LOW** | UI appears comprehensive. Most pages are reporting surfaces. | Not urgent — focus on the 3 operational pages first. | **Honest classification** |

### NON-CRITICAL GAPS (limitations, not false impressions)

| # | Gap | Note |
|---|-----|------|
| 11 | Archetype scoring uses hardcoded weights | Acceptable for initial version — would improve with learned weights from actual performance data |
| 12 | Payout speed uses static estimates | Acceptable — would improve when actual ledger confirmed_at/paid_out_at timestamps accumulate |
| 13 | Durability traits are hardcoded | Acceptable — structural assumptions are reasonable starting points |
| 14 | Packaging engine recommends but doesn't create objects | Acceptable — packaging actions are in the assisted tier for operator approval |
| 15 | Cross-platform compounding recommends but doesn't create briefs | Acceptable — compounding actions are in the assisted tier |

---

## SECTION 3: FANTASY-TO-REALITY CONVERSION PLAN

### Phase 1: Highest-Risk False Promises (eliminate misleading behavior)

| # | Work | Impact | Effort |
|---|------|--------|--------|
| 1.1 | **Fix QA scoring**: Replace hardcoded inputs with computed values (word count → quality score, readability → compliance, dedup hash → originality, metadata checks → technical) | Eliminates #1 gap. Quality gate becomes real. | Medium |
| 1.2 | **Reclassify provider audit**: Rename "Provider Health Audit" to "Provider Credential Check" in UI and API docs. Add actual HTTP connectivity test as future enhancement. | Eliminates #5 gap. Honest naming. | Low |
| 1.3 | **Reclassify autonomous execution**: Remove or demote "Autonomous Execution" page label. The revenue execution engine IS the real autonomy. Legacy autonomous_execution_service is consultative only. | Eliminates #6 gap. | Low |
| 1.4 | **Hide CRM Sync page** until real API client exists. Or add disclaimer "Coming soon — data model only". | Eliminates #7 gap. | Low |

### Phase 2: Critical Missing Execution Links

| # | Work | Impact | Effort |
|---|------|--------|--------|
| 2.1 | **Add performance data collection**: YouTube Analytics API client + TikTok Analytics API client. Schedule daily ingestion worker. Write to PerformanceMetric table. | Closes #2 gap. System learns from published content. Experiments get real observations. | High |
| 2.2 | **Wire brain decisions to execution**: When brain_phase_b creates a "scale" or "suppress" decision, auto-create corresponding OperatorAction via intelligence_bridge. | Closes #4 gap. Brain becomes prescriptive. | Medium |
| 2.3 | **Wire Publer/Ayrshare as publishing fallbacks**: publishing_worker checks Buffer first, then Publer, then Ayrshare. | Closes #8 gap. Publishing has redundancy. | Medium |

### Phase 3: Missing Feedback Loops

| # | Work | Impact | Effort |
|---|------|--------|--------|
| 3.1 | **Auto-feed experiment observations**: When PerformanceMetric rows arrive (from 2.1), match to active experiments via content_item_id, auto-call add_observation(). | Experiments become self-evaluating. | Medium |
| 3.2 | **Auto-compute payout speed from ledger timestamps**: When ledger entries get confirmed_at/paid_out_at set, compute actual days-to-cash per source type. Replace static estimates. | Payout speed becomes data-driven. | Low |
| 3.3 | **Add external signal ingestion**: Google Trends API or YouTube Keyword Planner for discovery. Schedule daily scan worker. | Discovery becomes automated. Closes #3 gap. | High |

### Phase 4: Missing Autonomous/State-Changing Behavior

| # | Work | Impact | Effort |
|---|------|--------|--------|
| 4.1 | **Prove scheduled revenue cycle in deployment**: After deploying, verify Celery Beat fires run_revenue_cycle and actions are created + dispatched. | Closes #9 gap. Autonomy proven in production. | Low (deployment step) |
| 4.2 | **Auto-create KillLedgerEntry from failure families**: When FailureFamilyReport.failure_count >= threshold, auto-create KillLedgerEntry. | Kill ledger becomes self-populating. | Low |

### Phase 5: Polish (after truth is complete)

| # | Work | Impact | Effort |
|---|------|--------|--------|
| 5.1 | Add action buttons to remaining dashboard pages | UI becomes operational across more surfaces | Medium |
| 5.2 | Learn archetype/durability weights from actual performance data | Scoring becomes adaptive | Medium |
| 5.3 | Add real-time WebSocket updates to control layer | Dashboard reflects state changes instantly | Medium |
