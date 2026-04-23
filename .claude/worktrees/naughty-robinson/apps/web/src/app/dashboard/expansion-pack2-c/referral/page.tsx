'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { RefreshCcw, Terminal } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';

interface ReferralProgramRecommendation {
  id: string;
  brand_id: string;
  customer_segment: string;
  recommendation_type: string;
  referral_bonus: number;
  referred_bonus: number;
  estimated_conversion_rate: number;
  estimated_revenue_impact: number;
  confidence: number;
  explanation: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function ReferralDashboard() {
  const brandId = useBrandId();
  const [reports, setReports] = useState<ReferralProgramRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/api/v1/brands/${brandId}/referral-programs`);
      setReports(response.data);
    } catch (err) {
      console.error('Failed to fetch referral programs:', err);
      setError('Failed to load referral program recommendations.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/referral-programs/recompute`);
      setTimeout(fetchReports, 5000);
    } catch (err) {
      console.error('Failed to recompute referral programs:', err);
      setError('Failed to recompute referral program recommendations.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading referral program recommendations...</div>;
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
        <h1 className="text-3xl font-bold">Referral Program Dashboard</h1>
        <Button onClick={handleRecompute} disabled={recomputing}>
          {recomputing ? (
            <>
              <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
              Recomputing...
            </>
          ) : (
            <>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Recompute Recommendations
            </>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Referral Program Recommendations</CardTitle>
        </CardHeader>
        <CardContent>
          {reports.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer Segment</TableHead>
                  <TableHead>Recommendation Type</TableHead>
                  <TableHead>Referral Bonus</TableHead>
                  <TableHead>Referred Bonus</TableHead>
                  <TableHead>Est. Conversion Rate</TableHead>
                  <TableHead>Est. Revenue Impact</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Explanation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((report) => (
                  <TableRow key={report.id}>
                    <TableCell className="font-medium">{report.customer_segment}</TableCell>
                    <TableCell>{report.recommendation_type}</TableCell>
                    <TableCell>${report.referral_bonus.toFixed(2)}</TableCell>
                    <TableCell>${report.referred_bonus.toFixed(2)}</TableCell>
                    <TableCell>{(report.estimated_conversion_rate * 100).toFixed(2)}%</TableCell>
                    <TableCell>${report.estimated_revenue_impact.toFixed(2)}</TableCell>
                    <TableCell>
                      <Progress value={report.confidence * 100} className="w-[100px]" />
                      <span className="ml-2 text-sm text-gray-500">{(report.confidence * 100).toFixed(0)}%</span>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">{report.explanation}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No referral program recommendations available. Recompute to generate some.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}