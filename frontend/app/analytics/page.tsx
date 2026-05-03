'use client';

import { useEffect, useState } from 'react';
import { BarChart3, TrendingUp } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line,
} from 'recharts';
import { analyticsApi, leadApi } from '@/lib/api';

interface FunnelStage {
  stage: string;
  count: number;
}

interface OverviewTotals {
  vendors: number;
  products: number;
  leads: number;
  customers: number;
}

export default function AnalyticsPage() {
  const [totals, setTotals] = useState<OverviewTotals | null>(null);
  const [funnel, setFunnel] = useState<FunnelStage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const results = await Promise.allSettled([
        analyticsApi.overview(),
        leadApi.funnel(),
      ]);

      // overview = CrmDashboard: { totals: {vendors, products, leads, customers}, ... }
      if (results[0].status === 'fulfilled') {
        const ov = results[0].value as { totals?: OverviewTotals };
        if (ov?.totals) setTotals(ov.totals);
      }

      // funnel = SalesFunnelMetrics: { stage_counts: {stage: count}, ... }
      if (results[1].status === 'fulfilled') {
        const fn = results[1].value as { stage_counts?: Record<string, number>; total_leads?: number };
        if (fn?.stage_counts) {
          const entries = Object.entries(fn.stage_counts)
            .map(([stage, count]) => ({ stage, count: Number(count) || 0 }));
          setFunnel(entries);
        }
      }

      setLoading(false);
    }
    load();
  }, []);

  const hasData = (totals !== null) || funnel.length > 0;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <BarChart3 size={20} className="text-blue-400" /> Analytics
        </h1>
        <p className="text-sm text-[#9aacbc] mt-0.5">Business intelligence and pipeline insights</p>
      </div>

      {/* Totals */}
      {totals && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {(Object.entries(totals) as [string, number][]).map(([k, v]) => (
            <div key={k} className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-4">
              <p className="text-xs text-[#9aacbc] uppercase tracking-wide mb-1 capitalize">{k.replace('_', ' ')}</p>
              <p className="text-2xl font-bold text-white">{v}</p>
            </div>
          ))}
        </div>
      )}

      {/* Charts */}
      {funnel.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp size={15} className="text-blue-400" />
              <h2 className="text-sm font-semibold text-white">Lead Funnel by Stage</h2>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={funnel} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3540" />
                <XAxis dataKey="stage" tick={{ fill: '#9aacbc', fontSize: 10 }} />
                <YAxis tick={{ fill: '#9aacbc', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#1a232e', border: '1px solid #2a3540', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#e7ecf1' }}
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Pipeline Trend</h2>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={funnel}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3540" />
                <XAxis dataKey="stage" tick={{ fill: '#9aacbc', fontSize: 10 }} />
                <YAxis tick={{ fill: '#9aacbc', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#1a232e', border: '1px solid #2a3540', borderRadius: 8, fontSize: 12 }}
                />
                <Line type="monotone" dataKey="count" stroke="#8b5cf6" strokeWidth={2} dot={{ fill: '#8b5cf6', r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!loading && !hasData && (
        <div className="text-center py-16 text-[#9aacbc] text-sm">
          <BarChart3 size={40} className="mx-auto mb-3 opacity-30" />
          <p className="font-medium text-white">No data yet</p>
          <p className="text-xs mt-1">Add vendors, leads, and orders to see analytics.</p>
        </div>
      )}
    </div>
  );
}
