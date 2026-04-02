'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchMetaMonitoring, recomputeMetaMonitoring } from '@/lib/brain-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Gauge } from 'lucide-react';

interface MMReport {
  id: string;
  health_score: number;
  health_band: string;
  decision_quality_score: number;
  confidence_drift_score: number;
  policy_drift_score: number;
  execution_failure_rate: number;
  memory_quality_score: number;
  escalation_rate: number;
  queue_congestion: number;
  dead_agent_count: number;
  low_signal_count: number;
  wasted_action_count: number;
  weak_areas_json: string[] | null;
  recommended_corrections_json: Array<{ type: string; target: string; reason: string }> | null;
  explanation: string | null;
}

const BAND_COLORS: Record<string, string> = { excellent: 'bg-green-100 text-green-800', good: 'bg-emerald-100 text-emerald-800', medium: 'bg-yellow-100 text-yellow-800', degraded: 'bg-orange-100 text-orange-800', critical: 'bg-red-100 text-red-800' };

export default function MetaMonitoringPage() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<MMReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => { if (brandId) { setLoading(true); fetchMetaMonitoring(brandId, '').then(setReports).finally(() => setLoading(false)); } }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try { await recomputeMetaMonitoring(brandId, ''); setReports(await fetchMetaMonitoring(brandId, '')); } finally { setRecomputing(false); }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;
  const r = reports[0];

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Gauge className="h-6 w-6" /> Meta-Monitoring</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">{recomputing ? 'Running…' : 'Recompute'}</button>
      </div>
      {loading ? <p>Loading…</p> : !r ? <p className="text-muted-foreground">No monitoring data. Click Recompute.</p> : (
        <>
          <Card>
            <CardHeader><CardTitle>Brain Health: <span className={`rounded px-2 py-0.5 text-sm ${BAND_COLORS[r.health_band] || ''}`}>{(r.health_score * 100).toFixed(0)}% — {r.health_band}</span></CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>Decision Quality: <span className="font-semibold">{(r.decision_quality_score * 100).toFixed(0)}%</span></div>
                <div>Confidence Drift: <span className="font-semibold">{(r.confidence_drift_score * 100).toFixed(0)}%</span></div>
                <div>Policy Drift: <span className="font-semibold">{(r.policy_drift_score * 100).toFixed(0)}%</span></div>
                <div>Failure Rate: <span className="font-semibold">{(r.execution_failure_rate * 100).toFixed(0)}%</span></div>
                <div>Memory Quality: <span className="font-semibold">{(r.memory_quality_score * 100).toFixed(0)}%</span></div>
                <div>Escalation Rate: <span className="font-semibold">{(r.escalation_rate * 100).toFixed(0)}%</span></div>
                <div>Queue Congestion: <span className="font-semibold">{(r.queue_congestion * 100).toFixed(0)}%</span></div>
                <div>Dead Agents: <span className="font-semibold">{r.dead_agent_count}</span></div>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">{r.explanation}</p>
            </CardContent>
          </Card>
          {r.weak_areas_json && r.weak_areas_json.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Weak Areas ({r.weak_areas_json.length})</CardTitle></CardHeader>
              <CardContent><ul className="list-disc pl-5 text-sm space-y-1">{r.weak_areas_json.map((w, i) => <li key={i}>{w}</li>)}</ul></CardContent>
            </Card>
          )}
          {r.recommended_corrections_json && r.recommended_corrections_json.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Recommended Corrections</CardTitle></CardHeader>
              <CardContent><ul className="space-y-2 text-sm">{r.recommended_corrections_json.map((c, i) => <li key={i}><span className="font-semibold">{c.type}</span> on <span className="font-mono">{c.target}</span> — {c.reason}</li>)}</ul></CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
