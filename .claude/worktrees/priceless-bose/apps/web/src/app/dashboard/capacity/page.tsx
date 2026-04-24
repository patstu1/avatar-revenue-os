'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Gauge, RefreshCcw } from 'lucide-react';

interface CapacityReport {
  id: string;
  brand_id: string;
  capacity_type: string;
  current_capacity: number;
  used_capacity: number;
  constrained_scope_json: Record<string, unknown> | null;
  recommended_volume: number;
  recommended_throttle: number | null;
  expected_profit_impact: number;
  confidence_score: number;
  explanation_json: Record<string, unknown> | null;
  is_active: boolean;
}

interface QueueAllocation {
  id: string;
  brand_id: string;
  queue_name: string;
  priority_score: number;
  allocated_capacity: number;
  deferred_capacity: number;
  reason_json: Record<string, unknown> | null;
}

export default function CapacityDashboard() {
  const brandId = useBrandId();
  const [capacityReports, setCapacityReports] = useState<CapacityReport[]>([]);
  const [queueAllocations, setQueueAllocations] = useState<QueueAllocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const [capRes, qaRes] = await Promise.all([
        api.get(`/api/v1/brands/${brandId}/capacity-reports`),
        api.get(`/api/v1/brands/${brandId}/queue-allocations`),
      ]);
      setCapacityReports(capRes.data);
      setQueueAllocations(qaRes.data);
    } catch {
      setError('Failed to load capacity data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/capacity-reports/recompute`);
      setTimeout(fetchData, 5000);
    } catch {
      setError('Failed to recompute capacity.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading capacity data...</div>;
  if (error) return (
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
          <Gauge className="h-8 w-8 text-orange-400" />
          <h1 className="text-3xl font-bold">Capacity &amp; Queue Orchestrator</h1>
        </div>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <><RefreshCcw className="mr-2 h-4 w-4 animate-spin" />Recomputing...</>
          ) : (
            <><RefreshCcw className="mr-2 h-4 w-4" />Recompute</>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle>Capacity Reports</CardTitle></CardHeader>
        <CardContent>
          {capacityReports.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {capacityReports.map((r) => {
                const utilization = r.current_capacity > 0 ? r.used_capacity / r.current_capacity : 0;
                const isThrottled = r.recommended_throttle != null && r.recommended_throttle > 0;
                return (
                  <div key={r.id} className="rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{r.capacity_type?.replace(/_/g, ' ')}</span>
                      {isThrottled && <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-600 text-white">Throttled</span>}
                    </div>
                    <div>
                      <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                        <span>Utilization</span>
                        <span>{(utilization * 100).toFixed(0)}%</span>
                      </div>
                      <Progress value={utilization * 100} className="h-2" />
                    </div>
                    <div className="text-sm text-gray-400">
                      {r.used_capacity.toFixed(0)} / {r.current_capacity.toFixed(0)} capacity
                    </div>
                    <div className="text-xs text-gray-500">
                      Recommended volume: {r.recommended_volume.toFixed(0)} | Confidence: {(r.confidence_score * 100).toFixed(0)}%
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-center text-gray-500 py-4">No capacity reports. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Queue Allocations</CardTitle></CardHeader>
        <CardContent>
          {queueAllocations.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Queue</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Allocated</TableHead>
                  <TableHead>Deferred</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...queueAllocations].sort((a, b) => b.priority_score - a.priority_score).map((q) => (
                  <TableRow key={q.id}>
                    <TableCell className="font-medium">{q.queue_name}</TableCell>
                    <TableCell>{q.priority_score.toFixed(0)}</TableCell>
                    <TableCell>{q.allocated_capacity.toFixed(0)}</TableCell>
                    <TableCell>{q.deferred_capacity.toFixed(0)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-4">No queue allocations. Recompute to generate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
