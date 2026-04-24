'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api';
import {
  Cpu,
  Layers,
  Users,
  ShoppingBag,
  Zap,
  CheckCircle2,
  ArrowRight,
  Settings,
  Brain,
  Shield,
  Target,
  Network,
  ChevronRight,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

interface ChecklistItem {
  key: string;
  label: string;
  done: boolean;
  count: number;
  priority: number;
}

interface SystemState {
  system_state: 'empty' | 'partial' | 'ready';
  checklist: ChecklistItem[];
  completed_steps: number;
  total_steps: number;
  providers_configured: number;
  brand_count: number;
  account_count: number;
  offer_count: number;
  content_count: number;
}

/* ------------------------------------------------------------------ */
/*  Setup Card                                                        */
/* ------------------------------------------------------------------ */

const STEP_CONFIG: Record<string, { icon: typeof Cpu; color: string; description: string; href: string; actionLabel: string }> = {
  providers: {
    icon: Cpu,
    color: 'cyan',
    description: 'Connect AI providers, publishing platforms, payment processors, and analytics APIs. This powers every autonomous capability.',
    href: '/dashboard/settings',
    actionLabel: 'Configure Providers',
  },
  brands: {
    icon: Target,
    color: 'blue',
    description: 'Create your brands and projects. Each brand operates as an independent revenue unit in your portfolio.',
    href: '/dashboard/brands',
    actionLabel: 'Create Brands',
  },
  accounts: {
    icon: Users,
    color: 'purple',
    description: 'Connect creator accounts across platforms. YouTube, TikTok, Instagram, X, LinkedIn, and 25+ more.',
    href: '/dashboard/accounts',
    actionLabel: 'Connect Accounts',
  },
  offers: {
    icon: ShoppingBag,
    color: 'amber',
    description: 'Add revenue offers — affiliate programs, products, services, sponsorships, courses, memberships.',
    href: '/dashboard/offers',
    actionLabel: 'Add Offers',
  },
  content: {
    icon: Zap,
    color: 'green',
    description: 'Generate your first content. The AI pipeline creates scripts, media, and publishes autonomously.',
    href: '/dashboard/content',
    actionLabel: 'Generate Content',
  },
};

const COLOR_MAP: Record<string, { bg: string; border: string; text: string; glow: string }> = {
  cyan: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/30', text: 'text-cyan-400', glow: 'shadow-[0_0_20px_rgba(34,211,238,0.15)]' },
  blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', glow: 'shadow-[0_0_20px_rgba(59,130,246,0.15)]' },
  purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', glow: 'shadow-[0_0_20px_rgba(168,85,247,0.15)]' },
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', glow: 'shadow-[0_0_20px_rgba(245,158,11,0.15)]' },
  green: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', glow: 'shadow-[0_0_20px_rgba(34,197,94,0.15)]' },
};

function SetupCard({ item, index }: { item: ChecklistItem; index: number }) {
  const router = useRouter();
  const config = STEP_CONFIG[item.key];
  if (!config) return null;
  const colors = COLOR_MAP[config.color];
  const Icon = config.icon;

  return (
    <div
      className={`relative group border rounded-2xl p-6 transition-all duration-300 ${
        item.done
          ? 'border-green-800/40 bg-green-950/10'
          : `${colors.border} bg-gray-900/60 hover:${colors.glow} hover:border-opacity-60 cursor-pointer`
      }`}
      onClick={() => !item.done && router.push(config.href)}
    >
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${
          item.done ? 'bg-green-500/15' : colors.bg
        }`}>
          {item.done ? (
            <CheckCircle2 size={24} className="text-green-400" />
          ) : (
            <Icon size={24} className={colors.text} />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono text-gray-600 uppercase">Step {index + 1}</span>
            {item.done && (
              <span className="text-[10px] font-mono text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">
                {item.count} configured
              </span>
            )}
          </div>
          <h3 className={`text-lg font-bold mb-1 ${item.done ? 'text-green-300' : 'text-white'}`}>
            {item.label}
          </h3>
          <p className="text-sm text-gray-400 leading-relaxed">
            {config.description}
          </p>
        </div>

        {!item.done && (
          <div className="shrink-0 self-center">
            <div className={`flex items-center gap-1 text-sm font-medium ${colors.text} group-hover:gap-2 transition-all`}>
              {config.actionLabel}
              <ChevronRight size={16} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Quick Actions                                                     */
/* ------------------------------------------------------------------ */

function QuickActions() {
  const router = useRouter();

  const actions = [
    { label: 'Settings & API Keys', href: '/dashboard/settings', icon: Settings, desc: 'Manage all provider credentials' },
    { label: 'Revenue Dashboard', href: '/dashboard', icon: Layers, desc: 'Portfolio command center' },
    { label: 'AI Command Center', href: '/dashboard/ai-command-center', icon: Brain, desc: 'AI orchestration overview' },
    { label: 'Provider Registry', href: '/dashboard/provider-registry', icon: Network, desc: 'Full provider inventory' },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {actions.map((a) => (
        <button
          key={a.href}
          onClick={() => router.push(a.href)}
          className="flex flex-col items-start gap-2 p-4 bg-gray-900/40 border border-gray-800/60 rounded-xl hover:border-cyan-800/40 hover:bg-gray-900/60 transition-all text-left group"
        >
          <a.icon size={18} className="text-gray-500 group-hover:text-cyan-400 transition-colors" />
          <p className="text-sm font-medium text-gray-300 group-hover:text-white transition-colors">{a.label}</p>
          <p className="text-[10px] text-gray-600">{a.desc}</p>
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Setup Page                                                   */
/* ------------------------------------------------------------------ */

export default function SetupPage() {
  const router = useRouter();
  const [state, setState] = useState<SystemState | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<SystemState>('/api/v1/onboarding/status')
      .then((data) => {
        // If system is ready, redirect to dashboard
        if (data.system_state === 'ready') {
          router.replace('/dashboard');
          return;
        }
        setState(data);
      })
      .catch(() => {
        setState({
          system_state: 'empty',
          checklist: [
            { key: 'providers', label: 'Connect AI Providers', done: false, count: 0, priority: 1 },
            { key: 'brands', label: 'Create Brands / Projects', done: false, count: 0, priority: 2 },
            { key: 'accounts', label: 'Connect Creator Accounts', done: false, count: 0, priority: 3 },
            { key: 'offers', label: 'Add Revenue Offers', done: false, count: 0, priority: 4 },
            { key: 'content', label: 'Generate Content', done: false, count: 0, priority: 5 },
          ],
          completed_steps: 0,
          total_steps: 5,
          providers_configured: 0,
          brand_count: 0,
          account_count: 0,
          offer_count: 0,
          content_count: 0,
        });
      })
      .finally(() => setLoading(false));
  }, [router]);

  if (loading || !state) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
          <p className="text-sm text-gray-500 font-mono">Scanning system state...</p>
        </div>
      </div>
    );
  }

  const progress = state.total_steps > 0
    ? Math.round((state.completed_steps / state.total_steps) * 100)
    : 0;

  return (
    <div className="max-w-4xl mx-auto py-8">
      {/* Header */}
      <div className="text-center mb-10">
        <div className="w-20 h-20 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-cyan-500/15 to-blue-500/15 border border-cyan-800/40 flex items-center justify-center">
          <Shield size={36} className="text-cyan-400" />
        </div>
        <h1 className="text-4xl font-black bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
          Control Plane Setup
        </h1>
        <p className="text-gray-400 mt-3 text-base max-w-xl mx-auto leading-relaxed">
          Configure your portfolio operating system. Connect providers, create brands,
          link accounts, and activate your autonomous revenue machine.
        </p>
      </div>

      {/* Progress */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-400 font-mono">
            System Readiness
          </span>
          <span className="text-xs text-cyan-400 font-mono">
            {state.completed_steps}/{state.total_steps} modules active
          </span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-700"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Setup Checklist */}
      <div className="space-y-3 mb-10">
        {state.checklist
          .sort((a, b) => a.priority - b.priority)
          .map((item, i) => (
            <SetupCard key={item.key} item={item} index={i} />
          ))}
      </div>

      {/* Quick Actions */}
      <div className="mb-8">
        <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Zap size={14} className="text-cyan-400" />
          Quick Access
        </h2>
        <QuickActions />
      </div>

      {/* Skip to Dashboard */}
      <div className="text-center">
        <button
          onClick={() => router.push('/dashboard')}
          className="inline-flex items-center gap-2 px-6 py-3 text-sm text-gray-400 hover:text-white border border-gray-800 hover:border-gray-700 rounded-xl transition-all"
        >
          Skip to Portfolio Dashboard
          <ArrowRight size={16} />
        </button>
        <p className="text-[10px] text-gray-600 mt-2">
          You can always complete setup from Settings
        </p>
      </div>
    </div>
  );
}
