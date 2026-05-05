'use client';

import { useState, useEffect, useCallback } from 'react';
import { Copy, Plus, RefreshCw, Package, Database } from 'lucide-react';

interface RFQTemplate {
  template_id: number;
  name: string;
  category: string;
  use_count: number;
  created_at: string;
}

interface TemplateDetail {
  template_id: number;
  name: string;
  category: string;
  description: string;
  items: Array<{ product: string; quantity: number; target_price: number | null; lead_time_days: number | null }>;
}

const CATEGORIES = ['Electronics', 'Manufacturing', 'Raw Materials', 'Logistics', 'Software', 'Services', 'Chemicals', 'Packaging'];

export default function RFQTemplatesPage() {
  const [templates, setTemplates] = useState<RFQTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTemplate, setNewTemplate] = useState({ name: '', category: 'Electronics', description: '' });
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateDetail | null>(null);
  const [addingItem, setAddingItem] = useState(false);
  const [itemForm, setItemForm] = useState({ product_name: '', quantity: '', target_price: '', lead_time_days: '' });

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/rfq/templates');
      if (res.ok) {
        const data = await res.json();
        setTemplates(data.templates || []);
      }
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  async function seedTemplates() {
    setSeeding(true);
    setSeedMsg('');
    try {
      const res = await fetch('/api/v1/seed-all', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        const n = data.rfq_templates?.created ?? 0;
        setSeedMsg(n > 0 ? `${n} sample templates seeded!` : 'Templates already seeded.');
        loadTemplates();
      }
    } catch { setSeedMsg('Seed failed.'); }
    finally { setSeeding(false); }
  }

  async function createTemplate() {
    if (!newTemplate.name || !newTemplate.category) return;
    setCreating(true);
    try {
      const params = new URLSearchParams({
        name: newTemplate.name,
        category: newTemplate.category,
        description: newTemplate.description,
        is_public: 'false',
      });
      const res = await fetch(`/api/v1/rfq/templates?${params}`, { method: 'POST' });
      if (res.ok) {
        setNewTemplate({ name: '', category: 'Electronics', description: '' });
        setShowForm(false);
        loadTemplates();
      }
    } catch {}
    finally { setCreating(false); }
  }

  async function loadTemplateDetail(id: number) {
    try {
      const res = await fetch(`/api/v1/rfq/templates/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedTemplate(data);
      }
    } catch {}
  }

  async function addItem() {
    if (!selectedTemplate || !itemForm.product_name || !itemForm.quantity) return;
    setAddingItem(true);
    try {
      const params = new URLSearchParams({
        product_name: itemForm.product_name,
        quantity: itemForm.quantity,
        notes: '',
      });
      if (itemForm.target_price) params.set('target_price', itemForm.target_price);
      if (itemForm.lead_time_days) params.set('lead_time_days', itemForm.lead_time_days);
      const res = await fetch(`/api/v1/rfq/templates/${selectedTemplate.template_id}/items?${params}`, { method: 'POST' });
      if (res.ok) {
        setItemForm({ product_name: '', quantity: '', target_price: '', lead_time_days: '' });
        loadTemplateDetail(selectedTemplate.template_id);
      }
    } catch {}
    finally { setAddingItem(false); }
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Copy size={20} className="text-indigo-400" /> RFQ Templates
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">Save and reuse RFQ patterns for bulk multi-product sourcing</p>
        </div>
        <div className="flex items-center gap-2">
          {seedMsg && <span className="text-xs text-emerald-400">{seedMsg}</span>}
          <button
            onClick={seedTemplates}
            disabled={seeding}
            className="px-3 py-2 bg-[#1a232e] border border-[#2a3540] hover:border-indigo-500 text-[#9aacbc] hover:text-white text-sm rounded flex items-center gap-1 transition-colors disabled:opacity-50"
          >
            {seeding ? <RefreshCw size={13} className="animate-spin" /> : <Database size={13} />}
            Seed Sample Templates
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded flex items-center gap-1 transition-colors"
          >
            <Plus size={14} /> New Template
          </button>
        </div>
      </div>

      {showForm && (
        <div className="bg-[#1a232e] border border-indigo-600/40 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-white">Create Template</h3>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Template name"
              value={newTemplate.name}
              onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
              className="bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
            />
            <select
              value={newTemplate.category}
              onChange={(e) => setNewTemplate({ ...newTemplate, category: e.target.value })}
              className="bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
            >
              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <input
            type="text"
            placeholder="Description (optional)"
            value={newTemplate.description}
            onChange={(e) => setNewTemplate({ ...newTemplate, description: e.target.value })}
            className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
          />
          <div className="flex gap-2">
            <button
              onClick={createTemplate}
              disabled={creating || !newTemplate.name}
              className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-1"
            >
              {creating && <RefreshCw size={12} className="animate-spin" />} Create Template
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="flex-1 py-2 bg-[#2a3540] hover:bg-[#3a4550] text-white text-sm rounded transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-1 space-y-2">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-xs font-semibold text-[#9aacbc] uppercase tracking-wider">Templates</h3>
            <button onClick={loadTemplates} className="text-[#9aacbc] hover:text-white">
              <RefreshCw size={12} />
            </button>
          </div>
          {loading ? (
            <div className="text-center py-6 text-[#9aacbc] text-sm">Loading...</div>
          ) : templates.length === 0 ? (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 text-center">
              <p className="text-xs text-[#9aacbc]">No templates yet. Create one above!</p>
            </div>
          ) : (
            templates.map((template) => (
              <button
                key={template.template_id}
                onClick={() => loadTemplateDetail(template.template_id)}
                className={`w-full text-left bg-[#1a232e] border rounded-lg p-3 transition-colors hover:border-indigo-600 ${
                  selectedTemplate?.template_id === template.template_id ? 'border-indigo-600' : 'border-[#2a3540]'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-semibold text-white">{template.name}</p>
                    <p className="text-xs text-[#9aacbc]">{template.category}</p>
                  </div>
                  <span className="text-[10px] text-[#4a5c6a] bg-[#0f1419] rounded px-1.5 py-0.5">×{template.use_count}</span>
                </div>
              </button>
            ))
          )}
        </div>

        <div className="col-span-2">
          {selectedTemplate ? (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-5 space-y-4">
              <div>
                <h2 className="text-base font-bold text-white">{selectedTemplate.name}</h2>
                <p className="text-xs text-[#9aacbc]">{selectedTemplate.category}{selectedTemplate.description ? ` · ${selectedTemplate.description}` : ''}</p>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-[#9aacbc] uppercase tracking-wider mb-2">Products in Template</h3>
                {selectedTemplate.items.length === 0 ? (
                  <p className="text-xs text-[#9aacbc]">No items added yet.</p>
                ) : (
                  <div className="space-y-1">
                    {selectedTemplate.items.map((item, i) => (
                      <div key={i} className="flex items-center justify-between bg-[#0f1419] rounded p-2 text-xs">
                        <div className="flex items-center gap-2">
                          <Package size={12} className="text-indigo-400" />
                          <span className="text-white">{item.product}</span>
                        </div>
                        <div className="flex gap-4 text-[#9aacbc]">
                          <span>Qty: {item.quantity}</span>
                          {item.target_price != null && <span className="text-emerald-400">Target: ${item.target_price}</span>}
                          {item.lead_time_days != null && <span>{item.lead_time_days}d lead</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="border-t border-[#2a3540] pt-4">
                <h3 className="text-xs font-semibold text-[#9aacbc] uppercase tracking-wider mb-3">Add Product</h3>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="Product name"
                    value={itemForm.product_name}
                    onChange={(e) => setItemForm({ ...itemForm, product_name: e.target.value })}
                    className="bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-xs"
                  />
                  <input
                    type="number"
                    placeholder="Quantity"
                    value={itemForm.quantity}
                    onChange={(e) => setItemForm({ ...itemForm, quantity: e.target.value })}
                    className="bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-xs"
                  />
                  <input
                    type="number"
                    placeholder="Target price (optional)"
                    value={itemForm.target_price}
                    onChange={(e) => setItemForm({ ...itemForm, target_price: e.target.value })}
                    className="bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-xs"
                  />
                  <input
                    type="number"
                    placeholder="Lead time days (optional)"
                    value={itemForm.lead_time_days}
                    onChange={(e) => setItemForm({ ...itemForm, lead_time_days: e.target.value })}
                    className="bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-xs"
                  />
                </div>
                <button
                  onClick={addItem}
                  disabled={addingItem || !itemForm.product_name || !itemForm.quantity}
                  className="mt-2 w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs rounded transition-colors flex items-center justify-center gap-1"
                >
                  {addingItem && <RefreshCw size={12} className="animate-spin" />}
                  <Plus size={12} /> Add Product to Template
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-8 text-center h-full flex flex-col items-center justify-center min-h-48">
              <Copy size={32} className="text-[#4a5c6a] mb-3" />
              <p className="text-sm text-[#9aacbc]">Select a template to view and manage its products</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
