'use client';

import { useState, useEffect } from 'react';
import { DollarSign, TrendingDown, Plus, RefreshCw, AlertCircle, CheckCircle, Database } from 'lucide-react';

interface Opportunity {
  opportunity_id: number;
  title: string;
  type: string;
  current_cost: number;
  savings: number;
  savings_pct: number;
  status: string;
}

interface DiscountForm {
  vendor_id: string;
  category: string;
  min_quantity: string;
  unit_price: string;
  max_quantity: string;
  notes: string;
}

const CATEGORIES = ['Electronics', 'Manufacturing', 'Raw Materials', 'Logistics', 'Software', 'Services', 'Chemicals', 'Packaging'];

export default function CostOptimizationPage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [vendors, setVendors] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'opportunities' | 'discount-tiers' | 'analyze'>('opportunities');
  const [discountForm, setDiscountForm] = useState<DiscountForm>({
    vendor_id: '', category: 'Electronics', min_quantity: '', unit_price: '', max_quantity: '', notes: '',
  });
  const [analyzeForm, setAnalyzeForm] = useState({ category: 'Electronics', current_spend: '', current_quantity: '' });
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<any>(null);
  const [savingTier, setSavingTier] = useState(false);
  const [tierMsg, setTierMsg] = useState('');
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState('');

  useEffect(() => {
    loadOpportunities();
    fetch('/api/v1/vendors').then((r) => r.json()).then((d) => setVendors(Array.isArray(d) ? d : (d.vendors || []))).catch(() => {});
  }, []);

  async function loadOpportunities() {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/cost-optimization/opportunities?limit=20');
      if (res.ok) {
        const data = await res.json();
        setOpportunities(data.opportunities || []);
      }
    } catch {}
    finally { setLoading(false); }
  }

  async function seedData() {
    setSeeding(true);
    setSeedMsg('');
    try {
      const res = await fetch('/api/v1/cost-optimization/seed', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSeedMsg(`Created ${data.tiers_created} discount tiers and ${data.opportunities_created} opportunities.`);
        await loadOpportunities();
      } else {
        setSeedMsg('Seed failed.');
      }
    } catch {
      setSeedMsg('Error connecting to server.');
    } finally {
      setSeeding(false);
    }
  }

  async function analyzeBulk() {
    if (!analyzeForm.current_spend || !analyzeForm.current_quantity) return;
    setAnalyzing(true);
    setAnalyzeResult(null);
    try {
      const params = new URLSearchParams({
        category: analyzeForm.category,
        current_spend: analyzeForm.current_spend,
        current_quantity: analyzeForm.current_quantity,
      });
      const [bulkRes, altRes] = await Promise.all([
        fetch(`/api/v1/cost-optimization/bulk-discount-opportunity?${params}`, { method: 'POST' }),
        fetch(`/api/v1/cost-optimization/alternative-vendor-opportunity?${new URLSearchParams({ category: analyzeForm.category, current_spend: analyzeForm.current_spend })}`, { method: 'POST' }),
      ]);
      const results: any = {};
      if (bulkRes.ok) results.bulk = await bulkRes.json();
      if (altRes.ok) results.alternative = await altRes.json();
      setAnalyzeResult(results);
      loadOpportunities();
    } catch {}
    finally { setAnalyzing(false); }
  }

  async function addDiscountTier() {
    if (!discountForm.vendor_id || !discountForm.min_quantity || !discountForm.unit_price) return;
    setSavingTier(true);
    setTierMsg('');
    try {
      const params = new URLSearchParams({
        vendor_id: discountForm.vendor_id,
        category: discountForm.category,
        min_quantity: discountForm.min_quantity,
        unit_price: discountForm.unit_price,
        notes: discountForm.notes,
      });
      if (discountForm.max_quantity) params.set('max_quantity', discountForm.max_quantity);
      const res = await fetch(`/api/v1/cost-optimization/discount-tier?${params}`, { method: 'POST' });
      if (res.ok) {
        setTierMsg('Discount tier added!');
        setDiscountForm({ vendor_id: '', category: 'Electronics', min_quantity: '', unit_price: '', max_quantity: '', notes: '' });
      } else {
        setTierMsg('Failed to add tier.');
      }
    } catch { setTierMsg('Error adding tier.'); }
    finally { setSavingTier(false); }
  }

  const statusColor = (s: string) => s === 'implemented' ? 'text-emerald-400' : s === 'approved' ? 'text-blue-400' : s === 'rejected' ? 'text-red-400' : 'text-amber-400';
  const typeLabel = (t: string) => t === 'bulk_discount' ? 'Bulk Discount' : t === 'alternative_vendor' ? 'Alt Vendor' : t === 'consolidation' ? 'Consolidation' : t;
  const typeColor = (t: string) => t === 'bulk_discount' ? 'bg-blue-900/40 text-blue-400' : t === 'alternative_vendor' ? 'bg-purple-900/40 text-purple-400' : 'bg-amber-900/40 text-amber-400';

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <DollarSign size={20} className="text-emerald-400" /> Cost Optimization
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">Bulk discounts, volume pricing tiers, category spend analysis</p>
        </div>
        <button
          onClick={seedData}
          disabled={seeding}
          className="flex items-center gap-2 px-4 py-2 bg-[#1a232e] border border-emerald-600/50 hover:border-emerald-500 text-emerald-400 text-xs rounded transition-colors disabled:opacity-50"
        >
          {seeding ? <RefreshCw size={13} className="animate-spin" /> : <Database size={13} />}
          {seeding ? 'Seeding...' : 'Seed Sample Data'}
        </button>
      </div>

      {seedMsg && (
        <div className={`text-xs px-4 py-2 rounded border ${seedMsg.includes('Created') ? 'bg-emerald-900/20 border-emerald-700/40 text-emerald-400' : 'bg-red-900/20 border-red-700/40 text-red-400'}`}>
          {seedMsg}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[#2a3540]">
        {(['opportunities', 'analyze', 'discount-tiers'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm transition-colors border-b-2 -mb-px ${
              activeTab === tab ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-[#9aacbc] hover:text-white'
            }`}
          >
            {tab === 'opportunities' ? 'Opportunities' : tab === 'analyze' ? 'Analyze Spend' : 'Discount Tiers'}
          </button>
        ))}
      </div>

      {activeTab === 'opportunities' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[#9aacbc]">{opportunities.length} cost-saving opportunities identified</p>
            <button onClick={loadOpportunities} className="text-xs text-[#9aacbc] hover:text-white flex items-center gap-1">
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          {loading ? (
            <div className="text-center py-8 text-[#9aacbc] text-sm">Loading...</div>
          ) : opportunities.length === 0 ? (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-8 text-center">
              <TrendingDown size={32} className="text-[#4a5c6a] mx-auto mb-3" />
              <p className="text-sm text-[#9aacbc] mb-2">No opportunities yet.</p>
              <p className="text-xs text-[#4a5c6a]">Click <strong className="text-emerald-400">Seed Sample Data</strong> above, or use the Analyze tab to find savings.</p>
            </div>
          ) : (
            opportunities.map((opp) => (
              <div key={opp.opportunity_id} className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${typeColor(opp.type)}`}>
                        {typeLabel(opp.type)}
                      </span>
                      <span className={`text-xs font-medium ${statusColor(opp.status)}`}>{opp.status}</span>
                    </div>
                    <h3 className="text-sm font-semibold text-white">{opp.title}</h3>
                    <p className="text-xs text-[#9aacbc] mt-0.5">
                      Current spend: <span className="text-white">${opp.current_cost.toLocaleString()}</span>
                      {' '}→ Save <span className="text-emerald-400 font-bold">${opp.savings.toLocaleString()}</span>
                      {' '}({opp.savings_pct.toFixed(1)}%)
                    </p>
                  </div>
                  <div className="text-right ml-4">
                    <p className="text-lg font-bold text-emerald-400">${opp.savings.toFixed(0)}</p>
                    <p className="text-xs text-[#9aacbc]">savings</p>
                  </div>
                </div>
              </div>
            ))
          )}

          {opportunities.length > 0 && (
            <div className="bg-[#0f1419] rounded-lg p-3 flex items-center justify-between">
              <p className="text-xs text-[#9aacbc]">Total potential savings</p>
              <p className="text-base font-bold text-emerald-400">
                ${opportunities.reduce((s, o) => s + o.savings, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'analyze' && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-5 space-y-4">
            <h3 className="text-sm font-semibold text-white">Analyze Category Spend</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[#9aacbc] mb-1 block">Category</label>
                <select
                  value={analyzeForm.category}
                  onChange={(e) => setAnalyzeForm({ ...analyzeForm, category: e.target.value })}
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                >
                  {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[#9aacbc] mb-1 block">Current Monthly Spend ($)</label>
                <input
                  type="number"
                  value={analyzeForm.current_spend}
                  onChange={(e) => setAnalyzeForm({ ...analyzeForm, current_spend: e.target.value })}
                  placeholder="e.g. 50000"
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-[#9aacbc] mb-1 block">Current Monthly Quantity</label>
                <input
                  type="number"
                  value={analyzeForm.current_quantity}
                  onChange={(e) => setAnalyzeForm({ ...analyzeForm, current_quantity: e.target.value })}
                  placeholder="e.g. 500"
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                />
              </div>
              <button
                onClick={analyzeBulk}
                disabled={analyzing || !analyzeForm.current_spend || !analyzeForm.current_quantity}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-2"
              >
                {analyzing && <RefreshCw size={14} className="animate-spin" />}
                Find Savings Opportunities
              </button>
            </div>
          </div>

          <div className="space-y-4">
            {analyzeResult ? (
              <>
                {analyzeResult.bulk && analyzeResult.bulk.savings && (
                  <div className="bg-[#1a232e] border border-emerald-600/40 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle size={16} className="text-emerald-400" />
                      <h4 className="text-sm font-semibold text-white">Bulk Discount Opportunity</h4>
                    </div>
                    <p className="text-xs text-[#9aacbc]">
                      Order {analyzeResult.bulk.details?.min_quantity} units to save{' '}
                      <span className="text-emerald-400 font-bold">${analyzeResult.bulk.savings?.toFixed(2)}</span>
                    </p>
                  </div>
                )}
                {analyzeResult.alternative && analyzeResult.alternative.savings && (
                  <div className="bg-[#1a232e] border border-blue-600/40 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle size={16} className="text-blue-400" />
                      <h4 className="text-sm font-semibold text-white">Alternative Vendor</h4>
                    </div>
                    <p className="text-xs text-[#9aacbc]">
                      Switch to {analyzeResult.alternative.vendor} and save{' '}
                      <span className="text-blue-400 font-bold">${analyzeResult.alternative.savings?.toFixed(2)}</span>
                    </p>
                  </div>
                )}
                {(!analyzeResult.bulk?.savings && !analyzeResult.alternative?.savings) && (
                  <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4">
                    <div className="flex items-center gap-2">
                      <AlertCircle size={16} className="text-amber-400" />
                      <p className="text-sm text-[#9aacbc]">No significant opportunities found. Add discount tiers first (or use Seed Data).</p>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-6 text-center">
                <DollarSign size={32} className="text-[#4a5c6a] mx-auto mb-2" />
                <p className="text-sm text-[#9aacbc]">Enter spend details to find savings opportunities</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'discount-tiers' && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-5 space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Plus size={14} /> Add Volume Discount Tier
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[#9aacbc] mb-1 block">Vendor</label>
                <select
                  value={discountForm.vendor_id}
                  onChange={(e) => setDiscountForm({ ...discountForm, vendor_id: e.target.value })}
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                >
                  <option value="">Select vendor...</option>
                  {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[#9aacbc] mb-1 block">Category</label>
                <select
                  value={discountForm.category}
                  onChange={(e) => setDiscountForm({ ...discountForm, category: e.target.value })}
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                >
                  {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-[#9aacbc] mb-1 block">Min Quantity</label>
                  <input
                    type="number"
                    value={discountForm.min_quantity}
                    onChange={(e) => setDiscountForm({ ...discountForm, min_quantity: e.target.value })}
                    placeholder="e.g. 100"
                    className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs text-[#9aacbc] mb-1 block">Max Quantity (opt)</label>
                  <input
                    type="number"
                    value={discountForm.max_quantity}
                    onChange={(e) => setDiscountForm({ ...discountForm, max_quantity: e.target.value })}
                    placeholder="e.g. 999"
                    className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-[#9aacbc] mb-1 block">Unit Price at This Tier ($)</label>
                <input
                  type="number"
                  value={discountForm.unit_price}
                  onChange={(e) => setDiscountForm({ ...discountForm, unit_price: e.target.value })}
                  placeholder="e.g. 9.50"
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-[#9aacbc] mb-1 block">Notes</label>
                <input
                  type="text"
                  value={discountForm.notes}
                  onChange={(e) => setDiscountForm({ ...discountForm, notes: e.target.value })}
                  placeholder="Optional notes"
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
                />
              </div>
              <button
                onClick={addDiscountTier}
                disabled={savingTier || !discountForm.vendor_id || !discountForm.min_quantity || !discountForm.unit_price}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-2"
              >
                {savingTier && <RefreshCw size={14} className="animate-spin" />}
                Add Discount Tier
              </button>
              {tierMsg && (
                <p className={`text-xs text-center ${tierMsg.includes('added') ? 'text-emerald-400' : 'text-red-400'}`}>{tierMsg}</p>
              )}
            </div>
          </div>

          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-5">
            <h3 className="text-sm font-semibold text-white mb-3">How Volume Tiers Work</h3>
            <div className="space-y-3 text-xs text-[#9aacbc]">
              <p>Volume discount tiers define lower unit prices at higher quantities. For example:</p>
              <div className="bg-[#0f1419] rounded p-3 space-y-1">
                <div className="flex justify-between text-white">
                  <span>1–99 units</span><span>$12.00 / unit</span>
                </div>
                <div className="flex justify-between text-emerald-400">
                  <span>100–499 units</span><span>$10.50 / unit</span>
                </div>
                <div className="flex justify-between text-blue-400">
                  <span>500+ units</span><span>$9.00 / unit</span>
                </div>
              </div>
              <p>Once tiers are set, use <strong className="text-white">Seed Sample Data</strong> or the Analyze Spend tab to automatically find savings.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
