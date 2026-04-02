"use client";

import { useEffect, useState } from "react";
import { fetchExperiments, fetchWinners, fetchLosers, fetchPromotedRules, ActiveExperiment, PWWinner, PWLoser, PromotedRule } from "@/lib/promote-winner-api";

const brandId = "00000000-0000-0000-0000-000000000001";

export default function ExperimentsPage() {
  const [tab, setTab] = useState<"experiments" | "winners" | "losers" | "rules">("experiments");
  const [experiments, setExperiments] = useState<ActiveExperiment[]>([]);
  const [winners, setWinners] = useState<PWWinner[]>([]);
  const [losers, setLosers] = useState<PWLoser[]>([]);
  const [rules, setRules] = useState<PromotedRule[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchExperiments(brandId), fetchWinners(brandId), fetchLosers(brandId), fetchPromotedRules(brandId)])
      .then(([e, w, l, r]) => { setExperiments(e); setWinners(w); setLosers(l); setRules(r); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const tabs = [
    { key: "experiments" as const, label: `Experiments (${experiments.length})` },
    { key: "winners" as const, label: `Winners (${winners.length})` },
    { key: "losers" as const, label: `Losers (${losers.length})` },
    { key: "rules" as const, label: `Promoted Rules (${rules.length})` },
  ];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white">Experiment / Promote-Winner Engine</h1>
      <div className="flex gap-2">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t.key ? "bg-amber-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
            {t.label}
          </button>
        ))}
      </div>
      {loading ? <p className="text-gray-500">Loading…</p> : (
        <>
          {tab === "experiments" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Name</th><th className="py-2 px-3">Variable</th><th className="py-2 px-3">Platform</th><th className="py-2 px-3">Metric</th><th className="py-2 px-3">Status</th></tr></thead>
              <tbody>{experiments.map(e => (
                <tr key={e.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium">{e.experiment_name}</td><td className="py-2 px-3">{e.tested_variable}</td>
                  <td className="py-2 px-3">{e.target_platform || "—"}</td><td className="py-2 px-3">{e.primary_metric}</td>
                  <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs ${e.status === "active" ? "bg-green-900 text-green-300" : e.status === "completed" ? "bg-blue-900 text-blue-300" : "bg-gray-700 text-gray-400"}`}>{e.status}</span></td>
                </tr>
              ))}</tbody>
            </table>{experiments.length === 0 && <p className="text-gray-500 mt-4">No experiments yet.</p>}</div>
          )}
          {tab === "winners" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Margin</th><th className="py-2 px-3">Confidence</th><th className="py-2 px-3">Samples</th><th className="py-2 px-3">Promoted</th><th className="py-2 px-3">Explanation</th></tr></thead>
              <tbody>{winners.map(w => (
                <tr key={w.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3 font-medium">{(w.win_margin * 100).toFixed(1)}%</td>
                  <td className="py-2 px-3">{(w.confidence * 100).toFixed(1)}%</td>
                  <td className="py-2 px-3">{w.sample_size}</td>
                  <td className="py-2 px-3">{w.promoted ? <span className="text-green-400">Yes</span> : <span className="text-gray-500">No</span>}</td>
                  <td className="py-2 px-3 text-gray-500">{w.explanation}</td>
                </tr>
              ))}</tbody>
            </table>{winners.length === 0 && <p className="text-gray-500 mt-4">No winners yet.</p>}</div>
          )}
          {tab === "losers" && (
            <div className="overflow-x-auto"><table className="w-full text-sm text-left">
              <thead className="text-gray-400 border-b border-gray-800"><tr><th className="py-2 px-3">Loss Margin</th><th className="py-2 px-3">Suppressed</th><th className="py-2 px-3">Explanation</th></tr></thead>
              <tbody>{losers.map(l => (
                <tr key={l.id} className="border-b border-gray-800/50 text-gray-300">
                  <td className="py-2 px-3">{(l.loss_margin * 100).toFixed(1)}%</td>
                  <td className="py-2 px-3">{l.suppressed ? <span className="text-red-400">Yes</span> : <span className="text-gray-500">No</span>}</td>
                  <td className="py-2 px-3 text-gray-500">{l.explanation}</td>
                </tr>
              ))}</tbody>
            </table>{losers.length === 0 && <p className="text-gray-500 mt-4">No losers yet.</p>}</div>
          )}
          {tab === "rules" && (
            <div className="grid gap-4 md:grid-cols-2">{rules.map(r => (
              <div key={r.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-medium text-amber-400">{r.rule_type}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-green-900 text-green-300">+{(r.weight_boost * 100).toFixed(0)}%</span>
                </div>
                <p className="text-white font-medium">{r.rule_key}</p>
                <p className="text-gray-500 text-sm mt-1">{r.explanation}</p>
                {r.target_platform && <p className="text-gray-600 text-xs mt-1">Platform: {r.target_platform}</p>}
              </div>
            ))}{rules.length === 0 && <p className="text-gray-500">No promoted rules yet.</p>}</div>
          )}
        </>
      )}
    </div>
  );
}
