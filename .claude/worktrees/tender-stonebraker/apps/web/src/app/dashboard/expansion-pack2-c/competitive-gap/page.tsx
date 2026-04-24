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

interface CompetitiveGapReport {
  id: string;
  brand_id: string;
  offer_id: string | null;
  competitor_name: string;
  gap_type: string;
  gap_description: string | null;
  severity: string;
  estimated_impact: number;
  confidence: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function CompetitiveGapDashboard() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<CompetitiveGapReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/api/v1/brands/${brandId}/competitive-gaps`);
      setReports(response.data);
    } catch (err) {
      console.error('Failed to fetch competitive gap reports:', err);
      setError('Failed to load competitive gap reports.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/competitive-gaps/recompute`);
      setTimeout(fetchReports, 5000); // Refetch after 5 seconds
    } catch (err) {
      console.error('Failed to recompute competitive gap reports:', err);
      setError('Failed to recompute competitive gap reports.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading competitive gap reports...</div>;
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
        <h1 className="text-3xl font-bold">Competitive Gap Dashboard</h1>
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
          <CardTitle>Competitive Gap Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {reports.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Competitor</TableHead>
                  <TableHead>Offer ID</TableHead>
                  <TableHead>Gap Type</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Estimated Impact</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Description</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((report) => (
                  <TableRow key={report.id}>
                    <TableCell className="font-medium">{report.competitor_name}</TableCell>
                    <TableCell>{report.offer_id || 'N/A'}</TableCell>
                    <TableCell>{report.gap_type}</TableCell>
                    <TableCell>{report.severity}</TableCell>
                    <TableCell>${report.estimated_impact.toFixed(2)}</TableCell>
                    <TableCell>
                      <Progress value={report.confidence * 100} className="w-[100px]" />
                      <span className="ml-2 text-sm text-gray-500">{(report.confidence * 100).toFixed(0)}%</span>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">{report.gap_description}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No competitive gap reports available. Recompute to generate some.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
