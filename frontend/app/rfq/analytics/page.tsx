'use client';

import { useState, useEffect, useCallback } from 'react';
import { BarChart2, TrendingUp, Users, RefreshCw, Database, Award, Clock, DollarSign, Zap, CheckCircle } from 'lucide-react';

interface KPIs {
  total_broadcasts: number;
  total_vendors_reached: number;
  total_responses: number;
  total_quotes: number;
  avg_response_rate_pct: number;
  avg_quote_price_usd: number | null;
  avg_lead_time_days: number | null;
  top_winning_vendor: string | null;
}

interface BroadcastStat {
  broadcast_id: number;
  message: string;
  status: string;
  channel: string;
  created_at: string;
  vendor_count: number;
  response_count: number;
  response_rate: number;
  avg_unit_price: number | null;
  best_unit_price: number | null;
  avg_lead_time_days: number | null;
  winning_vendor: string | null;
  quote_count: number;
}

interface VendorWinRate {
  vendor_id: number;
  vendor_name: string;
  category: string;
  attempts: number;
  responses: number;
  response_rate: number;
  quote_count: number;
  wins: number;
  win_rate: number;
  avg_quote_price: number | null;
}

interface CategoryBreakdown {
  category: string;
  attempts: number;
  responses: number;
  response_rate: number;
}

interface AnalyticsData {
  window_days: number;
  kpis: KPIs;
  broadcasts: BroadcastStat[];
  vendor_win_rates: VendorWinRate[];
  category_breakdown: CategoryBreakdown[];
}

const WINDOW_OPTIONS = [
  { label: '30 days', value: 30 },
  { label: '60 days', value: 60 },
  { label: '90 days', value: 90 },
  { label: '180 days', value: 180 },
];

