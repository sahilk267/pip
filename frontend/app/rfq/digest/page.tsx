'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Mail, Plus, Trash2, RefreshCw, Send, Clock,
  CheckCircle, AlertCircle, XCircle, BarChart2,
  Settings, History, Link as LinkIcon,
} from 'lucide-react';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

interface DigestConfig {
  id: number;
  recipient_emails: string[];
  schedule_day: number;
  schedule_hour: number;
  window_days: number;
  is_active: boolean;
  last_run_at: string | null;
  schedule_label: string;
}

interface DigestLog {
  id: number;
  triggered_by: string;
  recipients: string[];
  status: string;
  sent_count: number;
  failed_count: number;
  error_message: string | null;
  stats_snapshot: Record<string, unknown>;
  sent_at: string;
}

interface UnsubToken {
  id: number;
  email: string;
  token: string;
  log_id: number | null;
  used: boolean;
  used_at: string | null;
  created_at: string;
}

interface DigestPreview {
  window_days: number;
  stats: {
    total_broadcasts: number;
    vendors_reached: number;
    total_responses: number;
    response_rate_pct: number;
    total_quotes: number;
    avg_unit_price_usd: number | null;
    avg_lead_time_days: number | null;
    top_broadcast: { message: string; rate: number } | null;
    top_winning_vendor: string | null;
  };
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; icon: React.ReactNode }> = {
    success: { color: 'text-emerald-400 bg-emerald-900/30 border-emerald-800', icon: <CheckCircle size={11} /> },
    partial: { color: 'text-amber-400 bg-amber-900/30 border-amber-800', icon: <AlertCircle size={11} /> },
    failed: { color: 'text-rose-400 bg-rose-900/30 border-rose-800', icon: <XCircle size={11} /> },
    pending: { color: 'text-slate-400 bg-slate-900/30 border-slate-700', icon: <Clock size={11} /> },
  };
  const s = map[status] ?? map.pending;
  return (
    <span className={`inline-flex items-center gap-1 text-xs border rounded px-1.5 py-0.5 ${s.color}`}>
      {s.icon} {status}
    </span>
  );
}

