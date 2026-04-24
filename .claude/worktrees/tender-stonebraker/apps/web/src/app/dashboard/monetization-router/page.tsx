'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { fetchMonetizationRoutes, recomputeMonetizationRoutes } from '@/lib/autonomous-phase-b-api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { DollarSign, RefreshCcw } from 'lucide-react';

interface Route {
  id: string;
  selected_route: string;
  route_class: string;
  funnel_path: string | null;
  revenue_estimate: number;
  confidence: number;
  route_status: string;
  explanation: string | null;
}

const CLASS_COLORS: Record<string, string> = {
  direct_sale: 'bg-green-100 text-green-800',
  lead_capture: 'bg-blue-100 text-blue-800',
  partnership: 'bg-purple-100 text-purple-800',
  passive_income: 'bg-yellow-100 text-yellow-800',
  recurring: 'bg-teal-100 text-teal-800',
};

export default function MonetizationRouterPage() {
  const brandId = useBrandId();
  const [routes, setRoutes] = useState<Route[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      setRoutes(await fetchMonetizationRoutes(brandId, ''));
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [brandId]);

  const handleRecompute = async () => {
    if (!brandId) return;
    setLoading(true);
    try {
      await recomputeMonetizationRoutes(brandId, '');
      await load();
    } catch { /* empty */ }
    setLoading(false);
  };

  if (!brandId) return <p className="p-8 text-zinc-400">Select a brand first.</p>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <DollarSign className="h-6 w-6 text-emerald-500" />
          <h1 className="text-2xl font-bold">Monetization Router</h1>
        </div>
        <Button onClick={handleRecompute} disabled={loading} size="sm" variant="outline">
          <RefreshCcw className="mr-2 h-4 w-4" /> Recompute
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle>Active Routes ({routes.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Route</TableHead>
                <TableHead>Class</TableHead>
                <TableHead>Funnel</TableHead>
                <TableHead>Revenue Est.</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {routes.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">{r.selected_route.replace(/_/g, ' ')}</TableCell>
                  <TableCell>
                    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${CLASS_COLORS[r.route_class] || 'bg-zinc-100'}`}>
                      {r.route_class.replace(/_/g, ' ')}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-xs text-zinc-500">{r.funnel_path}</TableCell>
                  <TableCell className="font-mono">${r.revenue_estimate.toFixed(2)}</TableCell>
                  <TableCell>{(r.confidence * 100).toFixed(0)}%</TableCell>
                  <TableCell>{r.route_status}</TableCell>
                </TableRow>
              ))}
              {routes.length === 0 && (
                <TableRow><TableCell colSpan={6} className="text-center text-zinc-400">No routes yet</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
