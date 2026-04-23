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

interface SponsorTarget {
  id: string;
  brand_id: string;
  target_company_name: string;
  industry: string | null;
  contact_info: Record<string, any> | null;
  estimated_deal_value: number;
  fit_score: number;
  confidence: number;
  explanation: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface SponsorOutreachSequence {
  id: string;
  sponsor_target_id: string;
  sequence_name: string;
  steps: { order: number; type: string; content: string }[];
  estimated_response_rate: number;
  expected_value: number;
  confidence: number;
  explanation: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function OutboundSponsorSalesDashboard() {
  const brandId = useBrandId();
  const [sponsorTargets, setSponsorTargets] = useState<SponsorTarget[]>([]);
  const [outreachSequences, setOutreachSequences] = useState<SponsorOutreachSequence[]>([]);
  const [loadingTargets, setLoadingTargets] = useState(true);
  const [loadingSequences, setLoadingSequences] = useState(true);
  const [recomputingOutreach, setRecomputingOutreach] = useState(false);
  const [recomputingTargets, setRecomputingTargets] = useState(false);
  const [errorTargets, setErrorTargets] = useState<string | null>(null);
  const [errorSequences, setErrorSequences] = useState<string | null>(null);

  const fetchSponsorTargets = async () => {
    if (!brandId) return;
    setLoadingTargets(true);
    setErrorTargets(null);
    try {
      const response = await api.get(`/api/v1/brands/${brandId}/sponsor-targets`);
      setSponsorTargets(response.data);
    } catch (err) {
      console.error('Failed to fetch sponsor targets:', err);
      setErrorTargets('Failed to load sponsor targets.');
    } finally {
      setLoadingTargets(false);
    }
  };

  const fetchOutreachSequences = async () => {
    if (!brandId) return;
    setLoadingSequences(true);
    setErrorSequences(null);
    try {
      const response = await api.get(`/api/v1/brands/${brandId}/sponsor-outreach`);
      setOutreachSequences(response.data);
    } catch (err) {
      console.error('Failed to fetch sponsor outreach sequences:', err);
      setErrorSequences('Failed to load sponsor outreach sequences.');
    } finally {
      setLoadingSequences(false);
    }
  };

  const handleRecomputeTargets = async () => {
    if (!brandId) return;
    setRecomputingTargets(true);
    setErrorTargets(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/sponsor-targets/recompute`);
      setTimeout(fetchSponsorTargets, 5000);
    } catch (err) {
      console.error('Failed to recompute sponsor targets:', err);
      setErrorTargets('Failed to recompute sponsor targets.');
    } finally {
      setRecomputingTargets(false);
    }
  };

  const handleRecomputeOutreach = async () => {
    if (!brandId) return;
    setRecomputingOutreach(true);
    setErrorSequences(null);
    try {
      await api.post(`/api/v1/brands/${brandId}/sponsor-outreach/recompute`);
      setTimeout(fetchOutreachSequences, 5000); // Refetch after 5 seconds
    } catch (err) {
      console.error('Failed to recompute sponsor outreach sequences:', err);
      setErrorSequences('Failed to recompute sponsor outreach sequences.');
    } finally {
      setRecomputingOutreach(false);
    }
  };

  useEffect(() => {
    fetchSponsorTargets();
    fetchOutreachSequences();
  }, [brandId]);

  if (loadingTargets || loadingSequences) return <div className="text-center py-8">Loading sponsor sales data...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Outbound Sponsor Sales Dashboard</h1>

      {errorTargets && (
        <Alert variant="destructive">
          <Terminal className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errorTargets}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-2xl font-bold">Sponsor Targets</CardTitle>
          <Button onClick={handleRecomputeTargets} disabled={recomputingTargets}>
            {recomputingTargets ? (
              <>
                <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
                Recomputing...
              </>
            ) : (
              <>
                <RefreshCcw className="mr-2 h-4 w-4" />
                Recompute Targets
              </>
            )}
          </Button>
        </CardHeader>
        <CardContent>
          {sponsorTargets.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company Name</TableHead>
                  <TableHead>Industry</TableHead>
                  <TableHead>Estimated Deal Value</TableHead>
                  <TableHead>Fit Score</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Explanation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sponsorTargets.map((target) => (
                  <TableRow key={target.id}>
                    <TableCell className="font-medium">{target.target_company_name}</TableCell>
                    <TableCell>{target.industry || 'N/A'}</TableCell>
                    <TableCell>${target.estimated_deal_value.toFixed(2)}</TableCell>
                    <TableCell>
                      <Progress value={target.fit_score * 100} className="w-[100px]" />
                      <span className="ml-2 text-sm text-gray-500">{(target.fit_score * 100).toFixed(0)}%</span>
                    </TableCell>
                    <TableCell>
                      <Progress value={target.confidence * 100} className="w-[100px]" />
                      <span className="ml-2 text-sm text-gray-500">{(target.confidence * 100).toFixed(0)}%</span>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">{target.explanation}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No sponsor targets available.</p>
          )}
        </CardContent>
      </Card>

      {errorSequences && (
        <Alert variant="destructive">
          <Terminal className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errorSequences}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-2xl font-bold">Sponsor Outreach Sequences</CardTitle>
          <Button onClick={handleRecomputeOutreach} disabled={recomputingOutreach}>
            {recomputingOutreach ? (
              <>
                <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
                Recomputing...
              </>
            ) : (
              <>
                <RefreshCcw className="mr-2 h-4 w-4" />
                Recompute Sequences
              </>
            )}
          </Button>
        </CardHeader>
        <CardContent>
          {outreachSequences.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Target Company</TableHead>
                  <TableHead>Sequence Name</TableHead>
                  <TableHead>Response Rate</TableHead>
                  <TableHead>Expected Value</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Explanation</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {outreachSequences.map((seq) => (
                  <TableRow key={seq.id}>
                    <TableCell className="font-medium">{sponsorTargets.find(t => t.id === seq.sponsor_target_id)?.target_company_name || 'N/A'}</TableCell>
                    <TableCell>{seq.sequence_name}</TableCell>
                    <TableCell>{(seq.estimated_response_rate * 100).toFixed(2)}%</TableCell>
                    <TableCell>${seq.expected_value.toFixed(2)}</TableCell>
                    <TableCell>
                      <Progress value={seq.confidence * 100} className="w-[100px]" />
                      <span className="ml-2 text-sm text-gray-500">{(seq.confidence * 100).toFixed(0)}%</span>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">{seq.explanation}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-gray-500 py-8">No sponsor outreach sequences available. Recompute to generate some.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
