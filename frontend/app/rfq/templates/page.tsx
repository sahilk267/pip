'use client';

import { useState, useCallback } from 'react';
import { Copy, Plus, Trash2 } from 'lucide-react';

interface RFQTemplate {
  template_id: number;
  name: string;
  category: string;
  use_count: number;
  created_at: string;
}

export default function RFQTemplatesPage() {
  const [templates, setTemplates] = useState<RFQTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [newTemplate, setNewTemplate] = useState({ name: '', category: '' });
  const [showForm, setShowForm] = useState(false);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/rfq/templates');
      if (res.ok) {
        const data = await res.json();
        setTemplates(data.templates || []);
      }
    } catch {}
    finally {
      setLoading(false);
    }
  }, []);

  const createTemplate = async () => {
    if (!newTemplate.name || !newTemplate.category) return;
    try {
      const res = await fetch('/api/v1/rfq/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newTemplate.name,
          category: newTemplate.category,
          description: '',
          is_public: false,
        }),
      });
      if (res.ok) {
        setNewTemplate({ name: '', category: '' });
        setShowForm(false);
        loadTemplates();
      }
    } catch {}
  };

  if (loading && templates.length === 0) {
    return <div className="p-6 text-[#9aacbc]">Loading templates...</div>;
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Copy size={20} className="text-indigo-400" /> RFQ Templates
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">Save and reuse RFQ patterns for bulk sourcing</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded flex items-center gap-1 transition-colors"
        >
          <Plus size={14} /> New Template
        </button>
      </div>

      {showForm && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 space-y-3">
          <input
            type="text"
            placeholder="Template name"
            value={newTemplate.name}
            onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
            className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
          />
          <input
            type="text"
            placeholder="Category (e.g., Electronics)"
            value={newTemplate.category}
            onChange={(e) => setNewTemplate({ ...newTemplate, category: e.target.value })}
            className="w-full bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm"
          />
          <div className="flex gap-2">
            <button
              onClick={createTemplate}
              className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded transition-colors"
            >
              Create
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

      <div className="grid gap-3">
        {templates.length === 0 ? (
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-6 text-center">
            <p className="text-sm text-[#9aacbc]">No templates yet. Create one to get started!</p>
          </div>
        ) : (
          templates.map((template) => (
            <div key={template.template_id} className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 flex items-center justify-between hover:border-indigo-600 transition-colors">
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-white">{template.name}</h3>
                <p className="text-xs text-[#9aacbc]">{template.category}</p>
                <p className="text-xs text-[#4a5c6a] mt-1">Used {template.use_count} times</p>
              </div>
              <button className="p-2 hover:bg-[#2a3540] rounded transition-colors">
                <Copy size={14} className="text-[#9aacbc]" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
