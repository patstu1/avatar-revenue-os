'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, GitBranch, RefreshCcw } from 'lucide-react';

interface ContributionReport {
  id: string;
  brand_id: string;
  attribution_model: string;
  scope_type: string;
  scope_id: string | null;
  estimated_contribution_value: number;
  contribution_score: number;
  confidence_score: number;
  caveats_json: Record<string, unknown> | null;
  explanation_json: Record<string, unknown> | null;
  is_active: boolean;
}

export default function ContributionDashboard() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<ContributionReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/contribution-reports`);
      setReports(res.data);
    } catch {
      setError('Failed to load contribution reports.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/contribution-reports/recompute`);
      setTimeout(fetchData, 5000);
    } catch {
      setError('Failed to recompute contribution reports.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading contribution reports...</div>;
  if (error) return (
    <Alert variant="destructive">
      <Terminal className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  );

  const grouped = reports.reduce<Record<string, ContributionReport[]>>((acc, r) => {
    (acc[r.attribution_model] ??= []).push(r);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch className="h-8 w-8 text-cyan-400" />
          <h1 className="text-3xl font-bold">Contribution &amp; Attribution</h1>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing...</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      {Object.keys(grouped).length > 0 ? (
        Object.entries(grouped).map(([model, items]) => (
          <Card key={model}>
            <CardHeader><CardTitle className="capitalize">{model} Attribution</CardTitle></CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {items.map((r) => (
                  <div key={r.id} className="rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-300">{r.scope_type}</span>
                      <span className="text-xs text-gray-500">{(r.confidence_score * 100).toFixed(0)}% conf</span>
                    </div>
                    <div>
                      <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                        <span>Contribution</span>
                        <span>{(r.contribution_score * 100).toFixed(0)}%</span>
                      </div>
                      <Progress value={r.contribution_score * 100} className="h-2" />
                    </div>
                    <p className="text-lg font-semibold">${r.estimated_contribution_value.toLocaleString()}</p>
                    {r.caveats_json && <p className="text-xs text-yellow-400 italic">{JSON.stringify(r.caveats_json)}</p>}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))
      ) : (
        <Card>
          <CardContent>
            <p className="text-center text-gray-500 py-8">No contribution reports available. Recompute to generate.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
