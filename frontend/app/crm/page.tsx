'use client';

import { useEffect, useState } from 'react';
import { Users, Search, Plus, ChevronDown } from 'lucide-react';
import { leadApi } from '@/lib/api';

interface Lead {
  id: number;
  full_name: string;
  email?: string;
  company?: string;
  stage: string;
  segment: string;
  lead_score?: number;
  source?: string;
  created_at?: string;
}

const STAGES = ['lead', 'qualified', 'proposal', 'negotiation', 'closed_won', 'closed_lost'];
const stageColor: Record<string, string> = {
  lead: 'bg-[#2a3540] text-[#9aacbc]',
  qualified: 'bg-blue-600/20 text-blue-400',
  proposal: 'bg-purple-600/20 text-purple-400',
  negotiation: 'bg-amber-600/20 text-amber-400',
  closed_won: 'bg-emerald-600/20 text-emerald-400',
  closed_lost: 'bg-red-600/20 text-red-400',
};

export default function CRMPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ full_name: '', email: '', company: '', source: '', segment: 'unsegmented' });
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await leadApi.list({ limit: 200, stage: stageFilter || undefined });
      setLeads(Array.isArray(data) ? data : data.items ?? []);
    } catch { /* no-op */ }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [stageFilter]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await leadApi.create(form);
      setShowAdd(false);
      setForm({ full_name: '', email: '', company: '', source: '', segment: 'unsegmented' });
      await load();
    } catch { /* no-op */ }
    finally { setSaving(false); }
  }

  async function handleStageChange(id: number, stage: string) {
    setUpdatingId(id);
    try {
      await leadApi.updateStage(id, stage);
      setLeads((prev) => prev.map((l) => (l.id === id ? { ...l, stage } : l)));
    } catch { /* no-op */ }
    finally { setUpdatingId(null); }
  }

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  const filtered = leads.filter((l) =>
    !search || [l.full_name, l.email, l.company].some((v) => v?.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Users size={20} className="text-purple-400" /> CRM / Leads
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">{filtered.length} lead{filtered.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={14} /> Add Lead
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9aacbc]" />
          <input
            className="w-full bg-[#1a232e] border border-[#2a3540] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-[#9aacbc] focus:outline-none focus:border-purple-500"
            placeholder="Search leads…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="relative">
          <select
            className="bg-[#1a232e] border border-[#2a3540] rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-purple-500 appearance-none pr-8"
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
          >
            <option value="">All Stages</option>
            {STAGES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
          <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#9aacbc] pointer-events-none" />
        </div>
      </div>

      {/* Stage pills summary */}
      <div className="flex flex-wrap gap-2">
        {STAGES.map((s) => {
          const count = leads.filter((l) => l.stage === s).length;
          return (
            <button
              key={s}
              onClick={() => setStageFilter(stageFilter === s ? '' : s)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                stageFilter === s ? stageColor[s] + ' border-transparent' : 'bg-transparent border-[#2a3540] text-[#9aacbc] hover:border-[#3a4550]'
              }`}
            >
              {s.replace('_', ' ')} · {count}
            </button>
          );
        })}
      </div>

      {/* Add Form */}
      {showAdd && (
        <form onSubmit={handleAdd} className="bg-[#1a232e] border border-[#2a3540] rounded-xl p-5 grid grid-cols-2 gap-4">
          <h3 className="col-span-2 text-sm font-semibold text-white">New Lead</h3>
          {([['full_name', 'Full Name *'], ['email', 'Email'], ['company', 'Company'], ['source', 'Source']] as [keyof typeof form, string][]).map(([k, label]) => (
            <div key={k}>
              <label className="block text-xs text-[#9aacbc] mb-1">{label}</label>
              <input
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                value={form[k]}
                onChange={f(k)}
                required={k === 'full_name'}
              />
            </div>
          ))}
          <div className="col-span-2 flex gap-3 justify-end">
            <button type="button" onClick={() => setShowAdd(false)} className="text-sm text-[#9aacbc] hover:text-white px-4 py-2">Cancel</button>
            <button type="submit" disabled={saving} className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm px-5 py-2 rounded-lg">
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-[#9aacbc] py-8 text-center">No leads found.</p>
      ) : (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#2a3540] text-[#9aacbc] text-xs uppercase tracking-wide">
                <th className="px-4 py-3 text-left">Lead</th>
                <th className="px-4 py-3 text-left">Company</th>
                <th className="px-4 py-3 text-left">Source</th>
                <th className="px-4 py-3 text-left">Score</th>
                <th className="px-4 py-3 text-left">Stage</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((lead) => (
                <tr key={lead.id} className="border-b border-[#2a3540] last:border-0 hover:bg-[#1e2c3a] transition-colors">
                  <td className="px-4 py-3">
                    <p className="text-white font-medium">{lead.full_name}</p>
                    {lead.email && <p className="text-xs text-[#9aacbc]">{lead.email}</p>}
                  </td>
                  <td className="px-4 py-3 text-[#9aacbc]">{lead.company || '—'}</td>
                  <td className="px-4 py-3 text-[#9aacbc]">{lead.source || '—'}</td>
                  <td className="px-4 py-3">
                    <span className="text-white font-medium">{lead.lead_score ?? 0}</span>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      className={`text-xs px-2 py-1 rounded-full border-0 cursor-pointer ${stageColor[lead.stage] || stageColor.lead} appearance-none`}
                      value={lead.stage}
                      disabled={updatingId === lead.id}
                      onChange={(e) => handleStageChange(lead.id, e.target.value)}
                    >
                      {STAGES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                    </select>
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