export default function RFQDigestPage() {
  const [config, setConfig] = useState<DigestConfig | null>(null);
  const [logs, setLogs] = useState<DigestLog[]>([]);
  const [tokens, setTokens] = useState<UnsubToken[]>([]);
  const [preview, setPreview] = useState<DigestPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<{ status: string; message: string } | null>(null);
  const [activeTab, setActiveTab] = useState<'config' | 'history' | 'preview' | 'unsubscribe'>('config');

  // Editable config state
  const [emails, setEmails] = useState<string[]>([]);
  const [newEmail, setNewEmail] = useState('');
  const [schedDay, setSchedDay] = useState(0);
  const [schedHour, setSchedHour] = useState(8);
  const [windowDays, setWindowDays] = useState(7);
  const [isActive, setIsActive] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cfgRes, logRes, prevRes, tokRes] = await Promise.all([
        fetch('/api/v1/rfq/digest/config'),
        fetch('/api/v1/rfq/digest/history?limit=20'),
        fetch('/api/v1/rfq/digest/preview?window_days=7'),
        fetch('/api/v1/rfq/digest/unsubscribe-tokens?limit=50'),
      ]);
      if (cfgRes.ok) {
        const cfg: DigestConfig = await cfgRes.json();
        setConfig(cfg);
        setEmails(cfg.recipient_emails || []);
        setSchedDay(cfg.schedule_day);
        setSchedHour(cfg.schedule_hour);
        setWindowDays(cfg.window_days);
        setIsActive(cfg.is_active);
      }
      if (logRes.ok) setLogs(await logRes.json());
      if (prevRes.ok) setPreview(await prevRes.json());
      if (tokRes.ok) setTokens(await tokRes.json());
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  function addEmail() {
    const e = newEmail.trim().toLowerCase();
    if (!e || emails.includes(e) || !e.includes('@')) return;
    setEmails([...emails, e]);
    setNewEmail('');
  }

  async function saveConfig() {
    setSaving(true);
    try {
      const params = new URLSearchParams({
        schedule_day: String(schedDay),
        schedule_hour: String(schedHour),
        window_days: String(windowDays),
        is_active: String(isActive),
      });
      const res = await fetch(`/api/v1/rfq/digest/config?${params}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(emails),
      });
      if (res.ok) setConfig(await res.json());
    } catch {}
    finally { setSaving(false); }
  }

  async function sendNow() {
    setSending(true);
    setSendResult(null);
    try {
      const res = await fetch('/api/v1/rfq/digest/send-now', { method: 'POST' });
      if (res.ok) {
        const d = await res.json();
        setSendResult({
          status: d.status,
          message:
            d.status === 'success'
              ? `Digest sent to ${d.sent_count} recipient(s) — each with a unique unsubscribe link.`
              : d.reason === 'no_recipients'
              ? 'No recipients configured. Add at least one email first.'
              : `Partial send: ${d.sent_count} sent, ${d.failed_count} failed.`,
        });
        await load();
      }
    } catch {
      setSendResult({ status: 'failed', message: 'Network error.' });
    } finally {
      setSending(false);
    }
  }

  const unsubUsed = tokens.filter((t) => t.used).length;
  const stats = preview?.stats;

  const TABS = [
    { id: 'config' as const, label: 'Configuration', icon: <Settings size={13} /> },
    { id: 'preview' as const, label: 'Email Preview', icon: <BarChart2 size={13} /> },
    { id: 'history' as const, label: `History${logs.length ? ` (${logs.length})` : ''}`, icon: <History size={13} /> },
    { id: 'unsubscribe' as const, label: `Unsubscribe${tokens.length ? ` (${unsubUsed}/${tokens.length})` : ''}`, icon: <LinkIcon size={13} /> },
  ];

  return (
    <div className="p-6 space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Mail size={20} className="text-sky-400" /> RFQ Digest Reports
          </h1>
          <p className="text-sm text-[#9aacbc] mt-0.5">
            Automated weekly email summary of RFQ performance — each recipient gets a unique one-click unsubscribe link
          </p>
        </div>
        <div className="flex items-center gap-3">
          {sendResult && (
            <span className={`text-xs max-w-xs text-right ${
              sendResult.status === 'success' ? 'text-emerald-400'
              : sendResult.status === 'partial' ? 'text-amber-400'
              : 'text-rose-400'
            }`}>
              {sendResult.message}
            </span>
          )}
          <button
            onClick={sendNow}
            disabled={sending}
            className="px-3 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm rounded flex items-center gap-1.5 transition-colors"
          >
            {sending ? <RefreshCw size={13} className="animate-spin" /> : <Send size={13} />}
            Send Now
          </button>
        </div>
      </div>

      {/* Status strip */}
      {config && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 flex flex-wrap items-center gap-5">
          <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${config.is_active ? 'bg-emerald-400' : 'bg-[#4a5c6a]'}`} />
            <span className="text-sm text-white font-medium">{config.is_active ? 'Active' : 'Paused'}</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-[#9aacbc]">
            <Clock size={13} /> {config.schedule_label}
          </div>
          <div className="flex items-center gap-1.5 text-sm text-[#9aacbc]">
            <Mail size={13} /> {config.recipient_emails.length} recipient{config.recipient_emails.length !== 1 ? 's' : ''}
          </div>
          {tokens.length > 0 && (
            <div className="flex items-center gap-1.5 text-sm text-[#9aacbc]">
              <LinkIcon size={13} /> {unsubUsed} unsubscribed / {tokens.length} tokens
            </div>
          )}
          <div className="ml-auto text-xs text-[#4a5c6a]">
            {config.last_run_at
              ? `Last sent: ${new Date(config.last_run_at).toLocaleString()}`
              : 'Never sent yet'}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#2a3540]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'border-sky-500 text-white'
                : 'border-transparent text-[#9aacbc] hover:text-white'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab: Configuration ───────────────────────────────────────────── */}
      {activeTab === 'config' && (
        <div className="grid grid-cols-2 gap-5">

          {/* Recipients */}
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-5 space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Recipients</h3>
              <p className="text-xs text-[#4a5c6a] mt-0.5">
                Every email sent includes a unique unsubscribe link for that recipient.
              </p>
            </div>
            <div className="space-y-2">
              {emails.map((e) => (
                <div key={e} className="flex items-center justify-between bg-[#0f1419] rounded px-3 py-2">
                  <span className="text-sm text-[#9aacbc]">{e}</span>
                  <button
                    onClick={() => setEmails(emails.filter((x) => x !== e))}
                    className="text-[#4a5c6a] hover:text-rose-400 transition-colors"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              {emails.length === 0 && (
                <p className="text-xs text-[#4a5c6a] text-center py-4">No recipients yet. Add one below.</p>
              )}
            </div>
            <div className="flex gap-2">
              <input
                type="email"
                placeholder="email@company.com"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addEmail()}
                className="flex-1 bg-[#0f1419] border border-[#2a3540] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-sky-500"
              />
              <button
                onClick={addEmail}
                className="px-3 py-2 bg-sky-700 hover:bg-sky-600 text-white text-sm rounded transition-colors"
              >
                <Plus size={14} />
              </button>
            </div>
          </div>

          {/* Schedule */}
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-5 space-y-4">
            <h3 className="text-sm font-semibold text-white">Schedule</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[#9aacbc] uppercase tracking-wider">Day of Week</label>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {DAYS.map((d, i) => (
                    <button
                      key={d}
                      onClick={() => setSchedDay(i)}
                      className={`px-2.5 py-1 text-xs rounded transition-colors ${
                        schedDay === i ? 'bg-sky-600 text-white' : 'bg-[#0f1419] text-[#9aacbc] hover:text-white'
                      }`}
                    >
                      {d.slice(0, 3)}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-[#9aacbc] uppercase tracking-wider">
                  Send Time (UTC) — {schedHour.toString().padStart(2, '0')}:00
                </label>
                <input
                  type="range" min={0} max={23} value={schedHour}
                  onChange={(e) => setSchedHour(Number(e.target.value))}
                  className="w-full mt-2 accent-sky-500"
                />
                <div className="flex justify-between text-xs text-[#4a5c6a] mt-0.5">
                  <span>00:00</span><span>12:00</span><span>23:00</span>
                </div>
              </div>
              <div>
                <label className="text-xs text-[#9aacbc] uppercase tracking-wider">Stats Window</label>
                <div className="mt-1.5 flex gap-1">
                  {[7, 14, 30].map((d) => (
                    <button
                      key={d}
                      onClick={() => setWindowDays(d)}
                      className={`px-3 py-1 text-xs rounded transition-colors ${
                        windowDays === d ? 'bg-sky-600 text-white' : 'bg-[#0f1419] text-[#9aacbc] hover:text-white'
                      }`}
                    >
                      {d} days
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-sm text-[#9aacbc]">Digest enabled</span>
                <button
                  onClick={() => setIsActive(!isActive)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${isActive ? 'bg-sky-600' : 'bg-[#2a3540]'}`}
                >
                  <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${isActive ? 'left-5' : 'left-0.5'}`} />
                </button>
              </div>
            </div>
            <button
              onClick={saveConfig}
              disabled={saving}
              className="w-full py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-1.5"
            >
              {saving ? <RefreshCw size={13} className="animate-spin" /> : null}
              Save Configuration
            </button>
          </div>
        </div>
      )}

      {/* ── Tab: Email Preview ───────────────────────────────────────────── */}
      {activeTab === 'preview' && (
        <div className="space-y-4">
          <p className="text-xs text-[#9aacbc]">
            Live preview of the next digest email based on the last {windowDays} days of data. The real email also contains a personalised unsubscribe link at the bottom.
          </p>
          {loading || !stats ? (
            <div className="text-center py-12 text-[#9aacbc] text-sm">Loading preview…</div>
          ) : (
            <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-6 space-y-5">
              <div className="border-b border-[#2a3540] pb-4">
                <div className="inline-block bg-[#1e3a5f] text-sky-400 text-xs font-bold uppercase tracking-widest px-2 py-1 rounded mb-2">
                  Weekly RFQ Digest
                </div>
                <h2 className="text-lg font-bold text-white">RFQ Performance Summary</h2>
                <p className="text-sm text-[#9aacbc]">Last {windowDays} days</p>
              </div>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: 'Broadcasts', value: stats.total_broadcasts, color: 'text-sky-400' },
                  { label: 'Response Rate', value: `${stats.response_rate_pct}%`, color: 'text-emerald-400' },
                  { label: 'Avg Quote Price', value: stats.avg_unit_price_usd ? `$${stats.avg_unit_price_usd.toLocaleString()}` : '—', color: 'text-amber-400' },
                  { label: 'Avg Lead Time', value: stats.avg_lead_time_days ? `${stats.avg_lead_time_days}d` : '—', color: 'text-violet-400' },
                ].map((k) => (
                  <div key={k.label} className="bg-[#0f1419] border border-[#2a3540] rounded p-3 text-center">
                    <div className={`text-xl font-bold ${k.color}`}>{k.value}</div>
                    <div className="text-[10px] text-[#4a5c6a] uppercase tracking-wider mt-1">{k.label}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-2 pt-1">
                <p className="text-xs text-[#4a5c6a] uppercase tracking-wider">Highlights</p>
                {stats.top_broadcast && (
                  <div className="flex justify-between text-sm border-b border-[#1e2a34] pb-2">
                    <span className="text-[#9aacbc]">{stats.top_broadcast.message}</span>
                    <span className="text-emerald-400 font-semibold">{stats.top_broadcast.rate}% response rate</span>
                  </div>
                )}
                <div className="flex justify-between text-sm">
                  <span className="text-[#9aacbc]">Top winning vendor</span>
                  <span className="text-amber-400 font-semibold">🏆 {stats.top_winning_vendor ?? '—'}</span>
                </div>
              </div>
              <div className="text-xs text-[#4a5c6a] pt-2 border-t border-[#2a3540]">
                {stats.vendors_reached} vendors reached · {stats.total_responses} responses · {stats.total_quotes} quotes
              </div>
              {/* Unsubscribe link preview */}
              <div className="bg-[#0f1419] border border-[#2a3540] rounded p-3 text-center">
                <span className="text-[10px] text-[#4a5c6a] underline cursor-default">
                  Unsubscribe from this digest
                </span>
                <span className="text-[10px] text-[#2a3540] ml-2">(unique token per recipient)</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: History ─────────────────────────────────────────────────── */}
      {activeTab === 'history' && (
        <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg overflow-hidden">
          {loading ? (
            <div className="text-center py-12 text-[#9aacbc] text-sm">Loading…</div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12">
              <History size={32} className="text-[#2a3540] mx-auto mb-3" />
              <p className="text-[#9aacbc] text-sm">No digests sent yet.</p>
              <p className="text-[#4a5c6a] text-xs mt-1">Click <strong>Send Now</strong> to send your first digest.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#2a3540] text-[10px] text-[#4a5c6a] uppercase tracking-wider">
                  <th className="text-left p-4">Sent At</th>
                  <th className="text-left p-4">Triggered By</th>
                  <th className="text-left p-4">Recipients</th>
                  <th className="text-center p-4 w-24">Status</th>
                  <th className="text-center p-4 w-20">Sent</th>
                  <th className="text-left p-4">Stats Snapshot</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2a34]">
                {logs.map((log) => {
                  const snap = log.stats_snapshot as Record<string, unknown>;
                  return (
                    <tr key={log.id} className="hover:bg-[#1e2a34] transition-colors">
                      <td className="p-4">
                        <p className="text-sm text-white">{new Date(log.sent_at).toLocaleDateString()}</p>
                        <p className="text-xs text-[#4a5c6a]">{new Date(log.sent_at).toLocaleTimeString()}</p>
                      </td>
                      <td className="p-4">
                        <span className={`text-xs px-2 py-0.5 rounded ${log.triggered_by === 'manual' ? 'bg-sky-900/40 text-sky-400' : 'bg-purple-900/40 text-purple-400'}`}>
                          {log.triggered_by}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-[#9aacbc]">
                        {(log.recipients || []).join(', ') || '—'}
                      </td>
                      <td className="p-4 text-center">
                        <StatusBadge status={log.status} />
                        {log.error_message && (
                          <p className="text-[10px] text-rose-400 mt-1 max-w-[140px] truncate" title={log.error_message}>
                            {log.error_message}
                          </p>
                        )}
                      </td>
                      <td className="p-4 text-center">
                        <span className="text-sm text-emerald-400 font-semibold">{log.sent_count}</span>
                        {log.failed_count > 0 && (
                          <span className="text-xs text-rose-400 ml-1">+{log.failed_count} fail</span>
                        )}
                      </td>
                      <td className="p-4 text-xs text-[#9aacbc]">
                        {snap && typeof snap.total_broadcasts === 'number'
                          ? `${snap.total_broadcasts} broadcasts · ${snap.response_rate_pct as number}% response${snap.avg_unit_price_usd ? ` · $${(snap.avg_unit_price_usd as number).toFixed(2)} avg` : ''}`
                          : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Tab: Unsubscribe Tokens ──────────────────────────────────────── */}
      {activeTab === 'unsubscribe' && (
        <div className="space-y-4">
          {/* Explainer */}
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg p-5">
            <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
              <LinkIcon size={14} className="text-sky-400" /> How Unsubscribe Tokens Work
            </h3>
            <ul className="text-sm text-[#9aacbc] space-y-1.5">
              <li>• Each time a digest is sent, a <strong className="text-white">unique UUID token</strong> is generated per recipient.</li>
              <li>• The token is embedded as a link in the email footer: <code className="text-xs bg-[#0f1419] px-1 py-0.5 rounded">GET /api/v1/rfq/digest/unsubscribe?token=…</code></li>
              <li>• Clicking the link removes that email from the recipient list and marks the token as used — no login required.</li>
              <li>• Tokens are single-use and tied to a specific send event. Re-sending issues new tokens.</li>
            </ul>
            {tokens.length > 0 && (
              <div className="mt-4 flex gap-4 text-sm">
                <span className="text-[#9aacbc]">Total tokens: <strong className="text-white">{tokens.length}</strong></span>
                <span className="text-[#9aacbc]">Used (unsubscribed): <strong className="text-rose-400">{unsubUsed}</strong></span>
                <span className="text-[#9aacbc]">Active: <strong className="text-emerald-400">{tokens.length - unsubUsed}</strong></span>
              </div>
            )}
          </div>

          {/* Token table */}
          <div className="bg-[#1a232e] border border-[#2a3540] rounded-lg overflow-hidden">
            {loading ? (
              <div className="text-center py-12 text-[#9aacbc] text-sm">Loading…</div>
            ) : tokens.length === 0 ? (
              <div className="text-center py-12">
                <LinkIcon size={32} className="text-[#2a3540] mx-auto mb-3" />
                <p className="text-[#9aacbc] text-sm">No tokens yet.</p>
                <p className="text-[#4a5c6a] text-xs mt-1">Tokens are created automatically each time a digest is sent.</p>
              </div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#2a3540] text-[10px] text-[#4a5c6a] uppercase tracking-wider">
                    <th className="text-left p-4">Recipient</th>
                    <th className="text-left p-4">Token</th>
                    <th className="text-center p-4 w-28">Status</th>
                    <th className="text-left p-4">Used At</th>
                    <th className="text-left p-4">Created</th>
                    <th className="text-center p-4 w-20">Digest #</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2a34]">
                  {tokens.map((tok) => (
                    <tr key={tok.id} className="hover:bg-[#1e2a34] transition-colors">
                      <td className="p-4 text-sm text-[#9aacbc]">{tok.email}</td>
                      <td className="p-4">
                        <code className="text-xs text-[#4a5c6a] bg-[#0f1419] px-1.5 py-0.5 rounded font-mono">
                          {tok.token.slice(0, 8)}…{tok.token.slice(-4)}
                        </code>
                      </td>
                      <td className="p-4 text-center">
                        {tok.used ? (
                          <span className="inline-flex items-center gap-1 text-xs border rounded px-1.5 py-0.5 text-rose-400 bg-rose-900/20 border-rose-800">
                            <XCircle size={11} /> unsubscribed
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs border rounded px-1.5 py-0.5 text-emerald-400 bg-emerald-900/20 border-emerald-800">
                            <CheckCircle size={11} /> active
                          </span>
                        )}
                      </td>
                      <td className="p-4 text-xs text-[#4a5c6a]">
                        {tok.used_at ? new Date(tok.used_at).toLocaleString() : '—'}
                      </td>
                      <td className="p-4 text-xs text-[#4a5c6a]">
                        {new Date(tok.created_at).toLocaleString()}
                      </td>
                      <td className="p-4 text-center text-xs text-[#9aacbc]">
                        {tok.log_id ? `#${tok.log_id}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
