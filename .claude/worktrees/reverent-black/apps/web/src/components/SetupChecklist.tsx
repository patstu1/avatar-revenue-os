'use client';

import Link from 'next/link';
import {
  CheckCircle2,
  Circle,
  Package,
  Key,
  Radio,
  DollarSign,
  X,
  ChevronRight,
} from 'lucide-react';

export interface ChecklistState {
  brand_created: boolean;
  ai_provider_connected: boolean;
  publishing_connected: boolean;
  offer_configured: boolean;
}

interface SetupChecklistProps {
  checklist: ChecklistState;
  progress: { completed: number; total: number };
  onDismiss?: () => void;
}

const ITEMS: {
  key: keyof ChecklistState;
  label: string;
  href: string;
  icon: typeof Package;
}[] = [
  { key: 'brand_created', label: 'Create a brand', href: '/dashboard/brands', icon: Package },
  { key: 'ai_provider_connected', label: 'Connect an AI provider', href: '/dashboard/settings', icon: Key },
  { key: 'publishing_connected', label: 'Connect a publishing account', href: '/dashboard/settings', icon: Radio },
  { key: 'offer_configured', label: 'Configure a monetization offer', href: '/dashboard/offers', icon: DollarSign },
];

export function SetupChecklist({ checklist, progress, onDismiss }: SetupChecklistProps) {
  // Don't render if everything is done
  if (progress.completed >= progress.total) return null;

  const pct = Math.round((progress.completed / progress.total) * 100);

  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            Setup Progress
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {progress.completed} of {progress.total} complete
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-cyan-400">{pct}%</span>
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="p-1 rounded hover:bg-gray-800 text-gray-600 hover:text-gray-400 transition"
              title="Dismiss"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-gray-800 rounded-full mb-4 overflow-hidden">
        <div
          className="h-full bg-cyan-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Checklist items */}
      <div className="space-y-1">
        {ITEMS.map((item) => {
          const done = checklist[item.key];
          const Icon = item.icon;
          return (
            <Link
              key={item.key}
              href={done ? '#' : item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition group ${
                done
                  ? 'text-gray-600 cursor-default'
                  : 'text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              {done ? (
                <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
              ) : (
                <Circle size={16} className="text-gray-600 shrink-0" />
              )}
              <Icon size={14} className={done ? 'text-gray-700' : 'text-gray-500'} />
              <span className={`text-sm flex-1 ${done ? 'line-through' : ''}`}>
                {item.label}
              </span>
              {!done && (
                <ChevronRight
                  size={14}
                  className="text-gray-700 group-hover:text-gray-400 transition shrink-0"
                />
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
