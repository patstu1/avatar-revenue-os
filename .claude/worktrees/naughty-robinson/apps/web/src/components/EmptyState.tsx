'use client';

import { ReactNode } from 'react';
import {
  Database, TrendingUp, Users, Zap, AlertTriangle, Settings,
  BarChart3, Globe, Clock, Shield, Package, FileText,
} from 'lucide-react';
import Link from 'next/link';

/**
 * Standardized empty-state display for pages with no data yet.
 *
 * Usage:
 *   <EmptyState reason="no_data" entity="offers" />
 *   <EmptyState reason="no_brand" />
 *   <EmptyState reason="insufficient_data" detail="Need 14 days of activity" />
 */

export type EmptyReason =
  | 'no_brand'
  | 'no_data'
  | 'insufficient_data'
  | 'no_accounts'
  | 'no_providers'
  | 'no_offers'
  | 'no_content'
  | 'no_history'
  | 'no_forecast'
  | 'no_jobs'
  | 'no_alerts'
  | 'loading_failed';

interface EmptyStateProps {
  reason: EmptyReason;
  entity?: string;
  detail?: string;
  action?: { label: string; href: string };
  children?: ReactNode;
}

const CONFIG: Record<EmptyReason, { icon: typeof Database; title: string; description: string; defaultAction?: { label: string; href: string } }> = {
  no_brand: {
    icon: Package,
    title: 'No Brand Selected',
    description: 'Create a brand first, then return here.',
    defaultAction: { label: 'Manage Brands', href: '/dashboard/brands' },
  },
  no_data: {
    icon: Database,
    title: 'No Data Yet',
    description: 'This section will populate as you use the system.',
  },
  insufficient_data: {
    icon: Clock,
    title: 'Insufficient Data',
    description: 'Not enough activity yet to generate this analysis.',
  },
  no_accounts: {
    icon: Users,
    title: 'No Accounts Connected',
    description: 'Connect social media accounts to start distributing content.',
    defaultAction: { label: 'Add Account', href: '/dashboard/accounts' },
  },
  no_providers: {
    icon: Settings,
    title: 'No Providers Configured',
    description: 'Configure API keys for AI, media, and publishing providers.',
    defaultAction: { label: 'Settings & API Keys', href: '/dashboard/settings' },
  },
  no_offers: {
    icon: TrendingUp,
    title: 'No Offers Created',
    description: 'Create monetization offers to start tracking revenue.',
    defaultAction: { label: 'Create Offer', href: '/dashboard/offers' },
  },
  no_content: {
    icon: FileText,
    title: 'No Content Yet',
    description: 'Generate or import content to populate this view.',
    defaultAction: { label: 'Content Pipeline', href: '/dashboard/content' },
  },
  no_history: {
    icon: Clock,
    title: 'No History Available',
    description: 'Historical data will appear as the system runs over time.',
  },
  no_forecast: {
    icon: BarChart3,
    title: 'Forecast Not Available',
    description: 'Need at least 14 days of activity to generate revenue forecasts.',
  },
  no_jobs: {
    icon: Zap,
    title: 'No Jobs Running',
    description: 'Background jobs will appear here when content is being generated or published.',
  },
  no_alerts: {
    icon: Shield,
    title: 'No Alerts',
    description: 'All systems are operating normally. Alerts will appear here when action is needed.',
  },
  loading_failed: {
    icon: AlertTriangle,
    title: 'Failed to Load',
    description: 'Something went wrong loading this data. Try refreshing.',
  },
};

export function EmptyState({ reason, entity, detail, action, children }: EmptyStateProps) {
  const config = CONFIG[reason];
  const Icon = config.icon;
  const finalAction = action ?? config.defaultAction;

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-16 h-16 rounded-full bg-gray-800/60 flex items-center justify-center mb-4">
        <Icon className="h-8 w-8 text-gray-500" />
      </div>
      <h3 className="text-lg font-semibold text-gray-300 mb-2">
        {config.title}{entity ? `: ${entity}` : ''}
      </h3>
      <p className="text-sm text-gray-500 max-w-md mb-4">
        {detail || config.description}
      </p>
      {finalAction && (
        <Link
          href={finalAction.href}
          className="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white text-sm rounded-md transition"
        >
          {finalAction.label}
        </Link>
      )}
      {children}
    </div>
  );
}
