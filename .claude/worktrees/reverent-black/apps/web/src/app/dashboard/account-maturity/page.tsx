'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Sprout, RefreshCcw } from 'lucide-react';

interface MaturityReport {
  id: string;
  account_id: string;
  platform: string;
  maturity_state: string;
  previous_state: string | null;
  days_in_current_state: number;
  posts_published: number;
  avg_engagement_rate: number;
  follower_velocity: number;
  health_score: number;
}

const STATE_COLORS: Record<string, { text: string; bg: string }> = {
  newborn:    { text: 'text-blue-400',    bg: 'bg-blue-400/10 border-blue-400/30' },
  warming:    { text: 'text-cyan-400',    bg: 'bg-cyan-400/10 border-cyan-400/30' },
  stable:     { text: 'text-green-400',   bg: 'bg-green-400/10 border-green-400/30' },
  scaling:    { text: 'text-emerald-400', bg: 'bg-emerald-400/10 border-emerald-400/30' },
  max_output: { text: 'text-purple-400',  bg: 'bg-purple-400/10 border-purple-400/30' },
  saturated:  { text: 'text-orange-400',  bg: 'bg-orange-400/10 border-orange-400/30' },
  cooling:    { text: 'text-yellow-400',  bg: 'bg-yellow-400/10 border-yellow-400/30' },
  at_risk:    { text: 'text-red-400',     bg: 'bg-red-400/10 border-red-400/30' },
};

function stateStyle(state: string) {
  return STATE_COLORS[state] ?? { text: 'text-gray-400', bg: 'bg-gray-400/10 border-gray-400/30' };
}

function truncId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) + '…' : id;
}

export default function AccountMaturityPage() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<MaturityReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/account-maturity`);
      setReports(res.data);
    } catch {
      setError('Failed to load account maturity data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading account maturity…</div>;
  if (error)
    return (
      <Alert variant="destructive">
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );

  const stateCounts = reports.reduce<Record<string, number>>((acc, r) => {
    acc[r.maturity_state] = (acc[r.maturity_state] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sprout className="h-8 w-8 text-green-400" />
          <div>
            <h1 className="text-3xl font-bold">Account Maturity States</h1>
            <p className="text-sm text-muted-foreground max-w-3xl mt-1">
              Lifecycle stage for each account — from newborn through scaling to at-risk.
              Maturity drives warmup policy, output ceilings, and monetisation eligibility.
            </p>
          </div>
        </div>
        <Button onClick={fetchData} variant="outline" size="sm">
          <RefreshCcw className="mr-2 h-4 w-4" />Refresh
        </Button>
      </div>

      {Object.keys(stateCounts).length > 0 && (
        <div className="grid gap-3 grid-cols-2 sm:grid-cols-4 lg:grid-cols-8">
          {Object.entries(stateCounts).map(([state, count]) => {
            const s = stateStyle(state);
            return (
              <Card key={state} className={`border ${s.bg}`}>
                <CardContent className="py-3 px-4 text-center">
                  <p className={`text-2xl font-bold ${s.text}`}>{count}</p>
                  <p className="text-xs text-muted-foreground capitalize mt-1">{state.replace('_', ' ')}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Maturity Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {reports.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Account</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Previous</TableHead>
                    <TableHead className="text-right">Days</TableHead>
                    <TableHead className="text-right">Posts</TableHead>
                    <TableHead className="text-right">Avg Eng.</TableHead>
                    <TableHead className="text-right">Follower Vel.</TableHead>
                    <TableHead className="text-right">Health</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reports.map((r) => {
                    const s = stateStyle(r.maturity_state);
                    return (
                      <TableRow key={r.id}>
                        <TableCell className="font-mono text-xs" title={r.account_id}>
                          {truncId(r.account_id)}
                        </TableCell>
                        <TableCell className="text-xs">{r.platform}</TableCell>
                        <TableCell>
                          <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium ${s.text} ${s.bg}`}>
                            {r.maturity_state.replace('_', ' ')}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {r.previous_state?.replace('_', ' ') ?? '—'}
                        </TableCell>
                        <TableCell className="text-right text-xs">{r.days_in_current_state}</TableCell>
                        <TableCell className="text-right text-xs">{r.posts_published}</TableCell>
                        <TableCell className="text-right text-xs">{(r.avg_engagement_rate * 100).toFixed(2)}%</TableCell>
                        <TableCell className="text-right text-xs">{r.follower_velocity.toFixed(1)}/d</TableCell>
                        <TableCell className="text-right text-xs">{r.health_score.toFixed(2)}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No maturity reports available.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
