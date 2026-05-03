'use client';

import { useEffect, useState } from 'react';
import { Bell, CheckCircle, AlertTriangle, Info, XCircle, Activity, RefreshCw, Shield } from 'lucide-react';
import { monitoringApi, analyticsApi } from '@/lib/api';

interface Alert {
  id: number;
  alert_type: string;
  severity: string;
  message: string;
  status: string;
  resolved_at?: string;
  created_at?: string;
}

interface AuditEntry {
  id: number;
  action: string;
  entity_type?: string;
  performed_by?: string;
  created_at?: string;
  detail?: Record<string, unknown>;
}

const severityConfig: Record<string, { icon: typeof Bell; color: string; bg: string }> = {
  critical: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/20 border-red-700/50' },
  high: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-900/20 border-orange-700/50' },
  medium: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-900/20 border-amber-700/50' },
  low: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-900/20 border-blue-700/50' },
  info: { icon: Info, color: 'text-slate-400', bg: 'bg-slate-800/50 border-slate-700' },
};

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function NotificationsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'alerts' | 'audit'>('alerts');
  const [filter, setFilter] = useState<'all' | 'open' | 'resolved'>('all');

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  async function load() {
    try {
      const [mon, logs] = await Promise.allSettled([
        monitoringApi.dashboard(),
        analyticsApi.auditLogs({ limit: 50 }),
      ]);

      if (mon.status === 'fulfilled') {
        const data = mon.value as { alerts?: Alert[] };
        setAlerts(Array.isArray(data?.alerts) ? data.alerts : []);
      }
      if (logs.status === 'fulfilled') {
        setAuditLogs(Array.isArray(logs.value) ? logs.value : []);
      }
    } finally {
      setLoading(false);
    }
  }

  const filteredAlerts = alerts.filter((a) => {
    if (filter === 'open') return a.status !== 'resolved';
    if (filter === 'resolved') return a.status === 'resolved';
    return true;
  });

  const openCount = alerts.filter((a) => a.status !== 'resolved').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bell className="text-amber-400" size={24} />
            Notifications & Activity
            {openCount > 0 && (
              <span className="bg-red-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                {openCount}
              </span>
            )}
          </h1>
          <p className="text-slate-400 mt-1">System alerts, events, and audit trail</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Alerts', value: alerts.length, color: 'text-white' },
          { label: 'Open', value: openCount, color: 'text-red-400' },
          { label: 'Resolved', value: alerts.filter((a) => a.status === 'resolved').length, color: 'text-emerald-400' },
          { label: 'Audit Events', value: auditLogs.length, color: 'text-blue-400' },
        ].map((s) => (
          <div key={s.label} className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
            <p className="text-slate-400 text-sm">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color} mt-1`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-800/50 p-1 rounded-lg w-fit">
        {(['alerts', 'audit'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors capitalize ${
              activeTab === tab
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            {tab === 'alerts' ? 'System Alerts' : 'Audit Log'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        </div>
      ) : activeTab === 'alerts' ? (
        <div className="space-y-4">
          {/* Filter */}
          <div className="flex gap-2">
            {(['all', 'open', 'resolved'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 rounded-md text-sm capitalize transition-colors ${
                  filter === f
                    ? 'bg-slate-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          {filteredAlerts.length === 0 ? (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-12 text-center">
              <CheckCircle size={48} className="text-emerald-500 mx-auto mb-4" />
              <p className="text-slate-400 text-lg">No alerts to display</p>
              <p className="text-slate-500 text-sm mt-1">System is running normally</p>
            </div>
          ) : (
            filteredAlerts.map((alert) => {
              const sev = alert.severity?.toLowerCase() || 'info';
              const cfg = severityConfig[sev] || severityConfig.info;
              const Icon = cfg.icon;
              return (
                <div
                  key={alert.id}
                  className={`rounded-xl border p-4 flex items-start gap-3 ${cfg.bg}`}
                >
                  <Icon size={18} className={`${cfg.color} flex-shrink-0 mt-0.5`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <p className="text-white font-medium text-sm">{alert.message}</p>
                      <span className={`text-xs font-semibold uppercase px-2 py-0.5 rounded-full flex-shrink-0 ${
                        alert.status === 'resolved'
                          ? 'bg-emerald-900/40 text-emerald-400'
                          : 'bg-slate-700 text-slate-300'
                      }`}>
                        {alert.status || 'open'}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 flex-wrap">
                      <span className={`text-xs font-medium uppercase ${cfg.color}`}>{alert.severity}</span>
                      {alert.alert_type && (
                        <span className="text-xs text-slate-500">{alert.alert_type}</span>
                      )}
                      {alert.created_at && (
                        <span className="text-xs text-slate-500">{timeAgo(alert.created_at)}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      ) : (
        /* Audit Log Tab */
        <div className="space-y-2">
          {auditLogs.length === 0 ? (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-12 text-center">
              <Activity size={48} className="text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 text-lg">No audit events yet</p>
            </div>
          ) : (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-700/50">
                    <tr>
                      <th className="text-left px-4 py-3 text-slate-400 font-medium">Action</th>
                      <th className="text-left px-4 py-3 text-slate-400 font-medium">Entity</th>
                      <th className="text-left px-4 py-3 text-slate-400 font-medium">Performed By</th>
                      <th className="text-left px-4 py-3 text-slate-400 font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-700/30 transition-colors">
                        <td className="px-4 py-3">
                          <span className="text-blue-400 font-mono text-xs bg-blue-900/20 px-2 py-0.5 rounded">
                            {log.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">
                          {log.entity_type || '—'}
                        </td>
                        <td className="px-4 py-3 text-slate-300 flex items-center gap-1.5">
                          <Shield size={12} className="text-slate-500" />
                          {log.performed_by || 'system'}
                        </td>
                        <td className="px-4 py-3 text-slate-500 text-xs">
                          {timeAgo(log.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
