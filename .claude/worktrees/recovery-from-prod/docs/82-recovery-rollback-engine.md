# 82 — Recovery / Rollback Engine

## Purpose
Actively protects the system when things go wrong. Not an error log — it detects incidents, selects playbooks, and executes rollback/reroute/throttle/escalation automatically.

## 6 Tables
rec_incidents, rec_rollbacks, rec_reroutes, rec_throttles, rec_outcomes, rec_playbooks

## 10 Incident Types
provider_failure, publish_failure, bad_scaling_push, experiment_failure_cluster, broken_routing_path, weak_content_push, campaign_failure, dependency_outage, retry_exhaustion, unsafe_system_state

## Recovery Actions
| Action | What it does |
|--------|-------------|
| rollback | Reverts to previously safe state |
| reroute | Switches to fallback provider/path |
| throttle | Reduces output to 25%/50%/minimal |
| retry | Retries up to N times |
| pause | Pauses all operations |
| escalate | Alerts operator for manual intervention |

## Playbooks (10 built-in)
Each incident type has a predefined sequence of recovery steps. Auto-execute flag determines whether the system acts without operator approval.

## Self-Recovery vs Escalation
- Auto-recoverable + auto-execute playbook → **auto_recovering**
- Critical + not auto-recoverable → **escalated** to operator
- Otherwise → **pending_review**

## Downstream Consumers
| Consumer | Integration |
|----------|-------------|
| Copilot | Recovery summary (open incidents, critical count, status) in grounded context |
| Publishing worker | Publish failures trigger rollback to draft |
| Provider readiness | Provider failures trigger reroute to fallback |
| Campaign execution | Campaign failures trigger pause + reroute |
| Scale logic | Bad scaling push triggers throttle + rollback |

## API (6 endpoints)
incidents, recompute, rollbacks, reroutes, throttles, outcomes

## Worker
`scan_recovery` — every 10 minutes
