'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Zap, ShieldAlert } from 'lucide-react';

interface Policy {
  operating_mode: string;
  min_confidence_auto_execute: number;
  min_confidence_publish: number;
  kill_switch_engaged: boolean;
  max_auto_cost_usd_per_action: number | null;
  require_approval_above_cost_usd: number | null;
}

interface Blocker {
  id: string;
  severity: string;
  title: string;
  summary: string;
  resolution_status: string;
  exact_operator_steps_json: { order?: number; action?: string; detail?: string; verify?: string }[];
}

interface Run {
  id: string;
  loop_step: string;
  status: string;
  confidence_score: number;
  created_at: string;
}

export default function AutonomousExecutionPage() {
  const brandId = useBrandId();
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [blockers, setBlockers] = useState<Blocker[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [steps, setSteps] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewStep, setPreviewStep] = useState('');
  const [previewConf, setPreviewConf] = useState('0.75');
  const [previewCost, setPreviewCost] = useState('');
  const [previewResult, setPreviewResult] = useState<string | null>(null);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const [p, b, r, s] = await Promise.all([
        api.get<Policy>(`/api/v1/brands/${brandId}/automation-execution-policy`),
        api.get<Blocker[]>(`/api/v1/brands/${brandId}/execution-blocker-escalations`),
        api.get<Run[]>(`/api/v1/brands/${brandId}/automation-execution-runs`),
        api.get<{ steps: string[] }>(`/api/v1/brands/${brandId}/automation-loop-steps`),
      ]);
      setPolicy(p.data);
      setBlockers(b.data);
      setRuns(r.data);
      setSteps(s.data.steps);
      if (!previewStep && s.data.steps.length) setPreviewStep(s.data.steps[0]);
    } catch {
      setError('Failed to load autonomous execution data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [brandId]);

  const runGatePreview = async () => {
    if (!brandId || !previewStep) return;
    setPreviewResult(null);
    try {
      const params = new URLSearchParams({
        loop_step: previewStep,
        confidence: String(parseFloat(previewConf) || 0),
      });
      const c = parseFloat(previewCost);
      if (!Number.isNaN(c)) params.set('estimated_cost_usd', String(c));
      const res = await api.get<{ decision: string; reasons: string[] }>(
        `/api/v1/brands/${brandId}/automation-gate-preview?${params.toString()}`
      );
      setPreviewResult(`${res.data.decision} — ${(res.data.reasons || []).join('; ') || 'no reasons'}`);
    } catch {
      setPreviewResult('Preview failed.');
    }
  };

  if (loading) return <div className="text-center py-8">Loading autonomous execution…</div>;
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
      <div className="flex items-center gap-3">
        <Zap className="h-8 w-8 text-amber-400" />
        <div>
          <h1 className="text-3xl font-bold">Autonomous Execution</h1>
          <p className="text-sm text-muted-foreground max-w-3xl mt-1">
            Phase A control plane: policies, gate preview, run log, and structured blockers. Full 14-step loop
            automation is rolled out in later phases; this surface is operator-supervised and audit-backed.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Policy</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-2">
          {policy ? (
            <>
              <p>
                <span className="text-muted-foreground">Mode:</span>{' '}
                <span className="font-mono">{policy.operating_mode}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Kill switch:</span>{' '}
                <span className={policy.kill_switch_engaged ? 'text-red-400' : 'text-green-400'}>
                  {policy.kill_switch_engaged ? 'ENGAGED' : 'off'}
                </span>
              </p>
              <p>
                <span className="text-muted-foreground">Min confidence (auto / publish-sensitive):</span>{' '}
                {policy.min_confidence_auto_execute} / {policy.min_confidence_publish}
              </p>
              <p>
                <span className="text-muted-foreground">Cost caps (USD):</span> max auto{' '}
                {policy.max_auto_cost_usd_per_action ?? '—'}, approval above{' '}
                {policy.require_approval_above_cost_usd ?? '—'}
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">No policy loaded.</p>
          )}
          <p className="text-xs text-muted-foreground pt-2">
            Operators with the right role can update policy via API (PUT /automation-execution-policy). UI editing can be
            added without changing service logic.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Gate preview (read-only)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <label htmlFor="ae-loop-step" className="text-xs text-muted-foreground block mb-1">
                Loop step
              </label>
              <select
                id="ae-loop-step"
                title="Automation loop step"
                aria-label="Automation loop step"
                className="bg-background border rounded px-2 py-1 text-sm"
                value={previewStep}
                onChange={(e) => setPreviewStep(e.target.value)}
              >
                {steps.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="ae-confidence" className="text-xs text-muted-foreground block mb-1">
                Confidence 0–1
              </label>
              <input
                id="ae-confidence"
                title="Confidence between 0 and 1"
                aria-label="Confidence between 0 and 1"
                className="bg-background border rounded px-2 py-1 text-sm w-24"
                value={previewConf}
                onChange={(e) => setPreviewConf(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="ae-cost" className="text-xs text-muted-foreground block mb-1">
                Est. cost USD (optional)
              </label>
              <input
                id="ae-cost"
                title="Estimated cost in USD"
                aria-label="Estimated cost in USD"
                className="bg-background border rounded px-2 py-1 text-sm w-28"
                value={previewCost}
                onChange={(e) => setPreviewCost(e.target.value)}
                placeholder="optional"
              />
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={runGatePreview}>
              Evaluate
            </Button>
          </div>
          {previewResult && <p className="text-sm font-mono text-amber-100">{previewResult}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-orange-400" />
            Blocker escalations
          </CardTitle>
        </CardHeader>
        <CardContent>
          {blockers.length > 0 ? (
            <div className="space-y-4">
              {blockers.map((b) => (
                <div key={b.id} className="border border-border rounded-lg p-3 text-sm">
                  <div className="flex justify-between gap-2">
                    <span className="font-medium">{b.title}</span>
                    <span className="text-xs text-muted-foreground">{b.resolution_status}</span>
                  </div>
                  <p className="text-muted-foreground mt-1">{b.summary}</p>
                  <ol className="list-decimal pl-5 mt-2 space-y-1">
                    {(b.exact_operator_steps_json || []).map((s, i) => (
                      <li key={i}>
                        <span className="font-medium">{s.action || 'Step'}</span>
                        {s.detail ? ` — ${s.detail}` : ''}
                        {s.verify ? (
                          <span className="text-xs text-muted-foreground block">Verify: {s.verify}</span>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No open blockers.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Execution runs</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Step</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((x) => (
                  <TableRow key={x.id}>
                    <TableCell className="font-mono text-xs">{x.loop_step}</TableCell>
                    <TableCell>{x.status}</TableCell>
                    <TableCell>{x.confidence_score.toFixed(2)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{x.created_at}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-muted-foreground text-sm">No runs yet. Created via API or future workers.</p>
          )}
          <Button variant="outline" size="sm" className="mt-3" onClick={load}>
            Refresh
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
