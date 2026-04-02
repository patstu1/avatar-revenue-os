'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import Link from 'next/link';
import {
  Clapperboard,
  Camera,
  Sun,
  Palette,
  Clock,
  Plus,
} from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-600 text-gray-200',
  ready: 'bg-blue-600 text-blue-100',
  generating: 'bg-amber-600 text-amber-100',
  completed: 'bg-green-600 text-green-100',
  failed: 'bg-red-600 text-red-100',
};

export default function SceneListPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [projectFilter, setProjectFilter] = useState('');

  const { data: brands, isLoading: brandsLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data: projects } = useQuery({
    queryKey: ['studio-projects', selectedBrandId],
    queryFn: () => cinemaStudioApi.listProjects(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const { data: scenes, isLoading, isError, error } = useQuery({
    queryKey: ['studio-scenes', selectedBrandId, projectFilter],
    queryFn: () =>
      cinemaStudioApi
        .listScenes(selectedBrandId, projectFilter || undefined)
        .then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const sceneList = (Array.isArray(scenes) ? scenes : []) as any[];
  const projectList = (Array.isArray(projects) ? projects : []) as any[];

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <Clapperboard className="h-7 w-7 text-purple-400" />
          <h1 className="text-2xl font-bold text-white">Scene Library</h1>
        </div>
        <Link
          href="/dashboard/studio/scenes/new"
          className="btn-primary inline-flex items-center gap-2 w-fit"
        >
          <Plus className="h-4 w-4" />
          New Scene
        </Link>
      </div>

      {/* Brand + Project filters */}
      <div className="flex flex-wrap gap-4">
        <select
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          className="input-field w-56"
          aria-label="Select brand"
        >
          <option value="">Select brand…</option>
          {brands?.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>

        <select
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
          className="input-field w-56"
          aria-label="Filter by project"
        >
          <option value="">All projects</option>
          {projectList.map((p: any) => (
            <option key={p.id} value={p.id}>
              {p.name || p.title || p.id}
            </option>
          ))}
        </select>
      </div>

      {/* Content */}
      {isLoading && (
        <div className="card py-12 text-center text-gray-500">Loading scenes…</div>
      )}

      {isError && (
        <div className="card py-8 text-center text-red-400">
          {errMessage(error)}
        </div>
      )}

      {!isLoading && !isError && sceneList.length === 0 && (
        <div className="card py-12 text-center text-gray-500">
          No scenes yet.{' '}
          <Link href="/dashboard/studio/scenes/new" className="text-purple-400 underline">
            Create your first scene
          </Link>
        </div>
      )}

      {/* Scene grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {sceneList.map((scene: any) => (
          <Link
            key={scene.id}
            href={`/dashboard/studio/scenes/${scene.id}`}
            className="card hover:border-purple-500 transition-colors group"
          >
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-white font-semibold text-lg group-hover:text-purple-300 transition-colors truncate pr-2">
                {scene.title || 'Untitled Scene'}
              </h3>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_COLORS[scene.status] || STATUS_COLORS.draft}`}
              >
                {scene.status || 'draft'}
              </span>
            </div>

            <p className="text-gray-400 text-sm mb-4 line-clamp-2">
              {scene.prompt
                ? scene.prompt.length > 100
                  ? scene.prompt.slice(0, 100) + '…'
                  : scene.prompt
                : 'No prompt'}
            </p>

            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
              <div className="flex items-center gap-1.5">
                <Camera className="h-3.5 w-3.5" />
                <span>{scene.camera_shot || '—'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Camera className="h-3.5 w-3.5" />
                <span>{scene.camera_movement || '—'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Sun className="h-3.5 w-3.5" />
                <span>{scene.lighting || '—'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Palette className="h-3.5 w-3.5" />
                <span>{scene.mood || '—'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Clapperboard className="h-3.5 w-3.5" />
                <span>{scene.aspect_ratio || '—'}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                <span>{scene.duration_seconds ? `${scene.duration_seconds}s` : '—'}</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
