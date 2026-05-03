'use client';

import { useState, useEffect } from 'react';
import { Award, TrendingUp } from 'lucide-react';
import { SupplierScorecard } from '@/components/SupplierScorecard';

export default function SuppliersPage() {
  const [vendors, setVendors] = useState<any[]>([]);
  const [selectedVendor, setSelectedVendor] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadVendors() {
      try {
        const res = await fetch('/api/v1/vendors');
        if (res.ok) {
          const data = await res.json();
          setVendors(data.vendors?.slice(0, 15) || []);
          if (data.vendors && data.vendors.length > 0) {
            setSelectedVendor(data.vendors[0].id);
          }
        }
      } catch {}
      finally {
        setLoading(false);
      }
    }
    loadVendors();
  }, []);

  if (loading) return <div className="p-6 text-[#9aacbc]">Loading suppliers...</div>;

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Award size={20} className="text-purple-400" /> Supplier Management
        </h1>
        <p className="text-sm text-[#9aacbc] mt-0.5">Performance ratings, reliability metrics, cost analysis</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Vendor list */}
        <div className="col-span-1 bg-[#1a232e] border border-[#2a3540] rounded-lg p-4 max-h-96 overflow-y-auto">
          <h3 className="text-sm font-semibold text-white mb-3">Vendors</h3>
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
                <p className="text-[10px] text-[#4a5c6a]">{vendor.country}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Scorecard */}
        {selectedVendor && (
          <div className="col-span-2">
            <SupplierScorecard vendorId={selectedVendor} />
          </div>
        )}
      </div>
    </div>
  );
}
