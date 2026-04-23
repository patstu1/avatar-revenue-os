'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import {
  ArrowLeft,
  Film,
  FolderOpen,
  Pencil,
  Plus,
  Trash2,
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

const GENRE_OPTIONS = [
  'drama', 'comedy', 'action', 'documentary', 'horror',
  'sci-fi', 'fantasy', 'thriller', 'animation',
] as const;

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editGenre, setEditGenre] = useState('');

  const { data: brands, isLoading: brandsLoading, isError: brandsError, error: brandsErr } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) {
      setSelectedBrandId(String(brands[0].id));
    }
  }, [brands, selectedBrandId]);

  const { data: project, isLoading, isError, error } = useQuery({
    queryKey: ['studio-project', selectedBrandId, id],
    queryFn: () => cinemaStudioApi.getProject(selectedBrandId, id).then((r) => r.data),
    enabled: Boolean(selectedBrandId && id),
  });

  const { data: scenesData, isLoading: scenesLoading } = useQuery({
    queryKey: ['studio-project-scenes', selectedBrandId, id],
    queryFn: () => cinemaStudioApi.listScenes(selectedBrandId, id).then((r) => r.data),
    enabled: Boolean(selectedBrandId && id),
  });

  const updateMut = useMutation({
    mutationFn: (payload: { title: string; description: string; genre: string }) =>
      cinemaStudioApi.updateProject(selectedBrandId, id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studio-project', selectedBrandId, id] });
      setEditing(false);
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => cinemaStudioApi.deleteProject(selectedBrandId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studio-projects', selectedBrandId] });
      router.push('/dashboard/studio/projects');
    },
  });

  const startEdit = () => {
    setEditTitle(project?.title ?? '');
    setEditDescription(project?.description ?? '');
    setEditGenre(project?.genre ?? '');
    setEditing(true);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTitle.trim()) return;
    updateMut.mutate({ title: editTitle.trim(), description: editDescription.trim(), genre: editGenre });
  };

  const handleDelete = () => {
    if (!window.confirm('Are you sure you want to delete this project? This action cannot be undone.')) return;
    deleteMut.mutate();
  };

  const scenes = Array.isArray(scenesData) ? scenesData : (scenesData as any)?.items ?? [];

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

  return (
    <div className="space-y-8 pb-16">
      <div className="flex items-center gap-3">
        <Link
          href="/dashboard/studio/projects"
          className="flex items-center gap-1 text-gray-400 hover:text-white transition-colors text-sm"
        >
          <ArrowLeft size={16} />
          Back to Projects
        </Link>
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

      {isLoading && <div className="card py-12 text-center text-gray-500">Loading project…</div>}
      {isError && <div className="card border-red-900/50 text-red-300 py-6">{errMessage(error)}</div>}

      {project && !isLoading && (
        <>
          {!editing ? (
            <div className="card">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    <FolderOpen className="text-brand-500" size={24} aria-hidden />
                    {project.title}
                  </h1>
                  {project.description && (
                    <p className="text-gray-400 mt-2">{project.description}</p>
                  )}
                  <div className="flex items-center gap-3 mt-3">
                    {project.genre && (
                      <span className="px-2 py-0.5 rounded text-xs bg-brand-600/25 text-brand-300 uppercase tracking-wide">
                        {project.genre}
                      </span>
                    )}
                    {project.status && (
                      <span className={`px-2 py-0.5 rounded text-xs uppercase tracking-wide ${
                        project.status === 'active'
                          ? 'bg-emerald-900/30 text-emerald-300'
                          : project.status === 'archived'
                            ? 'bg-gray-700/50 text-gray-400'
                            : 'bg-amber-900/30 text-amber-300'
                      }`}>
                        {project.status}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    className="btn-primary flex items-center gap-1 text-sm"
                    onClick={startEdit}
                  >
                    <Pencil size={14} /> Edit
                  </button>
                  <button
                    type="button"
                    className="flex items-center gap-1 text-sm px-3 py-2 rounded-lg border border-red-900/50 text-red-300 hover:bg-red-900/20 transition-colors disabled:opacity-50"
                    onClick={handleDelete}
                    disabled={deleteMut.isPending}
                  >
                    <Trash2 size={14} /> {deleteMut.isPending ? 'Deleting…' : 'Delete'}
                  </button>
                </div>
              </div>
              {deleteMut.isError && (
                <div className="text-red-300 text-sm mt-3">{errMessage(deleteMut.error)}</div>
              )}
            </div>
          ) : (
            <form onSubmit={handleUpdate} className="card space-y-4">
              <h2 className="text-lg font-semibold text-white">Edit Project</h2>

              <div>
                <label className="stat-label block mb-1">Title</label>
                <input
                  className="input-field w-full"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="Project title"
                  required
                />
              </div>

              <div>
                <label className="stat-label block mb-1">Description</label>
                <textarea
                  className="input-field w-full min-h-[80px]"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Brief description"
                />
              </div>

              <div>
                <label className="stat-label block mb-1">Genre</label>
                <select
                  className="input-field w-full"
                  value={editGenre}
                  onChange={(e) => setEditGenre(e.target.value)}
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

              {updateMut.isError && (
                <div className="text-red-300 text-sm">{errMessage(updateMut.error)}</div>
              )}

              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  className="btn-primary flex items-center gap-2 disabled:opacity-50"
                  disabled={updateMut.isPending || !editTitle.trim()}
                >
                  {updateMut.isPending ? 'Saving…' : 'Save Changes'}
                </button>
                <button
                  type="button"
                  className="text-sm text-gray-400 hover:text-white transition-colors"
                  onClick={() => setEditing(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}

          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Film size={18} className="text-brand-400" aria-hidden />
              Scenes
            </h2>
            <Link
              href={`/dashboard/studio/scenes/new?project_id=${id}`}
              className="btn-primary flex items-center gap-2 text-sm"
            >
              <Plus size={16} /> New Scene
            </Link>
          </div>

          {scenesLoading && <div className="card py-8 text-center text-gray-500">Loading scenes…</div>}

          {!scenesLoading && scenes.length === 0 && (
            <div className="card text-center py-12">
              <Film size={48} className="mx-auto text-gray-600 mb-4" aria-hidden />
              <p className="text-gray-400">No scenes in this project yet.</p>
            </div>
          )}

          {scenes.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {scenes.map((s: any) => (
                <Link
                  key={s.id}
                  href={`/dashboard/studio/scenes/${s.id}`}
                  className="card hover:border-brand-500/50 transition-colors flex flex-col gap-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-white font-semibold">{s.title || `Scene ${s.id}`}</span>
                    {s.status && (
                      <span className={`px-2 py-0.5 rounded text-xs uppercase tracking-wide shrink-0 ${
                        s.status === 'completed'
                          ? 'bg-emerald-900/30 text-emerald-300'
                          : s.status === 'failed'
                            ? 'bg-red-900/30 text-red-300'
                            : 'bg-amber-900/30 text-amber-300'
                      }`}>
                        {s.status}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                    {s.camera_shot && <span>Camera: {s.camera_shot}</span>}
                    {s.lighting && <span>Lighting: {s.lighting}</span>}
                    {s.mood && <span>Mood: {s.mood}</span>}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
