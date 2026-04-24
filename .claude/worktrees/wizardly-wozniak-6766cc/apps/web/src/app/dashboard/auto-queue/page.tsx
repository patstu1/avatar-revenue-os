'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, ListOrdered, RefreshCcw } from 'lucide-react';

interface QueueItem {
  id: string;
  queue_item_type: string;
  platform: string;
  niche: string;
  content_family: string | null;
  monetization_path: string | null;
  priority_score: number;
  urgency_score: number;
  queue_status: string;
}

function statusColor(status: string): string {
  switch (status) {
    case 'ready': return 'text-green-400';
    case 'held': return 'text-yellow-400';
    case 'suppressed': return 'text-red-400';
    default: return 'text-gray-400';
  }
}

export default function AutoQueuePage() {
  const brandId = useBrandId();
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/auto-queue`);
      setItems(res.data);
    } catch {
      setError('Failed to load auto-queue items.');
    } finally {
      setLoading(false);
    }
  };

  const handleRebuild = async () => {
    if (!brandId) return;
    setRebuilding(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/auto-queue/rebuild`);
      setTimeout(fetchData, 3000);
    } catch {
      setError('Failed to rebuild auto-queue.');
    } finally {
      setRebuilding(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading auto-queue…</div>;
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
          <ListOrdered className="h-8 w-8 text-violet-400" />
          <div>
            <h1 className="text-3xl font-bold">Auto Queue Builder</h1>
            <p className="text-sm text-muted-foreground max-w-3xl mt-1">
              Prioritised queue of content actions derived from signal events. Items flow through
              ready → held → suppressed states based on warmup capacity and monetisation gates.
            </p>
          </div>
        </div>
        <Button onClick={handleRebuild} disabled={rebuilding}>
          {rebuilding ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Rebuilding…</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Rebuild Queue</>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Queue Items</CardTitle>
        </CardHeader>
        <CardContent>
          {items.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Niche</TableHead>
                    <TableHead>Content Family</TableHead>
                    <TableHead>Monetization</TableHead>
                    <TableHead className="text-right">Priority</TableHead>
                    <TableHead className="text-right">Urgency</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((q) => (
                    <TableRow key={q.id}>
                      <TableCell className="font-mono text-xs">{q.queue_item_type}</TableCell>
                      <TableCell className="text-xs">{q.platform}</TableCell>
                      <TableCell className="text-xs">{q.niche}</TableCell>
                      <TableCell className="text-xs">{q.content_family ?? '—'}</TableCell>
                      <TableCell className="text-xs">{q.monetization_path ?? '—'}</TableCell>
                      <TableCell className="text-right text-xs">{q.priority_score.toFixed(2)}</TableCell>
                      <TableCell className="text-right text-xs">{q.urgency_score.toFixed(2)}</TableCell>
                      <TableCell>
                        <span className={`font-medium text-xs ${statusColor(q.queue_status)}`}>
                          {q.queue_status}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No queue items. Rebuild to generate from signal events.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
