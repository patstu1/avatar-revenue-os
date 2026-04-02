"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchClusters,
  fetchDecay,
  fetchLosers,
  fetchPatterns,
  fetchReuse,
  recomputePatterns,
  type LosingPattern,
  type PatternCluster,
  type PatternDecay,
  type PatternReuse,
  type WinningPattern,
} from "@/lib/pattern-memory-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Layers, RefreshCcw, Sparkles, Terminal } from "lucide-react";
import { brandsApi } from "@/lib/api";

type TabId = "winning" | "clusters" | "losing" | "reuse" | "decay";

const TABS: { id: TabId; label: string }[] = [
  { id: "winning", label: "Winning Patterns" },
  { id: "clusters", label: "Clusters" },
  { id: "losing", label: "Losing Patterns" },
  { id: "reuse", label: "Reuse Recommendations" },
  { id: "decay", label: "Decay Reports" },
];

function performanceBandClass(band: string): string {
  const b = band?.toLowerCase() ?? "";
  if (b.includes("elite") || b.includes("top") || b.includes("breakout")) return "bg-violet-600 text-white";
  if (b.includes("high") || b.includes("strong")) return "bg-emerald-600 text-white";
  if (b.includes("mid") || b.includes("medium") || b.includes("average")) return "bg-amber-600 text-white";
  if (b.includes("low") || b.includes("weak") || b.includes("poor")) return "bg-red-600 text-white";
  return "bg-gray-600 text-white";
}

