'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Library, RefreshCcw, AlertTriangle } from 'lucide-react';

interface CreativeAtom {
  id: string;
  brand_id: string;
  atom_type: string;
  content_json: Record<string, unknown> | null;
  niche: string | null;
  platform: string | null;
  monetization_type: string | null;
  funnel_stage: string | null;
  performance_summary_json: Record<string, unknown> | null;
  reuse_recommendations_json: unknown[] | null;
  originality_caution_score: number;
  confidence_score: number;
  is_active: boolean;
}

const typeColors: Record<string, string> = {
  hook: 'bg-pink-600', opening: 'bg-violet-600', cta: 'bg-blue-600',
  thumbnail_pattern: 'bg-emerald-600', trust_block: 'bg-orange-600',
  objection_response: 'bg-yellow-600', close_angle: 'bg-red-600',
  sponsor_safe_pattern: 'bg-cyan-600', visual_pacing: 'bg-indigo-600',
  scene_sequence: 'bg-teal-600',
};

export default function CreativeMemoryDashboard() {
  const brandId = useBrandId();
  const [atoms, setAtoms] = useState<CreativeAtom[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/creative-memory-atoms`);
      setAtoms(res.data);
    } catch {
      setError('Failed to load creative memory bank.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/creative-memory-atoms/recompute`);
      setTimeout(fetchData, 5000);
    } catch {
      setError('Failed to recompute creative memory.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading creative memory bank...</div>;
  if (error) return (
    <Alert variant="destructive">
      <Terminal className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Library className="h-8 w-8 text-violet-400" />
          <h1 className="text-3xl font-bold">Creative Memory Bank</h1>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing...</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      {atoms.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {atoms.map((a) => {
            const excerpt = a.content_json ? JSON.stringify(a.content_json).slice(0, 120) : '—';
            const isCautioned = a.originality_caution_score > 0.6;
            return (
              <Card key={a.id} className="bg-gray-800 border-gray-700">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <span className={`px-2 py-1 rounded text-xs font-medium text-white ${typeColors[a.atom_type?.toLowerCase()] ?? 'bg-gray-600'}`}>
                      {a.atom_type?.replace(/_/g, ' ')}
                    </span>
                    {a.platform && <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">{a.platform}</span>}
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-gray-300 line-clamp-2">{excerpt}</p>
                  <div>
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Confidence</span><span>{(a.confidence_score * 100).toFixed(0)}%</span>
                    </div>
                    <Progress value={a.confidence_score * 100} className="h-2" />
                  </div>
                  <div className="text-sm text-gray-400">
                    Originality caution: <span className="font-medium text-gray-200">{(a.originality_caution_score * 100).toFixed(0)}%</span>
                  </div>
                  {isCautioned && (
                    <div className="flex items-start gap-2 p-2 rounded bg-yellow-900/30 border border-yellow-700">
                      <AlertTriangle className="h-4 w-4 text-yellow-400 mt-0.5 shrink-0" />
                      <p className="text-xs text-yellow-300">High originality caution — consider refreshing this pattern</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent>
            <p className="text-center text-gray-500 py-8">No creative atoms available. Recompute to generate.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
