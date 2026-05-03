'use client';

import { useState } from 'react';
import { FileText, Check, Send } from 'lucide-react';

interface Invoice {
  invoice_id: number;
  invoice_number: string;
  vendor_id: number;
  total_amount: number;
  currency: string;
  status: string;
  due_date: string;
  created_at: string;
}

export function InvoicePanel({ quoteId }: { quoteId: number }) {
  const [poNumber, setPoNumber] = useState('');
  const [paymentTerms, setPaymentTerms] = useState('Net 30');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Invoice | null>(null);

  async function generateInvoice() {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/invoices/generate-from-quote/${quoteId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ po_number: poNumber, payment_terms: paymentTerms }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
      }
    } catch {}
    finally {
      setLoading(false);
    }
  }

  async function sendInvoice(invId: number) {
    try {
      const res = await fetch(`/api/v1/invoices/${invId}/send`, { method: 'POST' });
      if (res.ok) {
        setResult({ ...result!, status: 'sent' } as any);
      }
    } catch {}
  }

  return (
    <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 space-y-3">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
        <FileText size={14} /> Generate Invoice
      </h3>

      {!result ? (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-[#9aacbc] mb-1">PO Number</label>
            <input
              type="text"
              value={poNumber}
              onChange={(e) => setPoNumber(e.target.value)}
              placeholder="PO-20260503-0001"
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-2 py-1 text-white text-sm"
            />
          </div>

          <div>
            <label className="block text-xs text-[#9aacbc] mb-1">Payment Terms</label>
            <select
              value={paymentTerms}
              onChange={(e) => setPaymentTerms(e.target.value)}
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-2 py-1 text-white text-sm"
            >
              <option>Net 15</option>
              <option>Net 30</option>
              <option>Net 60</option>
            </select>
          </div>

          <button
            onClick={generateInvoice}
            disabled={loading || !poNumber}
            className="w-full py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm rounded transition-colors"
          >
            {loading ? 'Generating...' : 'Generate Invoice'}
          </button>
        </div>
      ) : (
        <div className="space-y-3 p-3 bg-[#0f1419] rounded">
          <div>
            <p className="text-xs text-[#9aacbc]">Invoice Number</p>
            <p className="text-sm font-bold text-white">{result.invoice_number}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <p className="text-[#9aacbc]">Total</p>
              <p className="text-white font-bold">{result.currency} {result.total_amount.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-[#9aacbc]">Status</p>
              <p className={`font-bold ${result.status === 'sent' ? 'text-emerald-400' : 'text-amber-400'}`}>
                {result.status}
              </p>
            </div>
          </div>

          {result.status === 'draft' && (
            <button
              onClick={() => sendInvoice(result.invoice_id)}
              className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded flex items-center justify-center gap-1"
            >
              <Send size={12} /> Send to Vendor
            </button>
          )}

          {result.status === 'sent' && (
            <div className="p-2 bg-emerald-600/20 border border-emerald-600/50 rounded flex items-center gap-2 text-xs text-emerald-400">
              <Check size={12} /> Invoice sent to vendor
            </div>
          )}
        </div>
      )}
    </div>
  );
}
