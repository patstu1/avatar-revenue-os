'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi, accountsApi, apiFetch } from '@/lib/api';
import {
  Activity, AlertTriangle, CheckCircle2, Clock, ExternalLink,
  Eye, Loader2, Plug, RefreshCw, Shield, Upload, Video, XCircle, Zap,
} from 'lucide-react';

/* ─── Types ─── */

type Brand = { id: string; name: string };

interface YouTubeAccount {
  id: string;
  platform_username: string;
  credential_status: string;
  token_expires_at: string | null;
  token_health: string;
  follower_count: number;
  last_synced_at: string | null;
  upload_ready: boolean;
  uploads_today: number;
  last_publish: {
    status: string;
    platform_post_url: string | null;
    published_at: string | null;
    error_message: string | null;
  } | null;
  recent_metrics: {
    views: number;
    likes: number;
    comments: number;
    watch_time_seconds: number;
    rpm: number;
    engagement_rate: number;
  } | null;
}

interface YouTubeDashboard {
  accounts: YouTubeAccount[];
  quota: { daily_upload_limit: number; uploads_today: number; remaining: number };
}

/* ─── Helpers ─── */

const API_BASE = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || window.location.origin)
  : '';

function healthColor(h: string) {
  switch (h) {
    case 'healthy': return 'text-emerald-400';
    case 'expiring': return 'text-amber-400';
    case 'expired': return 'text-red-400';
    default: return 'text-gray-500';
  }
}

function healthBadge(h: string) {
  const cls = {
    healthy: 'chip-green',
    expiring: 'chip-amber',
    expired: 'chip-red',
    disconnected: 'chip-red',
    unknown: 'chip-amber',
  }[h] ?? 'chip';
  return <span className={cls}>{h.toUpperCase()}</span>;
}

