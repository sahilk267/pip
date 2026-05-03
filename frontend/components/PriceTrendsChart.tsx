'use client';

import { useState, useEffect } from 'react';
import { TrendingDown, TrendingUp, BarChart3 } from 'lucide-react';

interface PricePoint {
  vendor_id: number;
  product: string;
  price: number;
  date: string;
}

export function PriceTrendsChart({ category }: { category: string }) {
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [benchmark, setBenchmark] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [priceRes, benchRes] = await Promise.all([
          fetch(`/api/v1/analytics/price-trends/${category}?days=90`),
          fetch(`/api/v1/analytics/price-trends/benchmark/${category}`),
        ]);
        if (priceRes.ok) {
          const data = await priceRes.json();
          setPrices(data.records || []);
        }
        if (benchRes.ok) {
          const data = await benchRes.json();
          setBenchmark(data);
        }
      } catch {}
      finally {
        setLoading(false);
      }
    }
    loadData();
  }, [category]);

  if (loading)
    return (
      <div className="text-sm text-[#9aacbc] text-center py-8">Loading price trends...</div>
    );

  return (
    <div className="space-y-4">
      {benchmark && (
        <div className="grid grid-cols-4 gap-2">
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
            <p className="text-xs text-[#9aacbc]">Min Price</p>
            <p className="text-lg font-bold text-emerald-400">${benchmark.min_price?.toFixed(2)}</p>
          </div>
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
            <p className="text-xs text-[#9aacbc]">Avg Price</p>
            <p className="text-lg font-bold text-blue-400">${benchmark.avg_price?.toFixed(2)}</p>
          </div>
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
            <p className="text-xs text-[#9aacbc]">Max Price</p>
            <p className="text-lg font-bold text-red-400">${benchmark.max_price?.toFixed(2)}</p>
          </div>
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
            <p className="text-xs text-[#9aacbc]">Sample Size</p>
            <p className="text-lg font-bold text-[#9aacbc]">{benchmark.sample_count}</p>
          </div>
        </div>
      )}

      <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <BarChart3 size={14} /> Price History (Last 90 Days)
        </h3>
        {prices.length === 0 ? (
          <p className="text-xs text-[#9aacbc]">No price data available</p>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {prices.slice(0, 20).map((p, i) => (
              <div key={i} className="flex items-center justify-between text-xs p-2 bg-[#0f1419] rounded">
                <span className="text-[#9aacbc] truncate flex-1">{p.product}</span>
                <span className="text-white font-semibold ml-2">${p.price.toFixed(2)}</span>
                <span className="text-[#4a5c6a] ml-2 text-[10px]">{new Date(p.date).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
