'use client';

import { useEffect, useState } from 'react';
import { Package, Search, Plus, Tag } from 'lucide-react';
import { productApi } from '@/lib/api';

interface Product {
  id: number;
  name: string;
  sku: string;
  category?: string;
  price?: number;
  currency?: string;
  stock_quantity?: number;
  vendor_id?: number;
  is_active?: boolean;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', sku: '', category: '', price: '', currency: 'USD', stock_quantity: '' });
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await productApi.list({ limit: 100, search: search || undefined });
      setProducts(Array.isArray(data) ? data : data.items ?? []);
    } catch { /* no-op */ }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [search]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await productApi.create({
        ...form,
        price: form.price ? parseFloat(form.price) : undefined,
        stock_quantity: form.stock_quantity ? parseInt(form.stock_quantity) : undefined,
      });
      setShowAdd(false);
      setForm({ name: '', sku: '', category: '', price: '', currency: 'USD', stock_quantity: '' });
      await load();
    } catch { /* no-op */ }
    finally { setSaving(false); }
  }

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  const statusColor = (active?: boolean) =>
    active !== false ? 'bg-emerald-600/20 text-emerald-400' : 'bg-red-600/20 text-red-400';

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Package size={20} className="text-emerald-400" /> Products
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">{products.length} product{products.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={14} /> Add Product
        </button>
      </div>

      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9aacbc]" />
        <input
          className="w-full bg-[#1a232e] border border-[#2a3540] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-[#9aacbc] focus:outline-none focus:border-emerald-500"
          placeholder="Search products…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {showAdd && (
        <form onSubmit={handleAdd} className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-5 grid grid-cols-2 gap-4">
          <h3 className="col-span-2 text-sm font-semibold text-white">New Product</h3>
          {([
            ['name', 'Product Name *'],
            ['sku', 'SKU *'],
            ['category', 'Category'],
            ['price', 'Price'],
            ['currency', 'Currency'],
            ['stock_quantity', 'Stock Qty'],
          ] as [keyof typeof form, string][]).map(([k, label]) => (
            <div key={k}>
              <label className="block text-xs text-[#9aacbc] mb-1">{label}</label>
              <input
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                value={form[k]}
                onChange={f(k)}
                required={k === 'name' || k === 'sku'}
              />
            </div>
          ))}
          <div className="col-span-2 flex gap-3 justify-end">
            <button type="button" onClick={() => setShowAdd(false)} className="text-sm text-[#9aacbc] hover:text-white px-4 py-2">Cancel</button>
            <button type="submit" disabled={saving} className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm px-5 py-2 rounded-lg">
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">Loading…</p>
      ) : products.length === 0 ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">No products yet.</p>
      ) : (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#2a3540] text-[#9aacbc] text-xs uppercase tracking-wide">
                <th className="px-4 py-3 text-left">Product</th>
                <th className="px-4 py-3 text-left">SKU</th>
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-left">Price</th>
                <th className="px-4 py-3 text-left">Stock</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-b border-[#2a3540] last:border-0 hover:bg-[#1e2c3a] transition-colors">
                  <td className="px-4 py-3">
                    <p className="text-white font-medium">{p.name}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-1 text-[#9aacbc]"><Tag size={11} />{p.sku}</span>
                  </td>
                  <td className="px-4 py-3 text-[#9aacbc]">{p.category || '—'}</td>
                  <td className="px-4 py-3 text-white">
                    {p.price != null ? `${p.currency || 'USD'} ${Number(p.price).toFixed(2)}` : '—'}
                  </td>
                  <td className="px-4 py-3 text-[#9aacbc]">{p.stock_quantity ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor(p.is_active)}`}>
                      {p.is_active !== false ? 'Active' : 'Inactive'}
                    </span>
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
