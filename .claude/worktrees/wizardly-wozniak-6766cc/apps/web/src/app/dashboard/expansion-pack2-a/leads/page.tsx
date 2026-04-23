"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { brandsApi } from "@/lib/api";
import { expansionPack2PhaseAApi } from "@/lib/expansion-pack2-phase-a-api";
import { RefreshCw, Users } from "lucide-react";

type Brand = { id: string; name: string };

function errMessage(e: unknown) {
  if (e && typeof e === "object" && "response" in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response
      ?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : "Error";
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function tierBadge(tier: string) {
  const t = String(tier ?? "").toLowerCase();
  if (t === "hot")
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-900/60 text-red-300">
        Hot
      </span>
    );
  if (t === "warm")
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-900/60 text-yellow-300">
        Warm
      </span>
    );
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-700 text-gray-300">
      Cold
    </span>
  );
}

export default function LeadQualificationPage() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState("");

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const lqQ = useQuery({
    queryKey: ["ep2a-lead-qual", brandId],
    queryFn: () =>
      expansionPack2PhaseAApi.leadQualification(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const leadsQ = useQuery({
    queryKey: ["ep2a-leads", brandId],
    queryFn: () =>
      expansionPack2PhaseAApi.leadOpportunities(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const mLeadQual = useMutation({
    mutationFn: () =>
      expansionPack2PhaseAApi.recomputeLeadQualification(brandId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ep2a-lead-qual", brandId] });
      qc.invalidateQueries({ queryKey: ["ep2a-leads", brandId] });
      qc.invalidateQueries({ queryKey: ["ep2a-closer", brandId] });
    },
  });

  const selected = useMemo(
    () => brands?.find((b) => String(b.id) === brandId),
    [brands, brandId],
  );

  const lqReport = (lqQ.data as any[] | undefined)?.[0] as
    | Record<string, any>
    | undefined;
  const leadsData = (leadsQ.data as any[] | undefined) ?? [];

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Users className="text-violet-400" size={28} />
          Lead Qualification
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Score inbound leads across urgency, budget, sophistication, offer fit,
          and trust readiness — then tier each as hot, warm, or cold with a
          recommended next action.
        </p>
      </div>

      {/* Brand selector */}
      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Lead Qualification"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
        >
          {(brands ?? []).map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name}
            </option>
          ))}
        </select>
        {selected && (
          <p className="text-sm text-gray-500 mt-2">{selected.name}</p>
        )}
      </div>

      {/* Recompute button */}
      <div className="flex justify-end">
        <button
          type="button"
          disabled={!brandId || mLeadQual.isPending}
          onClick={() => mLeadQual.mutate()}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw
            size={16}
            className={mLeadQual.isPending ? "animate-spin" : ""}
          />
          Recompute
        </button>
      </div>

      {mLeadQual.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">
          {errMessage(mLeadQual.error)}
        </div>
      )}

      {/* Summary card */}
      {lqReport ? (
        <div className="card border border-gray-800 space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="rounded-lg bg-gray-800/60 p-3 text-center">
              <p className="stat-label mb-1">Total Scored</p>
              <p className="text-2xl font-bold text-white">
                {lqReport.total_leads_scored ?? lqReport.total_scored ?? 0}
              </p>
            </div>
            <div className="rounded-lg bg-red-900/20 border border-red-900/40 p-3 text-center">
              <p className="stat-label mb-1">Hot</p>
              <p className="text-2xl font-bold text-red-300">
                {lqReport.hot_leads ?? lqReport.hot_count ?? 0}
              </p>
            </div>
            <div className="rounded-lg bg-yellow-900/20 border border-yellow-900/40 p-3 text-center">
              <p className="stat-label mb-1">Warm</p>
              <p className="text-2xl font-bold text-yellow-300">
                {lqReport.warm_leads ?? lqReport.warm_count ?? 0}
              </p>
            </div>
            <div className="rounded-lg bg-gray-800/60 p-3 text-center">
              <p className="stat-label mb-1">Cold</p>
              <p className="text-2xl font-bold text-gray-300">
                {lqReport.cold_leads ?? lqReport.cold_count ?? 0}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="stat-label">Avg Composite Score</p>
              <p className="text-lg font-semibold text-violet-300">
                {pct(Number(lqReport.avg_composite_score ?? 0))}
              </p>
            </div>
            <div>
              <p className="stat-label">Avg Expected Value</p>
              <p className="text-lg font-semibold text-emerald-300">
                $
                {Number(
                  lqReport.avg_expected_value ?? 0,
                ).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
            </div>
            <div>
              <p className="stat-label">Top Channel</p>
              <p className="text-lg font-semibold text-white">
                {lqReport.top_channel ?? "—"}
              </p>
            </div>
            <div>
              <p className="stat-label">Top Action</p>
              <p className="text-lg font-semibold text-white">
                {lqReport.top_recommended_action ?? lqReport.top_action ?? "—"}
              </p>
            </div>
            <div>
              <p className="stat-label">Confidence</p>
              <p className="text-lg font-semibold text-blue-300">
                {pct(Number(lqReport.confidence ?? 0))}
              </p>
            </div>
          </div>

          {lqReport.explanation && (
            <p className="text-sm text-gray-400 leading-relaxed border-t border-gray-800 pt-4">
              {lqReport.explanation}
            </p>
          )}
        </div>
      ) : (
        !lqQ.isLoading && (
          <div className="card text-center text-gray-500 py-8 text-sm">
            No qualification report yet — recompute to generate.
          </div>
        )
      )}

      {/* Lead opportunities table */}
      <div className="card border border-gray-800 overflow-x-auto">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">
          Lead Opportunities
        </h2>
        {leadsData.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
                <th className="text-left py-2 pr-4 font-medium">Source</th>
                <th className="text-left py-2 pr-4 font-medium">Tier</th>
                <th className="text-right py-2 pr-4 font-medium">
                  Composite
                </th>
                <th className="text-right py-2 pr-4 font-medium">
                  Exp. Value
                </th>
                <th className="text-left py-2 pr-4 font-medium">
                  Recommended Action
                </th>
                <th className="text-right py-2 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {leadsData.slice(0, 20).map((lead: any, i: number) => (
                <tr key={lead.id ?? i} className="hover:bg-gray-800/30">
                  <td className="py-2 pr-4 text-gray-200 max-w-[140px] truncate">
                    {lead.lead_source ?? lead.source ?? "—"}
                  </td>
                  <td className="py-2 pr-4">{tierBadge(lead.qualification_tier ?? lead.tier)}</td>
                  <td className="py-2 pr-4 text-right text-violet-300 tabular-nums">
                    {pct(Number(lead.composite_score ?? 0))}
                  </td>
                  <td className="py-2 pr-4 text-right text-emerald-300 tabular-nums">
                    $
                    {Number(
                      lead.expected_value ?? 0,
                    ).toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </td>
                  <td className="py-2 pr-4 text-gray-300 max-w-[200px] truncate">
                    {lead.recommended_action ?? "—"}
                  </td>
                  <td className="py-2 text-right text-blue-300 tabular-nums">
                    {pct(Number(lead.confidence ?? 0))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-center text-gray-500 py-8 text-sm">
            No leads scored — recompute to generate.
          </p>
        )}
      </div>
    </div>
  );
}
