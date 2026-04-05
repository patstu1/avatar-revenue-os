'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi, accountsApi, api } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  ChevronDown,
  Clock,
  Edit3,
  ExternalLink,
  Eye,
  FileText,
  Filter,
  Globe,
  Hash,
  Instagram,
  Layers,
  Loader2,
  Monitor,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  Send,
  Shield,
  Sparkles,
  Trash2,
  Video,
  Volume2,
  X,
  XCircle,
  Zap,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type Brand = { id: string; name: string };
type Account = { id: string; name: string; platform: string; brand_id: string };

interface ContentItem {
  id: string;
  title: string;
  description?: string;
  status: string;
  content_type?: string;
  platform?: string;
  target_platform?: string;
  quality_tier?: string;
  brand_id?: string;
  brand_name?: string;
  account_id?: string;
  account_name?: string;
  brief_text?: string;
  script_text?: string;
  script_content?: string;
  hook?: string;
  angle?: string;
  media_url?: string;
  media_type?: string;
  thumbnail_url?: string;
  created_at: string;
  updated_at?: string;
  published_at?: string;
  scheduled_at?: string;
  status_history?: { status: string; timestamp: string; note?: string }[];
  monetization_method?: string;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function errMsg(e: unknown) {
  const ax = e as { response?: { data?: { detail?: string } } };
  return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d`;
  return `${Math.floor(days / 7)}w`;
}

function truncate(str: string, len: number) {
  if (!str) return '';
  return str.length > len ? str.slice(0, len) + '...' : str;
}

/* ------------------------------------------------------------------ */
/* Column definitions                                                  */
/* ------------------------------------------------------------------ */

const KANBAN_COLUMNS = [
  {
    key: 'ideated',
    label: 'Ideated',
    color: 'text-gray-400',
    borderColor: 'border-gray-600',
    bgHeader: 'bg-gray-800/60',
    dotColor: 'bg-gray-500',
    statuses: ['draft', 'brief_ready'],
  },
  {
    key: 'scripted',
    label: 'Scripted',
    color: 'text-purple-400',
    borderColor: 'border-purple-600',
    bgHeader: 'bg-purple-900/30',
    dotColor: 'bg-purple-500',
    statuses: ['script_generated', 'generated'],
  },
  {
    key: 'generating',
    label: 'Generating',
    color: 'text-cyan-400',
    borderColor: 'border-cyan-600',
    bgHeader: 'bg-cyan-900/30',
    dotColor: 'bg-cyan-500',
    statuses: ['generating', 'media_queued', 'qa_review', 'qa_complete'],
  },
  {
    key: 'ready',
    label: 'Ready to Publish',
    color: 'text-green-400',
    borderColor: 'border-green-600',
    bgHeader: 'bg-green-900/30',
    dotColor: 'bg-green-500',
    statuses: ['media_complete', 'approved', 'scheduled'],
  },
  {
    key: 'published',
    label: 'Published',
    color: 'text-emerald-400',
    borderColor: 'border-emerald-600',
    bgHeader: 'bg-emerald-900/30',
    dotColor: 'bg-emerald-500',
    statuses: ['published', 'publishing'],
  },
] as const;

/* ------------------------------------------------------------------ */
/* Platform icon                                                       */
/* ------------------------------------------------------------------ */

function PlatformIcon({ platform, size = 14 }: { platform?: string; size?: number }) {
  const p = (platform || '').toLowerCase();
  if (p.includes('instagram')) return <Instagram size={size} className="text-pink-400" />;
  if (p.includes('youtube')) return <Play size={size} className="text-red-400" />;
  if (p.includes('tiktok')) return <Video size={size} className="text-cyan-300" />;
  if (p.includes('twitter') || p.includes('x')) return <Hash size={size} className="text-blue-400" />;
  if (p.includes('facebook')) return <Globe size={size} className="text-blue-500" />;
  if (p.includes('linkedin')) return <Monitor size={size} className="text-blue-300" />;
  return <Globe size={size} className="text-gray-500" />;
}

/* ------------------------------------------------------------------ */
/* Tier badge                                                          */
/* ------------------------------------------------------------------ */

function TierBadge({ tier }: { tier?: string }) {
  if (!tier) return null;
  const t = tier.toLowerCase();
  const cfg =
    t === 'cinema'
      ? { label: 'Cinema', bg: 'bg-amber-500/15 border-amber-500/40 text-amber-300' }
      : t === 'premium'
        ? { label: 'Premium', bg: 'bg-purple-500/15 border-purple-500/40 text-purple-300' }
        : { label: 'Standard', bg: 'bg-gray-500/15 border-gray-500/40 text-gray-400' };
  return (
    <span className={`text-[10px] font-medium border rounded px-1.5 py-0.5 ${cfg.bg}`}>
      {cfg.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Kanban Card                                                         */
/* ------------------------------------------------------------------ */

function KanbanCard({
  item,
  onClick,
}: {
  item: ContentItem;
  onClick: () => void;
}) {
  const platform = item.platform || item.target_platform;

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-gray-900/80 hover:bg-gray-800/80 border border-gray-800/60 hover:border-gray-700/60 rounded-lg p-3 transition-all group cursor-pointer"
    >
      <div className="flex items-start gap-2 mb-2">
        <PlatformIcon platform={platform} size={14} />
        <h4 className="text-sm font-medium text-white group-hover:text-cyan-400 transition leading-snug flex-1 min-w-0">
          {truncate(item.title, 55)}
        </h4>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <TierBadge tier={item.quality_tier} />
        {item.account_name && (
          <span className="text-[10px] text-gray-500 truncate max-w-[100px]">
            {item.account_name}
          </span>
        )}
        <span className="text-[10px] text-gray-600 ml-auto flex items-center gap-1">
          <Clock size={10} />
          {timeAgo(item.updated_at || item.created_at)}
        </span>
      </div>
      {item.status === 'generating' && (
        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-cyan-400">
          <Loader2 size={10} className="animate-spin" />
          Processing...
        </div>
      )}
      {(item.status === 'quality_blocked' || item.status === 'failed') && (
        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-red-400">
          <AlertTriangle size={10} />
          {item.status === 'quality_blocked' ? 'Blocked' : 'Failed'}
        </div>
      )}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Kanban Column                                                       */
/* ------------------------------------------------------------------ */

function KanbanColumn({
  column,
  items,
  onCardClick,
}: {
  column: (typeof KANBAN_COLUMNS)[number];
  items: ContentItem[];
  onCardClick: (item: ContentItem) => void;
}) {
  return (
    <div className="flex flex-col min-w-[280px] lg:min-w-0 lg:flex-1">
      {/* Header */}
      <div className={`flex items-center gap-2 px-3 py-2.5 rounded-t-lg border-b-2 ${column.bgHeader} ${column.borderColor}`}>
        <span className={`h-2.5 w-2.5 rounded-full ${column.dotColor}`} />
        <span className={`text-sm font-semibold ${column.color}`}>{column.label}</span>
        <span className="ml-auto text-xs text-gray-500 bg-gray-800/60 rounded-full px-2 py-0.5">
          {items.length}
        </span>
      </div>
      {/* Cards */}
      <div className="flex-1 flex flex-col gap-2 p-2 bg-gray-950/40 rounded-b-lg min-h-[200px] max-h-[calc(100vh-320px)] overflow-y-auto scrollbar-thin">
        {items.length === 0 ? (
          <div className="flex-1 flex items-center justify-center py-8">
            <p className="text-xs text-gray-600 italic">No content in this stage</p>
          </div>
        ) : (
          items.map((item) => (
            <KanbanCard key={item.id} item={item} onClick={() => onCardClick(item)} />
          ))
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Detail Slide-in Panel                                               */
/* ------------------------------------------------------------------ */

function DetailPanel({
  item,
  onClose,
  onPublish,
  onRegenerate,
  onDelete,
  publishing,
  regenerating,
  deleting,
}: {
  item: ContentItem;
  onClose: () => void;
  onPublish: () => void;
  onRegenerate: () => void;
  onDelete: () => void;
  publishing: boolean;
  regenerating: boolean;
  deleting: boolean;
}) {
  const platform = item.platform || item.target_platform;
  const script = item.script_text || item.script_content;
  const mediaUrl = item.media_url;
  const isVideo = item.media_type?.includes('video') || mediaUrl?.match(/\.(mp4|webm|mov)/i);
  const isAudio = item.media_type?.includes('audio') || mediaUrl?.match(/\.(mp3|wav|ogg)/i);

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />
      {/* Panel */}
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-lg bg-gray-950 border-l border-gray-800 z-50 flex flex-col animate-in slide-in-from-right duration-200">
        {/* Panel header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800/60">
          <div className="flex items-center gap-2 min-w-0">
            <PlatformIcon platform={platform} size={18} />
            <h2 className="text-lg font-semibold text-white truncate">{item.title}</h2>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition p-1">
            <X size={20} />
          </button>
        </div>

        {/* Panel body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-6">
          {/* Meta row */}
          <div className="flex items-center gap-3 flex-wrap">
            <TierBadge tier={item.quality_tier} />
            <span className="text-xs text-gray-500">
              {String(item.content_type || '').replace(/_/g, ' ')}
            </span>
            {item.account_name && (
              <span className="text-xs text-gray-400">@ {item.account_name}</span>
            )}
            {item.monetization_method && (
              <span className="text-[10px] text-gray-600 uppercase">{item.monetization_method}</span>
            )}
          </div>

          {/* Brief text */}
          {(item.brief_text || item.hook || item.angle || item.description) && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Brief</h3>
              <div className="bg-gray-900/60 border border-gray-800/60 rounded-lg p-3 text-sm text-gray-300 whitespace-pre-wrap">
                {item.brief_text || item.description || ''}
                {item.hook && (
                  <p className="mt-2 text-xs text-gray-500">
                    <span className="text-gray-600 font-medium">Hook: </span>
                    {item.hook}
                  </p>
                )}
                {item.angle && (
                  <p className="mt-1 text-xs text-gray-500">
                    <span className="text-gray-600 font-medium">Angle: </span>
                    {item.angle}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Script content */}
          {script && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Script</h3>
              <div className="bg-gray-900/60 border border-gray-800/60 rounded-lg p-3 text-sm text-gray-300 whitespace-pre-wrap max-h-64 overflow-y-auto">
                {script}
              </div>
            </div>
          )}

          {/* Media player */}
          {mediaUrl && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Media</h3>
              <div className="bg-gray-900/60 border border-gray-800/60 rounded-lg overflow-hidden">
                {isVideo ? (
                  <video
                    src={mediaUrl}
                    controls
                    className="w-full max-h-[300px] object-contain bg-black"
                    poster={item.thumbnail_url}
                  />
                ) : isAudio ? (
                  <div className="p-4 flex items-center gap-3">
                    <Volume2 size={20} className="text-cyan-400 shrink-0" />
                    <audio src={mediaUrl} controls className="w-full" />
                  </div>
                ) : (
                  <a
                    href={mediaUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 p-3 text-sm text-cyan-400 hover:text-cyan-300 transition"
                  >
                    <ExternalLink size={14} />
                    View media asset
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Status history timeline */}
          {item.status_history && item.status_history.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Status History
              </h3>
              <div className="space-y-0">
                {item.status_history.map((entry, i) => (
                  <div key={i} className="flex items-start gap-3 relative">
                    <div className="flex flex-col items-center">
                      <div className="w-2 h-2 rounded-full bg-gray-600 mt-1.5 shrink-0" />
                      {i < item.status_history!.length - 1 && (
                        <div className="w-px h-6 bg-gray-800" />
                      )}
                    </div>
                    <div className="pb-3">
                      <p className="text-xs text-gray-300 font-medium">
                        {String(entry.status).replace(/_/g, ' ')}
                      </p>
                      <p className="text-[10px] text-gray-600">
                        {new Date(entry.timestamp).toLocaleString()}
                        {entry.note && ` - ${entry.note}`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Panel actions */}
        <div className="border-t border-gray-800/60 px-5 py-4 flex items-center gap-2 flex-wrap">
          {['approved', 'media_complete', 'scheduled'].includes(item.status) && (
            <button
              onClick={onPublish}
              disabled={publishing}
              className="flex items-center gap-1.5 text-xs font-medium bg-green-500/20 text-green-300 border border-green-500/30 rounded-lg px-3 py-2 hover:bg-green-500/30 transition disabled:opacity-50"
            >
              {publishing ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
              Publish Now
            </button>
          )}
          <button
            onClick={onRegenerate}
            disabled={regenerating}
            className="flex items-center gap-1.5 text-xs font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-lg px-3 py-2 hover:bg-purple-500/30 transition disabled:opacity-50"
          >
            {regenerating ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Regenerate
          </button>
          <button
            className="flex items-center gap-1.5 text-xs font-medium bg-gray-500/15 text-gray-300 border border-gray-500/30 rounded-lg px-3 py-2 hover:bg-gray-500/25 transition"
          >
            <Edit3 size={12} />
            Edit
          </button>
          <button
            onClick={onDelete}
            disabled={deleting}
            className="flex items-center gap-1.5 text-xs font-medium bg-red-500/15 text-red-300 border border-red-500/30 rounded-lg px-3 py-2 hover:bg-red-500/25 transition disabled:opacity-50 ml-auto"
          >
            {deleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
            Delete
          </button>
        </div>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Bulk Generate Modal                                                 */
/* ------------------------------------------------------------------ */

function BulkGenerateModal({
  brands,
  onClose,
  onSubmit,
  submitting,
}: {
  brands: Brand[];
  onClose: () => void;
  onSubmit: (data: { brand_id: string; platform: string; topic: string; count: number }) => void;
  submitting: boolean;
}) {
  const [brandId, setBrandId] = useState(brands[0]?.id || '');
  const [platform, setPlatform] = useState('tiktok');
  const [topic, setTopic] = useState('');
  const [count, setCount] = useState(5);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!brandId || !topic.trim()) return;
    onSubmit({ brand_id: brandId, platform, topic: topic.trim(), count });
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-50" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <form
          onSubmit={handleSubmit}
          className="bg-gray-950 border border-gray-800 rounded-xl w-full max-w-md shadow-2xl"
        >
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800/60">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Sparkles size={18} className="text-purple-400" />
              Bulk Content Generation
            </h2>
            <button type="button" onClick={onClose} className="text-gray-500 hover:text-white transition p-1">
              <X size={18} />
            </button>
          </div>

          <div className="px-5 py-5 space-y-4">
            {/* Brand */}
            <div>
              <label className="text-xs font-medium text-gray-400 block mb-1.5">Brand</label>
              <select
                value={brandId}
                onChange={(e) => setBrandId(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 text-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            </div>

            {/* Platform */}
            <div>
              <label className="text-xs font-medium text-gray-400 block mb-1.5">Platform</label>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 text-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="tiktok">TikTok</option>
                <option value="instagram">Instagram</option>
                <option value="youtube">YouTube</option>
                <option value="twitter">Twitter / X</option>
                <option value="facebook">Facebook</option>
                <option value="linkedin">LinkedIn</option>
              </select>
            </div>

            {/* Topic */}
            <div>
              <label className="text-xs font-medium text-gray-400 block mb-1.5">Topic / Niche</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. fitness tips, cooking hacks, tech reviews..."
                className="w-full bg-gray-900 border border-gray-700 text-gray-300 rounded-lg px-3 py-2 text-sm placeholder:text-gray-600"
                required
              />
            </div>

            {/* Count */}
            <div>
              <label className="text-xs font-medium text-gray-400 block mb-1.5">
                Number of pieces ({count})
              </label>
              <input
                type="range"
                min={1}
                max={25}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full accent-purple-500"
              />
              <div className="flex justify-between text-[10px] text-gray-600 mt-1">
                <span>1</span>
                <span>25</span>
              </div>
            </div>
          </div>

          <div className="px-5 py-4 border-t border-gray-800/60 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="text-xs font-medium text-gray-400 hover:text-white transition px-4 py-2"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !topic.trim()}
              className="flex items-center gap-1.5 text-xs font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-lg px-4 py-2 hover:bg-purple-500/30 transition disabled:opacity-50"
            >
              {submitting ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
              Generate {count} Piece{count > 1 ? 's' : ''}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Filters Bar                                                         */
/* ------------------------------------------------------------------ */

function FiltersBar({
  brands,
  filters,
  onFilterChange,
}: {
  brands: Brand[];
  filters: {
    brand_id: string;
    platform: string;
    tier: string;
    status: string;
    search: string;
    date_from: string;
    date_to: string;
  };
  onFilterChange: (key: string, value: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasActiveFilters =
    filters.platform || filters.tier || filters.status || filters.search || filters.date_from || filters.date_to;

  return (
    <div className="bg-gray-900/60 border border-gray-800/40 rounded-xl p-3">
      <div className="flex items-center gap-3 flex-wrap">
        {/* Brand dropdown */}
        <select
          value={filters.brand_id}
          onChange={(e) => onFilterChange('brand_id', e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-3 py-1.5 text-sm min-w-[150px]"
        >
          <option value="">All Brands</option>
          {brands.map((b) => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>

        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600" />
          <input
            type="text"
            value={filters.search}
            onChange={(e) => onFilterChange('search', e.target.value)}
            placeholder="Search content..."
            className="w-full bg-gray-800 border border-gray-700 text-gray-300 rounded-lg pl-9 pr-3 py-1.5 text-sm placeholder:text-gray-600"
          />
        </div>

        {/* Toggle more filters */}
        <button
          onClick={() => setExpanded(!expanded)}
          className={`flex items-center gap-1.5 text-xs font-medium rounded-lg px-3 py-1.5 transition border ${
            hasActiveFilters
              ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
              : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-gray-300'
          }`}
        >
          <Filter size={12} />
          Filters
          {hasActiveFilters && (
            <span className="bg-cyan-500/30 text-cyan-200 text-[10px] rounded-full px-1.5">!</span>
          )}
          <ChevronDown size={12} className={`transition ${expanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Expanded filters */}
      {expanded && (
        <div className="flex items-center gap-3 flex-wrap mt-3 pt-3 border-t border-gray-800/40">
          {/* Platform */}
          <select
            value={filters.platform}
            onChange={(e) => onFilterChange('platform', e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-3 py-1.5 text-sm"
          >
            <option value="">All Platforms</option>
            <option value="tiktok">TikTok</option>
            <option value="instagram">Instagram</option>
            <option value="youtube">YouTube</option>
            <option value="twitter">Twitter / X</option>
            <option value="facebook">Facebook</option>
            <option value="linkedin">LinkedIn</option>
          </select>

          {/* Tier */}
          <select
            value={filters.tier}
            onChange={(e) => onFilterChange('tier', e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-3 py-1.5 text-sm"
          >
            <option value="">All Tiers</option>
            <option value="standard">Standard</option>
            <option value="premium">Premium</option>
            <option value="cinema">Cinema</option>
          </select>

          {/* Status */}
          <select
            value={filters.status}
            onChange={(e) => onFilterChange('status', e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-3 py-1.5 text-sm"
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="brief_ready">Brief Ready</option>
            <option value="script_generated">Scripted</option>
            <option value="generating">Generating</option>
            <option value="media_complete">Media Ready</option>
            <option value="approved">Approved</option>
            <option value="published">Published</option>
            <option value="failed">Failed</option>
            <option value="quality_blocked">Blocked</option>
          </select>

          {/* Date from */}
          <div className="flex items-center gap-1.5">
            <Calendar size={12} className="text-gray-600" />
            <input
              type="date"
              value={filters.date_from}
              onChange={(e) => onFilterChange('date_from', e.target.value)}
              className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-2 py-1.5 text-sm"
            />
            <span className="text-gray-600 text-xs">to</span>
            <input
              type="date"
              value={filters.date_to}
              onChange={(e) => onFilterChange('date_to', e.target.value)}
              className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-2 py-1.5 text-sm"
            />
          </div>

          {/* Clear */}
          {hasActiveFilters && (
            <button
              onClick={() => {
                onFilterChange('platform', '');
                onFilterChange('tier', '');
                onFilterChange('status', '');
                onFilterChange('search', '');
                onFilterChange('date_from', '');
                onFilterChange('date_to', '');
              }}
              className="text-xs text-gray-500 hover:text-white transition"
            >
              Clear all
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

export default function ContentKanbanPage() {
  const queryClient = useQueryClient();
  const [selectedItem, setSelectedItem] = useState<ContentItem | null>(null);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [filters, setFilters] = useState({
    brand_id: '',
    platform: '',
    tier: '',
    status: '',
    search: '',
    date_from: '',
    date_to: '',
  });

  const handleFilterChange = useCallback((key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  /* ---- Data fetching ---- */

  const { data: brands = [], isLoading: brandsLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  // Set default brand on first load
  useEffect(() => {
    if (brands.length && !filters.brand_id) {
      setFilters((f) => ({ ...f, brand_id: brands[0].id }));
    }
  }, [brands, filters.brand_id]);

  // Fetch briefs
  const { data: briefs = [] } = useQuery({
    queryKey: ['kanban-briefs', filters.brand_id],
    queryFn: () =>
      pipelineApi.listBriefs(filters.brand_id).then((r) => r.data || []),
    enabled: !!filters.brand_id,
    refetchInterval: 10_000,
  });

  // Fetch content items
  const { data: contentItems = [] } = useQuery({
    queryKey: ['kanban-content', filters.brand_id],
    queryFn: () =>
      pipelineApi.contentLibrary(filters.brand_id).then((r) => r.data || []),
    enabled: !!filters.brand_id,
    refetchInterval: 10_000,
  });

  /* ---- Merge briefs + content into unified items ---- */

  const allItems: ContentItem[] = useMemo(() => {
    const briefItems: ContentItem[] = (briefs as any[]).map((b: any) => ({
      id: b.id,
      title: b.title || b.topic || 'Untitled Brief',
      description: b.description || b.hook,
      status: b.status || 'draft',
      content_type: b.content_type,
      platform: b.target_platform,
      target_platform: b.target_platform,
      quality_tier: b.quality_tier,
      brand_id: b.brand_id,
      account_name: b.account_name,
      brief_text: b.brief_text || b.description,
      hook: b.hook,
      angle: b.angle,
      created_at: b.created_at,
      updated_at: b.updated_at || b.created_at,
    }));

    const contentList: ContentItem[] = (contentItems as any[]).map((c: any) => ({
      id: c.id,
      title: c.title || 'Untitled Content',
      description: c.description,
      status: c.status,
      content_type: c.content_type,
      platform: c.platform || c.target_platform,
      target_platform: c.target_platform,
      quality_tier: c.quality_tier,
      brand_id: c.brand_id,
      brand_name: c.brand_name,
      account_id: c.account_id,
      account_name: c.account_name,
      brief_text: c.brief_text,
      script_text: c.script_text,
      script_content: c.script_content,
      hook: c.hook,
      angle: c.angle,
      media_url: c.media_url,
      media_type: c.media_type,
      thumbnail_url: c.thumbnail_url,
      created_at: c.created_at,
      updated_at: c.updated_at || c.created_at,
      published_at: c.published_at,
      scheduled_at: c.scheduled_at,
      status_history: c.status_history,
      monetization_method: c.monetization_method,
    }));

    // Deduplicate by ID (content items override briefs)
    const map = new Map<string, ContentItem>();
    briefItems.forEach((b) => map.set(b.id, b));
    contentList.forEach((c) => map.set(c.id, c));
    return Array.from(map.values());
  }, [briefs, contentItems]);

  /* ---- Apply client-side filters ---- */

  const filteredItems = useMemo(() => {
    return allItems.filter((item) => {
      if (filters.platform) {
        const p = (item.platform || item.target_platform || '').toLowerCase();
        if (!p.includes(filters.platform.toLowerCase())) return false;
      }
      if (filters.tier) {
        if ((item.quality_tier || '').toLowerCase() !== filters.tier.toLowerCase()) return false;
      }
      if (filters.status) {
        if (item.status !== filters.status) return false;
      }
      if (filters.search) {
        const q = filters.search.toLowerCase();
        const searchable = `${item.title} ${item.description || ''} ${item.account_name || ''}`.toLowerCase();
        if (!searchable.includes(q)) return false;
      }
      if (filters.date_from) {
        if (new Date(item.created_at) < new Date(filters.date_from)) return false;
      }
      if (filters.date_to) {
        const to = new Date(filters.date_to);
        to.setDate(to.getDate() + 1);
        if (new Date(item.created_at) >= to) return false;
      }
      return true;
    });
  }, [allItems, filters]);

  /* ---- Sort items into columns ---- */

  const columnData = useMemo(() => {
    return KANBAN_COLUMNS.map((col) => ({
      column: col,
      items: filteredItems
        .filter((item) => col.statuses.includes(item.status))
        .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime()),
    }));
  }, [filteredItems]);

  // Items that don't fit any column (failed, rejected, etc.)
  const allColumnStatuses = KANBAN_COLUMNS.flatMap((c) => c.statuses);
  const orphanedItems = filteredItems.filter((item) => !allColumnStatuses.includes(item.status));

  /* ---- Mutations ---- */

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['kanban-briefs'] });
    queryClient.invalidateQueries({ queryKey: ['kanban-content'] });
  };

  const publishMut = useMutation({
    mutationFn: (id: string) => pipelineApi.publishNow(id, {}),
    onSuccess: () => {
      invalidateAll();
      setSelectedItem(null);
    },
  });

  const regenerateMut = useMutation({
    mutationFn: (id: string) => pipelineApi.generateScript(id),
    onSuccess: invalidateAll,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/pipeline/content/${id}`),
    onSuccess: () => {
      invalidateAll();
      setSelectedItem(null);
    },
  });

  const bulkGenerateMut = useMutation({
    mutationFn: (data: { brand_id: string; platform: string; topic: string; count: number }) =>
      api.post('/api/v1/content/generate-batch', data),
    onSuccess: () => {
      invalidateAll();
      setShowBulkModal(false);
    },
  });

  /* ---- Render ---- */

  if (brandsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="animate-spin text-gray-600" size={32} />
      </div>
    );
  }

  const totalCount = filteredItems.length;

  return (
    <div className="space-y-5 max-w-[1800px]">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Layers size={24} className="text-cyan-400" />
            Content Pipeline
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {totalCount} item{totalCount !== 1 ? 's' : ''} in pipeline
            {orphanedItems.length > 0 && (
              <span className="text-amber-500 ml-2">
                + {orphanedItems.length} blocked/failed
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => setShowBulkModal(true)}
          className="flex items-center gap-2 text-sm font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-lg px-4 py-2 hover:bg-purple-500/30 transition self-start"
        >
          <Plus size={16} />
          Bulk Generate
        </button>
      </div>

      {/* Filters */}
      <FiltersBar brands={brands} filters={filters} onFilterChange={handleFilterChange} />

      {/* Kanban Board */}
      <div className="flex gap-3 overflow-x-auto pb-4 lg:overflow-x-visible flex-col lg:flex-row">
        {columnData.map(({ column, items }) => (
          <KanbanColumn
            key={column.key}
            column={column}
            items={items}
            onCardClick={setSelectedItem}
          />
        ))}
      </div>

      {/* Orphaned items (blocked / failed / rejected) */}
      {orphanedItems.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
            <AlertTriangle size={14} />
            Blocked / Failed ({orphanedItems.length})
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
            {orphanedItems.map((item) => (
              <KanbanCard key={item.id} item={item} onClick={() => setSelectedItem(item)} />
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {allItems.length === 0 && !brandsLoading && (
        <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl text-center py-16">
          <Layers className="mx-auto text-gray-700 mb-4" size={48} />
          <p className="text-gray-500 text-lg">No content in the pipeline</p>
          <p className="text-gray-600 text-sm mt-2">
            Use the Bulk Generate button to start creating content
          </p>
        </div>
      )}

      {/* Mutation error toast */}
      {(publishMut.isError || regenerateMut.isError || deleteMut.isError || bulkGenerateMut.isError) && (
        <div className="fixed bottom-6 right-6 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-300 max-w-md z-30 shadow-xl">
          <div className="flex items-start gap-2">
            <XCircle size={16} className="shrink-0 mt-0.5" />
            <div>
              {publishMut.isError && <p>Publish failed: {errMsg(publishMut.error)}</p>}
              {regenerateMut.isError && <p>Regenerate failed: {errMsg(regenerateMut.error)}</p>}
              {deleteMut.isError && <p>Delete failed: {errMsg(deleteMut.error)}</p>}
              {bulkGenerateMut.isError && <p>Bulk generation failed: {errMsg(bulkGenerateMut.error)}</p>}
            </div>
          </div>
        </div>
      )}

      {/* Detail slide-in panel */}
      {selectedItem && (
        <DetailPanel
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onPublish={() => publishMut.mutate(selectedItem.id)}
          onRegenerate={() => regenerateMut.mutate(selectedItem.id)}
          onDelete={() => deleteMut.mutate(selectedItem.id)}
          publishing={publishMut.isPending}
          regenerating={regenerateMut.isPending}
          deleting={deleteMut.isPending}
        />
      )}

      {/* Bulk generate modal */}
      {showBulkModal && (
        <BulkGenerateModal
          brands={brands}
          onClose={() => setShowBulkModal(false)}
          onSubmit={(data) => bulkGenerateMut.mutate(data)}
          submitting={bulkGenerateMut.isPending}
        />
      )}
    </div>
  );
}
