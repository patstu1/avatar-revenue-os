'use client';

import { useQuery } from '@tanstack/react-query';
import { accountsApi } from '@/lib/api';

/* ─── Types ─── */

interface Account {
  id: string;
  platform: string;
  platform_username: string;
  credential_status: string;
  is_active: boolean;
}

/* ─── Platform Colors ─── */

const PLATFORM_COLORS: Record<string, string> = {
  youtube: 'bg-red-400',
  tiktok: 'bg-cyan-400',
  instagram: 'bg-fuchsia-400',
  x: 'bg-zinc-100',
  threads: 'bg-zinc-200',
  facebook: 'bg-blue-400',
  linkedin: 'bg-indigo-400',
  reddit: 'bg-orange-400',
  snapchat: 'bg-yellow-400',
  pinterest: 'bg-red-300',
  rumble: 'bg-green-400',
  twitch: 'bg-purple-400',
  kick: 'bg-emerald-400',
  bluesky: 'bg-sky-400',
  spotify: 'bg-green-400',
  telegram: 'bg-blue-300',
  discord: 'bg-indigo-300',
  substack: 'bg-orange-300',
  medium: 'bg-gray-300',
  blog: 'bg-gray-400',
};

const STATUS_COLORS: Record<string, string> = {
  connected: 'bg-emerald-400',
  expiring: 'bg-yellow-400',
  error: 'bg-red-400',
  disconnected: 'bg-gray-600',
  not_connected: 'bg-gray-600',
};

function platformLabel(p: string) {
  return p.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ─── Component ─── */

export function ChannelPills({ brandId }: { brandId?: string | null }) {
  const { data: accounts } = useQuery({
    queryKey: ['channel-pills-accounts', brandId],
    queryFn: () =>
      accountsApi.list(brandId ? { brand_id: brandId } : undefined).then((r) => {
        const d = r.data;
        return (Array.isArray(d) ? d : d?.items ?? []) as Account[];
      }),
    enabled: true,
  });

  const active = (accounts ?? []).filter((a) => a.is_active);

  if (!active.length) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
      {active.map((acct) => (
        <div
          key={acct.id}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-800 border border-gray-700 whitespace-nowrap shrink-0"
        >
          <span className={`w-2 h-2 rounded-full ${PLATFORM_COLORS[acct.platform] ?? 'bg-gray-400'}`} />
          <span className="text-xs font-mono text-gray-300">{acct.platform_username}</span>
          <span className={`w-1.5 h-1.5 rounded-full ${STATUS_COLORS[acct.credential_status] ?? 'bg-gray-600'}`} />
        </div>
      ))}
    </div>
  );
}
