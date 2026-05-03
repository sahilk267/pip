'use client';

import { useState } from 'react';
import { Send, Clock, Zap, CheckCircle } from 'lucide-react';

interface Vendor {
  id: number;
  name: string;
  email?: string;
}

interface Quote {
  vendor_id: number;
  vendor_name: string;
  unit_price?: number;
}

const REPLY_TYPES = [
  { id: 'rfq_received', label: 'RFQ Received', desc: 'Confirm receipt & next steps' },
  { id: 'escalation_reminder', label: 'Reminder', desc: 'Nudge for missing quotes' },
  { id: 'quote_acknowledged', label: 'Acknowledge Quote', desc: 'Thank them & compare' },
  { id: 'winner_notification', label: 'Winner Notification', desc: 'Order award message' },
];

export function VendorBotPanel({ rfqId, vendors, quotes }: { rfqId: number; vendors: Vendor[]; quotes: Quote[] }) {
  const [selected, setSelected] = useState<number | null>(null);
  const [replyType, setReplyType] = useState<string>('rfq_received');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const quotedVendorIds = new Set(quotes.map((q) => q.vendor_id));
  const pendingVendors = vendors.filter((v) => !quotedVendorIds.has(v.id));

  async function sendReply() {
    if (!selected) return;
    setSending(true);
    try {
      const res = await fetch(`/api/v1/rfq/vendor-engagement/send-reply/${rfqId}/${selected}?reply_type=${replyType}`, {
        method: 'POST',
      });
      if (res.ok) {
        setResult(`Message sent to ${vendors.find((v) => v.id === selected)?.name}`);
        setTimeout(() => setResult(null), 3000);
        setSelected(null);
      }
    } catch {
      setResult('Failed to send');
    } finally {
      setSending(false);
    }
  }

  if (vendors.length === 0) return null;

  return (
    <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 space-y-3">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
        <Zap size={14} className="text-purple-400" /> Vendor Engagement Bot
      </h3>

      {/* Pending vendors quick select */}
      {pendingVendors.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-[#9aacbc]">Awaiting quotes from {pendingVendors.length} vendor{pendingVendors.length > 1 ? 's' : ''}:</p>
          <div className="grid grid-cols-2 gap-2">
            {pendingVendors.map((v) => (
              <button
                key={v.id}
                onClick={() => setSelected(v.id)}
                className={`text-xs px-3 py-2 rounded border transition-colors ${
                  selected === v.id
                    ? 'bg-purple-600/30 border-purple-600 text-purple-400'
                    : 'bg-[#0f1419] border-[#2a3540] text-[#9aacbc] hover:border-purple-600/50'
                }`}
              >
                {v.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Reply type selector */}
      {selected && (
        <div className="space-y-2">
          <p className="text-xs text-[#9aacbc] font-medium">Message Type:</p>
          <div className="grid grid-cols-2 gap-2">
            {REPLY_TYPES.map((t) => (
              <button
                key={t.id}
                onClick={() => setReplyType(t.id)}
                className={`text-left text-xs p-2 rounded border transition-colors ${
                  replyType === t.id
                    ? 'bg-blue-600/30 border-blue-600 text-blue-400'
                    : 'bg-[#0f1419] border-[#2a3540] text-[#9aacbc] hover:border-blue-600/50'
                }`}
              >
                <div className="font-medium">{t.label}</div>
                <div className="text-[10px] opacity-70">{t.desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Send button */}
      {selected && (
        <button
          onClick={sendReply}
          disabled={sending}
          className="w-full py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm rounded flex items-center justify-center gap-2 transition-colors"
        >
          <Send size={12} /> {sending ? 'Sending...' : 'Send Message'}
        </button>
      )}

      {result && (
        <div className="text-xs p-2 bg-emerald-600/20 border border-emerald-600/50 rounded text-emerald-400 flex items-center gap-2">
          <CheckCircle size={12} /> {result}
        </div>
      )}

      {/* Stats */}
      <div className="text-[10px] text-[#4a5c6a] space-y-0.5 pt-2 border-t border-[#2a3540]">
        <div>• {quotes.length} quote{quotes.length > 1 ? 's' : ''} received</div>
        <div>• {pendingVendors.length} awaiting response</div>
      </div>
    </div>
  );
}
