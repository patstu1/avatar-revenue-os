'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { brandsApi } from '@/lib/api';
import { cinemaStudioApi } from '@/lib/cinema-studio-api';
import Link from 'next/link';
import { ArrowLeft, Camera, Clapperboard } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

const CAMERA_SHOTS = [
  'extreme_close_up', 'close_up', 'medium_close_up', 'medium', 'medium_wide',
  'wide', 'extreme_wide', 'over_shoulder', 'pov', 'aerial', 'low_angle',
  'high_angle', 'dutch_angle',
];

const CAMERA_MOVEMENTS = [
  'static', 'pan', 'tilt', 'dolly', 'tracking', 'crane', 'handheld',
  'steadicam', 'zoom', 'whip_pan', 'orbit',
];

const LIGHTING_OPTIONS = [
  'natural', 'golden_hour', 'blue_hour', 'studio', 'dramatic', 'neon',
  'low_key', 'high_key', 'silhouette', 'practical', 'moonlight',
];

const MOOD_OPTIONS = [
  'cinematic', 'energetic', 'calm', 'mysterious', 'dark', 'romantic',
  'epic', 'nostalgic', 'playful', 'tense', 'dreamy', 'documentary',
];

const ASPECT_RATIOS = ['16:9', '9:16', '1:1', '4:3', '21:9'];

