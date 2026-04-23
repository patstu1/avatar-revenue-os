# Account Expansion Advisor

## Overview
Proactively determines when more creator accounts are needed — or explicitly states when they are NOT — with execution-grade launch guidance backed by real system evidence.

## Core Questions Answered
1. **Do we need more accounts now?** → `should_add_account_now` (boolean)
2. **If yes, exactly what?** → platform, niche, sub_niche, account_type, content_role, monetization_path
3. **If no, why not?** → `hold_reason` with specific cause
4. **What must change?** → `blockers` list with actionable items
5. **New account vs push existing?** → `evidence.incremental_profit_new` vs `evidence.incremental_profit_existing`

## Evidence Inputs
- Scale engine output (incremental profit comparison, readiness, cannibalization, segment separation)
- Account health, fatigue, saturation scores
- Offer count and content count
- Expansion confidence from scale readiness math

## Blockers That Prevent Expansion
- `no_offers` — cannot monetize without offers
- `unhealthy_accounts` — stabilize before expanding
- `low_content` — fewer than 5 items
- `high_fatigue` — audience fatigue > 70%
- `high_saturation` — noted but supports expansion case

## API
- `GET /brands/{id}/expansion-advisor` — current advisory
- `POST /brands/{id}/expansion-advisor/recompute` — recompute from live data

## Migration
Revision: `expansion_adv_001` (down_revision: `gatekeeper_001`)
