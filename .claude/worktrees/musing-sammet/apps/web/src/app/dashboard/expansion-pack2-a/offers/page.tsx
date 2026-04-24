"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { brandsApi } from "@/lib/api";
import { expansionPack2PhaseAApi } from "@/lib/expansion-pack2-phase-a-api";
import { Package, RefreshCw } from "lucide-react";

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

function buildPriorityBadge(priority: string) {
  const p = String(priority ?? "").toLowerCase();
  if (p === "high")
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-900/60 text-red-300">
        High
      </span>
    );
  if (p === "medium")
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-900/60 text-yellow-300">
        Medium
      </span>
    );
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-700 text-gray-300">
      Low
    </span>
  );
}

export default function OwnedOfferOpportunitiesPage() {
  const qc = useQueryClient();
  const [brandId, setBrandId] = useState("");

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const offersQ = useQuery({
    queryKey: ["ep2a-owned-offers", brandId],
    queryFn: () =>
      expansionPack2PhaseAApi
        .ownedOfferRecommendations(brandId)
        .then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const mOffers = useMutation({
    mutationFn: () =>
      expansionPack2PhaseAApi.recomputeOwnedOfferRecommendations(brandId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["ep2a-owned-offers", brandId] }),
  });

  const selected = useMemo(
    () => brands?.find((b) => String(b.id) === brandId),
    [brands, brandId],
  );

  const offersData = (offersQ.data as any[] | undefined) ?? [];

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Package className="text-violet-400" size={28} />
          Owned Offer Opportunities
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          Detect owned-product opportunities from comment themes, funnel
          objections, content engagement, and audience segment signals — with
          offer type, price range, demand score, and estimated first-month
          revenue.
        </p>
      </div>

      {/* Brand selector */}
      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Owned Offer Opportunities"
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
          disabled={!brandId || mOffers.isPending}
          onClick={() => mOffers.mutate()}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw
            size={16}
            className={mOffers.isPending ? "animate-spin" : ""}
          />
          Recompute
        </button>
      </div>

      {mOffers.isError && (
        <div className="card border-red-900/50 text-red-300 text-sm">
          {errMessage(mOffers.error)}
        </div>
      )}

      {offersData.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {offersData.map((offer: any, i: number) => {
            const demandPct = Math.min(
              Math.max(Number(offer.estimated_demand_score ?? offer.demand_score ?? 0) * 100, 0),
              100,
            );
            const confidencePct = Number(offer.confidence ?? 0);
            const audienceFit = String(offer.audience_fit ?? "");
            const explanation = String(offer.explanation ?? "");
            return (
              <div
                key={offer.id ?? i}
                className="card border border-gray-800 space-y-3"
              >
                {/* Top row: name + priority badge */}
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-white leading-snug">
                    {offer.offer_name_suggestion ?? offer.name ?? "—"}
                  </p>
                  {buildPriorityBadge(offer.build_priority)}
                </div>

                {/* Signal type badge */}
                {offer.signal_type && (
                  <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-violet-900/40 text-violet-300 border border-violet-800/50">
                    {offer.signal_type}
                  </span>
                )}

                {/* Price range */}
                <div className="flex items-center gap-1 text-sm text-emerald-300 font-medium">
                  <span>
                    $
                    {Number(
                      offer.price_point_min ?? 0,
                    ).toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </span>
                  <span className="text-gray-600">–</span>
                  <span>
                    $
                    {Number(
                      offer.price_point_max ?? 0,
                    ).toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}
                  </span>
                </div>

                {/* Demand score bar */}
                <div>
                  <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                    <span>Demand Score</span>
                    <span className="text-violet-300 font-medium">
                      {demandPct.toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex-1 bg-gray-800 rounded h-1.5">
                    <div
                      className="h-1.5 rounded bg-violet-500"
                      style={{ width: `${demandPct}%` }}
                    />
                  </div>
                </div>

                {/* Confidence + Est. first month revenue */}
                <div className="flex gap-6 text-sm">
                  <div>
                    <p className="stat-label">Confidence</p>
                    <p className="text-blue-300 font-medium">
                      {pct(confidencePct)}
                    </p>
                  </div>
                  {offer.estimated_first_month_revenue !== undefined && (
                    <div>
                      <p className="stat-label">Est. First Month Rev.</p>
                      <p className="text-emerald-300 font-medium">
                        $
                        {Number(
                          offer.estimated_first_month_revenue,
                        ).toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })}
                      </p>
                    </div>
                  )}
                </div>

                {/* Audience fit */}
                {audienceFit && (
                  <p className="text-xs text-gray-400 truncate">
                    {audienceFit.length > 100
                      ? audienceFit.slice(0, 100) + "…"
                      : audienceFit}
                  </p>
                )}

                {/* Detected signal */}
                {offer.detected_signal && (
                  <p className="text-xs text-gray-500 italic">
                    {offer.detected_signal}
                  </p>
                )}

                {/* Explanation */}
                {explanation && (
                  <p className="text-xs text-gray-500 leading-relaxed">
                    {explanation}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        !offersQ.isLoading && (
          <div className="card text-center text-gray-500 py-8 text-sm">
            No offer opportunities detected — recompute to analyse signals.
          </div>
        )
      )}
    </div>
  );
}
