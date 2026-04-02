'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Skull, RefreshCcw } from 'lucide-react';

interface Hindsight {
  hindsight_outcome?: string;
  was_correct_kill?: boolean | null;
  explanation_json?: { explanation?: string } | null;
}

interface KillLedgerRow {
  id: string;
  scope_type: string;
  scope_name?: string;
  kill_reason: string;
  confidence_score: number;
  killed_at: string | null;
  hindsight?: Hindsight | null;
  replacement_recommendation_json?: { action?: string } | null;
}

interface KillLedgerBundle {
  entries: unknown[];
  hindsight_reviews: unknown[];
  entries_with_hindsight: KillLedgerRow[];
}

const hindsightBadge = (h: Hindsight | null | undefined) => {
  if (h?.was_correct_kill === true) return { label: 'Correct kill', className: 'bg-green-600' };
  if (h?.was_correct_kill === false) return { label: 'Regret', className: 'bg-red-600' };
  if (h?.hindsight_outcome) return { label: 'Reviewed', className: 'bg-blue-600' };
  return null;
};

export default function KillLedgerDashboard() {
  const brandId = useBrandId();
  const [entries, setEntries] = useState<KillLedgerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<KillLedgerBundle>(`/api/v1/brands/${brandId}/kill-ledger`);
      const rows = res.data.entries_with_hindsight ?? [];
      setEntries(rows);
    } catch {
      setError('Failed to load kill ledger.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/kill-ledger/recompute`);
      setTimeout(fetchData, 5000);
    } catch {
      setError('Failed to recompute kill ledger.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading kill ledger...</div>;
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
          <Skull className="h-8 w-8 text-gray-400" />
          <h1 className="text-3xl font-bold">Portfolio Kill Ledger</h1>
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

      <Card>
        <CardHeader>
          <CardTitle>Kill Entries</CardTitle>
        </CardHeader>
        <CardContent>
          {entries.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scope</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Kill Reason</TableHead>
                  <TableHead>Replacement</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Killed At</TableHead>
                  <TableHead>Hindsight</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((e) => {
                  const badge = hindsightBadge(e.hindsight);
                  const notes =
                    e.hindsight?.explanation_json?.explanation ??
                    (e.hindsight?.hindsight_outcome ? e.hindsight.hindsight_outcome.slice(0, 120) : null);
                  return (
                    <TableRow key={e.id}>
                      <TableCell className="font-medium">{e.scope_type}</TableCell>
                      <TableCell>{e.scope_name ?? '—'}</TableCell>
                      <TableCell
                        className="max-w-[220px] truncate text-sm text-gray-400"
                        title={e.kill_reason}
                      >
                        {e.kill_reason}
                      </TableCell>
                      <TableCell className="max-w-[180px] truncate text-xs text-gray-500">
                        {e.replacement_recommendation_json?.action ?? '—'}
                      </TableCell>
                      <TableCell>{(e.confidence_score * 100).toFixed(0)}%</TableCell>
                      <TableCell className="text-sm text-gray-400">
                        {e.killed_at ? new Date(e.killed_at).toLocaleDateString() : '—'}
                      </TableCell>
                      <TableCell>
                        {badge ? (
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium text-white ${badge.className}`}
                            title={notes ?? ''}
                          >
                            {badge.label}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-500">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No kill ledger entries. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
