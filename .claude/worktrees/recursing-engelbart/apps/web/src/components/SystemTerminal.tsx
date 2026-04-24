'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { controlLayerApi } from '@/lib/control-layer-api';
import { Terminal, Filter } from 'lucide-react';

/* ─── Types ─── */

interface SystemEvent {
  id: string;
  event_domain: string;
  event_type: string;
  event_severity: string;
  entity_type?: string;
  entity_id?: string;
  previous_state?: string;
  new_state?: string;
  created_at: string;
}

/* ─── Constants ─── */

const DOMAINS = ['all', 'content', 'publishing', 'monetization', 'intelligence', 'orchestration', 'system'] as const;

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'text-red-400',
  error: 'text-red-300',
  warning: 'text-amber-300',
  info: 'text-gray-400',
};

const DOMAIN_COLORS: Record<string, string> = {
  content: 'text-purple-400',
  publishing: 'text-cyan-400',
  monetization: 'text-emerald-400',
  intelligence: 'text-blue-400',
  orchestration: 'text-amber-400',
  governance: 'text-pink-400',
  recovery: 'text-orange-400',
  account: 'text-teal-400',
  brand: 'text-indigo-400',
  system: 'text-gray-400',
};

/* ─── Component ─── */

export function SystemTerminal({
  maxLines = 50,
  refreshInterval = 10000,
}: {
  maxLines?: number;
  refreshInterval?: number;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [domain, setDomain] = useState<string>('all');
  const [autoScroll, setAutoScroll] = useState(true);

  const { data } = useQuery({
    queryKey: ['system-terminal-events', domain],
    queryFn: () =>
      controlLayerApi
        .events({ domain: domain === 'all' ? undefined : domain, limit: maxLines })
        .then((r) => (r.data ?? []) as SystemEvent[]),
    refetchInterval: refreshInterval,
  });

  const events = data ?? [];

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  };

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString('en-US', { hour12: false });
    } catch {
      return '00:00:00';
    }
  };

  const formatEventLine = (e: SystemEvent) => {
    const parts = [e.event_type];
    if (e.entity_type) parts.push(`${e.entity_type}`);
    if (e.new_state) parts.push(`→ ${e.new_state}`);
    return parts.join(' ');
  };

  return (
    <div className="card-terminal">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-gray-500" />
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">System Log</span>
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        </div>
        <div className="flex items-center gap-1">
          <Filter size={12} className="text-gray-600" />
          {DOMAINS.map((d) => (
            <button
              key={d}
              className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase transition-colors ${
                domain === d
                  ? 'bg-gray-700 text-gray-200'
                  : 'text-gray-600 hover:text-gray-400'
              }`}
              onClick={() => setDomain(d)}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Log Lines */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="h-64 overflow-y-auto space-y-0.5 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent"
      >
        {events.length === 0 ? (
          <p className="text-gray-600 text-xs">Waiting for events...</p>
        ) : (
          events.map((e) => (
            <div key={e.id} className="flex gap-2 leading-5 hover:bg-white/[0.02] px-1 rounded">
              <span className="text-gray-600 shrink-0">{formatTime(e.created_at)}</span>
              <span className="text-gray-600 shrink-0">&gt;&gt;</span>
              <span className={`shrink-0 ${DOMAIN_COLORS[e.event_domain] ?? 'text-gray-500'}`}>
                [{e.event_domain}]
              </span>
              <span className={SEVERITY_COLORS[e.event_severity] ?? 'text-gray-400'}>
                {formatEventLine(e)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
