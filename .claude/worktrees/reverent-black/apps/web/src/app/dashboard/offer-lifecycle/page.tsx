'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Recycle, RefreshCcw } from 'lucide-react';

interface OfferLifecycle {
  id: string;
  brand_id: string;
  offer_id: string;
  lifecycle_state: string;
  health_score: number;
  decay_score: number;
  dependency_risk_score: number;
  recommended_next_action: string | null;
  expected_impact_json: Record<string, unknown> | null;
  confidence_score: number;
  explanation_json: Record<string, unknown> | null;
  is_active: boolean;
}

const stateColors: Record<string, string> = {
  onboarding: 'bg-blue-600',
  probation: 'bg-cyan-600',
  active: 'bg-green-600',
  scaling: 'bg-emerald-500',
  plateauing: 'bg-yellow-600',
  decaying: 'bg-orange-600',
  seasonal_pause: 'bg-purple-600',
  retired: 'bg-gray-600',
  relaunch_candidate: 'bg-pink-600',
};

export default function OfferLifecycleDashboard() {
  const brandId = useBrandId();
  const [records, setRecords] = useState<OfferLifecycle[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/offer-lifecycle-reports`);
      setRecords(res.data);
    } catch {
      setError('Failed to load offer lifecycle data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/offer-lifecycle-reports/recompute`);
      setTimeout(fetchData, 5000);
    } catch {
      setError('Failed to recompute offer lifecycle.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading offer lifecycle data...</div>;
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
          <Recycle className="h-8 w-8 text-emerald-400" />
          <h1 className="text-3xl font-bold">Offer Lifecycle Manager</h1>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing...</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      {records.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {records.map((r) => (
            <Card key={r.id} className="bg-gray-800 border-gray-700">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg truncate">{r.offer_id}</CardTitle>
                  <span className={`px-2 py-1 rounded text-xs font-medium text-white ${stateColors[r.lifecycle_state?.toLowerCase()] ?? 'bg-gray-600'}`}>
                    {r.lifecycle_state?.replace(/_/g, ' ')}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>Health</span><span>{(r.health_score * 100).toFixed(0)}%</span>
                  </div>
                  <Progress value={r.health_score * 100} className="h-2" />
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <span className="text-gray-400 text-xs">Decay</span>
                    <p className="font-medium">{(r.decay_score * 100).toFixed(0)}%</p>
                  </div>
                  <div>
                    <span className="text-gray-400 text-xs">Dependency</span>
                    <p className="font-medium">{(r.dependency_risk_score * 100).toFixed(0)}%</p>
                  </div>
                  <div>
                    <span className="text-gray-400 text-xs">Confidence</span>
                    <p className="font-medium">{(r.confidence_score * 100).toFixed(0)}%</p>
                  </div>
                </div>
                {r.recommended_next_action && (
                  <div className="pt-2 border-t border-gray-700">
                    <span className="text-xs text-gray-400">Recommended Action</span>
                    <p className="text-sm font-medium text-yellow-300">{r.recommended_next_action}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <p className="text-center text-gray-500 py-8">No offer lifecycle data available. Recompute to generate.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
