'use client';

import { useState, useEffect } from 'react';
import { useBrandId } from '@/hooks/useBrandId';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, Shield, RefreshCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface WarmupPolicy {
  id: string;
  platform: string;
  initial_posts_per_week_min: number;
  initial_posts_per_week_max: number;
  warmup_duration_weeks_min: number;
  warmup_duration_weeks_max: number;
  steady_state_posts_per_week_min: number;
  steady_state_posts_per_week_max: number;
  max_safe_posts_per_day: number;
  ramp_behavior: string | null;
  scale_ready_conditions_json: Record<string, unknown> | null;
  spam_risk_signals_json: Record<string, unknown> | null;
}

function conditionsList(obj: Record<string, unknown> | null): string[] {
  if (!obj) return [];
  if (Array.isArray(obj)) return obj.map(String);
  return Object.entries(obj).map(([k, v]) => `${k}: ${JSON.stringify(v)}`);
}

export default function PlatformWarmupPoliciesPage() {
  const brandId = useBrandId();
  const [policies, setPolicies] = useState<WarmupPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/v1/brands/${brandId}/platform-warmup-policies`);
      setPolicies(res.data);
    } catch {
      setError('Failed to load platform warm-up policies.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [brandId]);

  if (loading) return <div className="text-center py-8">Loading platform warm-up policies…</div>;
  if (error)
    return (
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
          <Shield className="h-8 w-8 text-indigo-400" />
          <div>
            <h1 className="text-3xl font-bold">Platform Warm-Up Policies</h1>
            <p className="text-sm text-muted-foreground max-w-3xl mt-1">
              Per-platform guardrails that govern posting ramp-up cadence, safe daily limits,
              and the conditions required before an account is considered scale-ready.
            </p>
          </div>
        </div>
        <Button onClick={fetchData} variant="outline" size="sm">
          <RefreshCcw className="mr-2 h-4 w-4" />Refresh
        </Button>
      </div>

      {policies.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {policies.map((p) => (
            <Card key={p.id} className="border border-border">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg capitalize">
                  {p.platform}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-3">
                <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                  <div>
                    <span className="text-muted-foreground block">Initial posting</span>
                    <span className="font-medium">{p.initial_posts_per_week_min}–{p.initial_posts_per_week_max}/wk</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Warmup duration</span>
                    <span className="font-medium">{p.warmup_duration_weeks_min}–{p.warmup_duration_weeks_max} weeks</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Steady state</span>
                    <span className="font-medium">{p.steady_state_posts_per_week_min}–{p.steady_state_posts_per_week_max}/wk</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Max safe/day</span>
                    <span className="font-medium">{p.max_safe_posts_per_day}</span>
                  </div>
                </div>

                {p.ramp_behavior && (
                  <div>
                    <span className="text-muted-foreground text-xs block mb-0.5">Ramp behaviour</span>
                    <span className="font-mono text-xs">{p.ramp_behavior}</span>
                  </div>
                )}

                {p.scale_ready_conditions_json && (
                  <div>
                    <span className="text-muted-foreground text-xs block mb-1">Scale-ready conditions</span>
                    <ul className="list-disc pl-4 space-y-0.5 text-xs">
                      {conditionsList(p.scale_ready_conditions_json).map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {p.spam_risk_signals_json && (
                  <div>
                    <span className="text-muted-foreground text-xs block mb-1">Spam risk signals</span>
                    <ul className="list-disc pl-4 space-y-0.5 text-xs text-red-300">
                      {conditionsList(p.spam_risk_signals_json).map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-8">
            <p className="text-center text-muted-foreground">No platform warm-up policies configured.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
