'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import { FolderOpen, Plus } from 'lucide-react';
import Link from 'next/link';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const GENRE_OPTIONS = [
  'drama', 'comedy', 'action', 'documentary', 'horror',
  'sci-fi', 'fantasy', 'thriller', 'animation',
] as const;

export default function ProjectListPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [genre, setGenre] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data: projects, isLoading, isError, error } = useQuery({
    queryKey: ['studio-projects', selectedBrandId],
    queryFn: () => cinemaStudioApi.listProjects(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const createMut = useMutation({
    mutationFn: (payload: { title: string; description: string; genre: string }) =>
      cinemaStudioApi.createProject(selectedBrandId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studio-projects', selectedBrandId] });
      setTitle('');
      setDescription('');
      setGenre('');
      setShowForm(false);
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    createMut.mutate({ title: title.trim(), description: description.trim(), genre });
  };

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
    return <div className="card text-center py-12 text-gray-500">Create a brand first.</div>;
  }

  const projectList = Array.isArray(projects) ? projects : (projects as any)?.items ?? [];

  return (
    <div className="space-y-8 pb-16">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FolderOpen className="text-brand-500" size={28} aria-hidden />
            Studio Projects
          </h1>
          <p className="text-gray-400 mt-1 max-w-3xl">
            Manage your cinematic production projects.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary flex items-center gap-2 shrink-0"
          onClick={() => setShowForm((v) => !v)}
        >
          <Plus size={16} />
          {showForm ? 'Cancel' : 'New Project'}
        </button>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          value={selectedBrandId}
          onChange={(e) => setSelectedBrandId(e.target.value)}
          aria-label="Select brand"
        >
          {brands.map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card space-y-4">
          <h2 className="text-lg font-semibold text-white">Create Project</h2>

          <div>
            <label className="stat-label block mb-1">Title</label>
            <input
              className="input-field w-full"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Project title"
              required
            />
          </div>

          <div>
            <label className="stat-label block mb-1">Description</label>
            <textarea
              className="input-field w-full min-h-[80px]"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description"
            />
          </div>

          <div>
            <label className="stat-label block mb-1">Genre</label>
            <select
              className="input-field w-full"
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
              aria-label="Select genre"
            >
              <option value="">— select genre —</option>
              {GENRE_OPTIONS.map((g) => (
                <option key={g} value={g}>
                  {g.charAt(0).toUpperCase() + g.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {createMut.isError && (
            <div className="text-red-300 text-sm">{errMessage(createMut.error)}</div>
          )}

          <button
            type="submit"
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
            disabled={createMut.isPending || !title.trim()}
          >
            <Plus size={16} />
            {createMut.isPending ? 'Creating…' : 'Create Project'}
          </button>
        </form>
      )}

      {isLoading && <div className="card py-12 text-center text-gray-500">Loading projects…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {!isLoading && projectList.length === 0 && (
        <div className="card text-center py-12">
          <FolderOpen size={48} className="mx-auto text-gray-600 mb-4" aria-hidden />
          <p className="text-gray-400">No projects yet. Create one to get started.</p>
        </div>
      )}

      {projectList.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projectList.map((p: any) => (
            <div key={p.id} className="card flex flex-col gap-3">
              <div className="flex items-start justify-between gap-2">
                <Link
                  href={`/dashboard/studio/projects/${p.id}`}
                  className="text-white font-semibold hover:text-brand-400 transition-colors"
                >
                  {p.title}
                </Link>
                <div className="flex items-center gap-2 shrink-0">
                  {p.genre && (
                    <span className="px-2 py-0.5 rounded text-xs bg-brand-600/25 text-brand-300 uppercase tracking-wide">
                      {p.genre}
                    </span>
                  )}
                  {p.status && (
                    <span className={`px-2 py-0.5 rounded text-xs uppercase tracking-wide ${
                      p.status === 'active'
                        ? 'bg-emerald-900/30 text-emerald-300'
                        : p.status === 'archived'
                          ? 'bg-gray-700/50 text-gray-400'
                          : 'bg-amber-900/30 text-amber-300'
                    }`}>
                      {p.status}
                    </span>
                  )}
                </div>
              </div>
              {p.description && <p className="text-sm text-gray-400 line-clamp-2">{p.description}</p>}
              <p className="text-xs text-gray-500 mt-auto">
                {p.created_at ? new Date(p.created_at).toLocaleDateString() : ''}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
