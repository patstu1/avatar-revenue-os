'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import Link from 'next/link';
import {
  ArrowLeft,
  Film,
  Play,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Camera,
  Sun,
  Palette,
  Clapperboard,
} from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

function GenStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'pending':
      return <Clock className="h-5 w-5 text-blue-400" />;
    case 'processing':
      return <Loader2 className="h-5 w-5 text-amber-400 animate-spin" />;
    case 'completed':
      return <CheckCircle2 className="h-5 w-5 text-green-400" />;
    case 'failed':
      return <AlertCircle className="h-5 w-5 text-red-400" />;
    default:
      return <Clock className="h-5 w-5 text-gray-500" />;
  }
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-600 text-gray-200',
  ready: 'bg-blue-600 text-blue-100',
  generating: 'bg-amber-600 text-amber-100',
  completed: 'bg-green-600 text-green-100',
  failed: 'bg-red-600 text-red-100',
};

export default function SceneDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const {
    data: scene,
    isLoading: sceneLoading,
    isError: sceneError,
    error: sceneErr,
  } = useQuery({
    queryKey: ['studio-scene', selectedBrandId, id],
    queryFn: () => cinemaStudioApi.getScene(selectedBrandId, id).then((r) => r.data),
    enabled: Boolean(selectedBrandId && id),
  });

  const {
    data: generations,
    isLoading: gensLoading,
    refetch: refetchGens,
  } = useQuery({
    queryKey: ['studio-generations', selectedBrandId, id],
    queryFn: () => cinemaStudioApi.listGenerations(selectedBrandId, id).then((r) => r.data),
    enabled: Boolean(selectedBrandId && id),
  });

  const genList = (Array.isArray(generations) ? generations : []) as any[];

  const hasActiveGen = genList.some(
    (g: any) => g.status === 'pending' || g.status === 'processing'
  );

  useEffect(() => {
    if (!hasActiveGen) return;
    const interval = setInterval(() => {
      refetchGens();
    }, 2000);
    return () => clearInterval(interval);
  }, [hasActiveGen, refetchGens]);

  const generateMut = useMutation({
    mutationFn: () =>
      cinemaStudioApi.generateFromScene(selectedBrandId, id, {
        model: 'runway',
        steps: 50,
        guidance: 7.5,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studio-generations', selectedBrandId, id] });
      queryClient.invalidateQueries({ queryKey: ['studio-scene', selectedBrandId, id] });
    },
  });

  if (brandsLoading || sceneLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  if (sceneError) {
    return (
      <div className="space-y-6">
        <Link href="/dashboard/studio/scenes" className="text-gray-400 hover:text-white inline-flex items-center gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to scenes
        </Link>
        <div className="card py-8 text-center text-red-400">{errMessage(sceneErr)}</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/dashboard/studio/scenes" className="text-gray-400 hover:text-white transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Film className="h-7 w-7 text-purple-400" />
          <h1 className="text-2xl font-bold text-white truncate">
            {scene?.title || 'Scene Detail'}
          </h1>
          {scene?.status && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[scene.status] || STATUS_COLORS.draft}`}>
              {scene.status}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedBrandId}
            onChange={(e) => setSelectedBrandId(e.target.value)}
            className="input-field w-48"
            aria-label="Select brand"
          >
            {brands?.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
          <button
            onClick={() => generateMut.mutate()}
            disabled={generateMut.isPending || !selectedBrandId}
            className="btn-primary inline-flex items-center gap-2"
          >
            {generateMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Generate
          </button>
        </div>
      </div>

      {generateMut.isError && (
        <div className="card border-red-500/40 text-red-400 text-sm">
          {errMessage(generateMut.error)}
        </div>
      )}

      {/* Scene details */}
      <div className="card space-y-4">
        <h2 className="text-white font-semibold flex items-center gap-2">
          <Clapperboard className="h-5 w-5 text-purple-400" />
          Scene Details
        </h2>

        <div>
          <span className="text-xs text-gray-500 uppercase tracking-wide">Prompt</span>
          <p className="text-gray-300 mt-1">{scene?.prompt || '—'}</p>
        </div>

        {scene?.negative_prompt && (
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide">Negative Prompt</span>
            <p className="text-gray-400 mt-1">{scene.negative_prompt}</p>
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 pt-2">
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide flex items-center gap-1">
              <Camera className="h-3 w-3" /> Shot
            </span>
            <p className="text-white text-sm mt-1">{scene?.camera_shot || '—'}</p>
          </div>
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide flex items-center gap-1">
              <Camera className="h-3 w-3" /> Movement
            </span>
            <p className="text-white text-sm mt-1">{scene?.camera_movement || '—'}</p>
          </div>
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide flex items-center gap-1">
              <Sun className="h-3 w-3" /> Lighting
            </span>
            <p className="text-white text-sm mt-1">{scene?.lighting || '—'}</p>
          </div>
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide flex items-center gap-1">
              <Palette className="h-3 w-3" /> Mood
            </span>
            <p className="text-white text-sm mt-1">{scene?.mood || '—'}</p>
          </div>
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide">Aspect Ratio</span>
            <p className="text-white text-sm mt-1">{scene?.aspect_ratio || '—'}</p>
          </div>
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wide flex items-center gap-1">
              <Clock className="h-3 w-3" /> Duration
            </span>
            <p className="text-white text-sm mt-1">
              {scene?.duration_seconds ? `${scene.duration_seconds}s` : '—'}
            </p>
          </div>
        </div>
      </div>

      {/* Generations */}
      <div className="space-y-4">
        <h2 className="text-white font-semibold flex items-center gap-2">
          <Film className="h-5 w-5 text-purple-400" />
          Generations
          {hasActiveGen && (
            <span className="text-xs text-amber-400 flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" /> Processing…
            </span>
          )}
        </h2>

        {gensLoading && (
          <div className="card py-8 text-center text-gray-500">Loading generations…</div>
        )}

        {!gensLoading && genList.length === 0 && (
          <div className="card py-8 text-center text-gray-500">
            No generations yet. Click <strong>Generate</strong> to create one.
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {genList.map((gen: any) => (
            <div key={gen.id} className="card space-y-3">
              {/* Thumbnail / video area */}
              <div className="aspect-video bg-gray-900 rounded-lg overflow-hidden flex items-center justify-center">
                {gen.status === 'completed' && gen.video_url ? (
                  <video
                    src={gen.video_url}
                    className="w-full h-full object-cover"
                    controls
                    muted
                    playsInline
                  />
                ) : gen.status === 'completed' && gen.thumbnail_url ? (
                  <img
                    src={gen.thumbnail_url}
                    alt="Generation thumbnail"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="flex flex-col items-center gap-2 text-gray-600">
                    <GenStatusIcon status={gen.status} />
                    <span className="text-xs capitalize">{gen.status}</span>
                  </div>
                )}
              </div>

              {/* Status row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <GenStatusIcon status={gen.status} />
                  <span className="text-sm text-white capitalize">{gen.status}</span>
                </div>
                {gen.model && (
                  <span className="text-xs text-gray-500">{gen.model}</span>
                )}
              </div>

              {/* Progress bar for processing */}
              {(gen.status === 'processing' || gen.status === 'pending') && (
                <div className="w-full bg-gray-900 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-amber-400 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${gen.progress ?? (gen.status === 'pending' ? 5 : 50)}%` }}
                  />
                </div>
              )}

              {/* Meta info */}
              <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                {gen.steps && <span>Steps: {gen.steps}</span>}
                {gen.guidance && <span>Guidance: {gen.guidance}</span>}
                {gen.duration_seconds && <span>Duration: {gen.duration_seconds}s</span>}
              </div>

              {gen.status === 'failed' && gen.error_message && (
                <p className="text-xs text-red-400">{gen.error_message}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
