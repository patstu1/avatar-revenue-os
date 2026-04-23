'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, RefreshCcw } from 'lucide-react';

interface ProfitGuardrailReport {
  id: string;
  brand_id: string;
  metric_name: string;
  current_value: number;
  threshold_value: number;
  status: string;
  action_recommended: string | null;
  estimated_impact: number;
  confidence: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function ProfitGuardrailsDashboard() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<ProfitGuardrailReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/api/v1/brands/${brandId}/profit-guardrails`);
      setReports(response.data);
    } catch (err) {
      console.error('Failed to fetch profit guardrail reports:', err);
      setError('Failed to load profit guardrail reports.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/profit-guardrails/recompute`);
      setTimeout(fetchReports, 5000); // Refetch after 5 seconds
    } catch (err) {
      console.error('Failed to recompute profit guardrail reports:', err);
      setError('Failed to recompute profit guardrail reports.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading profit guardrail reports...</div>;
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
        <h1 className="text-3xl font-bold">Profit Guardrails Dashboard</h1>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <>
              <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
              Recomputing...
            </>
          ) : (
            <>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Recompute Reports
            </>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profit Guardrail Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {reports.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Metric Name</TableHead>
                  <TableHead>Current Value</TableHead>
                  <TableHead>Threshold</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Action Recommended</TableHead>
                  <TableHead>Estimated Impact</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((report) => (
                  <TableRow key={report.id}>
                    <TableCell className="font-medium">{report.metric_name}</TableCell>
                    <TableCell>{report.current_value.toFixed(2)}</TableCell>
                    <TableCell>{report.threshold_value.toFixed(2)}</TableCell>
                    <TableCell>{report.status}</TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">{report.action_recommended || 'N/A'}</TableCell>
                    <TableCell>${report.estimated_impact.toFixed(2)}</TableCell>
                    <TableCell>
                      <Progress value={report.confidence * 100} className="w-[100px]" />
                      <span className="ml-2 text-sm text-gray-500">{(report.confidence * 100).toFixed(0)}%</span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No profit guardrail reports available. Recompute to generate some.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
