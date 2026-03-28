'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import {
  LayoutDashboard, Users, Megaphone, Palette, ShoppingBag, MonitorPlay,
  FileText, BarChart3, GitBranch, Brain, Shield, Settings, LogOut,
  Wallet, TrendingUp, Target, Zap, Scale
} from 'lucide-react';

const NAV_SECTIONS = [
  {
    label: 'Command Center',
    items: [
      { href: '/dashboard', label: 'Revenue Dashboard', icon: LayoutDashboard },
      { href: '/dashboard/cockpit', label: 'Operator Cockpit', icon: Target },
      { href: '/dashboard/scale', label: 'Scale Command', icon: TrendingUp },
    ],
  },
  {
    label: 'Content Engine',
    items: [
      { href: '/dashboard/brands', label: 'Brands', icon: Megaphone },
      { href: '/dashboard/avatars', label: 'Avatars', icon: Palette },
      { href: '/dashboard/accounts', label: 'Creator Accounts', icon: Users },
      { href: '/dashboard/content', label: 'Content Pipeline', icon: FileText },
      { href: '/dashboard/publishing', label: 'Publishing', icon: MonitorPlay },
    ],
  },
  {
    label: 'Monetization',
    items: [
      { href: '/dashboard/offers', label: 'Offer Catalog', icon: ShoppingBag },
      { href: '/dashboard/revenue', label: 'Revenue Attribution', icon: Wallet },
      { href: '/dashboard/experiments', label: 'Experiments', icon: Zap },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { href: '/dashboard/portfolio', label: 'Portfolio Allocation', icon: Scale },
      { href: '/dashboard/decisions', label: 'Decision Log', icon: GitBranch },
      { href: '/dashboard/analytics', label: 'Analytics', icon: BarChart3 },
      { href: '/dashboard/memory', label: 'Memory / Learning', icon: Brain },
    ],
  },
  {
    label: 'System',
    items: [
      { href: '/dashboard/jobs', label: 'Jobs & Workers', icon: Shield },
      { href: '/dashboard/settings', label: 'Settings', icon: Settings },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0">
      <div className="p-5 border-b border-gray-800">
        <h1 className="text-lg font-bold bg-gradient-to-r from-brand-400 to-brand-600 bg-clip-text text-transparent">
          Revenue OS
        </h1>
        <p className="text-xs text-gray-500 mt-0.5">AI Avatar Platform</p>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest px-3 mb-2">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                      isActive
                        ? 'bg-brand-600/20 text-brand-300 font-medium'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                    }`}
                  >
                    <item.icon size={16} />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-white text-xs font-bold">
            {user?.full_name?.charAt(0) || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-200 truncate">{user?.full_name || 'User'}</p>
            <p className="text-xs text-gray-500 truncate">{user?.email || ''}</p>
          </div>
          <button onClick={logout} className="text-gray-500 hover:text-red-400 transition-colors">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}
