'use client';

import { useState, useEffect } from 'react';
import { FileText, Send, Check, AlertCircle, Plus, RefreshCw, Database, X, ChevronDown } from 'lucide-react';

interface Invoice {
  invoice_id: number;
  invoice_number: string;
  vendor_id: number;
  vendor_name?: string;
  total_amount: number;
  currency: string;
  status: string;
  due_date: string | null;
  created_at: string | null;
}

const PAYMENT_TERMS = ['Net 15', 'Net 30', 'Net 60'];

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<'all' | 'draft' | 'sent' | 'paid'>('all');
  const [vendors, setVendors] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState('');
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [createForm, setCreateForm] = useState({
    vendor_id: '',
    description: '',
    quantity: '',
    unit_price: '',
    payment_terms: 'Net 30',
    po_number: '',
    notes: '',
  });
  const [createMsg, setCreateMsg] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadInvoices();
    fetch('/api/v1/vendors').then((r) => r.json()).then((d) => setVendors(Array.isArray(d) ? d : (d.vendors || []))).catch(() => {});
  }, [filterStatus]);

  async function loadInvoices() {
    setLoading(true);
    try {
      const query = filterStatus === 'all' ? '' : `?status=${filterStatus}`;
      const res = await fetch(`/api/v1/invoices${query}`);
      if (res.ok) {
        const data = await res.json();
        setInvoices(data.invoices || []);
      }
    } catch {}
    finally { setLoading(false); }
  }

  async function seedInvoices() {
    setSeeding(true);
    setSeedMsg('');
    try {
      const res = await fetch('/api/v1/invoices/seed', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'already_seeded') {
          setSeedMsg(`Already have ${data.existing} sample invoices.`);
        } else {
          setSeedMsg(`Generated ${data.created} sample invoices.`);
        }
        await loadInvoices();
      } else {
        setSeedMsg('Seed failed.');
      }
    } catch {
      setSeedMsg('Error connecting to server.');
    } finally {
      setSeeding(false);
    }
  }

  async function createInvoice() {
    if (!createForm.vendor_id || !createForm.description || !createForm.quantity || !createForm.unit_price) return;
    setCreating(true);
    setCreateMsg('');
    try {
      const params = new URLSearchParams({
        vendor_id: createForm.vendor_id,
        description: createForm.description,
        quantity: createForm.quantity,
        unit_price: createForm.unit_price,
        payment_terms: createForm.payment_terms,
        po_number: createForm.po_number,
        notes: createForm.notes,
      });
      const res = await fetch(`/api/v1/invoices/create?${params}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setCreateMsg(`Invoice ${data.invoice_number} created!`);
        setCreateForm({ vendor_id: '', description: '', quantity: '', unit_price: '', payment_terms: 'Net 30', po_number: '', notes: '' });
        await loadInvoices();
        setTimeout(() => { setShowCreate(false); setCreateMsg(''); }, 1500);
      } else {
        setCreateMsg('Failed to create invoice.');
      }
    } catch {
      setCreateMsg('Error.');
    } finally {
      setCreating(false);
    }
  }

  async function sendInvoice(id: number) {
    setActionLoading(id);
    try {
      const res = await fetch(`/api/v1/invoices/${id}/send`, { method: 'POST' });
      if (res.ok) await loadInvoices();
    } catch {}
    finally { setActionLoading(null); }
  }

  async function payInvoice(id: number) {
    setActionLoading(id);
    try {
      const res = await fetch(`/api/v1/invoices/${id}/record-payment`, { method: 'POST' });
      if (res.ok) await loadInvoices();
    } catch {}
    finally { setActionLoading(null); }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid': return 'text-emerald-400 bg-emerald-900/20';
      case 'sent': return 'text-blue-400 bg-blue-900/20';
      case 'overdue': return 'text-red-400 bg-red-900/20';
      default: return 'text-amber-400 bg-amber-900/20';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'paid': return <Check size={11} />;
      case 'sent': return <Send size={11} />;
      default: return <AlertCircle size={11} />;
    }
  };

  const totalPaid = invoices.filter(i => i.status === 'paid').reduce((s, i) => s + i.total_amount, 0);
  const totalOutstanding = invoices.filter(i => i.status !== 'paid').reduce((s, i) => s + i.total_amount, 0);

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText size={20} className="text-green-400" /> Invoice Management
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">Auto-generate, send, and track invoices from POs</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={seedInvoices}
            disabled={seeding}
            className="flex items-center gap-2 px-3 py-1.5 bg-[#1a232e] border border-green-600/50 hover:border-green-500 text-green-400 text-xs rounded transition-colors disabled:opacity-50"
          >
            {seeding ? <RefreshCw size={12} className="animate-spin" /> : <Database size={12} />}
            {seeding ? 'Generating...' : 'Sample Invoices'}
          </button>
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="flex items-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-xs rounded transition-colors"
          >
            {showCreate ? <X size={12} /> : <Plus size={12} />}
            {showCreate ? 'Cancel' : 'New Invoice'}
          </button>
        </div>
      </div>

      {seedMsg && (
        <div className={`text-xs px-4 py-2 rounded border ${seedMsg.includes('Generated') || seedMsg.includes('already') ? 'bg-emerald-900/20 border-emerald-700/40 text-emerald-400' : 'bg-red-900/20 border-red-700/40 text-red-400'}`}>
          {seedMsg}
        </div>
      )}

      {/* Summary KPIs */}
      {invoices.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
            <p className="text-xs text-[#9aacbc]">Total Invoices</p>
            <p className="text-xl font-bold text-white">{invoices.length}</p>
          </div>
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
            <p className="text-xs text-[#9aacbc]">Collected (Paid)</p>
            <p className="text-xl font-bold text-emerald-400">${totalPaid.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
          </div>
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-3">
            <p className="text-xs text-[#9aacbc]">Outstanding</p>
            <p className="text-xl font-bold text-amber-400">${totalOutstanding.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
          </div>
        </div>
      )}

      {/* Create Invoice Panel */}
      {showCreate && (
        <div className="bg-[#1a232e] border border-green-600/30 rounded-lg p-5 space-y-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2"><Plus size={14} className="text-green-400" /> Create Invoice</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-[#9aacbc] mb-1 block">Vendor</label>
              <select
                value={createForm.vendor_id}
                onChange={(e) => setCreateForm({ ...createForm, vendor_id: e.target.value })}
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
              >
                <option value="">Select vendor...</option>
                {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-[#9aacbc] mb-1 block">Payment Terms</label>
              <select
                value={createForm.payment_terms}
                onChange={(e) => setCreateForm({ ...createForm, payment_terms: e.target.value })}
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
              >
                {PAYMENT_TERMS.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="text-xs text-[#9aacbc] mb-1 block">Line Item Description</label>
              <input
                type="text"
                value={createForm.description}
                onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                placeholder="e.g. Bulk Electronics Supply Q3"
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-[#9aacbc] mb-1 block">Quantity</label>
              <input
                type="number"
                value={createForm.quantity}
                onChange={(e) => setCreateForm({ ...createForm, quantity: e.target.value })}
                placeholder="e.g. 200"
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-[#9aacbc] mb-1 block">Unit Price ($)</label>
              <input
                type="number"
                value={createForm.unit_price}
                onChange={(e) => setCreateForm({ ...createForm, unit_price: e.target.value })}
                placeholder="e.g. 45.00"
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-[#9aacbc] mb-1 block">PO Number (opt)</label>
              <input
                type="text"
                value={createForm.po_number}
                onChange={(e) => setCreateForm({ ...createForm, po_number: e.target.value })}
                placeholder="e.g. PO-2025001"
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-[#9aacbc] mb-1 block">Notes (opt)</label>
              <input
                type="text"
                value={createForm.notes}
                onChange={(e) => setCreateForm({ ...createForm, notes: e.target.value })}
                placeholder="Optional"
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
              />
            </div>
          </div>
          {createForm.quantity && createForm.unit_price && (
            <p className="text-xs text-[#9aacbc]">
              Total: <span className="text-white font-bold">${(parseFloat(createForm.quantity || '0') * parseFloat(createForm.unit_price || '0')).toFixed(2)}</span>
            </p>
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={createInvoice}
              disabled={creating || !createForm.vendor_id || !createForm.description || !createForm.quantity || !createForm.unit_price}
              className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center gap-2"
            >
              {creating && <RefreshCw size={13} className="animate-spin" />}
              Create Invoice
            </button>
            {createMsg && (
              <p className={`text-xs ${createMsg.includes('created') ? 'text-emerald-400' : 'text-red-400'}`}>{createMsg}</p>
            )}
          </div>
        </div>
      )}

      {/* Filter buttons */}
      <div className="flex gap-2">
        {(['all', 'draft', 'sent', 'paid'] as const).map((status) => (
          <button
            key={status}
            onClick={() => setFilterStatus(status)}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              filterStatus === status
                ? 'bg-green-600 text-white'
                : 'bg-[#1a232e] border border-[#2a3540] text-[#9aacbc] hover:border-green-600'
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
        <button onClick={loadInvoices} className="ml-auto text-xs text-[#9aacbc] hover:text-white flex items-center gap-1">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Invoices table */}
      <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg overflow-hidden">
        {loading ? (
          <div className="p-6 text-center text-[#9aacbc] text-sm">Loading...</div>
        ) : invoices.length === 0 ? (
          <div className="p-8 text-center">
            <FileText size={32} className="text-[#4a5c6a] mx-auto mb-3" />
            <p className="text-sm text-[#9aacbc] mb-1">No invoices found.</p>
            <p className="text-xs text-[#4a5c6a]">Click <strong className="text-green-400">Sample Invoices</strong> to generate demo data, or <strong className="text-green-400">New Invoice</strong> to create one.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-[#0f1419] border-b border-[#2a3540]">
                <tr>
                  <th className="px-4 py-3 text-left text-[#9aacbc] font-medium">Invoice #</th>
                  <th className="px-4 py-3 text-left text-[#9aacbc] font-medium">Vendor</th>
                  <th className="px-4 py-3 text-left text-[#9aacbc] font-medium">Amount</th>
                  <th className="px-4 py-3 text-left text-[#9aacbc] font-medium">Due Date</th>
                  <th className="px-4 py-3 text-left text-[#9aacbc] font-medium">Status</th>
                  <th className="px-4 py-3 text-left text-[#9aacbc] font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2a3540]">
                {invoices.map((inv) => (
                  <tr key={inv.invoice_id} className="hover:bg-[#0f1419] transition-colors">
                    <td className="px-4 py-3 text-white font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-3 text-[#9aacbc]">{inv.vendor_name || `Vendor ${inv.vendor_id}`}</td>
                    <td className="px-4 py-3 text-white font-semibold">
                      {inv.currency} {inv.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-[#9aacbc]">
                      {inv.due_date ? new Date(inv.due_date).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(inv.status)}`}>
                        {getStatusIcon(inv.status)} {inv.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        {inv.status === 'draft' && (
                          <button
                            onClick={() => sendInvoice(inv.invoice_id)}
                            disabled={actionLoading === inv.invoice_id}
                            className="px-2 py-1 bg-blue-700/40 hover:bg-blue-700/70 text-blue-300 rounded transition-colors flex items-center gap-1 disabled:opacity-50"
                          >
                            {actionLoading === inv.invoice_id ? <RefreshCw size={10} className="animate-spin" /> : <Send size={10} />}
                            Send
                          </button>
                        )}
                        {inv.status === 'sent' && (
                          <button
                            onClick={() => payInvoice(inv.invoice_id)}
                            disabled={actionLoading === inv.invoice_id}
                            className="px-2 py-1 bg-emerald-700/40 hover:bg-emerald-700/70 text-emerald-300 rounded transition-colors flex items-center gap-1 disabled:opacity-50"
                          >
                            {actionLoading === inv.invoice_id ? <RefreshCw size={10} className="animate-spin" /> : <Check size={10} />}
                            Mark Paid
                          </button>
                        )}
                        {inv.status === 'paid' && (
                          <span className="text-[#4a5c6a] text-xs">—</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
