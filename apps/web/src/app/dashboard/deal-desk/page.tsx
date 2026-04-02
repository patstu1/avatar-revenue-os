'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Handshake, RefreshCcw } from 'lucide-react';

interface DealDeskRow {
  id: string;
  brand_id: string;
  scope_type: string;
  scope_id: string | null;
  deal_strategy: string;
  pricing_stance: string;
  expected_margin: number;
  expected_close_probability: number;
  confidence_score: number;
  packaging_recommendation_json?: Record<string, unknown> | null;
  explanation_json?: { explanation?: string; decision_summary?: Record<string, unknown> } | null;
  created_at: string;
  updated_at: string;
}

const stanceColors: Record<string, string> = {
  premium: 'bg-violet-600',
  competitive: 'bg-blue-600',
  penetration: 'bg-red-600',
  hold: 'bg-yellow-600',
};

function dealTitle(d: DealDeskRow): string {
  const sid = d.scope_id ? d.scope_id.slice(0, 8) : 'brand';
  return `${d.scope_type} · ${sid}`;
}

export default function DealDeskDashboard() {
  const brandId = useBrandId();
  const [deals, setDeals] = useState<DealDeskRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<DealDeskRow[]>(`/api/v1/brands/${brandId}/deal-desk`);
      setDeals(res.data);
    } catch {
      setError('Failed to load deal desk data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/deal-desk/recompute`);
      setTimeout(fetchData, 5000);
    } catch {
      setError('Failed to recompute deal desk.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading deal desk data...</div>;
  if (error)
    return (
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
          <Handshake className="h-8 w-8 text-amber-400" />
          <h1 className="text-3xl font-bold">Deal Desk Engine</h1>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <>
              <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
              Recomputing...
            </>
          ) : (
            <>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Recompute
            </>
          )}
        </Button>
      </div>

      {deals.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {deals.map((d) => {
            const stanceKey = d.pricing_stance?.toLowerCase() ?? '';
            const expl =
              typeof d.explanation_json?.explanation === 'string'
                ? d.explanation_json.explanation
                : null;
            return (
              <Card key={d.id} className="bg-gray-800 border-gray-700">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{dealTitle(d)}</CardTitle>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium text-white ${stanceColors[stanceKey] ?? 'bg-gray-600'}`}
                    >
                      {d.pricing_stance}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="text-sm text-gray-400">
                    Strategy:{' '}
                    <span className="text-gray-200 font-medium">{d.deal_strategy}</span>
                  </div>
                  <div className="text-sm text-gray-400">
                    Scope: <span className="text-gray-300">{d.scope_type}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-xs text-gray-400">Expected Margin</span>
                      <p className="text-lg font-semibold">{(d.expected_margin * 100).toFixed(0)}%</p>
                    </div>
                    <div>
                      <span className="text-xs text-gray-400">Close Probability</span>
                      <Progress value={d.expected_close_probability * 100} className="h-2 mt-2" />
                      <span className="text-xs text-gray-400">
                        {(d.expected_close_probability * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500">
                    Confidence {(d.confidence_score * 100).toFixed(0)}%
                  </div>
                  {expl ? <p className="text-xs text-gray-400 italic pt-1">{expl}</p> : null}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent>
            <p className="text-center text-gray-500 py-8">
              No deal desk entries available. Recompute to generate.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
