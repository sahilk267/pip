'use client';

import { useEffect, useState } from 'react';
import { Building2, Search, Plus, MapPin, Globe, Star } from 'lucide-react';
import { vendorApi } from '@/lib/api';

interface Vendor {
  id: number;
  name: string;
  category: string;
  country?: string;
  city?: string;
  website?: string;
  rating?: number;
  contact_email?: string;
  verified?: boolean;
}

export default function VendorsPage() {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', category: '', country: '', city: '', contact_email: '', website: '' });
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await vendorApi.list({ limit: 100, search: search || undefined });
      setVendors(Array.isArray(data) ? data : data.items ?? []);
    } catch { /* no-op */ }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [search]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await vendorApi.create(form);
      setShowAdd(false);
      setForm({ name: '', category: '', country: '', city: '', contact_email: '', website: '' });
      await load();
    } catch { /* no-op */ }
    finally { setSaving(false); }
  }

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Building2 size={20} className="text-blue-400" /> Vendors
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">{vendors.length} vendor{vendors.length !== 1 ? 's' : ''} found</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={14} /> Add Vendor
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9aacbc]" />
        <input
          className="w-full bg-[#1a232e] border border-[#2a3540] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-[#9aacbc] focus:outline-none focus:border-blue-500"
          placeholder="Search vendors…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Add Form */}
      {showAdd && (
        <form onSubmit={handleAdd} className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-5 grid grid-cols-2 gap-4">
          <h3 className="col-span-2 text-sm font-semibold text-white">New Vendor</h3>
          {([
            ['name', 'Vendor Name *'],
            ['category', 'Category'],
            ['country', 'Country'],
            ['city', 'City'],
            ['contact_email', 'Contact Email'],
            ['website', 'Website'],
          ] as [keyof typeof form, string][]).map(([k, label]) => (
            <div key={k}>
              <label className="block text-xs text-[#9aacbc] mb-1">{label}</label>
              <input
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                value={form[k]}
                onChange={f(k)}
                required={k === 'name'}
              />
            </div>
          ))}
          <div className="col-span-2 flex gap-3 justify-end">
            <button type="button" onClick={() => setShowAdd(false)} className="text-sm text-[#9aacbc] hover:text-white px-4 py-2">Cancel</button>
            <button type="submit" disabled={saving} className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-5 py-2 rounded-lg">
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      )}

      {/* Table */}
      {loading ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">Loading…</p>
      ) : vendors.length === 0 ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">No vendors yet. Add one above.</p>
      ) : (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#2a3540] text-[#9aacbc] text-xs uppercase tracking-wide">
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-left">Location</th>
                <th className="px-4 py-3 text-left">Website</th>
                <th className="px-4 py-3 text-left">Rating</th>
              </tr>
            </thead>
            <tbody>
              {vendors.map((v) => (
                <tr key={v.id} className="border-b border-[#2a3540] last:border-0 hover:bg-[#1e2c3a] transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-md bg-blue-600/20 flex items-center justify-center text-blue-400 text-xs font-bold">
                        {v.name.charAt(0)}
                      </div>
                      <div>
                        <p className="text-white font-medium">{v.name}</p>
                        {v.contact_email && <p className="text-xs text-[#9aacbc]">{v.contact_email}</p>}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-[#9aacbc]">{v.category || '—'}</td>
                  <td className="px-4 py-3 text-[#9aacbc]">
                    {v.city || v.country ? (
                      <span className="flex items-center gap-1"><MapPin size={12} />{[v.city, v.country].filter(Boolean).join(', ')}</span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {v.website ? (
                      <a href={v.website} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-blue-400 hover:underline">
                        <Globe size={12} /> Link
                      </a>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {v.rating ? <span className="flex items-center gap-1 text-amber-400"><Star size={12} /> {v.rating}</span> : '—'}
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
