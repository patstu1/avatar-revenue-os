'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Users, RefreshCcw } from 'lucide-react';

interface AudienceState {
  id: string;
  brand_id: string;
  audience_segment_id: string | null;
  state_name: string;
  state_score: number;
  transition_probabilities_json: Record<string, number> | null;
  best_next_action: string;
  confidence_score: number;
  explanation_json: Record<string, unknown> | null;
  is_active: boolean;
}

export default function AudienceStateDashboard() {
  const brandId = useBrandId();
  const [states, setStates] = useState<AudienceState[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/audience-states`);
      setStates(res.data);
    } catch {
      setError('Failed to load audience states.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/audience-states/recompute`);
      setTimeout(fetchData, 5000);
    } catch {
      setError('Failed to recompute audience states.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading audience states...</div>;
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
          <Users className="h-8 w-8 text-sky-400" />
          <h1 className="text-3xl font-bold">Audience State Machine</h1>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing...</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      {states.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {states.map((s) => (
            <Card key={s.id} className="bg-gray-800 border-gray-700">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{s.state_name}</CardTitle>
                  <span className="text-xs text-gray-400">{(s.confidence_score * 100).toFixed(0)}% conf</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>State Score</span><span>{(s.state_score * 100).toFixed(0)}%</span>
                  </div>
                  <Progress value={s.state_score * 100} className="h-2" />
                </div>
                <div className="pt-2 border-t border-gray-700">
                  <span className="text-xs text-gray-400">Best Next Action</span>
                  <p className="text-sm font-medium text-emerald-300">{s.best_next_action}</p>
                </div>
                {s.transition_probabilities_json && Object.keys(s.transition_probabilities_json).length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(s.transition_probabilities_json).map(([state, prob]) => (
                      <span key={state} className="px-2 py-0.5 rounded-full text-xs bg-gray-700 text-gray-300">
                        {state}: {((prob as number) * 100).toFixed(0)}%
                      </span>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <p className="text-center text-gray-500 py-8">No audience states available. Recompute to generate.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
