'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchArbitrationReports } from '@/lib/brain-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Scale } from 'lucide-react';

interface ArbReport {
  id: string;
  chosen_winner_class: string;
  chosen_winner_label: string;
  competing_count: number;
  net_value_chosen: number;
  ranked_priorities_json: Array<{ rank: number; category: string; label: string; score: number }> | null;
  rejected_actions_json: Array<{ category: string; label: string; reason: string }> | null;
  explanation: string | null;
}

export default function ArbitrationPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<ArbReport[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    fetchArbitrationReports(brandId, '').then(setRows).finally(() => setLoading(false));
  }, [brandId]);

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Scale className="h-6 w-6" /> Priority Arbitration</h1>
      {loading ? <p>Loading…</p> : rows.map(r => (
        <div key={r.id} className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Winner: <span className="text-green-700">{r.chosen_winner_class}</span> — {r.chosen_winner_label}</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">{r.explanation}</p>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>Competing actions: <span className="font-semibold">{r.competing_count}</span></div>
                <div>Net value chosen: <span className="font-semibold text-green-700">${r.net_value_chosen.toFixed(0)}</span></div>
              </div>
            </CardContent>
          </Card>

          {r.ranked_priorities_json && r.ranked_priorities_json.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Ranked Priorities</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader><TableRow><TableHead>Rank</TableHead><TableHead>Category</TableHead><TableHead>Label</TableHead><TableHead>Score</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {r.ranked_priorities_json.map((p, i) => (
                      <TableRow key={i}><TableCell>{p.rank}</TableCell><TableCell>{p.category}</TableCell><TableCell className="max-w-xs truncate">{p.label}</TableCell><TableCell>{p.score}</TableCell></TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {r.rejected_actions_json && r.rejected_actions_json.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Rejected Actions</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader><TableRow><TableHead>Category</TableHead><TableHead>Label</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {r.rejected_actions_json.map((a, i) => (
                      <TableRow key={i}><TableCell>{a.category}</TableCell><TableCell className="max-w-xs truncate">{a.label}</TableCell><TableCell className="max-w-xs truncate">{a.reason}</TableCell></TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      ))}
      {rows.length === 0 && !loading && <p className="text-muted-foreground">No arbitration reports yet. Recompute brain decisions first.</p>}
    </div>
  );
}
