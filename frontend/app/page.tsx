'use client';

import { useEffect, useState } from 'react';
import { Building2, Package, Users, ShoppingCart, FileText, TrendingUp, AlertCircle } from 'lucide-react';
import StatCard from '@/components/StatCard';
import { vendorApi, productApi, leadApi, orderApi, rfqApi } from '@/lib/api';

interface Stats {
  vendors: number;
  products: number;
  leads: number;
  orders: number;
  rfqs: number;
}

interface FunnelStage {
  stage: string;
  count: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>({ vendors: 0, products: 0, leads: 0, orders: 0, rfqs: 0 });
  const [funnel, setFunnel] = useState<FunnelStage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [vendors, products, leads, orders, rfqs, funnelData] = await Promise.allSettled([
          vendorApi.list({ limit: 100 }),
          productApi.list({ limit: 100 }),
          leadApi.list({ limit: 100 }),
          orderApi.list({ limit: 100 }),
          rfqApi.list({ limit: 100 }),
          leadApi.funnel(),
        ]);

        const getVal = <T,>(r: PromiseSettledResult<T>): T | null =>
          r.status === 'fulfilled' ? r.value : null;

        const v = getVal(vendors);
        const p = getVal(products);
        const l = getVal(leads);
        const o = getVal(orders);
        const r = getVal(rfqs);
        const fn = getVal(funnelData);

        setStats({
          vendors: Array.isArray(v) ? v.length : 0,
          products: Array.isArray(p) ? p.length : 0,
          leads: Array.isArray(l) ? l.length : 0,
          orders: Array.isArray(o) ? o.length : 0,
          rfqs: Array.isArray(r) ? r.length : 0,
        });

        // SalesFunnelMetrics has stage_counts: dict[str, int]
        if (fn && typeof fn === 'object' && !Array.isArray(fn)) {
          const fc = fn as { stage_counts?: Record<string, number>; total_leads?: number };
          if (fc.stage_counts) {
            const entries = Object.entries(fc.stage_counts).map(([stage, count]) => ({
              stage,
              count: typeof count === 'number' ? count : 0,
            }));
            setFunnel(entries.filter((e) => e.count > 0));
          }
        }
      } catch {
        setError('Could not load dashboard data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-[#9aacbc] mt-0.5">Procurement Intelligence — at a glance</p>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-900/20 border border-red-700/30 rounded-lg px-4 py-3 text-sm text-red-400">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        <StatCard title="Vendors" value={loading ? '—' : stats.vendors} icon={Building2} color="blue" trend="up" trendLabel="active" />
        <StatCard title="Products" value={loading ? '—' : stats.products} icon={Package} color="green" />
        <StatCard title="Leads" value={loading ? '—' : stats.leads} icon={Users} color="purple" />
        <StatCard title="Orders" value={loading ? '—' : stats.orders} icon={ShoppingCart} color="amber" />
        <StatCard title="RFQs" value={loading ? '—' : stats.rfqs} icon={FileText} color="blue" />
      </div>

      {/* CRM Funnel */}
      {funnel.length > 0 && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={16} className="text-blue-400" />
            <h2 className="text-sm font-semibold text-white">Lead Funnel</h2>
          </div>
          <div className="space-y-2">
            {funnel.slice(0, 8).map(({ stage, count }) => {
              const max = Math.max(...funnel.map((f) => f.count), 1);
              const pct = Math.round((count / max) * 100);
              return (
                <div key={stage} className="flex items-center gap-3">
                  <span className="text-xs text-[#9aacbc] w-28 capitalize">{stage.replace('_', ' ')}</span>
                  <div className="flex-1 bg-[#0f1419] rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-white w-8 text-right">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Quick Links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'View Vendors', href: '/vendors', color: 'bg-blue-600/10 border-blue-600/20 text-blue-400' },
          { label: 'Manage Leads', href: '/crm', color: 'bg-purple-600/10 border-purple-600/20 text-purple-400' },
          { label: 'Track Orders', href: '/orders', color: 'bg-amber-600/10 border-amber-600/20 text-amber-400' },
          { label: 'Create RFQ', href: '/rfq', color: 'bg-emerald-600/10 border-emerald-600/20 text-emerald-400' },
        ].map(({ label, href, color }) => (
          <a
            key={href}
            href={href}
            className={`rounded-lg border px-4 py-3 text-sm font-medium text-center transition-opacity hover:opacity-80 ${color}`}
          >
            {label}
          </a>
        ))}
      </div>
    </div>
  );
}
