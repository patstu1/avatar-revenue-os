'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Clock, RefreshCcw } from 'lucide-react';

interface MarketTimingOpportunity {
  id: string;
  brand_id: string;
  market_category: string;
  timing_score: number;
  active_window: string | null;
  expected_uplift: number;
  recommendation: string;
  confidence_score: number;
  explanation_json: { explanation?: string } | null;
}

interface MacroSignalEventRow {
  id: string;
  signal_type: string;
  source_name: string;
  signal_metadata_json: { value?: number } | null;
  observed_at: string | null;
}

export default function MarketTimingDashboard() {
  const brandId = useBrandId();
  const [opportunities, setOpportunities] = useState<MarketTimingOpportunity[]>([]);
  const [macroSignals, setMacroSignals] = useState<MacroSignalEventRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const [mtRes, macroRes] = await Promise.all([
        api.get(`/api/v1/brands/${brandId}/market-timing`),
        api.get(`/api/v1/brands/${brandId}/macro-signal-events`),
      ]);
      setOpportunities(mtRes.data);
      setMacroSignals(Array.isArray(macroRes.data) ? macroRes.data : []);
    } catch {
      setError('Failed to load market timing data.');
      setMacroSignals([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/market-timing/recompute`);
      setTimeout(fetchData, 2000);
    } catch {
      setError('Failed to recompute market timing.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading market timing data...</div>;
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
          <Clock className="h-8 w-8 text-teal-400" />
          <h1 className="text-3xl font-bold">Market Timing &amp; Macro Opportunities</h1>
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

      {macroSignals.length > 0 && (
        <Card className="bg-gray-900/50 border-gray-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-gray-400">Macro signal inputs (persisted)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 text-sm">
              {macroSignals.map((s) => (
                <div key={s.id} className="rounded border border-gray-700/80 p-2">
                  <div className="font-mono text-gray-200">{s.signal_type.replace(/_/g, ' ')}</div>
                  <div className="text-xs text-gray-500 mt-1">{s.source_name}</div>
                  {s.signal_metadata_json?.value != null && (
                    <div className="text-xs text-teal-300 mt-1">value {s.signal_metadata_json.value}</div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {opportunities.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {opportunities.map((o) => {
            const expl = o.explanation_json?.explanation ?? '';
            return (
              <Card key={o.id} className="bg-gray-800 border-gray-700">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-lg font-mono">
                      {o.market_category.replace(/_/g, ' ')}
                    </CardTitle>
                    <span className="text-xs text-gray-400 shrink-0">
                      {(o.confidence_score * 100).toFixed(0)}% conf
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Market timing score</span>
                      <span>{(o.timing_score * 100).toFixed(0)}%</span>
                    </div>
                    <Progress value={o.timing_score * 100} className="h-2" />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-xs text-gray-400">Active window</span>
                      <p className="font-medium text-gray-200">{o.active_window ?? '—'}</p>
                    </div>
                    <div>
                      <span className="text-xs text-gray-400">Expected uplift</span>
                      <p
                        className={`font-medium ${o.expected_uplift >= 0 ? 'text-green-400' : 'text-amber-400'}`}
                      >
                        {o.expected_uplift >= 0 ? '+' : ''}
                        {(o.expected_uplift * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  <div className="pt-2 border-t border-gray-700">
                    <span className="text-xs text-gray-400">Recommendation</span>
                    <p className="text-sm text-yellow-200 mt-1">{o.recommendation}</p>
                  </div>
                  {expl ? (
                    <div className="text-xs text-gray-500 leading-relaxed border-t border-gray-700/80 pt-2">
                      {expl}
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent>
            <p className="text-center text-gray-500 py-8">
              No market timing rows. Recompute to evaluate windows.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
