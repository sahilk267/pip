'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  FileText, Plus, Clock, CheckCircle, Search, Star,
  ChevronRight, ChevronLeft, Zap, Building2, TrendingUp,
  BarChart2, Users, AlertCircle, X, DollarSign, Truck, Zap as Speed,
} from 'lucide-react';
import { rfqApi } from '@/lib/api';

// ── Types ────────────────────────────────────────────────────────────────────

interface RFQ {
  id: number;
  channel: string;
  status: string;
  message?: string;
  performed_by: string;
  created_at: string;
  updated_at: string;
}

interface VendorMatch {
  vendor_id: number;
  name: string;
  email?: string;
  industry?: string;
  category: string;
  score: number;
  confidence: 'excellent' | 'good' | 'fair' | 'low';
  score_breakdown: { category_fit: number; name_relevance: number; quote_history: number };
  quote_stats: {
    total_rfqs: number;
    total_responses: number;
    response_rate: number | null;
    avg_quoted_price: number | null;
    quote_count: number;
  };
}

interface Quote {
  id: number;
  vendor_id: number;
  vendor_name: string;
  unit_price?: number;
  total_price?: number;
  quantity?: number;
  lead_time_days?: number;
  currency: string;
  confidence: number;
  response_speed_hours?: number;
  responded_at?: string;
  created_at?: string;
}

