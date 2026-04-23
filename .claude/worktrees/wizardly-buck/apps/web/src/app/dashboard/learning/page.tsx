'use client';

import { Brain } from 'lucide-react';

export default function LearningMemoryPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Brain size={28} className="text-brand-400" />
        <div>
          <h1 className="text-2xl font-bold">Memory / Learning</h1>
          <p className="text-sm text-gray-400">
            Consolidated learning signals, pattern memory, and performance insights
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Patterns Stored</p>
          <p className="text-2xl font-bold text-white">—</p>
          <p className="text-xs text-gray-500 mt-1">Awaiting learning consolidation worker</p>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Last Consolidation</p>
          <p className="text-2xl font-bold text-white">—</p>
          <p className="text-xs text-gray-500 mt-1">Scheduled daily at 03:00 UTC</p>
        </div>
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Insight Quality</p>
          <p className="text-2xl font-bold text-white">—</p>
          <p className="text-xs text-gray-500 mt-1">Based on prediction accuracy over time</p>
        </div>
      </div>

      <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Learning Consolidation Log</h2>
        <p className="text-gray-500 text-sm">
          The learning worker consolidates performance outcomes, experiment results, and
          audience behavior patterns into reusable memory entries. This data feeds future
          scoring, prioritization, and content strategy decisions.
        </p>
        <div className="mt-4 border-t border-gray-700 pt-4">
          <p className="text-gray-500 text-sm italic">
            No consolidation runs recorded yet. The Celery beat scheduler triggers
            <code className="bg-gray-900 px-1.5 py-0.5 rounded text-xs ml-1">consolidate_memory</code> daily.
          </p>
        </div>
      </div>
    </div>
  );
}
