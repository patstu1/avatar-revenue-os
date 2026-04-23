'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Flame, RefreshCcw } from 'lucide-react';

interface WarmupPlan {
  id: string;
  account_id: string;
  platform: string;
  warmup_phase: string;
  current_posts_per_week: number;
  target_posts_per_week: number | null;
  engagement_target: number;
  confidence: number;
}

function phaseColor(phase: string): string {
  switch (phase) {
    case 'phase_1': return 'text-blue-400';
    case 'phase_2': return 'text-yellow-400';
    case 'phase_3': return 'text-green-400';
    case 'phase_4': return 'text-orange-400';
    default: return 'text-gray-400';
  }
}

function phaseBadgeBg(phase: string): string {
  switch (phase) {
    case 'phase_1': return 'bg-blue-400/10 border-blue-400/30';
    case 'phase_2': return 'bg-yellow-400/10 border-yellow-400/30';
    case 'phase_3': return 'bg-green-400/10 border-green-400/30';
    case 'phase_4': return 'bg-orange-400/10 border-orange-400/30';
    default: return 'bg-gray-400/10 border-gray-400/30';
  }
}

function truncId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) + '…' : id;
}

export default function AccountWarmupPage() {
  const brandId = useBrandId();
  const [plans, setPlans] = useState<WarmupPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/account-warmup`);
      setPlans(res.data);
    } catch {
      setError('Failed to load account warm-up plans.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/account-warmup/recompute`);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute warm-up plans.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading account warm-up plans…</div>;
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
          <Flame className="h-8 w-8 text-orange-400" />
          <div>
            <h1 className="text-3xl font-bold">Account Warm-Up Plans</h1>
            <p className="text-sm text-muted-foreground max-w-3xl mt-1">
              Phased posting ramp-up schedules for each account. Ensures new accounts build trust and
              engagement before scaling to full output volume.
            </p>
          </div>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing…</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Warm-Up Plans</CardTitle>
        </CardHeader>
        <CardContent>
          {plans.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Account</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Phase</TableHead>
                    <TableHead className="text-right">Current/wk</TableHead>
                    <TableHead className="text-right">Target/wk</TableHead>
                    <TableHead className="text-right">Eng. Target</TableHead>
                    <TableHead className="text-right">Confidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {plans.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="font-mono text-xs" title={p.account_id}>
                        {truncId(p.account_id)}
                      </TableCell>
                      <TableCell className="text-xs">{p.platform}</TableCell>
                      <TableCell>
                        <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium ${phaseColor(p.warmup_phase)} ${phaseBadgeBg(p.warmup_phase)}`}>
                          {p.warmup_phase.replace('_', ' ')}
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-xs">{p.current_posts_per_week}</TableCell>
                      <TableCell className="text-right text-xs">{p.target_posts_per_week ?? '—'}</TableCell>
                      <TableCell className="text-right text-xs">{(p.engagement_target * 100).toFixed(1)}%</TableCell>
                      <TableCell className="text-right text-xs">{p.confidence.toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No warm-up plans found. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
