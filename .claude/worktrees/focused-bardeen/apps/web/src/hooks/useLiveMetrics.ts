'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { controlLayerApi } from '@/lib/control-layer-api';
import { analyticsApi } from '@/lib/analytics-api';
import { useSystemEvents, type SystemEventPayload } from './useSystemEvents';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type LiveMetrics = {
  /** Gross revenue (30-day window) */
  revenue: number;
  /** Total active social/creator accounts */
  activeAccounts: number;
  /** Content items currently in the pipeline (not yet published) */
  contentInQueue: number;
  /** Counts by publishing status */
  publishingStatus: {
    draft: number;
    generating: number;
    review: number;
    approved: number;
    publishing: number;
    published: number;
    failed: number;
  };
  /** Pending operator actions */
  pendingActions: number;
  /** Running background jobs */
  jobsRunning: number;
  /** Whether the WebSocket feed is connected */
  wsConnected: boolean;
};

/* ------------------------------------------------------------------ */
/* Hook                                                                */
/* ------------------------------------------------------------------ */

/**
 * useLiveMetrics — combines WebSocket events with periodic API polling
 * to deliver live-updating dashboard metrics.
 *
 * Strategy:
 *   - Uses React Query for polling the control-layer dashboard every 15s
 *   - Listens to WebSocket system events and applies incremental state changes
 *   - Falls back gracefully to polling-only if the WebSocket disconnects
 */
export function useLiveMetrics(
  orgId: string | null | undefined,
  brandId: string | null | undefined,
): LiveMetrics {
  const queryClient = useQueryClient();

  // --- WebSocket feed ---
  const { lastEvent, connected: wsConnected } = useSystemEvents(orgId);

  // --- Polled data ---
  const { data: ctrl } = useQuery({
    queryKey: ['control-layer-dashboard'],
    queryFn: () => controlLayerApi.dashboard().then((r: any) => r.data),
    refetchInterval: wsConnected ? 30_000 : 15_000, // poll less often when WS is live
  });

  const { data: revenue } = useQuery({
    queryKey: ['analytics-revenue-dashboard', brandId],
    queryFn: () => analyticsApi.revenueDashboard(brandId!).then((r: any) => r.data),
    enabled: Boolean(brandId),
    refetchInterval: wsConnected ? 60_000 : 30_000,
  });

  // --- Incremental deltas from WebSocket ---
  const [deltas, setDeltas] = useState({
    revenueAdj: 0,
    contentQueueAdj: 0,
    publishedAdj: 0,
    failedAdj: 0,
  });

  // Reset deltas whenever polled data refreshes
  const lastCtrlRef = useRef(ctrl);
  useEffect(() => {
    if (ctrl && ctrl !== lastCtrlRef.current) {
      lastCtrlRef.current = ctrl;
      setDeltas({ revenueAdj: 0, contentQueueAdj: 0, publishedAdj: 0, failedAdj: 0 });
    }
  }, [ctrl]);

  // Apply WebSocket events as incremental adjustments
  useEffect(() => {
    if (!lastEvent) return;

    const eventType = lastEvent.event_type || '';
    const domain = lastEvent.event_domain || '';
    const newState = lastEvent.new_state || '';

    // Content state transitions
    if (domain === 'content' && eventType.includes('state_changed')) {
      if (newState === 'published') {
        setDeltas((d) => ({
          ...d,
          publishedAdj: d.publishedAdj + 1,
          contentQueueAdj: d.contentQueueAdj - 1,
        }));
      } else if (newState === 'failed') {
        setDeltas((d) => ({
          ...d,
          failedAdj: d.failedAdj + 1,
          contentQueueAdj: d.contentQueueAdj - 1,
        }));
      } else if (newState === 'draft' || newState === 'generating') {
        setDeltas((d) => ({
          ...d,
          contentQueueAdj: d.contentQueueAdj + 1,
        }));
      }
    }

    // Revenue events
    if (domain === 'monetization' && lastEvent.details) {
      const amount = Number((lastEvent.details as any).amount || 0);
      if (amount > 0) {
        setDeltas((d) => ({ ...d, revenueAdj: d.revenueAdj + amount }));
      }
    }

    // Invalidate React Query caches so the next poll picks up the change
    queryClient.invalidateQueries({ queryKey: ['control-layer-dashboard'] });
  }, [lastEvent, queryClient]);

  // --- Derive final metrics ---
  const health = ctrl?.health;

  const metrics: LiveMetrics = useMemo(() => {
    const baseRevenue = revenue?.gross_revenue ?? health?.total_revenue_30d ?? 0;
    const baseQueue =
      (health?.content_draft ?? 0) +
      (health?.content_generating ?? 0) +
      (health?.content_review ?? 0) +
      (health?.content_approved ?? 0) +
      (health?.content_publishing ?? 0);

    return {
      revenue: baseRevenue + deltas.revenueAdj,
      activeAccounts: health?.total_accounts ?? 0,
      contentInQueue: Math.max(0, baseQueue + deltas.contentQueueAdj),
      publishingStatus: {
        draft: health?.content_draft ?? 0,
        generating: health?.content_generating ?? 0,
        review: health?.content_review ?? 0,
        approved: health?.content_approved ?? 0,
        publishing: health?.content_publishing ?? 0,
        published: (health?.content_published ?? 0) + deltas.publishedAdj,
        failed: (health?.content_failed ?? 0) + deltas.failedAdj,
      },
      pendingActions: health?.actions_pending ?? 0,
      jobsRunning: health?.jobs_running ?? 0,
      wsConnected,
    };
  }, [health, revenue, deltas, wsConnected]);

  return metrics;
}
