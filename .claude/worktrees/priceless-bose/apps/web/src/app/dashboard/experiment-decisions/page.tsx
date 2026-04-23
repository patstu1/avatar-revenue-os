'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, FlaskConical, RefreshCcw } from 'lucide-react';

interface ExperimentDecision {
  id: string;
  brand_id: string;
  experiment_type: string;
  hypothesis: string;
  priority_score: number;
  expected_upside: number;
  confidence_gap: number;
  status: string;
  recommended_allocation: number;
  explanation_json?: { downstream?: { prior_outcome_signals_applied?: number } } | null;
  created_at: string;
  updated_at: string;
}

interface ExperimentOutcome {
  id: string;
  experiment_decision_id: string;
  observation_source: string;
  outcome_type: string;
  confidence_score: number;
  observed_uplift: number;
  recommended_next_action: string | null;
  explanation_json?: { explanation?: string; data_boundary?: { observation_source?: string; meaning?: string } } | null;
}

interface ExperimentOutcomeAction {
  id: string;
  experiment_outcome_id: string;
  action_kind: string;
  execution_status: string;
  structured_payload_json?: {
    recommended_operator_steps?: string[];
    observation_source?: string;
  } | null;
  operator_note: string | null;
}

const statusColor = (s: string) => {
  const m: Record<string, string> = {
    active: 'bg-green-600',
    proposed: 'bg-blue-600',
    paused: 'bg-yellow-600',
    completed: 'bg-gray-600',
    rejected: 'bg-red-600',
  };
  return m[s?.toLowerCase()] ?? 'bg-gray-600';
};

const outcomeColor = (o: string) => {
  const m: Record<string, string> = {
    promote: 'bg-emerald-600',
    suppress: 'bg-red-600',
    continue: 'bg-amber-600',
    inconclusive: 'bg-gray-600',
  };
  return m[o?.toLowerCase()] ?? 'bg-slate-600';
};

export default function ExperimentDecisionsDashboard() {
  const brandId = useBrandId();
  const [records, setRecords] = useState<ExperimentDecision[]>([]);
  const [outcomes, setOutcomes] = useState<ExperimentOutcome[]>([]);
  const [outcomeActions, setOutcomeActions] = useState<ExperimentOutcomeAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const [dec, out, act] = await Promise.all([
        api.get<ExperimentDecision[]>(`/api/v1/brands/${brandId}/experiment-decisions`),
        api.get<ExperimentOutcome[]>(`/api/v1/brands/${brandId}/experiment-outcomes`),
        api.get<ExperimentOutcomeAction[]>(`/api/v1/brands/${brandId}/experiment-outcome-actions`),
      ]);
      setRecords(dec.data);
      setOutcomes(out.data);
      setOutcomeActions(act.data);
    } catch {
      setError('Failed to load experiment data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/experiment-decisions/recompute`);
      setTimeout(fetchData, 4000);
    } catch {
      setError('Failed to recompute experiment loop.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading experiment decisions...</div>;
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
          <FlaskConical className="h-8 w-8 text-purple-400" />
          <div>
            <h1 className="text-3xl font-bold">Experiment Decision Engine</h1>
            <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
              Outcomes default to <span className="text-amber-500 font-medium">synthetic_proxy</span> (rules-based
              from your data). They are planning signals until live experiment imports exist.
            </p>
          </div>
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
              Recompute decisions + outcomes
            </>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Experiment Decisions</CardTitle>
        </CardHeader>
        <CardContent>
          {records.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Hypothesis</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Expected upside</TableHead>
                  <TableHead>Confidence gap</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Allocation</TableHead>
                  <TableHead>Prior signals</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {records.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.experiment_type}</TableCell>
                    <TableCell className="max-w-[220px] truncate text-sm text-gray-400" title={r.hypothesis}>
                      {r.hypothesis}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={r.priority_score * 100} className="w-[80px]" />
                        <span className="text-xs text-gray-400">{(r.priority_score * 100).toFixed(0)}%</span>
                      </div>
                    </TableCell>
                    <TableCell>{(r.expected_upside * 100).toFixed(1)}%</TableCell>
                    <TableCell>{(r.confidence_gap * 100).toFixed(1)}%</TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 rounded text-xs font-medium text-white ${statusColor(r.status)}`}>
                        {r.status}
                      </span>
                    </TableCell>
                    <TableCell>{(r.recommended_allocation * 100).toFixed(0)}%</TableCell>
                    <TableCell className="text-xs text-gray-500">
                      {r.explanation_json?.downstream?.prior_outcome_signals_applied ?? '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No experiment decisions. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Experiment Outcomes (persisted)</CardTitle>
        </CardHeader>
        <CardContent>
          {outcomes.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Decision</TableHead>
                  <TableHead>Data source</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Uplift</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Next action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {outcomes.map((o) => (
                  <TableRow key={o.id}>
                    <TableCell className="font-mono text-xs">{o.experiment_decision_id.slice(0, 8)}…</TableCell>
                    <TableCell>
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          o.observation_source === 'live_import'
                            ? 'bg-green-700 text-white'
                            : 'bg-amber-900/80 text-amber-100 border border-amber-700'
                        }`}
                        title={
                          o.explanation_json?.data_boundary?.meaning ??
                          'synthetic_proxy = rules-based proxy, not live A/B platform'
                        }
                      >
                        {o.observation_source === 'live_import' ? 'live_import' : 'synthetic_proxy'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium text-white ${outcomeColor(o.outcome_type)}`}
                      >
                        {o.outcome_type}
                      </span>
                    </TableCell>
                    <TableCell>{(o.observed_uplift * 100).toFixed(2)}%</TableCell>
                    <TableCell>{(o.confidence_score * 100).toFixed(0)}%</TableCell>
                    <TableCell className="max-w-[320px] truncate text-sm text-gray-400" title={o.recommended_next_action ?? ''}>
                      {o.recommended_next_action}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-6">No outcomes yet. Run recompute to evaluate and persist.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Downstream actions (operator queue)</CardTitle>
        </CardHeader>
        <CardContent>
          {outcomeActions.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Steps</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {outcomeActions.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-mono text-xs">{a.experiment_outcome_id.slice(0, 8)}…</TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 rounded text-xs font-medium text-white ${outcomeColor(a.action_kind)}`}>
                        {a.action_kind}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-gray-400">{a.execution_status}</TableCell>
                    <TableCell className="max-w-[380px] text-sm text-gray-300">
                      {(a.structured_payload_json?.recommended_operator_steps ?? []).join(' · ') || '—'}
                      {a.operator_note ? (
                        <span className="block text-xs text-muted-foreground mt-1">{a.operator_note}</span>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-6">No queued actions. Recompute decisions to generate outcome actions.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
