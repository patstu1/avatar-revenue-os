'use client';

import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Users, RefreshCcw } from 'lucide-react';

interface RetentionRecommendation {
  id: string;
  brand_id: string;
  customer_segment: string;
  recommendation_type: string;
  action_details: Record<string, any> | null;
  estimated_retention_lift: number;
  confidence: number;
  explanation: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface ReactivationCampaign {
  id: string;
  brand_id: string;
  campaign_name: string;
  target_segment: string;
  campaign_type: string;
  start_date: string | null;
  end_date: string | null;
  estimated_reactivation_rate: number;
  estimated_revenue_impact: number;
  confidence: number;
  explanation: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function RetentionReactivationDashboard() {
  const brandId = useBrandId();
  const [retentionRecommendations, setRetentionRecommendations] = useState<RetentionRecommendation[]>([]);
  const [reactivationCampaigns, setReactivationCampaigns] = useState<ReactivationCampaign[]>([]);
  const [loadingRetention, setLoadingRetention] = useState(true);
  const [loadingReactivation, setLoadingReactivation] = useState(true);
  const [recomputingRetention, setRecomputingRetention] = useState(false);
  const [recomputingReactivation, setRecomputingReactivation] = useState(false);
  const [errorRetention, setErrorRetention] = useState<string | null>(null);
  const [errorReactivation, setErrorReactivation] = useState<string | null>(null);

  const fetchRetentionRecommendations = async () => {
    if (!brandId) return;
    setLoadingRetention(true);
    setErrorRetention(null);
    try {
      const response = await api.get(`/api/v1/brands/${brandId}/retention-recommendations`);
      setRetentionRecommendations(response.data);
    } catch (err) {
      console.error('Failed to fetch retention recommendations:', err);
      setErrorRetention('Failed to load retention recommendations.');
    } finally {
      setLoadingRetention(false);
    }
  };

  const fetchReactivationCampaigns = async () => {
    if (!brandId) return;
    setLoadingReactivation(true);
    setErrorReactivation(null);
    try {
      const response = await api.get(`/api/v1/brands/${brandId}/reactivation-campaigns`);
      setReactivationCampaigns(response.data);
    } catch (err) {
      console.error('Failed to fetch reactivation campaigns:', err);
      setErrorReactivation('Failed to load reactivation campaigns.');
    } finally {
      setLoadingReactivation(false);
    }
  };

  const handleRecomputeReactivation = async () => {
    if (!brandId) return;
    setRecomputingReactivation(true);
    setErrorReactivation(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/reactivation-campaigns/recompute`);
      // Poll for completion or refetch after a delay
      setTimeout(fetchReactivationCampaigns, 5000); // Refetch after 5 seconds
    } catch (err) {
      console.error('Failed to recompute reactivation campaigns:', err);
      setErrorReactivation('Failed to recompute reactivation campaigns.');
    } finally {
      setRecomputingReactivation(false);
    }
  };

  const handleRecomputeRetention = async () => {
    if (!brandId) return;
    setRecomputingRetention(true);
    setErrorRetention(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/retention-recommendations/recompute`);
      setTimeout(fetchRetentionRecommendations, 5000);
    } catch (err) {
      console.error('Failed to recompute retention recommendations:', err);
      setErrorRetention('Failed to recompute retention recommendations.');
    } finally {
      setRecomputingRetention(false);
    }
  };

  useEffect(() => {
    fetchRetentionRecommendations();
    fetchReactivationCampaigns();
  }, [brandId]);

  if (loadingRetention || loadingReactivation) return <div className="text-center py-8">Loading retention and reactivation data...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Retention and Reactivation Dashboard</h1>

      {errorRetention && (
        <Alert variant="destructive">
          <Terminal className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errorRetention}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle>Retention Recommendations</CardTitle>
          <Button onClick={handleRecomputeRetention} disabled={recomputingRetention}>
            {recomputingRetention ? (
              <>
                <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
                Recomputing...
              </>
            ) : (
              <>
                <RefreshCcw className="mr-2 h-4 w-4" />
                Recompute Retention
              </>
            )}
          </Button>
        </CardHeader>
        <CardContent>
          {retentionRecommendations.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer Segment</TableHead>
                  <TableHead>Recommendation Type</TableHead>
                  <TableHead>Action Details</TableHead>
                  <TableHead>Retention Lift</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Explanation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {retentionRecommendations.map((rec) => (
                  <TableRow key={rec.id}>
                    <TableCell className="font-medium">{rec.customer_segment}</TableCell>
                    <TableCell>{rec.recommendation_type}</TableCell>
                    <TableCell>{JSON.stringify(rec.action_details)}</TableCell>
                    <TableCell>{(rec.estimated_retention_lift * 100).toFixed(2)}%</TableCell>
                    <TableCell>
                      <Progress value={rec.confidence * 100} className="w-[100px]" />
                      <span className="ml-2 text-sm text-gray-500">{(rec.confidence * 100).toFixed(0)}%</span>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">{rec.explanation}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No retention recommendations available.</p>
          )}
        </CardContent>
      </Card>

      {errorReactivation && (
        <Alert variant="destructive">
          <Terminal className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errorReactivation}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-2xl font-bold">Reactivation Campaigns</CardTitle>
          <Button onClick={handleRecomputeReactivation} disabled={recomputingReactivation}>
            {recomputingReactivation ? (
              <>
                <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
                Recomputing...
              </>
            ) : (
              <>
                <RefreshCcw className="mr-2 h-4 w-4" />
                Recompute Campaigns
              </>
            )}
          </Button>
        </CardHeader>
        <CardContent>
          {reactivationCampaigns.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Campaign Name</TableHead>
                  <TableHead>Target Segment</TableHead>
                  <TableHead>Campaign Type</TableHead>
                  <TableHead>Start Date</TableHead>
                  <TableHead>End Date</TableHead>
                  <TableHead>Reactivation Rate</TableHead>
                  <TableHead>Revenue Impact</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Explanation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reactivationCampaigns.map((campaign) => (
                  <TableRow key={campaign.id}>
                    <TableCell className="font-medium">{campaign.campaign_name}</TableCell>
                    <TableCell>{campaign.target_segment}</TableCell>
                    <TableCell>{campaign.campaign_type}</TableCell>
                    <TableCell>{campaign.start_date ? new Date(campaign.start_date).toLocaleDateString() : '-'}</TableCell>
                    <TableCell>{campaign.end_date ? new Date(campaign.end_date).toLocaleDateString() : '-'}</TableCell>
                    <TableCell>{(campaign.estimated_reactivation_rate * 100).toFixed(2)}%</TableCell>
                    <TableCell>${campaign.estimated_revenue_impact.toFixed(2)}</TableCell>
                    <TableCell>
                      <Progress value={campaign.confidence * 100} className="w-[100px]" />
                      <span className="ml-2 text-sm text-gray-500">{(campaign.confidence * 100).toFixed(0)}%</span>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">{campaign.explanation}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No reactivation campaigns available. Recompute to generate some.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
