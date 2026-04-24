'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { API_BASE } from '@/lib/api';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type SystemEventPayload = {
  id?: string;
  type: string;                // message envelope type — "system_event", "heartbeat", etc.
  event_domain?: string;
  event_type?: string;
  event_severity?: string;
  entity_type?: string;
  entity_id?: string;
  previous_state?: string;
  new_state?: string;
  summary?: string;
  details?: Record<string, unknown>;
  actor_type?: string;
  requires_action?: boolean;
  brand_id?: string;
  ts?: string;
  created_at?: string;
};

export type UseSystemEventsReturn = {
  /** All events received since mount (newest first, capped at 200) */
  events: SystemEventPayload[];
  /** The most recent event, or null */
  lastEvent: SystemEventPayload | null;
  /** Whether the WebSocket is currently connected */
  connected: boolean;
  /** Last error message, or null */
  error: string | null;
};

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const MAX_EVENTS = 200;
const BASE_RECONNECT_MS = 1_000;
const MAX_RECONNECT_MS = 30_000;

/* ------------------------------------------------------------------ */
/* Hook                                                                */
/* ------------------------------------------------------------------ */

/**
 * useSystemEvents — connects to the organization-scoped WebSocket
 * at /ws/events/{orgId} and streams all SystemEvents in real time.
 *
 * Features:
 *   - Auto-reconnect with exponential backoff (1s → 30s cap)
 *   - Keeps the most recent 200 events in memory
 *   - Sends periodic pings to keep connection alive
 *   - Cleans up fully on unmount
 *   - Reads JWT from localStorage (aro_token)
 */
export function useSystemEvents(orgId: string | null | undefined): UseSystemEventsReturn {
  const [events, setEvents] = useState<SystemEventPayload[]>([]);
  const [lastEvent, setLastEvent] = useState<SystemEventPayload | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const unmounted = useRef(false);

  const getToken = useCallback(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('aro_token');
  }, []);

  const cleanup = useCallback(() => {
    if (pingTimer.current) {
      clearInterval(pingTimer.current);
      pingTimer.current = null;
    }
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      if (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close(1000, 'cleanup');
      }
      wsRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (unmounted.current) return;
    const delay = Math.min(
      BASE_RECONNECT_MS * Math.pow(2, reconnectAttempt.current),
      MAX_RECONNECT_MS,
    );
    reconnectAttempt.current += 1;
    reconnectTimer.current = setTimeout(() => {
      if (!unmounted.current) connect();
    }, delay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connect = useCallback(() => {
    if (unmounted.current || !orgId) return;

    const token = getToken();
    if (!token) {
      setError('No auth token — cannot open WebSocket');
      setConnected(false);
      return;
    }

    cleanup();

    // Build WebSocket URL: convert http(s) to ws(s)
    const wsBase = API_BASE.replace(/^http/, 'ws');
    const url = `${wsBase}/api/v1/ws/events/${orgId}?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmounted.current) return;
      setConnected(true);
      setError(null);
      reconnectAttempt.current = 0;

      // Keepalive ping every 25 seconds
      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 25_000);
    };

    ws.onmessage = (evt) => {
      if (unmounted.current) return;
      try {
        const data: SystemEventPayload = JSON.parse(evt.data);

        // Ignore internal envelope types that are not real events
        if (data.type === 'pong' || data.type === 'heartbeat' || data.type === 'connected') {
          return;
        }

        setLastEvent(data);
        setEvents((prev) => [data, ...prev].slice(0, MAX_EVENTS));
      } catch {
        // Non-JSON message — ignore
      }
    };

    ws.onerror = () => {
      if (unmounted.current) return;
      setError('WebSocket error');
      setConnected(false);
    };

    ws.onclose = (evt) => {
      if (unmounted.current) return;
      setConnected(false);

      // Code 4001 = auth failure — do not reconnect
      if (evt.code === 4001 || evt.code === 4003) {
        setError(evt.reason || 'Authentication failed');
        return;
      }

      // All other closures: reconnect with backoff
      scheduleReconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId, getToken, cleanup, scheduleReconnect]);

  useEffect(() => {
    unmounted.current = false;
    connect();

    return () => {
      unmounted.current = true;
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  return { events, lastEvent, connected, error };
}
