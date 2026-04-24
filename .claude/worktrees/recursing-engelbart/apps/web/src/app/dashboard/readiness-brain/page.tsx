'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchReadinessBrain, recomputeReadinessBrain } from '@/lib/brain-phase-d-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ShieldCheck } from 'lucide-react';

interface RBReport { id: string; readiness_score: number; readiness_band: string; blockers_json: string[] | null; allowed_actions_json: string[] | null; forbidden_actions_json: string[] | null; explanation: string | null; }

const BAND_COLORS: Record<string, string> = { ready: 'bg-green-100 text-green-800', mostly_ready: 'bg-emerald-100 text-emerald-800', partially_ready: 'bg-yellow-100 text-yellow-800', not_ready: 'bg-orange-100 text-orange-800', blocked: 'bg-red-100 text-red-800' };

export default function ReadinessBrainPage() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<RBReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => { if (brandId) { setLoading(true); fetchReadinessBrain(brandId, '').then(setReports).finally(() => setLoading(false)); } }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try { await recomputeReadinessBrain(brandId, ''); setReports(await fetchReadinessBrain(brandId, '')); } finally { setRecomputing(false); }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;
  const r = reports[0];

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><ShieldCheck className="h-6 w-6" /> Readiness Brain</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">{recomputing ? 'Running…' : 'Recompute'}</button>
      </div>
      {loading ? <p>Loading…</p> : !r ? <p className="text-muted-foreground">No readiness data. Click Recompute.</p> : (
        <>
          <Card>
            <CardHeader><CardTitle>Readiness: <span className={`rounded px-2 py-0.5 text-sm ${BAND_COLORS[r.readiness_band] || ''}`}>{(r.readiness_score * 100).toFixed(0)}% — {r.readiness_band}</span></CardTitle></CardHeader>
            <CardContent><p className="text-sm text-muted-foreground">{r.explanation}</p></CardContent>
          </Card>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader><CardTitle className="text-green-700">Allowed Actions</CardTitle></CardHeader>
              <CardContent>{r.allowed_actions_json && r.allowed_actions_json.length > 0 ? <ul className="list-disc pl-5 text-sm space-y-1">{r.allowed_actions_json.map((a, i) => <li key={i}>{a}</li>)}</ul> : <p className="text-sm text-muted-foreground">None</p>}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-red-700">Forbidden Actions</CardTitle></CardHeader>
              <CardContent>{r.forbidden_actions_json && r.forbidden_actions_json.length > 0 ? <ul className="list-disc pl-5 text-sm space-y-1">{r.forbidden_actions_json.map((a, i) => <li key={i}>{a}</li>)}</ul> : <p className="text-sm text-muted-foreground">None</p>}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-orange-700">Blockers</CardTitle></CardHeader>
              <CardContent>{r.blockers_json && r.blockers_json.length > 0 ? <ul className="list-disc pl-5 text-sm space-y-1">{r.blockers_json.map((b, i) => <li key={i}>{b}</li>)}</ul> : <p className="text-sm text-muted-foreground">None</p>}</CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