function timeAgo(iso: string | null) {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatWatchTime(seconds: number) {
  if (!seconds) return '0h';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

/* ─── Page ─── */

export default function YouTubeDashboardPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : d?.items ?? [];
    }),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['youtube-dashboard', brandId],
    queryFn: () => apiFetch(`/api/v1/youtube/dashboard?brand_id=${brandId}`) as Promise<YouTubeDashboard>,
    enabled: !!brandId,
    refetchInterval: 30000,
  });

  const syncMutation = useMutation({
    mutationFn: (accountId: string) => accountsApi.triggerSync(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['youtube-dashboard', brandId] });
    },
  });

  const handleConnect = (accountId?: string) => {
    const params = new URLSearchParams({ brand_id: brandId! });
    if (accountId) params.set('account_id', accountId);
    window.location.href = `${API_BASE}/api/v1/oauth/connect/youtube?${params}`;
  };

  const accounts = dashboard?.accounts ?? [];
  const quota = dashboard?.quota;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded bg-red-900/40 flex items-center justify-center">
            <Video className="text-red-400" size={22} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">YouTube Integration</h1>
            <p className="text-gray-400 mt-1">Channel connections, upload readiness, and performance</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="input-field min-w-[180px]"
            value={brandId ?? ''}
            onChange={(e) => setBrandId(e.target.value || null)}
          >
            {!brands?.length && <option value="">No brands</option>}
            {(brands as Brand[] | undefined)?.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
          <button className="btn-primary flex items-center gap-2" onClick={() => handleConnect()}>
            <Plug size={16} /> Connect Channel
          </button>
        </div>
      </div>

      {/* Quota Bar */}
      {quota && (
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="metric-label">Daily Upload Quota</span>
            <span className="font-mono text-sm text-gray-300">
              {quota.uploads_today} / {quota.daily_upload_limit * Math.max(1, accounts.length)} used
            </span>
          </div>
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                quota.remaining === 0 ? 'bg-red-500' : quota.remaining <= 2 ? 'bg-amber-500' : 'bg-emerald-500'
              }`}
              style={{
                width: `${Math.min(100, (quota.uploads_today / Math.max(1, quota.daily_upload_limit * Math.max(1, accounts.length))) * 100)}%`,
              }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1 font-mono">{quota.remaining} uploads remaining today</p>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="card flex items-center justify-center py-12">
          <Loader2 className="animate-spin text-gray-500" size={24} />
        </div>
      )}

      {/* No Accounts */}
      {!isLoading && !accounts.length && (
        <div className="card text-center py-12">
          <Video className="mx-auto text-gray-600 mb-3" size={32} />
          <p className="text-gray-400">No YouTube channels connected</p>
          <p className="text-gray-600 text-sm mt-1">Connect a channel to start uploading</p>
          <button className="btn-primary mt-4" onClick={() => handleConnect()}>
            <Plug size={16} className="inline mr-2" /> Connect YouTube
          </button>
        </div>
      )}

      {/* Account Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {accounts.map((acct) => (
          <div key={acct.id} className="card space-y-4">
            {/* Account Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded bg-red-900/40 flex items-center justify-center text-red-400 font-mono font-bold text-sm">
                  YT
                </div>
                <div>
                  <p className="text-white font-medium">{acct.platform_username}</p>
                  <p className="text-gray-500 text-xs font-mono">{acct.follower_count.toLocaleString()} subscribers</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {healthBadge(acct.token_health)}
                {acct.upload_ready ? (
                  <span className="chip-green"><Upload size={12} className="mr-1" /> Ready</span>
                ) : (
                  <span className="chip-red"><XCircle size={12} className="mr-1" /> Not Ready</span>
                )}
              </div>
            </div>

            {/* Connection Details */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-gray-800/50 rounded p-3">
                <p className="metric-label">Auth Status</p>
                <p className={`text-sm font-mono font-semibold ${healthColor(acct.token_health)}`}>
                  {acct.credential_status}
                </p>
              </div>
              <div className="bg-gray-800/50 rounded p-3">
                <p className="metric-label">Token Expires</p>
                <p className="text-sm font-mono text-gray-300">
                  {acct.token_expires_at ? timeAgo(acct.token_expires_at) : 'N/A'}
                </p>
              </div>
              <div className="bg-gray-800/50 rounded p-3">
                <p className="metric-label">Last Sync</p>
                <p className="text-sm font-mono text-gray-300">{timeAgo(acct.last_synced_at)}</p>
              </div>
            </div>

            {/* Recent Metrics */}
            {acct.recent_metrics && (
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-gray-800/50 rounded p-3">
                  <p className="metric-label">Views</p>
                  <p className="metric-value text-lg">{acct.recent_metrics.views.toLocaleString()}</p>
                </div>
                <div className="bg-gray-800/50 rounded p-3">
                  <p className="metric-label">Watch Time</p>
                  <p className="metric-value text-lg">{formatWatchTime(acct.recent_metrics.watch_time_seconds)}</p>
                </div>
                <div className="bg-gray-800/50 rounded p-3">
                  <p className="metric-label">RPM</p>
                  <p className="metric-value text-lg text-emerald-400">${acct.recent_metrics.rpm}</p>
                </div>
                <div className="bg-gray-800/50 rounded p-3">
                  <p className="metric-label">Engagement</p>
                  <p className="metric-value text-lg">{(acct.recent_metrics.engagement_rate * 100).toFixed(1)}%</p>
                </div>
              </div>
            )}

            {/* Last Publish */}
            {acct.last_publish && (
              <div className={`rounded p-3 border ${
                acct.last_publish.status === 'completed' ? 'border-emerald-900/50 bg-emerald-950/20' :
                acct.last_publish.status === 'failed' ? 'border-red-900/50 bg-red-950/20' :
                'border-gray-800 bg-gray-800/30'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {acct.last_publish.status === 'completed' ? (
                      <CheckCircle2 size={16} className="text-emerald-400" />
                    ) : acct.last_publish.status === 'failed' ? (
                      <XCircle size={16} className="text-red-400" />
                    ) : (
                      <Clock size={16} className="text-amber-400" />
                    )}
                    <span className="text-sm text-gray-300 font-mono">
                      Last publish: {acct.last_publish.status}
                    </span>
                  </div>
                  <span className="text-xs text-gray-500">{timeAgo(acct.last_publish.published_at)}</span>
                </div>
                {acct.last_publish.platform_post_url && (
                  <a
                    href={acct.last_publish.platform_post_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-brand-400 hover:text-brand-300 mt-1 inline-flex items-center gap-1"
                  >
                    <ExternalLink size={12} /> View on YouTube
                  </a>
                )}
                {acct.last_publish.error_message && (
                  <p className="text-xs text-red-400 mt-1">{acct.last_publish.error_message}</p>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2">
              <button
                className="btn-secondary flex items-center gap-2 text-sm"
                onClick={() => syncMutation.mutate(acct.id)}
                disabled={syncMutation.isPending}
              >
                {syncMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                Sync Now
              </button>
              {acct.token_health === 'expired' || acct.token_health === 'disconnected' ? (
                <button
                  className="btn-primary flex items-center gap-2 text-sm"
                  onClick={() => handleConnect(acct.id)}
                >
                  <Plug size={14} /> Reconnect
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
