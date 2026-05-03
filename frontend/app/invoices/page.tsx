'use client';

import { useState, useEffect } from 'react';
import { FileText, Send, Check, AlertCircle } from 'lucide-react';

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

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<'all' | 'draft' | 'sent' | 'paid'>('all');

  useEffect(() => {
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
      finally {
        setLoading(false);
      }
    }
    loadInvoices();
  }, [filterStatus]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid':
        return 'text-emerald-400';
      case 'sent':
        return 'text-blue-400';
      default:
        return 'text-amber-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'paid':
        return <Check size={14} />;
      case 'sent':
        return <Send size={14} />;
      default:
        return <AlertCircle size={14} />;
    }
  };

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <FileText size={20} className="text-green-400" /> Invoice Management
        </h1>
        <p className="text-sm text-[#9aacbc] mt-0.5">Auto-generate, send, and track invoices from POs</p>
      </div>

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
      </div>

      {/* Invoices table */}
      <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg overflow-hidden">
        {loading ? (
          <div className="p-6 text-center text-[#9aacbc] text-sm">Loading...</div>
        ) : invoices.length === 0 ? (
          <div className="p-6 text-center text-[#9aacbc] text-sm">No invoices found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-[#0f1419] border-b border-[#2a3540]">
                <tr>
                  <th className="px-4 py-2 text-left text-[#9aacbc]">Invoice #</th>
                  <th className="px-4 py-2 text-left text-[#9aacbc]">Vendor</th>
                  <th className="px-4 py-2 text-left text-[#9aacbc]">Amount</th>
                  <th className="px-4 py-2 text-left text-[#9aacbc]">Due Date</th>
                  <th className="px-4 py-2 text-left text-[#9aacbc]">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2a3540]">
                {invoices.map((inv) => (
                  <tr key={inv.invoice_id} className="hover:bg-[#0f1419] transition-colors">
                    <td className="px-4 py-2 text-white font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-2 text-[#9aacbc]">Vendor {inv.vendor_id}</td>
                    <td className="px-4 py-2 text-white">
                      {inv.currency} {inv.total_amount.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-[#9aacbc]">{new Date(inv.due_date).toLocaleDateString()}</td>
                    <td className={`px-4 py-2 flex items-center gap-1 ${getStatusColor(inv.status)}`}>
                      {getStatusIcon(inv.status)} {inv.status}
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
