'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { revenueCeilingPhaseCApi } from '@/lib/revenue-ceiling-phase-c-api';
import { ShieldCheck, RefreshCw } from 'lucide-react';

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Error';
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

export default function TrustConversionDashboard() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState('');

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const tcQ = useQuery({
    queryKey: ['rc-c-trust', brandId],
    queryFn: () => revenueCeilingPhaseCApi.trustConversion(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const recompute = useMutation({
    mutationFn: () => revenueCeilingPhaseCApi.recomputeTrustConversion(brandId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rc-c-trust', brandId] }),
  });

  const selected = useMemo(() => brands?.find((b) => String(b.id) === brandId), [brands, brandId]);

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <ShieldCheck className="text-violet-400" size={28} />
          Trust Conversion Dashboard
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Trust deficit scoring, missing trust elements, recommended proof blocks with prioritised
          actions, and expected conversion uplift.
        </p>
      </div>

      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Trust Conversion"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
        >
          {(brands ?? []).map((b) => (
            <option key={b.id} value={String(b.id)}>{b.name}</option>
          ))}
        </select>
        {selected && <p className="text-sm text-gray-500 mt-2">{selected.name}</p>}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          disabled={!brandId || recompute.isPending}
          onClick={() => recompute.mutate()}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw size={16} className={recompute.isPending ? 'animate-spin' : ''} />
          Recompute
        </button>
      </div>
      {recompute.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">{errMessage(recompute.error)}</div>
      )}

      {(tcQ.data as any[] | undefined)?.[0] ? (
        (() => {
          const T = (tcQ.data as any[])[0] as Record<string, unknown>;
          const deficit = Number(T.trust_deficit_score ?? 0);
          const deficitColor = deficit > 0.5 ? 'text-red-400' : deficit >= 0.3 ? 'text-yellow-400' : 'text-emerald-400';
          const proofBlocks = T.recommended_proof_blocks as Array<Record<string, unknown>> | undefined;
          const missingElements = T.missing_trust_elements as string[] | undefined;

          return (
            <div className="space-y-4">
              {/* Summary card */}
              <div className="card border border-gray-800">
                <div className="flex flex-wrap gap-8 items-start">
                  <div>
                    <p className="stat-label">Trust Deficit Score</p>
                    <p className={`text-4xl font-bold ${deficitColor}`}>{pct(deficit)}</p>
                  </div>
                  <div>
                    <p className="stat-label">Expected Uplift</p>
                    <p className="text-2xl font-semibold text-emerald-300">
                      {pct(Number(T.expected_uplift ?? 0))}
                    </p>
                  </div>
                  <div>
                    <p className="stat-label">Confidence</p>
                    <p className="text-gray-300 text-lg">{pct(Number(T.confidence ?? 0))}</p>
                  </div>
                </div>
                {typeof T.explanation === 'string' && (
                  <p className="text-xs text-gray-500 mt-3 border-t border-gray-800 pt-3">{T.explanation}</p>
                )}
              </div>

              {/* Missing trust elements */}
              {missingElements && missingElements.length > 0 && (
                <div className="card border border-gray-800">
                  <p className="stat-label mb-3">Missing Trust Elements</p>
                  <div className="flex flex-wrap gap-2">
                    {missingElements.map((el, i) => (
                      <span
                        key={i}
                        className="px-2.5 py-1 rounded-full bg-red-900/30 text-red-300 text-xs border border-red-900/50"
                      >
                        {el}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Proof blocks table */}
              {proofBlocks && proofBlocks.length > 0 && (
                <div className="card border border-gray-800">
                  <p className="stat-label mb-3">Recommended Proof Blocks</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left text-gray-400">
                      <thead>
                        <tr className="border-b border-gray-800 text-gray-500 text-xs">
                          <th className="py-2 pr-4">Type</th>
                          <th className="py-2 pr-4">Priority</th>
                          <th className="py-2">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {proofBlocks.map((pb, i) => (
                          <tr key={i} className="border-b border-gray-900">
                            <td className="py-2 pr-4 text-gray-200 text-xs">{String(pb.type ?? '—')}</td>
                            <td className="py-2 pr-4">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] ${
                                  Number(pb.priority) === 1
                                    ? 'bg-red-900/30 text-red-300'
                                    : Number(pb.priority) === 2
                                      ? 'bg-yellow-900/30 text-yellow-300'
                                      : 'bg-gray-800 text-gray-400'
                                }`}
                              >
                                P{String(pb.priority ?? '—')}
                              </span>
                            </td>
                            <td className="py-2 text-xs text-gray-400">{String(pb.action ?? '—')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          );
        })()
      ) : (
        !tcQ.isLoading && <p className="text-gray-500">No data — recompute to generate.</p>
      )}
    </div>
  );
}
