'use client';

import { Target, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2, Pause } from 'lucide-react';

export default function OperatorCockpitPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Operator Cockpit</h1>
        <p className="text-gray-400 mt-1">Unified view of all operating modes, health, and active recommendations</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card border-emerald-800/50">
          <div className="flex items-center gap-3 mb-3">
            <CheckCircle2 size={20} className="text-emerald-400" />
            <h3 className="text-sm font-semibold text-emerald-300 uppercase tracking-wider">Scale</h3>
          </div>
          <p className="text-3xl font-bold text-emerald-400">0</p>
          <p className="text-xs text-gray-500 mt-1">Items recommended for scaling</p>
        </div>

        <div className="card border-amber-800/50">
          <div className="flex items-center gap-3 mb-3">
            <Pause size={20} className="text-amber-400" />
            <h3 className="text-sm font-semibold text-amber-300 uppercase tracking-wider">Monitor</h3>
          </div>
          <p className="text-3xl font-bold text-amber-400">0</p>
          <p className="text-xs text-gray-500 mt-1">Items under observation</p>
        </div>

        <div className="card border-red-800/50">
          <div className="flex items-center gap-3 mb-3">
            <AlertTriangle size={20} className="text-red-400" />
            <h3 className="text-sm font-semibold text-red-300 uppercase tracking-wider">Suppress</h3>
          </div>
          <p className="text-3xl font-bold text-red-400">0</p>
          <p className="text-xs text-gray-500 mt-1">Items flagged for suppression</p>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Active Queues</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {['Generation', 'Publishing', 'Analytics', 'QA', 'Learning', 'Portfolio'].map((q) => (
            <div key={q} className="bg-gray-800/50 rounded-lg p-4 text-center">
              <p className="text-xs text-gray-500 uppercase tracking-wider">{q}</p>
              <p className="text-2xl font-bold text-gray-300 mt-1">0</p>
              <p className="text-xs text-gray-600 mt-1">pending</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Revenue Bottleneck Distribution</h3>
        <p className="text-gray-500 text-sm py-8 text-center">
          Bottleneck classification will populate as performance data is ingested.
        </p>
      </div>
    </div>
  );
}
