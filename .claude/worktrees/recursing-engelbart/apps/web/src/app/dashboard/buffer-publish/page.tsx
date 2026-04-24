'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchBufferPublishJobs, recomputeBufferPublishJobs, submitBufferJob } from '@/lib/buffer-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Send } from 'lucide-react';

interface Job { id: string; platform: string; publish_mode: string; status: string; buffer_post_id: string | null; error_message: string | null; retry_count: number; created_at: string | null; }

const STATUS_COLORS: Record<string, string> = { pending: 'bg-gray-100 text-gray-800', submitted: 'bg-blue-100 text-blue-800', queued: 'bg-yellow-100 text-yellow-800', scheduled: 'bg-indigo-100 text-indigo-800', published: 'bg-green-100 text-green-800', failed: 'bg-red-100 text-red-800', cancelled: 'bg-gray-300 text-gray-700' };

export default function BufferPublishPage() {
  const brandId = useBrandId();
  const [rows, setRows] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  useEffect(() => { if (brandId) { setLoading(true); fetchBufferPublishJobs(brandId, '').then(setRows).finally(() => setLoading(false)); } }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    try { await recomputeBufferPublishJobs(brandId, ''); setRows(await fetchBufferPublishJobs(brandId, '')); } finally { setRecomputing(false); }
  };

  const handleSubmit = async (jobId: string) => {
    await submitBufferJob(jobId, '');
    if (brandId) setRows(await fetchBufferPublishJobs(brandId, ''));
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Send className="h-6 w-6" /> Buffer Publish Queue</h1>
        <button onClick={handleRecompute} disabled={recomputing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">{recomputing ? 'Scanning…' : 'Scan & Create Jobs'}</button>
      </div>
      <p className="text-sm text-muted-foreground">Content items are mapped to Buffer profiles and queued for submission. This is not direct platform-native posting — Buffer handles the final delivery.</p>
      {loading ? <p>Loading…</p> : (
        <Card>
          <CardHeader><CardTitle>Publish Jobs ({rows.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Platform</TableHead><TableHead>Mode</TableHead><TableHead>Status</TableHead><TableHead>Buffer ID</TableHead><TableHead>Retries</TableHead><TableHead>Error</TableHead><TableHead>Action</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.id}>
                    <TableCell>{r.platform}</TableCell>
                    <TableCell>{r.publish_mode}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_COLORS[r.status] || 'bg-gray-100'}`}>{r.status}</span></TableCell>
                    <TableCell className="font-mono text-xs">{r.buffer_post_id || '—'}</TableCell>
                    <TableCell>{r.retry_count}</TableCell>
                    <TableCell className="max-w-xs truncate text-xs text-red-600">{r.error_message || '—'}</TableCell>
                    <TableCell>{r.status === 'pending' && <button onClick={() => handleSubmit(r.id)} className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700">Submit</button>}</TableCell>
                  </TableRow>
                ))}
                {rows.length === 0 && <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground">No publish jobs. Click &quot;Scan &amp; Create Jobs&quot; to generate.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
