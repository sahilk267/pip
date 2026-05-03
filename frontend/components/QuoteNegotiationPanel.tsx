'use client';

import { useState } from 'react';
import { TrendingDown, Check, X, FileText } from 'lucide-react';

interface Quote {
  id: number;
  vendor_name: string;
  unit_price?: number;
  quantity?: number;
  lead_time_days?: number;
  status?: string;
}

export function QuoteNegotiationPanel({ quote }: { quote: Quote }) {
  const [step, setStep] = useState<'view' | 'counter' | 'confirm'>('view');
  const [counterPrice, setCounterPrice] = useState<string>(String(quote.unit_price || ''));
  const [counterDays, setCounterDays] = useState<string>(String(quote.lead_time_days || ''));
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const savings = parseFloat(counterPrice) < (quote.unit_price || 0) ? quote.unit_price - parseFloat(counterPrice) : 0;
  const savingsPct = quote.unit_price && savings > 0 ? (savings / quote.unit_price * 100).toFixed(1) : '0';
  const totalSavings = savings * (quote.quantity || 1);

  async function submitCounterOffer() {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/rfq/quotes/${quote.id}/counter-offer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          counter_price: parseFloat(counterPrice),
          lead_time_days: counterDays ? parseInt(counterDays) : undefined,
          notes,
          offered_by: 'buyer',
        }),
      });
      if (res.ok) {
        setResult('✓ Counter-offer sent to vendor!');
        setTimeout(() => { setStep('view'); setResult(null); }, 3000);
      }
    } catch {
      setResult('Error sending counter-offer');
    } finally {
      setLoading(false);
    }
  }

  async function acceptQuote() {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/rfq/quotes/${quote.id}/accept`, { method: 'POST' });
      if (res.ok) {
        setResult('✓ Quote accepted! Ready to generate PO.');
        setTimeout(() => setResult(null), 3000);
      }
    } catch {
      setResult('Error accepting quote');
    } finally {
      setLoading(false);
    }
  }

  async function rejectQuote() {
    if (confirm('Reject this quote?')) {
      setLoading(true);
      try {
        const res = await fetch(`/api/v1/rfq/quotes/${quote.id}/reject`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: 'Accepted competing vendor' }),
        });
        if (res.ok) {
          setResult('✓ Quote rejected.');
          setTimeout(() => setResult(null), 3000);
        }
      } catch {
        setResult('Error rejecting quote');
      } finally {
        setLoading(false);
      }
    }
  }

  async function generatePO() {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/rfq/quotes/${quote.id}/generate-po`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payment_terms: 'Net 30',
          delivery_address: { city: 'Destination', country: 'Global' },
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(`✓ PO ${data.po_number} generated!`);
        setTimeout(() => setResult(null), 3000);
      }
    } catch {
      setResult('Error generating PO');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 space-y-3">
      <h3 className="text-sm font-semibold text-white">Negotiation & PO</h3>

      {step === 'view' && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <p className="text-[#9aacbc]">Your Price</p>
              <p className="text-lg font-bold text-white">${quote.unit_price?.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-[#9aacbc]">Quantity</p>
              <p className="text-lg font-bold text-white">{quote.quantity}</p>
            </div>
            <div>
              <p className="text-[#9aacbc]">Total</p>
              <p className="text-lg font-bold text-emerald-400">
                ${((quote.unit_price || 0) * (quote.quantity || 1)).toFixed(2)}
              </p>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setStep('counter')}
              className="flex-1 py-2 bg-blue-600/20 border border-blue-600/50 text-blue-400 text-xs rounded hover:bg-blue-600/30 transition-colors flex items-center justify-center gap-1"
            >
              <TrendingDown size={12} /> Counter Offer
            </button>
            <button
              onClick={acceptQuote}
              disabled={loading}
              className="flex-1 py-2 bg-emerald-600/20 border border-emerald-600/50 text-emerald-400 text-xs rounded hover:bg-emerald-600/30 transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
            >
              <Check size={12} /> Accept
            </button>
            <button
              onClick={rejectQuote}
              disabled={loading}
              className="flex-1 py-2 bg-red-600/20 border border-red-600/50 text-red-400 text-xs rounded hover:bg-red-600/30 transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
            >
              <X size={12} /> Reject
            </button>
          </div>

          {quote.status === 'accepted' && (
            <button
              onClick={generatePO}
              disabled={loading}
              className="w-full py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs rounded flex items-center justify-center gap-2 transition-colors"
            >
              <FileText size={12} /> Generate PO
            </button>
          )}
        </div>
      )}

      {step === 'counter' && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-[#9aacbc] mb-1">Counter Price</label>
            <input
              type="number"
              value={counterPrice}
              onChange={(e) => setCounterPrice(e.target.value)}
              step="0.01"
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-2 py-1 text-white text-sm"
            />
            {savings > 0 && (
              <p className="text-xs text-emerald-400 mt-1">Save {savingsPct}% (${savings.toFixed(2)} per unit)</p>
            )}
          </div>

          <div>
            <label className="block text-xs text-[#9aacbc] mb-1">Lead Time (days)</label>
            <input
              type="number"
              value={counterDays}
              onChange={(e) => setCounterDays(e.target.value)}
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-2 py-1 text-white text-sm"
            />
          </div>

          <div>
            <label className="block text-xs text-[#9aacbc] mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Why this counter-offer..."
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-2 py-1 text-white text-sm text-xs h-16 resize-none"
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setStep('view')}
              className="flex-1 py-2 bg-[#1e2c3a] border border-[#2a3540] text-[#9aacbc] text-xs rounded hover:bg-[#2a3a4a]"
            >
              Cancel
            </button>
            <button
              onClick={submitCounterOffer}
              disabled={loading}
              className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs rounded"
            >
              {loading ? 'Sending...' : 'Send Counter'}
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className={`text-xs p-2 rounded ${result.startsWith('✓') ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/50' : 'bg-red-600/20 text-red-400 border border-red-600/50'}`}>
          {result}
        </div>
      )}
    </div>
  );
}
