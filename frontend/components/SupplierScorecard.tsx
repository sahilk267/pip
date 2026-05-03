'use client';

import { useState, useEffect } from 'react';
import { Star, TrendingUp } from 'lucide-react';

interface Scorecard {
  vendor_id: number;
  vendor_name: string;
  total_score: number;
  grade: string;
  breakdown: Record<string, number>;
  recent_events: Array<{ event_type: string; score: number; date: string }>;
}

export function SupplierScorecard({ vendorId }: { vendorId: number }) {
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadScorecard() {
      try {
        const res = await fetch(`/api/v1/suppliers/${vendorId}/scorecard`);
        if (res.ok) {
          const data = await res.json();
          setScorecard(data);
        }
      } catch {}
      finally {
        setLoading(false);
      }
    }
    loadScorecard();
  }, [vendorId]);

  if (loading) return <div className="text-sm text-[#9aacbc]">Loading scorecard...</div>;
  if (!scorecard) return <div className="text-sm text-red-400">No data</div>;

  const gradeColor = scorecard.grade[0] === 'A' ? 'text-emerald-400' : scorecard.grade[0] === 'B' ? 'text-blue-400' : 'text-orange-400';

  return (
    <div className="space-y-4 bg-[#1a232e] border border-[#2a3540] rounded-lg p-4">
      {/* Header with score */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">{scorecard.vendor_name}</h3>
          <p className="text-xs text-[#9aacbc]">Overall Rating</p>
        </div>
        <div className="text-right">
          <div className={`text-3xl font-bold ${gradeColor}`}>{scorecard.grade}</div>
          <div className="text-xl font-bold text-white">{scorecard.total_score.toFixed(0)}/100</div>
        </div>
      </div>

      {/* Score breakdown */}
      <div className="grid grid-cols-5 gap-2">
        {Object.entries(scorecard.breakdown).map(([key, value]) => (
          <div key={key} className="bg-[#0f1419] rounded p-2">
            <p className="text-[10px] text-[#9aacbc] capitalize">{key}</p>
            <p className="text-sm font-bold text-white">{value.toFixed(0)}</p>
            <div className="w-full h-1 bg-[#2a3540] rounded mt-1">
              <div className="h-full bg-blue-500 rounded" style={{ width: `${(value / 20) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>

      {/* Recent events */}
      {scorecard.recent_events.length > 0 && (
        <div className="pt-2 border-t border-[#2a3540]">
          <p className="text-xs text-[#9aacbc] mb-2">Recent Activity</p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {scorecard.recent_events.map((e, i) => (
              <div key={i} className="flex items-center justify-between text-[10px] p-1 bg-[#0f1419] rounded">
                <span className="text-[#9aacbc]">{e.event_type}</span>
                <span className="text-white font-semibold">{e.score.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
