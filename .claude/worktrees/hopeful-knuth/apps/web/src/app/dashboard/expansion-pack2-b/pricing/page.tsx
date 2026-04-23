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
import { Terminal, DollarSign, Package, RefreshCcw } from 'lucide-react';

interface PricingRecommendation {
  id: string;
  brand_id: string;
  offer_id: string;
  recommendation_type: string;
  current_price: number;
  recommended_price: number;
  price_elasticity: number;
  estimated_revenue_impact: number;
  confidence: number;
  explanation: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function PricingIntelligenceDashboard() {
  const brandId = useBrandId();
  const [recommendations, setRecommendations] = useState<PricingRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRecommendations = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/api/v1/brands/${brandId}/pricing-recommendations`);
      setRecommendations(response.data);
    } catch (err) {
      console.error('Failed to fetch pricing recommendations:', err);
      setError('Failed to load pricing recommendations.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecompute = async () => {
    if (!brandId) return;
    setRecomputing(true);
    setError(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/pricing-recommendations/recompute`);
      // Poll for completion or refetch after a delay
      setTimeout(fetchRecommendations, 5000); // Refetch after 5 seconds
    } catch (err) {
      console.error('Failed to recompute pricing recommendations:', err);
      setError('Failed to recompute pricing recommendations.');
    } finally {
      setRecomputing(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading pricing recommendations...</div>;
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
        <h1 className="text-3xl font-bold">Pricing Intelligence Dashboard</h1>
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
          <CardTitle>Pricing Recommendations</CardTitle>
        </CardHeader>
        <CardContent>
          {recommendations.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Offer ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Current Price</TableHead>
                  <TableHead>Recommended Price</TableHead>
                  <TableHead>Elasticity</TableHead>
                  <TableHead>Revenue Impact</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Explanation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recommendations.map((rec) => (
                  <TableRow key={rec.id}>
                    <TableCell className="font-medium">{rec.offer_id}</TableCell>
                    <TableCell>{rec.recommendation_type}</TableCell>
                    <TableCell>${rec.current_price.toFixed(2)}</TableCell>
                    <TableCell>${rec.recommended_price.toFixed(2)}</TableCell>
                    <TableCell>{rec.price_elasticity.toFixed(2)}</TableCell>
                    <TableCell>${rec.estimated_revenue_impact.toFixed(2)}</TableCell>
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
            <p className="text-center text-gray-500 py-8">No pricing recommendations available. Recompute to generate some.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
