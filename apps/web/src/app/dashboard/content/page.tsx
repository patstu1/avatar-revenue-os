'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { pipelineApi } from '@/lib/pipeline-api';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Eye,
  FileText,
  Layers,
  Loader2,
  Play,
  RefreshCw,
  Shield,
  XCircle,
  Zap,
} from 'lucide-react';

type Brand = { id: string; name: string };

function errMsg(e: unknown) {
  const ax = e as { response?: { data?: { detail?: string } } };
  return ax.response?.data?.detail ?? (e instanceof Error ? e.message : 'Request failed');
}

/* ------------------------------------------------------------------ */
/* Status helpers                                                      */
/* ------------------------------------------------------------------ */

const statusConfig: Record<string, { label: string; color: string; bg: string; icon: typeof Clock }> = {
  draft:              { label: 'Draft',         color: 'text-gray-400',   bg: 'bg-gray-500/10 border-gray-500/30', icon: FileText },
  brief_ready:        { label: 'Brief Ready',   color: 'text-blue-400',   bg: 'bg-blue-500/10 border-blue-500/30', icon: FileText },
  generating:         { label: 'Generating',    color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/30', icon: Loader2 },
  script_generated:   { label: 'Script Ready',  color: 'text-indigo-400', bg: 'bg-indigo-500/10 border-indigo-500/30', icon: Zap },
  generated:          { label: 'Generated',     color: 'text-indigo-400', bg: 'bg-indigo-500/10 border-indigo-500/30', icon: Zap },
  media_queued:       { label: 'Media Queued',  color: 'text-cyan-400',   bg: 'bg-cyan-500/10 border-cyan-500/30', icon: Clock },
  media_complete:     { label: 'Media Ready',   color: 'text-teal-400',   bg: 'bg-teal-500/10 border-teal-500/30', icon: Play },
  qa_review:          { label: 'QA Review',     color: 'text-amber-400',  bg: 'bg-amber-500/10 border-amber-500/30', icon: Eye },
  qa_complete:        { label: 'QA Passed',     color: 'text-lime-400',   bg: 'bg-lime-500/10 border-lime-500/30', icon: Shield },
  quality_blocked:    { label: 'Blocked',       color: 'text-red-400',    bg: 'bg-red-500/10 border-red-500/30', icon: AlertTriangle },
  approved:           { label: 'Approved',      color: 'text-green-400',  bg: 'bg-green-500/10 border-green-500/30', icon: CheckCircle2 },
  rejected:           { label: 'Rejected',      color: 'text-red-400',    bg: 'bg-red-500/10 border-red-500/30', icon: XCircle },
  revision_requested: { label: 'Needs Changes', color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30', icon: RefreshCw },
  scheduled:          { label: 'Scheduled',     color: 'text-blue-400',   bg: 'bg-blue-500/10 border-blue-500/30', icon: Clock },
  publishing:         { label: 'Publishing',    color: 'text-cyan-400',   bg: 'bg-cyan-500/10 border-cyan-500/30', icon: ArrowRight },
  published:          { label: 'Published',     color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30', icon: CheckCircle2 },
  failed:             { label: 'Failed',        color: 'text-red-400',    bg: 'bg-red-500/10 border-red-500/30', icon: XCircle },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status] || { label: status, color: 'text-gray-400', bg: 'bg-gray-500/10 border-gray-500/30', icon: Clock };
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium border rounded-full px-2.5 py-0.5 ${cfg.color} ${cfg.bg}`}>
      <Icon size={12} className={status === 'generating' ? 'animate-spin' : ''} />
      {cfg.label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Pipeline Stages View                                                */
/* ------------------------------------------------------------------ */

function PipelineSummary({ briefs, contentItems }: { briefs: any[]; contentItems: any[] }) {
  const briefStatuses: Record<string, number> = {};
  briefs.forEach((b) => { briefStatuses[b.status] = (briefStatuses[b.status] || 0) + 1; });

  const contentStatuses: Record<string, number> = {};
  contentItems.forEach((c) => { contentStatuses[c.status] = (contentStatuses[c.status] || 0) + 1; });

  const stages = [
    { label: 'Briefs', count: briefs.length, color: '#6b7280' },
    { label: 'Scripts', count: briefStatuses['script_generated'] || 0, color: '#8b5cf6' },
    { label: 'Media', count: (contentStatuses['media_complete'] || 0), color: '#06b6d4' },
    { label: 'QA', count: (contentStatuses['qa_complete'] || 0) + (contentStatuses['qa_review'] || 0), color: '#f59e0b' },
    { label: 'Approved', count: contentStatuses['approved'] || 0, color: '#22c55e' },
    { label: 'Published', count: contentStatuses['published'] || 0, color: '#14b8a6' },
    { label: 'Blocked', count: (contentStatuses['quality_blocked'] || 0) + (contentStatuses['failed'] || 0), color: '#ef4444' },
  ];

  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
        <Layers size={16} className="text-cyan-400" />
        Pipeline Overview
      </h3>
      <div className="grid grid-cols-7 gap-2">
        {stages.map((s, i) => (
          <div key={s.label} className="text-center relative">
            <p className="text-2xl font-bold" style={{ color: s.color }}>{s.count}</p>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">{s.label}</p>
            {i < stages.length - 1 && (
              <ChevronRight size={14} className="absolute right-[-12px] top-2 text-gray-700" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Brief Card with Actions                                             */
/* ------------------------------------------------------------------ */

function BriefCard({
  brief,
  onGenerate,
  generating,
}: {
  brief: any;
  onGenerate: () => void;
  generating: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            <StatusBadge status={brief.status} />
            {brief.target_platform && (
              <span className="text-[10px] text-gray-500 uppercase">{brief.target_platform}</span>
            )}
          </div>
          <h4
            className="text-sm font-medium text-white cursor-pointer hover:text-cyan-400 transition"
            onClick={() => setExpanded(!expanded)}
          >
            {brief.title}
          </h4>
        </div>
        {brief.status === 'draft' && (
          <button
            onClick={onGenerate}
            disabled={generating}
            className="flex items-center gap-1.5 text-xs font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-lg px-3 py-1.5 hover:bg-purple-500/30 transition disabled:opacity-50"
          >
            {generating ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
            Generate
          </button>
        )}
      </div>
      {expanded && (
        <div className="mt-3 pt-3 border-t border-gray-800/60 space-y-2">
          {brief.hook && <p className="text-xs text-gray-400"><span className="text-gray-600">Hook:</span> {brief.hook}</p>}
          {brief.angle && <p className="text-xs text-gray-400"><span className="text-gray-600">Angle:</span> {brief.angle}</p>}
          <p className="text-[10px] text-gray-600">
            {String(brief.content_type).replace(/_/g, ' ')} · Created {new Date(brief.created_at).toLocaleDateString()}
          </p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Content Item Card with Actions                                      */
/* ------------------------------------------------------------------ */

function ContentCard({
  item,
  onRunQA,
  onApprove,
  onReject,
}: {
  item: any;
  onRunQA: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const canQA = ['media_complete', 'draft', 'revision_requested'].includes(item.status);
  const canApprove = item.status === 'qa_complete';
  const canReject = ['qa_complete', 'quality_blocked'].includes(item.status);

  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            <StatusBadge status={item.status} />
          </div>
          <h4
            className="text-sm font-medium text-white cursor-pointer hover:text-cyan-400 transition"
            onClick={() => setExpanded(!expanded)}
          >
            {item.title}
            <ChevronDown size={14} className={`inline ml-1 text-gray-600 transition ${expanded ? 'rotate-180' : ''}`} />
          </h4>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {canQA && (
            <button
              onClick={onRunQA}
              className="flex items-center gap-1 text-[11px] font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30 rounded-lg px-2.5 py-1 hover:bg-amber-500/25 transition"
            >
              <Shield size={11} /> QA
            </button>
          )}
          {canApprove && (
            <button
              onClick={onApprove}
              className="flex items-center gap-1 text-[11px] font-medium bg-green-500/15 text-green-300 border border-green-500/30 rounded-lg px-2.5 py-1 hover:bg-green-500/25 transition"
            >
              <CheckCircle2 size={11} /> Approve
            </button>
          )}
          {canReject && (
            <button
              onClick={onReject}
              className="flex items-center gap-1 text-[11px] font-medium bg-red-500/15 text-red-300 border border-red-500/30 rounded-lg px-2.5 py-1 hover:bg-red-500/25 transition"
            >
              <XCircle size={11} /> Reject
            </button>
          )}
        </div>
      </div>
      {expanded && (
        <div className="mt-3 pt-3 border-t border-gray-800/60 space-y-1.5">
          {item.description && <p className="text-xs text-gray-400">{item.description}</p>}
          <p className="text-[10px] text-gray-600">
            {String(item.content_type).replace(/_/g, ' ')}
            {item.platform && ` · ${item.platform}`}
            {item.monetization_method && ` · ${item.monetization_method}`}
            {` · Created ${new Date(item.created_at).toLocaleDateString()}`}
          </p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

export default function ContentPipelinePage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'briefs' | 'content' | 'all'>('all');

  const { data: brands, isLoading: brandsLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(brands[0].id);
  }, [brands, brandId]);

  const { data: briefs = [] } = useQuery({
    queryKey: ['pipeline-briefs', brandId],
    queryFn: () => pipelineApi.listBriefs(brandId!).then((r) => r.data || []),
    enabled: !!brandId,
    refetchInterval: 15_000,
  });

  const { data: contentItems = [] } = useQuery({
    queryKey: ['pipeline-content', brandId],
    queryFn: () => pipelineApi.contentLibrary(brandId!).then((r) => r.data || []),
    enabled: !!brandId,
    refetchInterval: 15_000,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['pipeline-briefs', brandId] });
    queryClient.invalidateQueries({ queryKey: ['pipeline-content', brandId] });
    queryClient.invalidateQueries({ queryKey: ['control-layer-dashboard'] });
  };

  const generateMut = useMutation({
    mutationFn: (briefId: string) => pipelineApi.generateScript(briefId),
    onSuccess: invalidateAll,
  });

  const runQAMut = useMutation({
    mutationFn: (contentId: string) => pipelineApi.runQA(contentId),
    onSuccess: invalidateAll,
  });

  const approveMut = useMutation({
    mutationFn: (contentId: string) => pipelineApi.approve(contentId),
    onSuccess: invalidateAll,
  });

  const rejectMut = useMutation({
    mutationFn: (contentId: string) => pipelineApi.reject(contentId),
    onSuccess: invalidateAll,
  });

  // Split content by actionability
  const needsAction = contentItems.filter((c: any) =>
    ['media_complete', 'qa_complete', 'quality_blocked', 'revision_requested'].includes(c.status)
  );
  const inProgress = contentItems.filter((c: any) =>
    ['generating', 'media_queued', 'qa_review', 'publishing', 'scheduled'].includes(c.status)
  );
  const completed = contentItems.filter((c: any) =>
    ['published', 'approved', 'rejected', 'archived'].includes(c.status)
  );

  if (brandsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="animate-spin text-gray-600" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Content Pipeline</h1>
          <p className="text-sm text-gray-500 mt-0.5">Brief → Generate → QA → Approve → Publish</p>
        </div>
        <select
          className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-3 py-1.5 text-sm"
          value={brandId ?? ''}
          onChange={(e) => setBrandId(e.target.value || null)}
        >
          {brands?.map((b) => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>
      </div>

      {/* Pipeline Overview */}
      {brandId && <PipelineSummary briefs={briefs} contentItems={contentItems} />}

      {/* Tabs */}
      <div className="flex items-center gap-1 bg-gray-900/60 border border-gray-800/40 rounded-lg p-1 w-fit">
        {(['all', 'briefs', 'content'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-1.5 rounded-md text-xs font-medium transition ${
              activeTab === tab
                ? 'bg-gray-800 text-white'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab === 'all' ? 'All Items' : tab === 'briefs' ? 'Briefs' : 'Content'}
          </button>
        ))}
      </div>

      {/* Needs Action Section */}
      {(activeTab === 'all' || activeTab === 'content') && needsAction.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-amber-400 mb-3 flex items-center gap-2">
            <AlertTriangle size={14} />
            Needs Action ({needsAction.length})
          </h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {needsAction.map((item: any) => (
              <ContentCard
                key={item.id}
                item={item}
                onRunQA={() => runQAMut.mutate(item.id)}
                onApprove={() => approveMut.mutate(item.id)}
                onReject={() => rejectMut.mutate(item.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Briefs Section */}
      {(activeTab === 'all' || activeTab === 'briefs') && briefs.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
            <FileText size={14} className="text-gray-500" />
            Briefs ({briefs.length})
          </h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {briefs.map((brief: any) => (
              <BriefCard
                key={brief.id}
                brief={brief}
                onGenerate={() => generateMut.mutate(brief.id)}
                generating={generateMut.isPending}
              />
            ))}
          </div>
        </div>
      )}

      {/* In Progress Section */}
      {(activeTab === 'all' || activeTab === 'content') && inProgress.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-cyan-400 mb-3 flex items-center gap-2">
            <Loader2 size={14} className="animate-spin" />
            In Progress ({inProgress.length})
          </h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {inProgress.map((item: any) => (
              <ContentCard
                key={item.id}
                item={item}
                onRunQA={() => runQAMut.mutate(item.id)}
                onApprove={() => approveMut.mutate(item.id)}
                onReject={() => rejectMut.mutate(item.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Completed Section */}
      {(activeTab === 'all' || activeTab === 'content') && completed.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-500 mb-3 flex items-center gap-2">
            <CheckCircle2 size={14} />
            Completed ({completed.length})
          </h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {completed.slice(0, 10).map((item: any) => (
              <ContentCard
                key={item.id}
                item={item}
                onRunQA={() => runQAMut.mutate(item.id)}
                onApprove={() => approveMut.mutate(item.id)}
                onReject={() => rejectMut.mutate(item.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {briefs.length === 0 && contentItems.length === 0 && (
        <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl text-center py-16">
          <Layers className="mx-auto text-gray-700 mb-4" size={48} />
          <p className="text-gray-500 text-lg">No content in the pipeline</p>
          <p className="text-gray-600 text-sm mt-2">Create a content brief to start the flow</p>
        </div>
      )}

      {/* Mutation feedback */}
      {(generateMut.isError || runQAMut.isError || approveMut.isError || rejectMut.isError) && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2 text-sm text-red-300">
          {generateMut.isError && `Generation: ${errMsg(generateMut.error)}`}
          {runQAMut.isError && `QA: ${errMsg(runQAMut.error)}`}
          {approveMut.isError && `Approval: ${errMsg(approveMut.error)}`}
          {rejectMut.isError && `Rejection: ${errMsg(rejectMut.error)}`}
        </div>
      )}
    </div>
  );
}