export default function PatternMemoryPage() {
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<{id: string; name: string}[]>([]);
  const [tab, setTab] = useState<TabId>("winning");
  const [patterns, setPatterns] = useState<WinningPattern[]>([]);
  const [clusters, setClusters] = useState<PatternCluster[]>([]);
  const [losers, setLosers] = useState<LosingPattern[]>([]);
  const [reuse, setReuse] = useState<PatternReuse[]>([]);
  const [decay, setDecay] = useState<PatternDecay[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    brandsApi.list().then((r) => {
      const list = r.data ?? r;
      setBrands(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) setBrandId(list[0].id);
    }).catch(() => {});
  }, []);

  const loadAll = useCallback(async () => {
    if (!brandId) return;
    setLoading(true);
    setError(null);
    try {
      const [p, c, l, r, d] = await Promise.all([
        fetchPatterns(brandId),
        fetchClusters(brandId),
        fetchLosers(brandId),
        fetchReuse(brandId),
        fetchDecay(brandId),
      ]);
      setPatterns(Array.isArray(p) ? p : []);
      setClusters(Array.isArray(c) ? c : []);
      setLosers(Array.isArray(l) ? l : []);
      setReuse(Array.isArray(r) ? r : []);
      setDecay(Array.isArray(d) ? d : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load pattern memory.");
    } finally {
      setLoading(false);
    }
  }, [brandId]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const sortedPatterns = useMemo(() => {
    return [...patterns].sort((a, b) => b.win_score - a.win_score);
  }, [patterns]);

  const maxWinScore = useMemo(() => {
    if (sortedPatterns.length === 0) return 1;
    return Math.max(...sortedPatterns.map((p) => p.win_score), 1e-6);
  }, [sortedPatterns]);

  const handleRecompute = async () => {
    setRecomputing(true);
    setError(null);
    try {
      await recomputePatterns(brandId);
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recompute failed.");
    } finally {
      setRecomputing(false);
    }
  };

  return (
    <div className="space-y-6 p-6 bg-gray-950 min-h-screen text-gray-100">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Sparkles className="h-8 w-8 text-amber-400" />
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Winning-Pattern Memory</h1>
            <p className="text-sm text-gray-400">Clusters, reuse signals, losers, and decay for this brand.</p>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-400">Brand:</label>
            <select aria-label="Select brand" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white" value={brandId} onChange={e => setBrandId(e.target.value)}>
              {brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
        </div>
        <Button
          onClick={() => void handleRecompute()}
          disabled={recomputing || loading}
          className="bg-amber-600 hover:bg-amber-500 text-white"
        >
          {recomputing ? (
            <>
              <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />
              Recomputing…
            </>
          ) : (
            <>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Recompute
            </>
          )}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="border-red-800 bg-red-950/40">
          <Terminal className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap gap-2 border-b border-gray-800 pb-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-t-md px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? "bg-gray-900 text-amber-300 border border-b-0 border-gray-700"
                : "text-gray-400 hover:text-gray-200 hover:bg-gray-900/50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-8 text-center text-gray-400">Loading pattern memory…</div>
      ) : (
        <>
          {tab === "winning" && (
            <Card className="border-gray-800 bg-gray-900">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-gray-100">
                  <Layers className="h-5 w-5 text-amber-400" />
                  Winning patterns ({sortedPatterns.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-gray-800 hover:bg-transparent">
                      <TableHead className="text-gray-300">Type</TableHead>
                      <TableHead className="text-gray-300">Name</TableHead>
                      <TableHead className="text-gray-300">Platform</TableHead>
                      <TableHead className="text-gray-300 w-40">Win score</TableHead>
                      <TableHead className="text-gray-300">Confidence</TableHead>
                      <TableHead className="text-gray-300">Band</TableHead>
                      <TableHead className="text-gray-300 text-right">Usage</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedPatterns.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center text-gray-500 py-8">
                          No winning patterns yet. Run Recompute to populate.
                        </TableCell>
                      </TableRow>
                    ) : (
                      sortedPatterns.map((p) => (
                        <TableRow key={p.id} className="border-gray-800">
                          <TableCell className="font-medium text-gray-200">{p.pattern_type}</TableCell>
                          <TableCell className="text-gray-300 max-w-[200px] truncate" title={p.pattern_name}>
                            {p.pattern_name}
                          </TableCell>
                          <TableCell className="text-gray-400">{p.platform ?? "—"}</TableCell>
                          <TableCell>
                            <div className="space-y-1">
                              <div className="flex justify-between text-xs text-gray-400">
                                <span>{p.win_score.toFixed(2)}</span>
                              </div>
                              <Progress
                                value={Math.min(100, (p.win_score / maxWinScore) * 100)}
                                className="h-2 bg-gray-800 [&>div]:bg-amber-500"
                              />
                            </div>
                          </TableCell>
                          <TableCell className="text-gray-300">{(p.confidence * 100).toFixed(0)}%</TableCell>
                          <TableCell>
                            <span
                              className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${performanceBandClass(
                                p.performance_band
                              )}`}
                            >
                              {p.performance_band}
                            </span>
                          </TableCell>
                          <TableCell className="text-right text-gray-300">{p.usage_count}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {tab === "clusters" && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {clusters.length === 0 ? (
                <Card className="border-gray-800 bg-gray-900 md:col-span-2 lg:col-span-3">
                  <CardContent className="py-8 text-center text-gray-500">No clusters yet.</CardContent>
                </Card>
              ) : (
                clusters.map((c) => (
                  <Card key={c.id} className="border-gray-800 bg-gray-900">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-lg text-gray-100">{c.cluster_name}</CardTitle>
                      <span className="text-xs font-medium uppercase tracking-wide text-cyan-400">{c.cluster_type}</span>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <div className="flex justify-between text-gray-400">
                        <span>Platform</span>
                        <span className="text-gray-200">{c.platform ?? "—"}</span>
                      </div>
                      <div className="flex justify-between text-gray-400">
                        <span>Avg win score</span>
                        <span className="font-mono text-amber-300">{c.avg_win_score.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between text-gray-400">
                        <span>Patterns</span>
                        <span className="text-gray-200">{c.pattern_count}</span>
                      </div>
                      {c.explanation && <p className="text-xs text-gray-500 leading-relaxed border-t border-gray-800 pt-3">{c.explanation}</p>}
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          )}

          {tab === "losing" && (
            <Card className="border-gray-800 bg-gray-900">
              <CardHeader>
                <CardTitle className="text-gray-100">Losing patterns ({losers.length})</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-gray-800 hover:bg-transparent">
                      <TableHead className="text-gray-300">Type</TableHead>
                      <TableHead className="text-gray-300">Name</TableHead>
                      <TableHead className="text-gray-300">Platform</TableHead>
                      <TableHead className="text-gray-300">Fail score</TableHead>
                      <TableHead className="text-gray-300">Suppress reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {losers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-gray-500 py-8">
                          No losing patterns recorded.
                        </TableCell>
                      </TableRow>
                    ) : (
                      losers.map((row) => (
                        <TableRow key={row.id} className="border-gray-800">
                          <TableCell className="font-medium text-gray-200">{row.pattern_type}</TableCell>
                          <TableCell className="text-gray-300 max-w-xs truncate">{row.pattern_name}</TableCell>
                          <TableCell className="text-gray-400">{row.platform ?? "—"}</TableCell>
                          <TableCell className="font-mono text-red-400">{row.fail_score.toFixed(2)}</TableCell>
                          <TableCell className="text-gray-400 max-w-md">{row.suppress_reason ?? "—"}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {tab === "reuse" && (
            <Card className="border-gray-800 bg-gray-900">
              <CardHeader>
                <CardTitle className="text-gray-100">Reuse recommendations ({reuse.length})</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-gray-800 hover:bg-transparent">
                      <TableHead className="text-gray-300">Target platform</TableHead>
                      <TableHead className="text-gray-300">Content form</TableHead>
                      <TableHead className="text-gray-300">Expected uplift</TableHead>
                      <TableHead className="text-gray-300">Confidence</TableHead>
                      <TableHead className="text-gray-300">Explanation</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reuse.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-gray-500 py-8">
                          No reuse recommendations.
                        </TableCell>
                      </TableRow>
                    ) : (
                      reuse.map((row) => (
                        <TableRow key={row.id} className="border-gray-800">
                          <TableCell className="font-medium text-gray-200">{row.target_platform}</TableCell>
                          <TableCell className="text-gray-400">{row.target_content_form ?? "—"}</TableCell>
                          <TableCell className="text-emerald-400 font-mono">{(row.expected_uplift * 100).toFixed(1)}%</TableCell>
                          <TableCell className="text-gray-300">{(row.confidence * 100).toFixed(0)}%</TableCell>
                          <TableCell className="text-gray-400 max-w-lg text-sm">{row.explanation ?? "—"}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {tab === "decay" && (
            <Card className="border-gray-800 bg-gray-900">
              <CardHeader>
                <CardTitle className="text-gray-100">Decay reports ({decay.length})</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-gray-800 hover:bg-transparent">
                      <TableHead className="text-gray-300">Decay rate</TableHead>
                      <TableHead className="text-gray-300">Reason</TableHead>
                      <TableHead className="text-gray-300">Previous win</TableHead>
                      <TableHead className="text-gray-300">Current win</TableHead>
                      <TableHead className="text-gray-300">Recommendation</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {decay.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-gray-500 py-8">
                          No decay events.
                        </TableCell>
                      </TableRow>
                    ) : (
                      decay.map((row) => (
                        <TableRow key={row.id} className="border-gray-800">
                          <TableCell className="font-mono text-orange-400">{(row.decay_rate * 100).toFixed(1)}%</TableCell>
                          <TableCell className="text-gray-300 max-w-xs">{row.decay_reason}</TableCell>
                          <TableCell className="text-gray-400 font-mono">{row.previous_win_score.toFixed(2)}</TableCell>
                          <TableCell className="text-gray-200 font-mono">{row.current_win_score.toFixed(2)}</TableCell>
                          <TableCell className="text-gray-400 max-w-md text-sm">{row.recommendation ?? "—"}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
