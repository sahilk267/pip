'use client';

import { useState, useEffect } from 'react';
import { Award, Star, RefreshCw, Zap, Database } from 'lucide-react';
import { SupplierScorecard } from '@/components/SupplierScorecard';

const CATEGORIES = ['Electronics', 'Manufacturing', 'Raw Materials', 'Logistics', 'Software', 'Services', 'Chemicals', 'Packaging'];

interface Recommendation {
  vendor_id: number;
  rank: number;
  score: number;
  reason: string | null;
}

export default function SuppliersPage() {
  const [vendors, setVendors] = useState<any[]>([]);
  const [selectedVendor, setSelectedVendor] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'scorecard' | 'recommendations'>('scorecard');
  const [recCategory, setRecCategory] = useState('Electronics');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [recLoading, setRecLoading] = useState(false);
  const [ranking, setRanking] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState('');
  const [scorecardKey, setScorecardKey] = useState(0);

  useEffect(() => {
    async function loadVendors() {
      try {
        const res = await fetch('/api/v1/vendors');
        if (res.ok) {
          const data = await res.json();
          const list = Array.isArray(data) ? data : (data.vendors || []);
          setVendors(list.slice(0, 20));
          if (list.length > 0) {
            setSelectedVendor(list[0].id);
          }
        }
      } catch {}
      finally { setLoading(false); }
    }
    loadVendors();
  }, []);

  async function seedScores() {
    setSeeding(true);
    setSeedMsg('');
    try {
      const res = await fetch('/api/v1/suppliers/seed-scores', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSeedMsg(`Scored ${data.scored} vendors successfully.`);
        setScorecardKey((k) => k + 1);
      } else {
        setSeedMsg('Failed to seed scores.');
      }
    } catch {
      setSeedMsg('Error connecting to server.');
    } finally {
      setSeeding(false);
    }
  }

  async function loadRecommendations(category: string) {
    setRecLoading(true);
    try {
      const res = await fetch(`/api/v1/rfq/recommendations/${encodeURIComponent(category)}?limit=10`);
      if (res.ok) {
        const data = await res.json();
        setRecommendations(data.recommendations || []);
      }
    } catch {}
    finally { setRecLoading(false); }
  }

  async function rankVendors(category: string) {
    setRanking(true);
    try {
      await fetch(`/api/v1/rfq/recommendations/rank/${encodeURIComponent(category)}`, { method: 'POST' });
      await loadRecommendations(category);
    } catch {}
    finally { setRanking(false); }
  }

  function handleRecCategory(cat: string) {
    setRecCategory(cat);
    loadRecommendations(cat);
  }

  const vendorName = (id: number) => vendors.find((v) => v.id === id)?.name || `Vendor ${id}`;

  if (loading) return <div className="p-6 text-[#9aacbc]">Loading suppliers...</div>;

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Award size={20} className="text-purple-400" /> Supplier Management
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">Performance ratings, reliability metrics & smart recommendations</p>
        </div>
        <div className="flex gap-2 items-center">
          {activeTab === 'scorecard' && (
            <button
              onClick={seedScores}
              disabled={seeding}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a232e] border border-purple-600/50 hover:border-purple-500 text-purple-400 text-xs rounded transition-colors disabled:opacity-50"
            >
              {seeding ? <RefreshCw size={12} className="animate-spin" /> : <Database size={12} />}
              {seeding ? 'Scoring...' : 'Seed All Scores'}
            </button>
          )}
          {(['scorecard', 'recommendations'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); if (tab === 'recommendations') loadRecommendations(recCategory); }}
              className={`px-3 py-1.5 text-xs rounded transition-colors ${
                activeTab === tab ? 'bg-purple-600 text-white' : 'bg-[#1a232e] border border-[#2a3540] text-[#9aacbc] hover:border-purple-600'
              }`}
            >
              {tab === 'scorecard' ? '🏆 Scorecard' : '🤖 Recommendations'}
            </button>
          ))}
        </div>
      </div>

      {seedMsg && (
        <div className={`text-xs px-4 py-2 rounded border ${seedMsg.includes('successfully') ? 'bg-emerald-900/20 border-emerald-700/40 text-emerald-400' : 'bg-red-900/20 border-red-700/40 text-red-400'}`}>
          {seedMsg}
        </div>
      )}

      {activeTab === 'scorecard' && (
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-1 bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 max-h-[520px] overflow-y-auto">
            <h3 className="text-sm font-semibold text-white mb-3">Vendors</h3>
            {vendors.length === 0 ? (
              <p className="text-xs text-[#9aacbc]">No vendors found. Add vendors first.</p>
            ) : (
              <div className="space-y-2">
                {vendors.map((vendor) => (
                  <button
                    key={vendor.id}
                    onClick={() => setSelectedVendor(vendor.id)}
                    className={`w-full text-left p-2 rounded transition-colors text-xs ${
                      selectedVendor === vendor.id
                        ? 'bg-purple-600/20 border border-purple-600 text-white'
                        : 'bg-[#0f1419] border border-[#2a3540] text-[#9aacbc] hover:border-purple-600'
                    }`}
                  >
                    <p className="font-medium">{vendor.name}</p>
                    <p className="text-[10px] text-[#4a5c6a]">{vendor.country || vendor.category}</p>
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedVendor && (
            <div className="col-span-2">
              <SupplierScorecard key={scorecardKey} vendorId={selectedVendor} />
            </div>
          )}
        </div>
      )}

      {activeTab === 'recommendations' && (
        <div className="space-y-5">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  onClick={() => handleRecCategory(cat)}
                  className={`px-3 py-1 text-xs rounded transition-colors ${
                    recCategory === cat ? 'bg-purple-600 text-white' : 'bg-[#1a232e] border border-[#2a3540] text-[#9aacbc] hover:border-purple-600'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
            <button
              onClick={() => rankVendors(recCategory)}
              disabled={ranking}
              className="ml-auto px-3 py-1.5 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-white text-xs rounded transition-colors flex items-center gap-1"
            >
              {ranking ? <RefreshCw size={12} className="animate-spin" /> : <Zap size={12} />}
              Rank Vendors
            </button>
          </div>

          {recLoading ? (
            <div className="text-center py-10 text-[#9aacbc] text-sm">Loading recommendations...</div>
          ) : recommendations.length === 0 ? (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-8 text-center">
              <Star size={32} className="text-[#4a5c6a] mx-auto mb-3" />
              <p className="text-sm text-[#9aacbc] mb-3">No rankings yet for <strong className="text-white">{recCategory}</strong>.</p>
              <p className="text-xs text-[#4a5c6a] mb-4">Use <strong className="text-purple-400">Seed All Scores</strong> first, then rank.</p>
              <button
                onClick={() => rankVendors(recCategory)}
                disabled={ranking}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded transition-colors flex items-center gap-1 mx-auto"
              >
                <Zap size={14} /> Run Ranking Now
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-[#9aacbc]">Top vendors for <strong className="text-white">{recCategory}</strong> — sorted by composite score</p>
              {recommendations.map((rec, i) => (
                <div key={rec.vendor_id} className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 flex items-center gap-4">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    i === 0 ? 'bg-yellow-500 text-black' : i === 1 ? 'bg-gray-400 text-black' : i === 2 ? 'bg-amber-700 text-white' : 'bg-[#2a3540] text-[#9aacbc]'
                  }`}>
                    {rec.rank}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-white">{vendorName(rec.vendor_id)}</p>
                    {rec.reason && <p className="text-xs text-[#9aacbc] mt-0.5">{rec.reason}</p>}
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-purple-400">{rec.score.toFixed(1)}</p>
                    <p className="text-[10px] text-[#9aacbc]">score</p>
                  </div>
                  <button
                    onClick={() => { setSelectedVendor(rec.vendor_id); setActiveTab('scorecard'); }}
                    className="px-2 py-1 bg-[#2a3540] hover:bg-[#3a4550] text-[#9aacbc] text-xs rounded transition-colors"
                  >
                    View
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
