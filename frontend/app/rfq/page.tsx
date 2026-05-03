'use client';

import { useEffect, useState } from 'react';
import { FileText, Plus, ChevronDown, CheckCircle, Clock } from 'lucide-react';
import { rfqApi } from '@/lib/api';

interface RFQ {
  id: number;
  product_name: string;
  quantity: number;
  currency: string;
  target_price?: number;
  status: string;
  delivery_deadline?: string;
  vendor_count?: number;
  created_at?: string;
}

const statusColor: Record<string, string> = {
  open: 'bg-blue-600/20 text-blue-400',
  closed: 'bg-[#2a3540] text-[#9aacbc]',
  awarded: 'bg-emerald-600/20 text-emerald-400',
  cancelled: 'bg-red-600/20 text-red-400',
  draft: 'bg-amber-600/20 text-amber-400',
};

export default function RFQPage() {
  const [rfqs, setRfqs] = useState<RFQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    product_name: '', quantity: '', currency: 'USD', target_price: '',
    delivery_deadline: '', notes: '',
  });
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await rfqApi.list({ limit: 100 });
      setRfqs(Array.isArray(data) ? data : data.items ?? []);
    } catch { /* no-op */ }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await rfqApi.create({
        ...form,
        quantity: parseInt(form.quantity) || 1,
        target_price: form.target_price ? parseFloat(form.target_price) : undefined,
      });
      setShowAdd(false);
      setForm({ product_name: '', quantity: '', currency: 'USD', target_price: '', delivery_deadline: '', notes: '' });
      await load();
    } catch { /* no-op */ }
    finally { setSaving(false); }
  }

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText size={20} className="text-blue-400" /> RFQ Broadcasts
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">{rfqs.length} RFQ{rfqs.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={14} /> Create RFQ
        </button>
      </div>

      {showAdd && (
        <form onSubmit={handleAdd} className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-5 grid grid-cols-2 gap-4">
          <h3 className="col-span-2 text-sm font-semibold text-white">New RFQ Broadcast</h3>
          {([
            ['product_name', 'Product / Item *'],
            ['quantity', 'Quantity *'],
            ['currency', 'Currency'],
            ['target_price', 'Target Price'],
            ['delivery_deadline', 'Delivery Deadline'],
          ] as [keyof typeof form, string][]).map(([k, label]) => (
            <div key={k}>
              <label className="block text-xs text-[#9aacbc] mb-1">{label}</label>
              <input
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                type={k === 'delivery_deadline' ? 'date' : 'text'}
                value={form[k]}
                onChange={f(k)}
                required={k === 'product_name' || k === 'quantity'}
              />
            </div>
          ))}
          <div className="col-span-2">
            <label className="block text-xs text-[#9aacbc] mb-1">Notes</label>
            <textarea
              className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 resize-none"
              rows={3}
              value={form.notes}
              onChange={f('notes')}
            />
          </div>
          <div className="col-span-2 flex gap-3 justify-end">
            <button type="button" onClick={() => setShowAdd(false)} className="text-sm text-[#9aacbc] hover:text-white px-4 py-2">Cancel</button>
            <button type="submit" disabled={saving} className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-5 py-2 rounded-lg">
              {saving ? 'Broadcasting…' : 'Broadcast'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">Loading…</p>
      ) : rfqs.length === 0 ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">No RFQs yet. Create one to start sourcing.</p>
      ) : (
        <div className="grid gap-4">
          {rfqs.map((rfq) => (
            <div key={rfq.id} className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="font-mono text-xs text-[#9aacbc]">#{rfq.id}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor[rfq.status] || 'bg-[#2a3540] text-[#9aacbc]'}`}>
                      {rfq.status}
                    </span>
                  </div>
                  <h3 className="text-white font-semibold">{rfq.product_name}</h3>
                  <div className="flex flex-wrap gap-4 mt-2 text-xs text-[#9aacbc]">
                    <span>Qty: <span className="text-white">{rfq.quantity}</span></span>
                    {rfq.target_price && <span>Target: <span className="text-white">{rfq.currency} {rfq.target_price}</span></span>}
                    {rfq.delivery_deadline && (
                      <span className="flex items-center gap-1">
                        <Clock size={11} /> {new Date(rfq.delivery_deadline).toLocaleDateString()}
                      </span>
                    )}
                    {rfq.vendor_count != null && (
                      <span className="flex items-center gap-1">
                        <CheckCircle size={11} className="text-emerald-400" /> {rfq.vendor_count} vendors
                      </span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-[#9aacbc]">
                  {rfq.created_at ? new Date(rfq.created_at).toLocaleDateString() : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
