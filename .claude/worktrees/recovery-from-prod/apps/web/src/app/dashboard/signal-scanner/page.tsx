'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Radar, RefreshCcw } from 'lucide-react';

interface ScanRun {
  id: string;
  scan_type: string;
  status: string;
  signals_detected: number;
  signals_actionable: number;
  created_at: string | null;
}

interface SignalEvent {
  id: string;
  signal_type: string;
  signal_source: string;
  normalized_title: string;
  freshness_score: number;
  monetization_relevance: number;
  urgency_score: number;
  confidence: number;
  is_actionable: boolean;
}

function urgencyColor(score: number): string {
  if (score >= 0.7) return 'text-red-400';
  if (score >= 0.4) return 'text-yellow-400';
  return 'text-green-400';
}

export default function SignalScannerPage() {
  const brandId = useBrandId();
  const [scans, setScans] = useState<ScanRun[]>([]);
  const [events, setEvents] = useState<SignalEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const [scansRes, eventsRes] = await Promise.all([
        api.get(`/api/v1/brands/${brandId}/signal-scans`),
        api.get(`/api/v1/brands/${brandId}/signal-events`).catch(() => ({ data: [] })),
      ]);
      setScans(scansRes.data);
      setEvents(eventsRes.data);
    } catch {
      setError('Failed to load signal scanner data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/signal-scans/recompute`);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to recompute signal scans.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading signal scanner…</div>;
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
          <Radar className="h-8 w-8 text-cyan-400" />
          <div>
            <h1 className="text-3xl font-bold">Continuous Signal Scanner</h1>
            <p className="text-sm text-muted-foreground max-w-3xl mt-1">
              Scans external and internal signals — trends, competitor moves, audience behaviour shifts — and
              normalises them into actionable events for the auto-queue.
            </p>
          </div>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Scanning…</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Scan Runs</CardTitle>
        </CardHeader>
        <CardContent>
          {scans.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scan Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Detected</TableHead>
                  <TableHead className="text-right">Actionable</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scans.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-mono text-xs">{s.scan_type}</TableCell>
                    <TableCell>
                      <span className={s.status === 'completed' ? 'text-green-400' : s.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}>
                        {s.status}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">{s.signals_detected}</TableCell>
                    <TableCell className="text-right">{s.signals_actionable}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{s.created_at ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-muted-foreground text-sm">No scan runs yet. Hit Recompute to trigger a scan.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Signal Events</CardTitle>
        </CardHeader>
        <CardContent>
          {events.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead className="text-right">Freshness</TableHead>
                    <TableHead className="text-right">Monetization</TableHead>
                    <TableHead className="text-right">Urgency</TableHead>
                    <TableHead className="text-right">Confidence</TableHead>
                    <TableHead>Actionable</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((e) => (
                    <TableRow key={e.id}>
                      <TableCell className="font-mono text-xs">{e.signal_type}</TableCell>
                      <TableCell className="text-xs">{e.signal_source}</TableCell>
                      <TableCell className="max-w-[240px] truncate text-sm">{e.normalized_title}</TableCell>
                      <TableCell className="text-right text-xs">{e.freshness_score.toFixed(2)}</TableCell>
                      <TableCell className="text-right text-xs">{e.monetization_relevance.toFixed(2)}</TableCell>
                      <TableCell className={`text-right text-xs ${urgencyColor(e.urgency_score)}`}>
                        {e.urgency_score.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right text-xs">{e.confidence.toFixed(2)}</TableCell>
                      <TableCell>
                        <span className={e.is_actionable ? 'text-green-400' : 'text-gray-500'}>
                          {e.is_actionable ? 'Yes' : 'No'}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No signal events found. Events are created by scan runs.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