function fmt(n: number | null, prefix = '$') {
  if (n === null || n === undefined) return '—';
  return `${prefix}${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function RateBar({ pct, color = 'bg-cyan-500' }: { pct: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-[#0f1419] rounded-full h-2">
        <div
          className={`h-2 rounded-full ${color} transition-all`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-[#9aacbc] w-10 text-right">{pct}%</span>
    </div>
  );
}

export default function RFQAnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState('');
  const [window, setWindow] = useState(90);
  const [activeTab, setActiveTab] = useState<'broadcasts' | 'vendors' | 'categories'>('broadcasts');

  const load = useCallback(async (w: number) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/rfq/analytics?window_days=${w}`);
      if (res.ok) setData(await res.json());
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(window); }, [load, window]);

  async function seed() {
    setSeeding(true);
    setSeedMsg('');
    try {
      const res = await fetch('/api/v1/seed-all', { method: 'POST' });
      if (res.ok) {
        const d = await res.json();
        const n = d.rfq_broadcasts?.created ?? 0;
        setSeedMsg(n > 0 ? `${n} RFQ broadcasts seeded!` : 'Data already seeded.');
        await load(window);
      }
    } catch { setSeedMsg('Seed failed.'); }
    finally { setSeeding(false); }
  }

  const kpi = data?.kpis;

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart2 size={20} className="text-cyan-400" /> RFQ Analytics
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">
            Response rates, quote prices &amp; vendor win rates per broadcast
          </p>
        </div>
        <div className="flex items-center gap-2">
          {seedMsg && <span className="text-xs text-emerald-400">{seedMsg}</span>}
          <button
            onClick={seed}
            disabled={seeding}
            className="px-3 py-2 bg-[#1a232e] border border-[#2a3540] hover:border-cyan-500 text-[#9aacbc] hover:text-white text-sm rounded flex items-center gap-1 transition-colors disabled:opacity-50"
          >
            {seeding ? <RefreshCw size={13} className="animate-spin" /> : <Database size={13} />}
            Seed RFQ Data
          </button>
          <div className="flex bg-[#1a232e] border border-[#2a3540] rounded overflow-hidden">
            {WINDOW_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setWindow(opt.value)}
                className={`px-3 py-2 text-xs transition-colors ${
                  window === opt.value
                    ? 'bg-cyan-600 text-white'
                    : 'text-[#9aacbc] hover:text-white'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => load(window)}
            className="p-2 text-[#9aacbc] hover:text-white transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          {
            label: 'Total Broadcasts',
            value: kpi?.total_broadcasts ?? '—',
            icon: <Zap size={16} className="text-cyan-400" />,
            sub: `${kpi?.total_vendors_reached ?? 0} vendors reached`,
          },
          {
            label: 'Avg Response Rate',
            value: kpi ? `${kpi.avg_response_rate_pct}%` : '—',
            icon: <CheckCircle size={16} className="text-emerald-400" />,
            sub: `${kpi?.total_responses ?? 0} of ${kpi?.total_vendors_reached ?? 0} responded`,
          },
          {
            label: 'Avg Quote Price',
            value: fmt(kpi?.avg_quote_price_usd ?? null),
            icon: <DollarSign size={16} className="text-amber-400" />,
            sub: `${kpi?.total_quotes ?? 0} quotes received`,
          },
          {
            label: 'Avg Lead Time',
            value: kpi?.avg_lead_time_days ? `${kpi.avg_lead_time_days} days` : '—',
            icon: <Clock size={16} className="text-violet-400" />,
            sub: kpi?.top_winning_vendor ? `Top winner: ${kpi.top_winning_vendor}` : 'No winner yet',
          },
        ].map((card) => (
          <div key={card.label} className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[#9aacbc] uppercase tracking-wider">{card.label}</span>
              {card.icon}
            </div>
            <div className="text-2xl font-bold text-white">
              {loading ? <span className="text-[#2a3540]">···</span> : card.value}
            </div>
            <div className="text-xs text-[#4a5c6a] mt-1">{card.sub}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#2a3540]">
        {(['broadcasts', 'vendors', 'categories'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm capitalize transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-cyan-500 text-white'
                : 'border-transparent text-[#9aacbc] hover:text-white'
            }`}
          >
            {tab === 'broadcasts' ? 'Per-Broadcast' : tab === 'vendors' ? 'Vendor Win Rates' : 'By Category'}
          </button>
        ))}
      </div>

      {/* Tab: Per-Broadcast */}
      {activeTab === 'broadcasts' && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg overflow-hidden">
          {loading ? (
            <div className="text-center py-12 text-[#9aacbc] text-sm">Loading…</div>
          ) : !data || data.broadcasts.length === 0 ? (
            <div className="text-center py-12">
              <BarChart2 size={32} className="text-[#2a3540] mx-auto mb-3" />
              <p className="text-[#9aacbc] text-sm">No broadcast data yet.</p>
              <p className="text-[#4a5c6a] text-xs mt-1">Click <strong>Seed RFQ Data</strong> to populate sample broadcasts.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#2a3540] text-[10px] text-[#4a5c6a] uppercase tracking-wider">
                  <th className="text-left p-4">Broadcast / RFQ</th>
                  <th className="text-center p-4 w-28">Vendors</th>
                  <th className="p-4 w-52">Response Rate</th>
                  <th className="text-right p-4 w-28">Best Price</th>
                  <th className="text-right p-4 w-24">Lead Time</th>
                  <th className="text-left p-4 w-44">Winning Vendor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2a34]">
                {data.broadcasts.map((bc) => (
                  <tr key={bc.broadcast_id} className="hover:bg-[#1e2a34] transition-colors">
                    <td className="p-4">
                      <p className="text-sm font-medium text-white truncate max-w-xs">{bc.message}</p>
                      <p className="text-xs text-[#4a5c6a] mt-0.5">
                        #{bc.broadcast_id} · {bc.created_at ? new Date(bc.created_at).toLocaleDateString() : '—'}
                      </p>
                    </td>
                    <td className="p-4 text-center">
                      <span className="text-sm text-white">{bc.vendor_count}</span>
                      <span className="text-xs text-[#4a5c6a] ml-1">sent</span>
                    </td>
                    <td className="p-4">
                      <RateBar
                        pct={bc.response_rate}
                        color={bc.response_rate >= 70 ? 'bg-emerald-500' : bc.response_rate >= 40 ? 'bg-amber-500' : 'bg-rose-500'}
                      />
                      <p className="text-xs text-[#4a5c6a] mt-1">
                        {bc.response_count}/{bc.vendor_count} vendors
                      </p>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-sm font-semibold text-emerald-400">
                        {bc.best_unit_price !== null ? `$${bc.best_unit_price.toLocaleString()}` : '—'}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-sm text-[#9aacbc]">
                        {bc.avg_lead_time_days !== null ? `${bc.avg_lead_time_days}d` : '—'}
                      </span>
                    </td>
                    <td className="p-4">
                      {bc.winning_vendor ? (
                        <span className="flex items-center gap-1 text-xs text-amber-400">
                          <Award size={12} /> {bc.winning_vendor}
                        </span>
                      ) : (
                        <span className="text-xs text-[#4a5c6a]">No quotes</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab: Vendor Win Rates */}
      {activeTab === 'vendors' && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg overflow-hidden">
          {loading ? (
            <div className="text-center py-12 text-[#9aacbc] text-sm">Loading…</div>
          ) : !data || data.vendor_win_rates.length === 0 ? (
            <div className="text-center py-12">
              <Users size={32} className="text-[#2a3540] mx-auto mb-3" />
              <p className="text-[#9aacbc] text-sm">No vendor data yet. Seed RFQ data first.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#2a3540] text-[10px] text-[#4a5c6a] uppercase tracking-wider">
                  <th className="text-left p-4">Vendor</th>
                  <th className="text-left p-4">Category</th>
                  <th className="p-4 w-44">Response Rate</th>
                  <th className="text-center p-4 w-20">Wins</th>
                  <th className="p-4 w-44">Win Rate</th>
                  <th className="text-right p-4 w-32">Avg Quote</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2a34]">
                {data.vendor_win_rates.map((v, i) => (
                  <tr key={v.vendor_id} className="hover:bg-[#1e2a34] transition-colors">
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        {i < 3 && (
                          <span className={`text-xs font-bold ${i === 0 ? 'text-amber-400' : i === 1 ? 'text-slate-300' : 'text-amber-700'}`}>
                            #{i + 1}
                          </span>
                        )}
                        <span className="text-sm font-medium text-white">{v.vendor_name}</span>
                      </div>
                    </td>
                    <td className="p-4">
                      <span className="text-xs text-[#9aacbc]">{v.category}</span>
                    </td>
                    <td className="p-4">
                      <RateBar
                        pct={v.response_rate}
                        color={v.response_rate >= 70 ? 'bg-emerald-500' : v.response_rate >= 40 ? 'bg-amber-500' : 'bg-rose-500'}
                      />
                    </td>
                    <td className="p-4 text-center">
                      <span className="text-sm font-bold text-amber-400">{v.wins}</span>
                      <span className="text-xs text-[#4a5c6a] ml-1">/ {v.quote_count}</span>
                    </td>
                    <td className="p-4">
                      <RateBar pct={v.win_rate} color="bg-amber-500" />
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-sm text-[#9aacbc]">
                        {v.avg_quote_price !== null ? `$${v.avg_quote_price.toLocaleString()}` : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab: Category Breakdown */}
      {activeTab === 'categories' && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-5">
          {loading ? (
            <div className="text-center py-12 text-[#9aacbc] text-sm">Loading…</div>
          ) : !data || data.category_breakdown.length === 0 ? (
            <div className="text-center py-12">
              <TrendingUp size={32} className="text-[#2a3540] mx-auto mb-3" />
              <p className="text-[#9aacbc] text-sm">No category data yet. Seed RFQ data first.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-white mb-4">Response Rate by Vendor Category</h3>
              {data.category_breakdown.map((cat) => (
                <div key={cat.category} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-white font-medium">{cat.category}</span>
                    <span className="text-[#4a5c6a]">
                      {cat.responses}/{cat.attempts} vendors responded
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 bg-[#0f1419] rounded-full h-3">
                      <div
                        className={`h-3 rounded-full transition-all ${
                          cat.response_rate >= 70 ? 'bg-emerald-500' : cat.response_rate >= 40 ? 'bg-amber-500' : 'bg-rose-500'
                        }`}
                        style={{ width: `${Math.min(cat.response_rate, 100)}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-white w-12 text-right">{cat.response_rate}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
