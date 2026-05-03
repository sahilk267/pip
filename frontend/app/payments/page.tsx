'use client';

import { useEffect, useState } from 'react';
import { CreditCard, CheckCircle, XCircle, RefreshCw, AlertCircle, Zap } from 'lucide-react';
import { paymentApi, orderApi } from '@/lib/api';

interface Gateway {
  code: string;
  name: string;
  configured: boolean;
  currencies: string[];
  test_mode: boolean;
}

interface Order {
  id: number;
  total_amount: number;
  currency: string;
  fulfillment_status: string;
  payment_status?: string;
}

interface PaymentResult {
  transaction_id: number;
  external_payment_id: string;
  gateway: string;
  amount: number;
  currency: string;
  status: string;
}

export default function PaymentsPage() {
  const [gateways, setGateways] = useState<Gateway[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<number | ''>('');
  const [selectedGateway, setSelectedGateway] = useState('mock');
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<PaymentResult | null>(null);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState<number | null>(null);
  const [confirmResult, setConfirmResult] = useState<Record<number, string>>({});

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [gw, ord] = await Promise.allSettled([
        paymentApi.gateways(),
        orderApi.list({ limit: 20 }),
      ]);
      if (gw.status === 'fulfilled') {
        const data = gw.value as { gateways?: Gateway[] };
        setGateways(data?.gateways || []);
      }
      if (ord.status === 'fulfilled') {
        setOrders(Array.isArray(ord.value) ? ord.value : []);
      }
    } finally {
      setLoading(false);
    }
  }

  async function createIntent() {
    if (!selectedOrder) { setError('Please select an order'); return; }
    const order = orders.find((o) => o.id === Number(selectedOrder));
    if (!order) return;

    setProcessing(true);
    setError('');
    setResult(null);
    try {
      const res = await paymentApi.createIntent({
        order_id: Number(selectedOrder),
        gateway: selectedGateway,
        currency: order.currency || 'USD',
      });
      setResult(res as PaymentResult);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || 'Payment intent failed');
    } finally {
      setProcessing(false);
    }
  }

  async function confirmPayment(txnId: number) {
    setConfirming(txnId);
    try {
      const res = await paymentApi.confirm(txnId);
      const data = res as { status?: string };
      setConfirmResult((prev) => ({ ...prev, [txnId]: data?.status || 'confirmed' }));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || 'Confirm failed');
    } finally {
      setConfirming(null);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <CreditCard className="text-blue-400" size={24} />
          Payment Gateway
        </h1>
        <p className="text-slate-400 mt-1">Process payments via Stripe, Razorpay, or Demo mode</p>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg px-4 py-3 flex items-center gap-2 text-red-300">
          <AlertCircle size={16} />
          {error}
          <button onClick={() => setError('')} className="ml-auto text-red-400 hover:text-red-200">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Gateway Status */}
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Zap size={18} className="text-amber-400" />
            Available Gateways
          </h2>
          {loading ? (
            <div className="animate-pulse space-y-3">
              {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-slate-700 rounded-lg" />)}
            </div>
          ) : (
            <div className="space-y-3">
              {gateways.map((gw) => (
                <div
                  key={gw.code}
                  onClick={() => setSelectedGateway(gw.code)}
                  className={`p-4 rounded-lg border cursor-pointer transition-all ${
                    selectedGateway === gw.code
                      ? 'border-blue-500 bg-blue-900/20'
                      : 'border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className={`w-2.5 h-2.5 rounded-full ${gw.configured ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                      <span className="font-medium text-white">{gw.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {gw.test_mode && (
                        <span className="text-xs bg-amber-900/30 text-amber-400 px-2 py-0.5 rounded">TEST</span>
                      )}
                      {gw.configured ? (
                        <CheckCircle size={14} className="text-emerald-400" />
                      ) : (
                        <XCircle size={14} className="text-slate-500" />
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">{gw.currencies.join(', ')}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Create Payment Intent */}
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Create Payment Intent</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Select Order</label>
              <select
                value={selectedOrder}
                onChange={(e) => setSelectedOrder(e.target.value ? Number(e.target.value) : '')}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">— choose an order —</option>
                {orders.map((o) => (
                  <option key={o.id} value={o.id}>
                    Order #{o.id} — {o.currency} {(o.total_amount || 0).toFixed(2)} [{o.fulfillment_status}]
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-slate-400 mb-1">Gateway</label>
              <select
                value={selectedGateway}
                onChange={(e) => setSelectedGateway(e.target.value)}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
              >
                {gateways.map((gw) => (
                  <option key={gw.code} value={gw.code}>{gw.name}</option>
                ))}
              </select>
            </div>

            <button
              onClick={createIntent}
              disabled={!selectedOrder || processing}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              {processing ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <CreditCard size={16} />
                  Create Payment Intent
                </>
              )}
            </button>
          </div>

          {/* Result */}
          {result && (
            <div className="mt-4 bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle size={16} className="text-emerald-400" />
                <span className="font-semibold text-emerald-400">Payment Intent Created</span>
              </div>
              <div className="space-y-1.5 text-sm font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-400">Transaction ID</span>
                  <span className="text-white">#{result.transaction_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Gateway</span>
                  <span className="text-white capitalize">{result.gateway}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Amount</span>
                  <span className="text-emerald-400">{result.currency} {result.amount?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Status</span>
                  <span className="text-amber-400">{result.status}</span>
                </div>
                <div className="text-xs text-slate-500 mt-2 break-all">
                  ID: {result.external_payment_id}
                </div>
              </div>
              <button
                onClick={() => confirmPayment(result.transaction_id)}
                disabled={!!confirmResult[result.transaction_id] || confirming === result.transaction_id}
                className="mt-3 w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-600 text-white py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
              >
                {confirming === result.transaction_id ? (
                  <><RefreshCw size={14} className="animate-spin" />Confirming...</>
                ) : confirmResult[result.transaction_id] ? (
                  <><CheckCircle size={14} />Payment {confirmResult[result.transaction_id]}</>
                ) : (
                  <><CheckCircle size={14} />Confirm Payment</>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Recent Orders Table */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
          <h2 className="font-semibold text-white">Recent Orders</h2>
          <button onClick={loadData} className="text-slate-400 hover:text-white">
            <RefreshCw size={14} />
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-700/50">
              <tr>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Order</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Amount</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Status</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Payment</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {orders.slice(0, 10).map((order) => (
                <tr key={order.id} className="hover:bg-slate-700/30 transition-colors">
                  <td className="px-4 py-3 font-medium text-white">#{order.id}</td>
                  <td className="px-4 py-3 text-emerald-400 font-semibold">
                    {order.currency} {(order.total_amount || 0).toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    <span className="bg-slate-700 text-slate-300 text-xs px-2 py-0.5 rounded capitalize">
                      {order.fulfillment_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded capitalize ${
                      order.payment_status === 'paid'
                        ? 'bg-emerald-900/30 text-emerald-400'
                        : 'bg-slate-700 text-slate-400'
                    }`}>
                      {order.payment_status || 'pending'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => { setSelectedOrder(order.id); }}
                      className="text-blue-400 hover:text-blue-300 text-xs"
                    >
                      Pay →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
