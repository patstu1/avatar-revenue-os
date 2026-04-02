'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Shield, RefreshCcw } from 'lucide-react';

interface PrimaryRisk {
  risk_type: string;
  score: number;
  detail: string;
}

interface MitigationRow {
  risk_type: string;
  action: string;
  urgency: string;
}

interface ReputationReport {
  id: string;
  brand_id: string;
  reputation_risk_score: number;
  primary_risks_json: PrimaryRisk[] | null;
  recommended_mitigation_json: MitigationRow[] | null;
  expected_impact_if_unresolved: number;
  confidence_score: number;
}

interface ReputationEventRow {
  id: string;
  event_type: string;
  severity: string;
  details_json: { score?: number; detail?: string } | null;
  created_at: string | null;
}

const riskHeat = (score: number) => {
  if (score >= 0.6) return 'text-red-400';
  if (score >= 0.35) return 'text-amber-400';
  return 'text-emerald-400';
};

export default function ReputationMonitorDashboard() {
  const brandId = useBrandId();
  const [report, setReport] = useState<ReputationReport | null>(null);
  const [events, setEvents] = useState<ReputationEventRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const [repRes, evRes] = await Promise.all([
        api.get(`/api/v1/brands/${brandId}/reputation`),
        api.get(`/api/v1/brands/${brandId}/reputation-events`),
      ]);
      const data = Array.isArray(repRes.data) ? repRes.data[0] ?? null : repRes.data;
      setReport(data);
      setEvents(Array.isArray(evRes.data) ? evRes.data : []);
    } catch {
      setError('Failed to load reputation data.');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/reputation/recompute`);
      setTimeout(fetchData, 2000);
    } catch {
      setError('Failed to recompute reputation.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading reputation data...</div>;
  if (error)
    return (
      <Alert variant="destructive">
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );

  if (!report)
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="h-8 w-8 text-sky-400" />
            <h1 className="text-3xl font-bold">Trust &amp; Safety Reputation Monitor</h1>
          </div>
          <Button onClick={handleRecompute} disabled={recomputing}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            Recompute
          </Button>
        </div>
        <Card>
          <CardContent>
            <p className="text-center text-gray-500 py-8">No reputation data. Recompute to generate.</p>
          </CardContent>
        </Card>
        {events.length > 0 && (
          <Card className="bg-gray-800 border-gray-700">
            <CardHeader>
              <CardTitle className="text-sm text-gray-400">Persisted risk events</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                {events.slice(0, 20).map((e) => (
                  <li key={e.id} className="flex justify-between gap-2 border-b border-gray-700/60 pb-2">
                    <span className="text-gray-300 font-mono">{e.event_type.replace(/_/g, ' ')}</span>
                    <span className="text-xs text-gray-500">{e.severity}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    );

  const risks = report.primary_risks_json ?? [];
  const mitigations = report.recommended_mitigation_json ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-sky-400" />
          <h1 className="text-3xl font-bold">Trust &amp; Safety Reputation Monitor</h1>
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

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="bg-gray-800 border-gray-700">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">Reputation risk score</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-5xl font-bold ${riskHeat(report.reputation_risk_score)}`}>
              {(report.reputation_risk_score * 100).toFixed(0)}
            </p>
            <p className="text-xs text-gray-500 mt-2">0 = best · 100 = worst</p>
          </CardContent>
        </Card>

        <Card className="bg-gray-800 border-gray-700">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">Confidence</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-sky-300">
              {(report.confidence_score * 100).toFixed(0)}%
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gray-800 border-gray-700">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">Expected impact if unresolved</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-rose-300">
              {(report.expected_impact_if_unresolved * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-gray-500 mt-1">Composite downside proxy</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="bg-gray-800 border-gray-700">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">Primary risk factors</CardTitle>
          </CardHeader>
          <CardContent>
            {risks.length > 0 ? (
              <ul className="space-y-3">
                {risks.map((r, i) => (
                  <li key={i} className="border-b border-gray-700/80 pb-2 last:border-0">
                    <div className="flex justify-between gap-2">
                      <span className="text-gray-200 font-mono text-sm">
                        {r.risk_type?.replace(/_/g, ' ')}
                      </span>
                      <span className={`text-sm font-medium ${riskHeat(r.score)}`}>
                        {(r.score * 100).toFixed(0)}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{r.detail}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500 text-sm">No primary risks above threshold.</p>
            )}
          </CardContent>
        </Card>

        <Card className="bg-gray-800 border-gray-700">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">Recommended mitigation</CardTitle>
          </CardHeader>
          <CardContent>
            {mitigations.length > 0 ? (
              <ul className="space-y-3">
                {mitigations.map((m, i) => (
                  <li key={i} className="text-sm">
                    <span
                      className={`text-xs uppercase mr-2 px-1.5 py-0.5 rounded ${
                        m.urgency === 'high'
                          ? 'bg-red-900/60 text-red-200'
                          : m.urgency === 'medium'
                            ? 'bg-amber-900/50 text-amber-200'
                            : 'bg-gray-700 text-gray-300'
                      }`}
                    >
                      {m.urgency}
                    </span>
                    <p className="text-emerald-200 mt-1">{m.action}</p>
                    <p className="text-xs text-gray-500 mt-0.5 font-mono">{m.risk_type}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500 text-sm">No mitigations queued.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {events.length > 0 && (
        <Card className="bg-gray-800 border-gray-700">
          <CardHeader>
            <CardTitle className="text-sm text-gray-400">Persisted risk events</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-gray-700/80">
              {events.map((e) => (
                <li key={e.id} className="py-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                  <span className="text-gray-200 font-mono text-sm">{e.event_type.replace(/_/g, ' ')}</span>
                  <span className="text-xs text-gray-500">
                    {e.severity}
                    {e.created_at ? ` · ${new Date(e.created_at).toLocaleString()}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
