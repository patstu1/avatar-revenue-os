"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { brandsApi } from "@/lib/api";
import { expansionPack2PhaseAApi } from "@/lib/expansion-pack2-phase-a-api";
import { Phone } from "lucide-react";

type Brand = { id: string; name: string };
type CloserFilter = "all" | "pending" | "completed";

function priorityBadge(priority: number | string) {
  const p = Number(priority ?? 3);
  if (p === 1)
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-900/60 text-red-300">
        P1
      </span>
    );
  if (p === 2)
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-yellow-900/60 text-yellow-300">
        P2
      </span>
    );
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-gray-700 text-gray-300">
      P{p}
    </span>
  );
}

export default function SalesCloserPage() {
  const [brandId, setBrandId] = useState("");
  const [closerFilter, setCloserFilter] = useState<CloserFilter>("all");

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !brandId) setBrandId(String(brands[0].id));
  }, [brands, brandId]);

  const closerQ = useQuery({
    queryKey: ["ep2a-closer", brandId],
    queryFn: () =>
      expansionPack2PhaseAApi.leadCloserActions(brandId).then((r) => r.data),
    enabled: Boolean(brandId),
  });

  const selected = useMemo(
    () => brands?.find((b) => String(b.id) === brandId),
    [brands, brandId],
  );

  const closerData = (closerQ.data as any[] | undefined) ?? [];

  const filteredCloser = closerData.filter((a: any) => {
    if (closerFilter === "pending") return a.is_completed === false;
    if (closerFilter === "completed") return a.is_completed === true;
    return true;
  });

  return (
    <div className="space-y-6 pb-16">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Phone className="text-violet-400" size={28} />
          Sales Closer Actions
        </h1>
        <p className="text-gray-400 mt-1 max-w-2xl">
          AI-generated, prioritised sales actions per lead — discovery calls,
          proposals, objection handling, case studies, and more.
        </p>
      </div>

      {/* Brand selector */}
      <div className="card max-w-xl">
        <label className="stat-label block mb-2">Brand</label>
        <select
          className="input-field w-full"
          aria-label="Brand for Sales Closer"
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

      {/* Info banner */}
      <div className="flex items-start gap-3 rounded-lg bg-blue-900/20 border border-blue-800/40 px-4 py-3 text-sm text-blue-300">
        <Phone size={16} className="mt-0.5 shrink-0 text-blue-400" />
        <span>
          Closer actions are generated automatically during Lead
          Qualification recompute.
        </span>
      </div>

      {/* Filter buttons */}
      <div className="flex gap-2">
        {(
          [
            ["all", "All"],
            ["pending", "Pending"],
            ["completed", "Completed"],
          ] as const
        ).map(([f, label]) => (
          <button
            key={f}
            type="button"
            onClick={() => setCloserFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              closerFilter === f
                ? "bg-violet-900/50 text-violet-200 border border-violet-800"
                : "text-gray-400 hover:text-white bg-gray-800/50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Closer actions table */}
      <div className="card border border-gray-800 overflow-x-auto">
        {filteredCloser.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
                <th className="text-left py-2 pr-4 font-medium">
                  Priority
                </th>
                <th className="text-left py-2 pr-4 font-medium">
                  Action Type
                </th>
                <th className="text-left py-2 pr-4 font-medium">Channel</th>
                <th className="text-left py-2 pr-4 font-medium">Timing</th>
                <th className="text-left py-2 pr-4 font-medium">
                  Subject / Opener
                </th>
                <th className="text-left py-2 font-medium">Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {filteredCloser.map((action: any, i: number) => {
                const opener = String(
                  action.subject_or_opener ?? action.subject_line ?? action.opener ?? "",
                );
                const rationale = String(action.rationale ?? "");
                return (
                  <tr
                    key={action.id ?? i}
                    className="hover:bg-gray-800/30 align-top"
                  >
                    <td className="py-2.5 pr-4">
                      {priorityBadge(action.priority)}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-200 whitespace-nowrap">
                      {action.action_type ?? "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-300 whitespace-nowrap">
                      {action.channel ?? "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-400 whitespace-nowrap text-xs">
                      {action.timing ?? "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-300 max-w-[200px]">
                      {opener.length > 60
                        ? opener.slice(0, 60) + "…"
                        : opener || "—"}
                    </td>
                    <td className="py-2.5 text-gray-400 text-xs max-w-[240px]">
                      {rationale.length > 100
                        ? rationale.slice(0, 100) + "…"
                        : rationale || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="text-center text-gray-500 py-8 text-sm">
            No closer actions yet — run Lead Qualification recompute first.
          </p>
        )}
      </div>
    </div>
  );
}
