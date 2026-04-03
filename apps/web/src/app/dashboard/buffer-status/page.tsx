'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { recomputeBufferStatusSync } from '@/lib/buffer-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RefreshCw } from 'lucide-react';

export default function BufferStatusPage() {
  const brandId = useBrandId();
  const [syncing, setSyncing] = useState(false);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);

  const handleSync = async () => {
    if (!brandId) return;
    setSyncing(true);
    try {
      const result = await recomputeBufferStatusSync(brandId, '');
      setLastResult(result);
    } finally { setSyncing(false); }
  };

  if (!brandId) return <div className="p-6 text-muted-foreground">Select a brand.</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><RefreshCw className="h-6 w-6" /> Buffer Status Sync</h1>
        <button onClick={handleSync} disabled={syncing} className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">{syncing ? 'Syncing…' : 'Sync Now'}</button>
      </div>
      <p className="text-sm text-muted-foreground">Pull Buffer post statuses back into the system. Statuses: queued → scheduled → published / failed.</p>

      {lastResult ? (
        <Card>
          <CardHeader><CardTitle>Last Sync Result</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>Status: <span className="font-semibold">{String(lastResult.status || '—')}</span></div>
              <div>Detail: <span className="font-semibold">{String(lastResult.detail || '—')}</span></div>
            </div>
            {lastResult.counts != null && (
              <pre className="mt-4 text-xs bg-muted p-3 rounded overflow-auto">{JSON.stringify(lastResult.counts as Record<string, unknown>, null, 2)}</pre>
            )}
          </CardContent>
        </Card>
      ) : (
        <p className="text-muted-foreground">Click &quot;Sync Now&quot; to pull latest statuses from Buffer.</p>
      )}
    </div>
  );
}
