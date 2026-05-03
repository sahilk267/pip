import { LucideIcon } from 'lucide-react';
import clsx from 'clsx';

interface StatCardProps {
  title: string;
  value: string | number;
  sub?: string;
  icon: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  color?: 'blue' | 'green' | 'amber' | 'purple';
}

const colorMap = {
  blue:   { bg: 'bg-blue-600/10',   icon: 'text-blue-400',   border: 'border-blue-600/20' },
  green:  { bg: 'bg-emerald-600/10', icon: 'text-emerald-400', border: 'border-emerald-600/20' },
  amber:  { bg: 'bg-amber-600/10',  icon: 'text-amber-400',  border: 'border-amber-600/20' },
  purple: { bg: 'bg-purple-600/10', icon: 'text-purple-400', border: 'border-purple-600/20' },
};

export default function StatCard({ title, value, sub, icon: Icon, trend, trendLabel, color = 'blue' }: StatCardProps) {
  const c = colorMap[color];
  return (
    <div className={clsx('rounded-xl bg-[#1a232e] border p-5', c.border)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-[#9aacbc] uppercase tracking-wide mb-1">{title}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
          {sub && <p className="text-xs text-[#9aacbc] mt-0.5">{sub}</p>}
          {trendLabel && (
            <p className={clsx('text-xs mt-1 font-medium', trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-[#9aacbc]')}>
              {trend === 'up' ? '↑' : trend === 'down' ? '↓' : ''} {trendLabel}
            </p>
          )}
        </div>
        <div className={clsx('p-2.5 rounded-lg', c.bg)}>
          <Icon size={20} className={c.icon} />
        </div>
      </div>
    </div>
  );
}