function labelFromValue(v: string) {
  return v.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function SceneBuilderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');

  const [title, setTitle] = useState('');
  const [projectId, setProjectId] = useState(searchParams.get('project_id') ?? '');
  const [prompt, setPrompt] = useState('');
  const [negativePrompt, setNegativePrompt] = useState('');
  const [cameraShot, setCameraShot] = useState('medium');
  const [cameraMovement, setCameraMovement] = useState('static');
  const [lighting, setLighting] = useState('natural');
  const [mood, setMood] = useState('cinematic');
  const [stylePresetId, setStylePresetId] = useState('');
  const [durationSeconds, setDurationSeconds] = useState(5);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<string[]>([]);

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

  const { data: styles } = useQuery({
    queryKey: ['studio-styles', selectedBrandId],
    queryFn: () => cinemaStudioApi.listStyles(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const { data: characters } = useQuery({
    queryKey: ['studio-characters', selectedBrandId],
    queryFn: () => cinemaStudioApi.listCharacters(selectedBrandId).then((r) => r.data),
    enabled: Boolean(selectedBrandId),
  });

  const projectList = (Array.isArray(projects) ? projects : []) as any[];
  const styleList = (Array.isArray(styles) ? styles : []) as any[];
  const characterList = (Array.isArray(characters) ? characters : []) as any[];

  const createMut = useMutation({
    mutationFn: (payload: any) => cinemaStudioApi.createScene(selectedBrandId, payload),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['studio-scenes'] });
      const newScene = res.data;
      router.push(`/dashboard/studio/scenes/${newScene.id}`);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedBrandId || !title.trim() || !prompt.trim()) return;
    createMut.mutate({
      title: title.trim(),
      project_id: projectId || undefined,
      prompt: prompt.trim(),
      negative_prompt: negativePrompt.trim() || undefined,
      camera_shot: cameraShot,
      camera_movement: cameraMovement,
      lighting,
      mood,
      style_preset_id: stylePresetId || undefined,
      duration_seconds: durationSeconds,
      aspect_ratio: aspectRatio,
      character_ids: selectedCharacterIds.length ? selectedCharacterIds : undefined,
    });
  }

  function toggleCharacter(id: string) {
    setSelectedCharacterIds((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  }

  if (brandsLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-96 bg-gray-800 rounded animate-pulse" />
        <div className="card py-12 text-center text-gray-500">Loading…</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Back link + header */}
      <div className="flex items-center gap-3">
        <Link
          href="/dashboard/studio/scenes"
          className="text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <Clapperboard className="h-7 w-7 text-purple-400" />
        <h1 className="text-2xl font-bold text-white">Scene Builder</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Brand selector */}
        <div className="card space-y-4">
          <h2 className="text-white font-semibold flex items-center gap-2">
            <Camera className="h-5 w-5 text-purple-400" />
            Brand &amp; Project
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Brand</label>
              <select
                value={selectedBrandId}
                onChange={(e) => setSelectedBrandId(e.target.value)}
                className="input-field w-full"
                aria-label="Select brand"
              >
                <option value="">Select brand…</option>
                {brands?.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Project (optional)</label>
              <select
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="input-field w-full"
                aria-label="Select project"
              >
                <option value="">None</option>
                {projectList.map((p: any) => (
                  <option key={p.id} value={p.id}>{p.name || p.title || p.id}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Core details */}
        <div className="card space-y-4">
          <h2 className="text-white font-semibold">Scene Details</h2>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Title *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Give your scene a name"
              className="input-field w-full"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Prompt *</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the scene in detail…"
              rows={5}
              className="input-field w-full"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Negative Prompt (optional)</label>
            <textarea
              value={negativePrompt}
              onChange={(e) => setNegativePrompt(e.target.value)}
              placeholder="Describe what to exclude…"
              rows={3}
              className="input-field w-full"
            />
          </div>
        </div>

        {/* Camera settings */}
        <div className="card space-y-4">
          <h2 className="text-white font-semibold flex items-center gap-2">
            <Camera className="h-5 w-5 text-purple-400" />
            Camera Settings
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Camera Shot</label>
              <select value={cameraShot} onChange={(e) => setCameraShot(e.target.value)} className="input-field w-full" aria-label="Camera shot">
                {CAMERA_SHOTS.map((v) => (
                  <option key={v} value={v}>{labelFromValue(v)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Camera Movement</label>
              <select value={cameraMovement} onChange={(e) => setCameraMovement(e.target.value)} className="input-field w-full" aria-label="Camera movement">
                {CAMERA_MOVEMENTS.map((v) => (
                  <option key={v} value={v}>{labelFromValue(v)}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Lighting & Mood */}
        <div className="card space-y-4">
          <h2 className="text-white font-semibold">Lighting &amp; Mood</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Lighting</label>
              <select value={lighting} onChange={(e) => setLighting(e.target.value)} className="input-field w-full" aria-label="Lighting">
                {LIGHTING_OPTIONS.map((v) => (
                  <option key={v} value={v}>{labelFromValue(v)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Mood</label>
              <select value={mood} onChange={(e) => setMood(e.target.value)} className="input-field w-full" aria-label="Mood">
                {MOOD_OPTIONS.map((v) => (
                  <option key={v} value={v}>{labelFromValue(v)}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Style & Format */}
        <div className="card space-y-4">
          <h2 className="text-white font-semibold">Style &amp; Format</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Style Preset</label>
              <select
                value={stylePresetId}
                onChange={(e) => setStylePresetId(e.target.value)}
                className="input-field w-full"
                aria-label="Style preset"
              >
                <option value="">None</option>
                {styleList.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.name || s.id}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Duration (seconds)</label>
              <input
                type="number"
                value={durationSeconds}
                onChange={(e) => setDurationSeconds(Number(e.target.value) || 5)}
                min={1}
                max={120}
                className="input-field w-full"
                aria-label="Duration in seconds"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Aspect Ratio</label>
              <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)} className="input-field w-full" aria-label="Aspect ratio">
                {ASPECT_RATIOS.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Characters */}
        {characterList.length > 0 && (
          <div className="card space-y-4">
            <h2 className="text-white font-semibold">Characters</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {characterList.map((ch: any) => (
                <label
                  key={ch.id}
                  className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedCharacterIds.includes(ch.id)
                      ? 'border-purple-500 bg-purple-500/10'
                      : 'border-gray-700 bg-gray-900 hover:border-gray-600'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedCharacterIds.includes(ch.id)}
                    onChange={() => toggleCharacter(ch.id)}
                    className="accent-purple-500"
                  />
                  <span className="text-sm text-white">{ch.name || ch.id}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Submit */}
        {createMut.isError && (
          <div className="card border-red-500/40 text-red-400 text-sm">
            {errMessage(createMut.error)}
          </div>
        )}

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={createMut.isPending || !selectedBrandId || !title.trim() || !prompt.trim()}
            className="btn-primary inline-flex items-center gap-2"
          >
            {createMut.isPending ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Creating…
              </>
            ) : (
              <>
                <Clapperboard className="h-4 w-4" />
                Create Scene
              </>
            )}
          </button>
          <Link href="/dashboard/studio/scenes" className="text-gray-400 hover:text-white text-sm transition-colors">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
