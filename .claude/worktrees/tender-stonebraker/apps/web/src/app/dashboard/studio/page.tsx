'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import {
  Film,
  Clapperboard,
  Users,
  Sparkles,
  Play,
  ArrowRight,
} from 'lucide-react';
import Link from 'next/link';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function StudioDashboardPage() {
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data: stats, isLoading, isError, error } = useQuery({
    queryKey: ['studio-dashboard', selectedBrandId],
    queryFn: () => cinemaStudioApi.dashboardStats(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  if (brandsError) {
    return <div className="card border-red-900/50 text-red-300 py-8 text-center">{errMessage(brandsErr)}</div>;
  }

  if (!brands?.length) {
    return <div className="card text-center py-12 text-gray-500">Create a brand to access the Cinema Studio.</div>;
  }

  const totalProjects = stats?.total_projects ?? 0;
  const totalScenes = stats?.total_scenes ?? 0;
  const totalCharacters = stats?.total_characters ?? 0;
  const totalGenerations = stats?.total_generations ?? 0;
  const genCompleted = stats?.completed_generations ?? 0;
  const genProcessing = stats?.processing_generations ?? 0;
  const genFailed = stats?.failed_generations ?? 0;
  const recentActivity = (stats?.recent_activity ?? []) as any[];

  return (
    <div className="space-y-8 pb-16">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Film className="text-brand-500" size={28} aria-hidden />
            Cinema Studio
          </h1>
          <p className="text-gray-400 mt-1 max-w-3xl">
            Create cinematic AI-generated content — manage projects, scenes, characters, and generations.
          </p>
        </div>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand for cinema studio"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <div className="card py-12 text-center text-gray-500">Loading studio data…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {stats && !isLoading && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-400 text-xs uppercase flex items-center gap-1">
                <Clapperboard size={12} aria-hidden /> Total Projects
              </p>
              <p className="text-3xl font-bold text-white mt-1">{totalProjects}</p>
            </div>
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-400 text-xs uppercase flex items-center gap-1">
                <Film size={12} aria-hidden /> Total Scenes
              </p>
              <p className="text-3xl font-bold text-white mt-1">{totalScenes}</p>
            </div>
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-400 text-xs uppercase flex items-center gap-1">
                <Users size={12} aria-hidden /> Total Characters
              </p>
              <p className="text-3xl font-bold text-white mt-1">{totalCharacters}</p>
            </div>
            <div className="rounded-lg bg-gray-800/40 p-4 border border-gray-800">
              <p className="text-gray-400 text-xs uppercase flex items-center gap-1">
                <Sparkles size={12} aria-hidden /> Total Generations
              </p>
              <p className="text-3xl font-bold text-white mt-1">{totalGenerations}</p>
            </div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">Generation Status</h2>
            <div className="flex flex-wrap gap-6">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-sm text-gray-400">Completed</span>
                <span className="text-sm font-semibold text-emerald-300">{genCompleted}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-amber-500" />
                <span className="text-sm text-gray-400">Processing</span>
                <span className="text-sm font-semibold text-amber-300">{genProcessing}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500" />
                <span className="text-sm text-gray-400">Failed</span>
                <span className="text-sm font-semibold text-red-300">{genFailed}</span>
              </div>
            </div>
          </div>

          {recentActivity.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Play size={18} className="text-brand-400" aria-hidden />
                Recent Activity
              </h2>
              <ul className="space-y-2">
                {recentActivity.slice(0, 10).map((a: any, i: number) => (
                  <li key={a.id || i} className="flex items-center justify-between gap-4 border-b border-gray-800 py-2 last:border-0 text-sm">
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-0.5 rounded text-xs bg-brand-600/25 text-brand-300 uppercase tracking-wide">
                        {a.activity_type}
                      </span>
                      <span className="text-white">{a.entity_name}</span>
                    </div>
                    <span className="text-gray-500 text-xs shrink-0">
                      {a.created_at ? new Date(a.created_at).toLocaleString() : ''}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">Quick Links</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              <Link
                href="/dashboard/studio/projects"
                className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 p-4 hover:border-brand-500/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Clapperboard size={18} className="text-brand-400" />
                  <span className="text-white text-sm font-medium">Projects</span>
                </div>
                <ArrowRight size={16} className="text-gray-500" />
              </Link>
              <Link
                href="/dashboard/studio/scenes/new"
                className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 p-4 hover:border-brand-500/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Film size={18} className="text-brand-400" />
                  <span className="text-white text-sm font-medium">New Scene</span>
                </div>
                <ArrowRight size={16} className="text-gray-500" />
              </Link>
              <Link
                href="/dashboard/studio/characters"
                className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 p-4 hover:border-brand-500/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Users size={18} className="text-brand-400" />
                  <span className="text-white text-sm font-medium">Characters</span>
                </div>
                <ArrowRight size={16} className="text-gray-500" />
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
