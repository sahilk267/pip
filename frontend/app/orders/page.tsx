'use client';

import { useEffect, useState } from 'react';
import { ShoppingCart, Search, ExternalLink, ChevronDown } from 'lucide-react';
import { orderApi } from '@/lib/api';

interface Order {
  id: number;
  customer_id?: number;
  lead_id?: number;
  currency: string;
  total_amount: number;
  fulfillment_status: string;
  source_channel: string;
  created_at?: string;
  order_items?: unknown[];
}

const statusColor: Record<string, string> = {
  pending: 'bg-amber-600/20 text-amber-400',
  packed: 'bg-blue-600/20 text-blue-400',
  shipped: 'bg-purple-600/20 text-purple-400',
  in_transit: 'bg-blue-600/20 text-blue-400',
  delivered: 'bg-emerald-600/20 text-emerald-400',
  failed: 'bg-red-600/20 text-red-400',
  returned: 'bg-red-600/20 text-red-400',
};

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const data = await orderApi.list({ limit: 200, status: statusFilter || undefined });
      setOrders(Array.isArray(data) ? data : data.items ?? []);
    } catch { /* no-op */ }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [statusFilter]);

  const filtered = orders.filter((o) =>
    !search || String(o.id).includes(search) || o.source_channel?.toLowerCase().includes(search.toLowerCase())
  );

  const statuses = ['pending', 'packed', 'shipped', 'in_transit', 'delivered', 'failed', 'returned'];

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <ShoppingCart size={20} className="text-amber-400" /> Orders
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">{filtered.length} order{filtered.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9aacbc]" />
          <input
            className="w-full bg-[#1a232e] border border-[#2a3540] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-[#9aacbc] focus:outline-none focus:border-amber-500"
            placeholder="Search by order ID or channel…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="relative">
          <select
            className="bg-[#1a232e] border border-[#2a3540] rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500 appearance-none pr-8"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            {statuses.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
          <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#9aacbc] pointer-events-none" />
        </div>
      </div>

      {/* Status summary */}
      <div className="flex flex-wrap gap-2">
        {statuses.map((s) => {
          const count = orders.filter((o) => o.fulfillment_status === s).length;
          if (!count) return null;
          return (
            <button
              key={s}
              onClick={() => setStatusFilter(statusFilter === s ? '' : s)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                statusFilter === s ? (statusColor[s] || 'bg-[#2a3540] text-[#9aacbc]') + ' border-transparent' : 'bg-transparent border-[#2a3540] text-[#9aacbc] hover:border-[#3a4550]'
              }`}
            >
              {s.replace('_', ' ')} · {count}
            </button>
          );
        })}
      </div>

      {loading ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">No orders found.</p>
      ) : (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#2a3540] text-[#9aacbc] text-xs uppercase tracking-wide">
                <th className="px-4 py-3 text-left">Order #</th>
                <th className="px-4 py-3 text-left">Channel</th>
                <th className="px-4 py-3 text-left">Total</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((order) => (
                <tr key={order.id} className="border-b border-[#2a3540] last:border-0 hover:bg-[#1e2c3a] transition-colors">
                  <td className="px-4 py-3">
                    <span className="font-mono text-white">#{order.id}</span>
                  </td>
                  <td className="px-4 py-3 text-[#9aacbc]">{order.source_channel || '—'}</td>
                  <td className="px-4 py-3 text-white font-medium">
                    {order.currency} {order.total_amount?.toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor[order.fulfillment_status] || 'bg-[#2a3540] text-[#9aacbc]'}`}>
                      {(order.fulfillment_status || 'pending').replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[#9aacbc]">
                    {order.created_at ? new Date(order.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <a
                      href={`/api/v1/orders/b2c/${order.id}/tracking`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 text-blue-400 hover:underline text-xs"
                    >
                      <ExternalLink size={11} /> Track
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
