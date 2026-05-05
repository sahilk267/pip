'use client';

import { useState, useEffect, useCallback } from 'react';
import { TrendingUp, RefreshCw, BarChart3, Database } from 'lucide-react';
import { PriceTrendsChart } from '@/components/PriceTrendsChart';

const COMMON_CATEGORIES = [
  'Electronics', 'Manufacturing', 'Raw Materials', 'Logistics',
  'Software', 'Services', 'Chemicals', 'Packaging', 'uncategorized',
];

export default function PriceTrendsPage() {
  const [selectedCategory, setSelectedCategory] = useState('Electronics');
  const [recording, setRecording] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState('');
  const [vendors, setVendors] = useState<any[]>([]);
  const [chartKey, setChartKey] = useState(0);
  const [form, setForm] = useState({
    vendor_id: '',
    product_name: '',
    unit_price: '',
    category: 'Electronics',
  });
  const [recordMsg, setRecordMsg] = useState('');

  useEffect(() => {
    fetch('/api/v1/vendors')
      .then((r) => r.json())
      .then((d) => setVendors(Array.isArray(d) ? d : (d.vendors || [])))
      .catch(() => {});
  }, []);

  async function seedData() {
    setSeeding(true);
    setSeedMsg('');
    try {
      const res = await fetch('/api/v1/analytics/price-trends/seed', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSeedMsg(`Seeded ${data.records_created} price records across ${data.vendors_used} vendors and ${data.benchmarks_updated?.length ?? 0} categories.`);
        setChartKey((k) => k + 1);
      } else {
        setSeedMsg('Seed failed — check backend logs.');
      }
    } catch {
      setSeedMsg('Error connecting to server.');
    } finally {
      setSeeding(false);
    }
  }

  async function recordPrice() {
    if (!form.vendor_id || !form.product_name || !form.unit_price) return;
    setRecording(true);
    setRecordMsg('');
    try {
      const params = new URLSearchParams({
        vendor_id: form.vendor_id,
        product_name: form.product_name,
        unit_price: form.unit_price,
        category: form.category,
        source: 'manual',
      });
      const res = await fetch(`/api/v1/analytics/price-trends/record?${params}`, { method: 'POST' });
      if (res.ok) {
        setRecordMsg('Price recorded successfully!');
        setSelectedCategory(form.category);
        setChartKey((k) => k + 1);
        setForm({ ...form, product_name: '', unit_price: '' });
      } else {
        setRecordMsg('Failed to record price.');
      }
    } catch {
      setRecordMsg('Error recording price.');
    } finally {
      setRecording(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <TrendingUp size={20} className="text-cyan-400" /> Price Trend Analytics
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">Historical price tracking and supplier benchmarking by category</p>
        </div>
        <button
          onClick={seedData}
          disabled={seeding}
          className="flex items-center gap-2 px-4 py-2 bg-[#1a232e] border border-cyan-600/50 hover:border-cyan-500 text-cyan-400 text-xs rounded transition-colors disabled:opacity-50"
        >
          {seeding ? <RefreshCw size={13} className="animate-spin" /> : <Database size={13} />}
          {seeding ? 'Seeding...' : 'Seed Sample Data'}
        </button>
      </div>

      {seedMsg && (
        <div className={`text-xs px-4 py-2 rounded border ${seedMsg.includes('Seeded') ? 'bg-emerald-900/20 border-emerald-700/40 text-emerald-400' : 'bg-red-900/20 border-red-700/40 text-red-400'}`}>
          {seedMsg}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-5">
          {/* Category selector */}
          <div className="flex flex-wrap gap-2">
            {COMMON_CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  selectedCategory === cat
                    ? 'bg-cyan-600 text-white'
                    : 'bg-[#1a232e] border border-[#2a3540] text-[#9aacbc] hover:border-cyan-600'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <PriceTrendsChart key={chartKey} category={selectedCategory} />
        </div>

        <div className="col-span-1 space-y-4">
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <BarChart3 size={14} className="text-cyan-400" /> Record Price Data
            </h3>
            <select
              value={form.vendor_id}
              onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-xs"
            >
              <option value="">Select vendor...</option>
              {vendors.map((v) => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </select>
            <input
              type="text"
              placeholder="Product name"
              value={form.product_name}
              onChange={(e) => setForm({ ...form, product_name: e.target.value })}
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-xs"
            />
            <input
              type="number"
              placeholder="Unit price (USD)"
              value={form.unit_price}
              onChange={(e) => setForm({ ...form, unit_price: e.target.value })}
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-xs"
            />
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-xs"
            >
              {COMMON_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
            <button
              onClick={recordPrice}
              disabled={recording || !form.vendor_id || !form.product_name || !form.unit_price}
              className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs rounded transition-colors flex items-center justify-center gap-1"
            >
              {recording ? <RefreshCw size={12} className="animate-spin" /> : null}
              Record Price
            </button>
            {recordMsg && (
              <p className={`text-xs text-center ${recordMsg.includes('success') ? 'text-emerald-400' : 'text-red-400'}`}>
                {recordMsg}
              </p>
            )}
          </div>

          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4">
            <h3 className="text-sm font-semibold text-white mb-3">How It Works</h3>
            <div className="space-y-2 text-xs text-[#9aacbc]">
              <p>• Click <strong className="text-cyan-400">Seed Sample Data</strong> to populate historical prices for all vendors</p>
              <p>• Select a category to view its price trends and benchmarks</p>
              <p>• Price benchmarks show min/avg/max across all vendors</p>
              <p>• Record new price data points manually above</p>
              <p>• Prices are auto-recorded when RFQ quotes arrive</p>
              <p>• Trends show if prices are increasing or decreasing</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
