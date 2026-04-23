'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { expansionAdvisorApi } from '@/lib/expansion-advisor-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Compass, RefreshCcw } from 'lucide-react';

interface Advisory {
  id: string;
  expansion_type: string;
  recommendation: string;
  confidence: number;
  expected_upside: number;
  risk_level: string;
  priority: number;
  created_at: string | null;
}

export default function ExpansionAdvisorPage() {
  const brandId = useBrandId();
  const [advisories, setAdvisories] = useState<Advisory[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    setLoading(true);
    expansionAdvisorApi.advisories(brandId)
      .then(r => setAdvisories((r.data ?? r) as Advisory[]))
      .catch(() => setAdvisories([]))
      .finally(() => setLoading(false));
  }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try {
      await expansionAdvisorApi.recompute(brandId);
      const r = await expansionAdvisorApi.advisories(brandId);
      setAdvisories((r.data ?? r) as Advisory[]);
    } finally {
      setRecomputing(false);
    }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand to view expansion advisories.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Compass className="h-6 w-6" /> Expansion Advisor
        </h1>
        <button
          onClick={handleRecompute}
          disabled={recomputing}
          className="flex items-center gap-2 rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <RefreshCcw size={14} className={recomputing ? 'animate-spin' : ''} />
          {recomputing ? 'Recomputing...' : 'Recompute'}
        </button>
      </div>

      {loading ? <p>Loading...</p> : (
        <Card>
          <CardHeader><CardTitle>Expansion Advisories ({advisories.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Recommendation</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Expected Upside</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Priority</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {advisories.map(a => (
                  <TableRow key={a.id}>
                    <TableCell className="font-medium">{a.expansion_type}</TableCell>
                    <TableCell className="max-w-xs truncate">{a.recommendation}</TableCell>
                    <TableCell>{(a.confidence * 100).toFixed(0)}%</TableCell>
                    <TableCell>${a.expected_upside?.toLocaleString() ?? '0'}</TableCell>
                    <TableCell>{a.risk_level}</TableCell>
                    <TableCell>{a.priority}</TableCell>
                  </TableRow>
                ))}
                {advisories.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      No expansion advisories yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
