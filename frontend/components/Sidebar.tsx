'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import clsx from 'clsx';
import {
  LayoutDashboard,
  Building2,
  Package,
  Users,
  ShoppingCart,
  FileText,
  BarChart3,
  LogOut,
  ChevronRight,
  Bell,
  CreditCard,
  ShoppingBag,
  Award,
  Receipt,
  TrendingUp,
  DollarSign,
  Copy,
  BarChart2,
  Mail,
} from 'lucide-react';

const nav = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/vendors', label: 'Vendors', icon: Building2 },
  { href: '/products', label: 'Products', icon: Package },
  { href: '/crm', label: 'CRM / Leads', icon: Users },
  { href: '/orders', label: 'Orders', icon: ShoppingCart },
  { href: '/rfq', label: 'RFQ', icon: FileText },
  { href: '/rfq/templates', label: 'RFQ Templates', icon: Copy },
  { href: '/rfq/analytics', label: 'RFQ Analytics', icon: BarChart2 },
  { href: '/rfq/digest', label: 'RFQ Digest', icon: Mail },
  { href: '/cart', label: 'Cart', icon: ShoppingBag },
  { href: '/payments', label: 'Payments', icon: CreditCard },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/price-trends', label: 'Price Trends', icon: TrendingUp },
  { href: '/suppliers', label: 'Suppliers', icon: Award },
  { href: '/cost-optimization', label: 'Cost Optimizer', icon: DollarSign },
  { href: '/invoices', label: 'Invoices', icon: Receipt },
  { href: '/notifications', label: 'Notifications', icon: Bell },
];

export default function Sidebar() {
  const pathname = usePathname();

  function handleLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  }

  return (
    <aside className="flex flex-col w-56 min-h-screen bg-[#121a24] border-r border-[#2a3540]">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-[#2a3540]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-blue-600 flex items-center justify-center text-white text-xs font-bold">PI</div>
          <span className="text-sm font-semibold text-white">Procurement Intel</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                active
                  ? 'bg-blue-600/20 text-blue-400 font-medium'
                  : 'text-[#9aacbc] hover:bg-[#1a232e] hover:text-white'
              )}
            >
              <Icon size={16} />
              {label}
              {active && <ChevronRight size={12} className="ml-auto" />}
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="px-3 py-4 border-t border-[#2a3540]">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-[#9aacbc] hover:bg-[#1a232e] hover:text-red-400 transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