interface QuoteComparison {
  broadcast_id: number;
  total_quotes: number;
  currency: string;
  quotes: Quote[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const statusColor: Record<string, string> = {
  pending:        'bg-amber-600/20 text-amber-400',
  in_progress:    'bg-blue-600/20 text-blue-400',
  completed:      'bg-emerald-600/20 text-emerald-400',
  failed:         'bg-red-600/20 text-red-400',
  partial_failed: 'bg-orange-600/20 text-orange-400',
};

const confidenceColor: Record<string, string> = {
  excellent: 'text-emerald-400',
  good:      'text-blue-400',
  fair:      'text-amber-400',
  low:       'text-[#9aacbc]',
};

const confidenceBg: Record<string, string> = {
  excellent: 'bg-emerald-600/20 text-emerald-400',
  good:      'bg-blue-600/20 text-blue-400',
  fair:      'bg-amber-600/20 text-amber-400',
  low:       'bg-[#2a3540] text-[#9aacbc]',
};

function ScoreBar({ value, max = 50, color = 'bg-blue-500' }: { value: number; max?: number; color?: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="h-1 bg-[#2a3540] rounded-full overflow-hidden w-full">
      <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function ConfidenceStars({ confidence }: { confidence: string }) {
  const levels: Record<string, number> = { excellent: 4, good: 3, fair: 2, low: 1 };
  const count = levels[confidence] ?? 1;
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4].map((i) => (
        <Star
          key={i}
          size={10}
          className={i <= count ? confidenceColor[confidence] : 'text-[#2a3540]'}
          fill={i <= count ? 'currentColor' : 'none'}
        />
      ))}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

type Step = 'list' | 'details' | 'match' | 'confirm' | 'quotes';

const INIT_FORM = {
  product_name: '', quantity: '1', currency: 'USD',
  target_price: '', delivery_deadline: '', notes: '',
};

export default function RFQPage() {
  const [rfqs, setRfqs]           = useState<RFQ[]>([]);
  const [loading, setLoading]     = useState(true);
  const [step, setStep]           = useState<Step>('list');
  const [form, setForm]           = useState(INIT_FORM);
  const [matches, setMatches]     = useState<VendorMatch[]>([]);
  const [selected, setSelected]   = useState<Set<number>>(new Set());
  const [matching, setMatching]   = useState(false);
  const [saving, setSaving]       = useState(false);
  const [matchErr, setMatchErr]   = useState('');
  const [saveErr, setSaveErr]     = useState('');
  const [selectedRfq, setSelectedRfq] = useState<RFQ | null>(null);
  const [comparison, setComparison] = useState<QuoteComparison | null>(null);
  const [loadingQuotes, setLoadingQuotes] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await rfqApi.list({ limit: 100 });
      setRfqs(Array.isArray(data) ? data : data.items ?? []);
    } catch { /* no-op */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  function resetFlow() {
    setStep('list');
    setForm(INIT_FORM);
    setMatches([]);
    setSelected(new Set());
    setMatchErr('');
    setSaveErr('');
    setSelectedRfq(null);
    setComparison(null);
  }

  async function viewQuotes(rfq: RFQ) {
    setSelectedRfq(rfq);
    setLoadingQuotes(true);
    try {
      const data = await rfqApi.quotesComparison(rfq.id);
      setComparison(data);
      setStep('quotes');
    } catch {
      setComparison(null);
    } finally {
      setLoadingQuotes(false);
    }
  }

  const f = (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((p) => ({ ...p, [k]: e.target.value }));

  // Step 1 → Step 2: fetch vendor matches
  async function findVendors() {
    setMatching(true);
    setMatchErr('');
    try {
      const data = await rfqApi.vendorSuggestions({
        product_name: form.product_name,
        target_price: form.target_price ? parseFloat(form.target_price) : undefined,
        limit: 20,
      });
      const list: VendorMatch[] = Array.isArray(data) ? data : [];
      setMatches(list);
      // pre-select all "good" or "excellent" vendors
      setSelected(new Set(list.filter((m) => m.confidence !== 'low').map((m) => m.vendor_id)));
      setStep('match');
    } catch {
      setMatchErr('Could not fetch vendor suggestions. Please try again.');
    } finally {
      setMatching(false);
    }
  }

  function toggleVendor(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  // Step 2 → broadcast
  async function broadcast() {
    setSaving(true);
    setSaveErr('');
    try {
      const vendorIds = Array.from(selected);
      await rfqApi.create({
        vendor_ids: vendorIds,
        channel: 'email',
        message: [
          `Product: ${form.product_name}`,
          `Quantity: ${form.quantity}`,
          form.target_price ? `Target Price: ${form.currency} ${form.target_price}` : '',
          form.delivery_deadline ? `Delivery by: ${form.delivery_deadline}` : '',
          form.notes ? `Notes: ${form.notes}` : '',
          'Please share your best quote and delivery timeline.',
        ].filter(Boolean).join('\n'),
        auto_match_limit: vendorIds.length === 0 ? 5 : 0,
        performed_by: 'sales',
      });
      await load();
      resetFlow();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Broadcast failed. Please try again.';
      setSaveErr(msg);
    } finally {
      setSaving(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="p-6 space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText size={20} className="text-blue-400" /> RFQ Broadcasts
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">{rfqs.length} RFQ{rfqs.length !== 1 ? 's' : ''}</p>
        </div>
        {step === 'list' && (
          <button
            onClick={() => setStep('details')}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            <Plus size={14} /> Create RFQ
          </button>
        )}
        {step !== 'list' && (
          <button onClick={resetFlow} className="flex items-center gap-1.5 text-sm text-[#9aacbc] hover:text-white transition-colors">
            <X size={14} /> Cancel
          </button>
        )}
      </div>

      {/* ── STEP 1: Product Details ─────────────────────────────────────────── */}
      {step === 'details' && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-6 space-y-5">
          {/* Progress */}
          <div className="flex items-center gap-2 text-xs mb-2">
            <span className="px-2.5 py-1 rounded-full bg-blue-600 text-white font-semibold">1</span>
            <span className="text-white font-medium">Product Details</span>
            <ChevronRight size={14} className="text-[#2a3540]" />
            <span className="px-2.5 py-1 rounded-full bg-[#2a3540] text-[#9aacbc] font-semibold">2</span>
            <span className="text-[#9aacbc]">Match Vendors</span>
            <ChevronRight size={14} className="text-[#2a3540]" />
            <span className="px-2.5 py-1 rounded-full bg-[#2a3540] text-[#9aacbc] font-semibold">3</span>
            <span className="text-[#9aacbc]">Broadcast</span>
          </div>

          <h3 className="text-sm font-semibold text-white border-b border-[#2a3540] pb-3">
            What are you sourcing?
          </h3>

          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-[#9aacbc] mb-1.5">Product / Item Name *</label>
              <input
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 placeholder-[#4a5c6a]"
                placeholder="e.g. Industrial Cooling Units, Electronic Sensors, Steel Pipes…"
                value={form.product_name}
                onChange={f('product_name')}
                required
              />
            </div>

            <div>
              <label className="block text-xs text-[#9aacbc] mb-1.5">Quantity *</label>
              <input
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                type="number" min="1"
                value={form.quantity}
                onChange={f('quantity')}
              />
            </div>

            <div>
              <label className="block text-xs text-[#9aacbc] mb-1.5">Currency</label>
              <select
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                value={form.currency}
                onChange={f('currency')}
              >
                {['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'INR', 'AUD', 'CAD'].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-[#9aacbc] mb-1.5">Target Unit Price</label>
              <input
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 placeholder-[#4a5c6a]"
                placeholder="0.00 (optional — used for scoring)"
                type="number" min="0" step="0.01"
                value={form.target_price}
                onChange={f('target_price')}
              />
            </div>

            <div>
              <label className="block text-xs text-[#9aacbc] mb-1.5">Delivery Deadline</label>
              <input
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                type="date"
                value={form.delivery_deadline}
                onChange={f('delivery_deadline')}
              />
            </div>

            <div className="col-span-2">
              <label className="block text-xs text-[#9aacbc] mb-1.5">Additional Notes</label>
              <textarea
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 resize-none placeholder-[#4a5c6a]"
                rows={2}
                placeholder="Specs, certifications, packaging requirements…"
                value={form.notes}
                onChange={f('notes')}
              />
            </div>
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={findVendors}
              disabled={!form.product_name.trim() || matching}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
            >
              {matching ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Matching vendors…
                </>
              ) : (
                <>
                  <Search size={14} /> Find Matching Vendors
                  <ChevronRight size={14} />
                </>
              )}
            </button>
          </div>
          {matchErr && (
            <p className="text-xs text-red-400 flex items-center gap-1.5 mt-1">
              <AlertCircle size={12} /> {matchErr}
            </p>
          )}
        </div>
      )}

      {/* ── STEP 2: Vendor Matching Results ────────────────────────────────── */}
      {step === 'match' && (
        <div className="space-y-4">
          {/* Progress */}
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-4">
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2.5 py-1 rounded-full bg-emerald-600/30 text-emerald-400 font-semibold">✓</span>
              <span className="text-[#9aacbc]">Product Details</span>
              <ChevronRight size={14} className="text-[#2a3540]" />
              <span className="px-2.5 py-1 rounded-full bg-blue-600 text-white font-semibold">2</span>
              <span className="text-white font-medium">Match Vendors</span>
              <ChevronRight size={14} className="text-[#2a3540]" />
              <span className="px-2.5 py-1 rounded-full bg-[#2a3540] text-[#9aacbc] font-semibold">3</span>
              <span className="text-[#9aacbc]">Broadcast</span>
            </div>

            {/* Summary row */}
            <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-[#9aacbc]">
              <span className="flex items-center gap-1.5">
                <FileText size={11} />
                <span className="text-white font-medium">{form.product_name}</span>
              </span>
              <span>Qty: <span className="text-white">{form.quantity}</span></span>
              {form.target_price && (
                <span>Target: <span className="text-white">{form.currency} {form.target_price}</span></span>
              )}
              <button
                onClick={() => setStep('details')}
                className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors"
              >
                <ChevronLeft size={11} /> Edit
              </button>
            </div>
          </div>

          {/* Match header */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Zap size={14} className="text-amber-400" />
                {matches.length} Vendor{matches.length !== 1 ? 's' : ''} Ranked
              </h3>
              <p className="text-xs text-[#9aacbc] mt-0.5">
                Select vendors to include in this broadcast
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs text-[#9aacbc]">
              <button
                onClick={() => setSelected(new Set(matches.map((m) => m.vendor_id)))}
                className="hover:text-white transition-colors"
              >
                Select all
              </button>
              <span className="text-[#2a3540]">|</span>
              <button
                onClick={() => setSelected(new Set())}
                className="hover:text-white transition-colors"
              >
                Clear
              </button>
            </div>
          </div>

          {/* No vendors */}
          {matches.length === 0 && (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-8 text-center">
              <Building2 size={32} className="text-[#2a3540] mx-auto mb-3" />
              <p className="text-sm text-[#9aacbc]">No vendors in your catalog yet.</p>
              <p className="text-xs text-[#4a5c6a] mt-1">Add vendors first, then they'll appear here ranked by fit.</p>
            </div>
          )}

          {/* Vendor cards */}
          <div className="grid gap-3">
            {matches.map((m, idx) => {
              const isSelected = selected.has(m.vendor_id);
              return (
                <button
                  key={m.vendor_id}
                  onClick={() => toggleVendor(m.vendor_id)}
                  className={`text-left w-full bg-[#1a232e] border rounded-xl p-4 transition-all ${
                    isSelected
                      ? 'border-blue-500 ring-1 ring-blue-500/30'
                      : 'border-[#2a3540] hover:border-[#3a4c5a]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Rank badge */}
                    <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold mt-0.5 ${
                      idx === 0 ? 'bg-amber-600/30 text-amber-400' :
                      idx === 1 ? 'bg-[#9aacbc]/20 text-[#9aacbc]' :
                      idx === 2 ? 'bg-orange-800/30 text-orange-500' :
                      'bg-[#1e2c3a] text-[#4a5c6a]'
                    }`}>
                      {idx + 1}
                    </div>

                    {/* Main content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-white truncate">{m.name}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${confidenceBg[m.confidence]}`}>
                          {m.confidence}
                        </span>
                        <ConfidenceStars confidence={m.confidence} />
                      </div>

                      <div className="flex flex-wrap gap-3 mt-1.5 text-xs text-[#9aacbc]">
                        {m.industry && (
                          <span className="flex items-center gap-1">
                            <Building2 size={10} /> {m.industry}
                          </span>
                        )}
                        {m.email && <span className="truncate max-w-[180px]">{m.email}</span>}
                        <span className="px-1.5 py-0.5 bg-[#1e2c3a] rounded text-[#6a7c8c]">{m.category}</span>
                      </div>

                      {/* Score breakdown */}
                      <div className="mt-3 grid grid-cols-3 gap-3">
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] text-[#6a7c8c] flex items-center gap-0.5">
                              <TrendingUp size={9} /> Category fit
                            </span>
                            <span className="text-[10px] text-[#9aacbc]">{m.score_breakdown.category_fit}</span>
                          </div>
                          <ScoreBar value={m.score_breakdown.category_fit} max={50} color="bg-blue-500" />
                        </div>
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] text-[#6a7c8c] flex items-center gap-0.5">
                              <Search size={9} /> Name match
                            </span>
                            <span className="text-[10px] text-[#9aacbc]">{m.score_breakdown.name_relevance}</span>
                          </div>
                          <ScoreBar value={m.score_breakdown.name_relevance} max={15} color="bg-purple-500" />
                        </div>
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] text-[#6a7c8c] flex items-center gap-0.5">
                              <BarChart2 size={9} /> Quote history
                            </span>
                            <span className="text-[10px] text-[#9aacbc]">{m.score_breakdown.quote_history}</span>
                          </div>
                          <ScoreBar value={m.score_breakdown.quote_history} max={35} color="bg-emerald-500" />
                        </div>
                      </div>

                      {/* Quote stats */}
                      <div className="mt-2.5 flex flex-wrap gap-3 text-[10px] text-[#6a7c8c]">
                        <span className="flex items-center gap-1">
                          <Users size={9} />
                          {m.quote_stats.total_rfqs === 0
                            ? 'No prior RFQs'
                            : `${m.quote_stats.total_rfqs} past RFQ${m.quote_stats.total_rfqs !== 1 ? 's' : ''}`}
                        </span>
                        {m.quote_stats.response_rate !== null && (
                          <span className={m.quote_stats.response_rate >= 70 ? 'text-emerald-400' : 'text-amber-400'}>
                            {m.quote_stats.response_rate}% response rate
                          </span>
                        )}
                        {m.quote_stats.avg_quoted_price !== null && (
                          <span>Avg quote: {m.quote_stats.avg_quoted_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                        )}
                      </div>
                    </div>

                    {/* Checkbox */}
                    <div className={`flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
                      isSelected ? 'bg-blue-600 border-blue-600' : 'border-[#3a4c5a]'
                    }`}>
                      {isSelected && <CheckCircle size={12} className="text-white" fill="white" />}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Broadcast bar */}
          <div className="sticky bottom-0 bg-[#0f1419] border-t border-[#2a3540] rounded-b-xl p-4 flex items-center justify-between gap-4 -mx-0">
            <span className="text-xs text-[#9aacbc]">
              {selected.size === 0
                ? 'Select at least one vendor to broadcast'
                : `${selected.size} vendor${selected.size !== 1 ? 's' : ''} selected`}
            </span>
            <div className="flex items-center gap-3">
              {saveErr && (
                <span className="text-xs text-red-400 flex items-center gap-1">
                  <AlertCircle size={11} /> {saveErr}
                </span>
              )}
              <button
                onClick={broadcast}
                disabled={selected.size === 0 || saving}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
              >
                {saving ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Broadcasting…
                  </>
                ) : (
                  <>
                    <Zap size={14} /> Broadcast to {selected.size} Vendor{selected.size !== 1 ? 's' : ''}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Quote Comparison View ──────────────────────────────────────────── */}
      {step === 'quotes' && selectedRfq && (
        <div className="space-y-4">
          {/* Header */}
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-4">
            <button
              onClick={resetFlow}
              className="text-xs text-[#9aacbc] hover:text-white flex items-center gap-1 mb-3 transition-colors"
            >
              <ChevronLeft size={12} /> Back to RFQs
            </button>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <FileText size={18} className="text-blue-400" />
                  RFQ #{selectedRfq.id} — Quote Comparison
                </h2>
                <p className="text-xs text-[#9aacbc] mt-1">
                  {selectedRfq.message?.split('\n')[0]}
                </p>
              </div>
              <span className={`text-xs px-2.5 py-1 rounded-full ${statusColor[selectedRfq.status] ?? 'bg-[#2a3540] text-[#9aacbc]'}`}>
                {selectedRfq.status.replace('_', ' ')}
              </span>
            </div>
          </div>

          {/* Quotes table */}
          {loadingQuotes ? (
            <div className="text-center py-8">
              <div className="inline-flex items-center gap-2 text-sm text-[#9aacbc]">
                <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Loading quotes…
              </div>
            </div>
          ) : !comparison || comparison.quotes.length === 0 ? (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-8 text-center">
              <BarChart2 size={32} className="text-[#2a3540] mx-auto mb-3" />
              <p className="text-sm text-[#9aacbc]">No vendor quotes yet.</p>
              <p className="text-xs text-[#4a5c6a] mt-1">Vendors will respond to your RFQ as they receive it.</p>
            </div>
          ) : (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#2a3540] bg-[#0f1419]">
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#9aacbc]">Rank</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#9aacbc]">Vendor</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#9aacbc] flex items-center gap-1">
                        <DollarSign size={11} /> Unit Price
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#9aacbc]">Total</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#9aacbc] flex items-center gap-1">
                        <Truck size={11} /> Lead Time
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#9aacbc] flex items-center gap-1">
                        <Speed size={11} /> Response Speed
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#9aacbc]">Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.quotes.map((q, idx) => {
                      const priceMatch = idx === 0;
                      const leadTimeMatch = q.lead_time_days === Math.min(...comparison.quotes.map((x) => x.lead_time_days ?? Infinity));
                      const speedMatch = q.response_speed_hours === Math.min(...comparison.quotes.map((x) => x.response_speed_hours ?? Infinity));
                      return (
                        <tr key={q.id} className={`border-b border-[#2a3540] last:border-0 hover:bg-[#1e2c3a] transition-colors ${
                          idx === 0 ? 'bg-emerald-600/5' : ''
                        }`}>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                              idx === 0 ? 'bg-emerald-600/30 text-emerald-400' :
                              idx === 1 ? 'bg-[#9aacbc]/20 text-[#9aacbc]' :
                              idx === 2 ? 'bg-orange-800/30 text-orange-500' :
                              'bg-[#1e2c3a] text-[#4a5c6a]'
                            }`}>
                              {idx + 1}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-medium text-white">{q.vendor_name}</td>
                          <td className={`px-4 py-3 font-semibold ${priceMatch ? 'text-emerald-400' : 'text-white'}`}>
                            {q.unit_price ? `${comparison.currency} ${q.unit_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—'}
                            {priceMatch && q.unit_price && (
                              <span className="ml-1.5 text-[10px] px-1.5 py-0.5 bg-emerald-600/20 text-emerald-400 rounded">Best</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-[#9aacbc]">
                            {q.total_price ? `${comparison.currency} ${q.total_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—'}
                          </td>
                          <td className={`px-4 py-3 font-medium ${leadTimeMatch && q.lead_time_days ? 'text-emerald-400' : 'text-white'}`}>
                            {q.lead_time_days ? `${q.lead_time_days} days` : '—'}
                            {leadTimeMatch && q.lead_time_days && (
                              <span className="ml-1.5 text-[10px] px-1.5 py-0.5 bg-blue-600/20 text-blue-400 rounded">Fastest</span>
                            )}
                          </td>
                          <td className={`px-4 py-3 font-medium ${speedMatch && q.response_speed_hours ? 'text-emerald-400' : 'text-white'}`}>
                            {q.response_speed_hours ? `${q.response_speed_hours}h` : '—'}
                            {speedMatch && q.response_speed_hours && (
                              <span className="ml-1.5 text-[10px] px-1.5 py-0.5 bg-purple-600/20 text-purple-400 rounded">Quick</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <div className="w-full bg-[#0f1419] rounded h-1.5 overflow-hidden">
                              <div
                                className="h-full bg-blue-500 transition-all"
                                style={{ width: `${Math.min(q.confidence * 100, 100)}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-[#6a7c8c] mt-1">{(q.confidence * 100).toFixed(0)}%</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="px-4 py-3 border-t border-[#2a3540] bg-[#0f1419] text-xs text-[#9aacbc]">
                Sorted by: unit price (lowest), lead time (fastest), response speed (quickest)
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── RFQ List ────────────────────────────────────────────────────────── */}
      {step === 'list' && (
        <>
          {loading ? (
            <p className="text-sm text-[#9aacbc] py-8 text-center">Loading…</p>
          ) : rfqs.length === 0 ? (
            <div className="text-center py-16 space-y-3">
              <FileText size={36} className="text-[#2a3540] mx-auto" />
              <p className="text-sm text-[#9aacbc]">No RFQs yet.</p>
              <p className="text-xs text-[#4a5c6a]">Create one to broadcast sourcing requests to matched vendors.</p>
              <button
                onClick={() => setStep('details')}
                className="mt-2 inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
              >
                <Plus size={13} /> Create your first RFQ
              </button>
            </div>
          ) : (
            <div className="grid gap-3">
              {rfqs.map((rfq) => (
                <button
                  key={rfq.id}
                  onClick={() => viewQuotes(rfq)}
                  className="text-left w-full bg-[#1a232e] border border-[#2a3540] rounded-xl p-4 hover:border-[#3a4c5a] hover:bg-[#1e2c3a] transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        <span className="font-mono text-xs text-[#9aacbc]">#{rfq.id}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor[rfq.status] ?? 'bg-[#2a3540] text-[#9aacbc]'}`}>
                          {rfq.status.replace('_', ' ')}
                        </span>
                        <span className="text-xs text-[#4a5c6a]">via {rfq.channel}</span>
                      </div>
                      {rfq.message && (
                        <p className="text-sm text-white font-medium leading-snug line-clamp-2">
                          {rfq.message.split('\n')[0]}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-3 mt-2 text-xs text-[#9aacbc]">
                        <span className="flex items-center gap-1">
                          <Clock size={10} /> {new Date(rfq.created_at).toLocaleDateString()}
                        </span>
                        <span>by {rfq.performed_by}</span>
                      </div>
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-2">
                      <span className="text-xs text-[#9aacbc]">View quotes</span>
                      <ChevronRight size={14} className="text-[#4a5c6a]" />
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
