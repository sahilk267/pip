'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [form, setForm] = useState({ email: '', password: '', full_name: '', role: 'sales_rep' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = mode === 'login'
        ? await authApi.login({ email: form.email, password: form.password })
        : await authApi.register(form);
      localStorage.setItem('token', res.access_token);
      localStorage.setItem('user', JSON.stringify(res.user));
      router.push('/');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Something went wrong';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  }

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0f1419] px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm">PI</div>
          <div>
            <p className="text-white font-semibold text-sm">Procurement Intelligence</p>
            <p className="text-[#9aacbc] text-xs">AI-powered B2B+B2C Commerce</p>
          </div>
        </div>

        <div className="bg-[#1a232e] border border-[#2a3540] rounded-2xl p-6">
          {/* Toggle */}
          <div className="flex bg-[#0f1419] rounded-lg p-1 mb-6">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  mode === m ? 'bg-blue-600 text-white' : 'text-[#9aacbc] hover:text-white'
                }`}
              >
                {m === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-xs text-[#9aacbc] mb-1">Full Name</label>
                <input
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white placeholder-[#9aacbc] focus:outline-none focus:border-blue-500"
                  placeholder="Jane Smith"
                  value={form.full_name}
                  onChange={f('full_name')}
                  required
                />
              </div>
            )}
            <div>
              <label className="block text-xs text-[#9aacbc] mb-1">Email</label>
              <input
                type="email"
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white placeholder-[#9aacbc] focus:outline-none focus:border-blue-500"
                placeholder="you@company.com"
                value={form.email}
                onChange={f('email')}
                required
              />
            </div>
            <div>
              <label className="block text-xs text-[#9aacbc] mb-1">Password</label>
              <input
                type="password"
                className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white placeholder-[#9aacbc] focus:outline-none focus:border-blue-500"
                placeholder="••••••••"
                value={form.password}
                onChange={f('password')}
                required
                minLength={6}
              />
            </div>
            {mode === 'register' && (
              <div>
                <label className="block text-xs text-[#9aacbc] mb-1">Role</label>
                <select
                  className="w-full bg-[#0f1419] border border-[#2a3540] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  value={form.role}
                  onChange={f('role')}
                >
                  <option value="sales_rep">Sales Rep</option>
                  <option value="admin">Admin</option>
                  <option value="customer">Customer</option>
                  <option value="vendor">Vendor</option>
                </select>
              </div>
            )}
            {error && (
              <div className="bg-red-900/30 border border-red-700/50 rounded-lg px-3 py-2 text-xs text-red-400">
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-lg py-2 text-sm transition-colors"
            >
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-[#9aacbc] mt-4">
          Procurement Intelligence Platform v1.0
        </p>
      </div>
    </div>
  );
}
