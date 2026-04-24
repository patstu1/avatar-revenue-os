"""Batch 9 fulfillment worker.

Closes the autonomous tail of the revenue circle for every avenue:

  - ``drain_pending_production_jobs``: picks up production_jobs in
    status='queued' and transitions them to 'in_progress' so downstream
    workers / GM can complete them. Surfaces stale in-progress jobs
    via escalation.
  - ``dispatch_due_followups``: sends scheduled post-delivery follow-ups
    whose followup_scheduled_at has matured.
  - ``chase_unpaid_proposals_task``: sends next-in-sequence dunning
    reminders for proposals in status='sent' that haven't paid.
  - ``reconcile_stripe_webhooks_task``: fills gaps from missed Stripe
    webhook deliveries by polling Stripe /v1/events per org.
"""
