'use client';

import { useEffect, useState, useCallback } from 'react';
import { TrendingDown, RotateCw, Activity, Zap } from 'lucide-react';
import { rfqApi } from '@/lib/api';

interface Quote {
  id: number;
  vendor_id: number;
  vendor_name: string;
  unit_price?: number;
  lead_time_days?: number;
  confidence: number;
  response_speed_hours?: number;
  responded_at?: string;
  created_at?: string;
}

interface QuoteUpdate {
  vendor: string;
  oldPrice: number;
  newPrice: number;
  timestamp: string;
  trend: 'down' | 'up' | 'stable';
}

export function QuoteDashboard({ broadcastId, currency = 'USD' }: { broadcastId: number; currency?: string }) {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [updates, setUpdates] = useState<QuoteUpdate[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<string>(new Date().toLocaleTimeString());

  const loadQuotes = useCallback(async () => {
    setLoading(true);
    try {
      const data = await rfqApi.quotesComparison(broadcastId);
      const newQuotes = data.quotes || [];

      // Detect price changes for timeline
      if (quotes.length > 0) {
        const timelineUpdates: QuoteUpdate[] = [];
        newQuotes.forEach((q) => {
          const prev = quotes.find((pq) => pq.vendor_id === q.vendor_id);
          if (prev && prev.unit_price && q.unit_price && prev.unit_price !== q.unit_price) {
            timelineUpdates.push({
              vendor: q.vendor_name,
              oldPrice: prev.unit_price,
              newPrice: q.unit_price,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              trend: q.unit_price < prev.unit_price ? 'down' : 'up',
            });
          }
        });
        if (timelineUpdates.length > 0) {
          setUpdates((prev) => [...timelineUpdates, ...prev].slice(0, 10));
        }
      }

      setQuotes(newQuotes);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch {
      /* no-op */
    } finally {
      setLoading(false);
    }
  }, [broadcastId, quotes]);

  useEffect(() => {
    const interval = autoRefresh ? setInterval(loadQuotes, 5000) : null;
    return () => interval && clearInterval(interval);
  }, [autoRefresh, loadQuotes]);

  if (quotes.length === 0) return null;

  const bestPrice = Math.min(...quotes.filter((q) => q.unit_price).map((q) => q.unit_price || Infinity));
  const avgPrice = quotes.filter((q) => q.unit_price).reduce((s, q) => s + (q.unit_price || 0), 0) / quotes.filter((q) => q.unit_price).length;
  const minLeadTime = Math.min(...quotes.filter((q) => q.lead_time_days).map((q) => q.lead_time_days || Infinity));

  return (
    <div className="space-y-4 mt-6">
      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
          <p className="text-xs text-[#9aacbc] mb-1">Best Price</p>
          <p className="text-lg font-bold text-emerald-400">{currency} {bestPrice.toFixed(2)}</p>
        </div>
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
          <p className="text-xs text-[#9aacbc] mb-1">Avg Price</p>
          <p className="text-lg font-bold text-blue-400">{currency} {avgPrice.toFixed(2)}</p>
        </div>
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
          <p className="text-xs text-[#9aacbc] mb-1">Fastest Delivery</p>
          <p className="text-lg font-bold text-purple-400">{minLeadTime} days</p>
        </div>
      </div>

      {/* Live Updates Timeline */}
      {updates.length > 0 && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity size={14} className="text-amber-400" /> Live Price Updates
            </h3>
            <span className="text-xs text-[#9aacbc]">{updates.length} changes</span>
          </div>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {updates.map((u, i) => (
              <div key={i} className="flex items-center justify-between text-xs p-2 bg-[#0f1419] rounded border border-[#2a3540]/50">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <TrendingDown size={12} className={u.trend === 'down' ? 'text-emerald-400' : 'text-red-400'} />
                  <span className="text-white truncate">{u.vendor}</span>
                </div>
                <div className="flex items-center gap-2 ml-2">
                  <span className="text-[#9aacbc] line-through">{currency} {u.oldPrice.toFixed(2)}</span>
                  <span className={u.trend === 'down' ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
                    {currency} {u.newPrice.toFixed(2)}
                  </span>
                  <span className="text-[#4a5c6a] text-[10px]">{u.timestamp}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Refresh Control */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <Zap size={12} className={autoRefresh ? 'text-blue-400 animate-pulse' : 'text-[#4a5c6a]'} />
          <span className="text-[#9aacbc]">
            {autoRefresh ? 'Auto-updating' : 'Paused'} • Last: {lastRefresh}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadQuotes}
            disabled={loading}
            className="px-2 py-1 bg-[#1a232e] border border-[#2a3540] rounded hover:bg-[#2a3540] text-[#9aacbc] hover:text-white transition-colors disabled:opacity-50 flex items-center gap-1"
          >
            <RotateCw size={10} /> Refresh
          </button>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-2 py-1 rounded transition-colors text-xs ${
              autoRefresh ? 'bg-blue-600/30 text-blue-400 border border-blue-600/50' : 'bg-[#1a232e] border border-[#2a3540] text-[#9aacbc]'
            }`}
          >
            {autoRefresh ? 'Auto On' : 'Auto Off'}
          </button>
        </div>
      </div>
    </div>
  );
}
