'use client';

import { useEffect, useState } from 'react';
import { ShoppingCart, Plus, Minus, Trash2, CreditCard, Package, ArrowRight, AlertCircle } from 'lucide-react';
import { cartApi, productApi } from '@/lib/api';

interface Product {
  id: number;
  name: string;
  sku: string;
  price: number;
  currency: string;
  stock_quantity?: number;
}

interface CartItem {
  id: number;
  product_id: number;
  product_name?: string;
  quantity: number;
  unit_price: number;
  currency?: string;
}

const DEMO_ACCOUNT_ID = 1;

export default function CartPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [addingId, setAddingId] = useState<number | null>(null);
  const [checkingOut, setCheckingOut] = useState(false);
  const [checkoutResult, setCheckoutResult] = useState<{ order_id?: number; total?: number } | null>(null);
  const [error, setError] = useState('');
  const [coupon, setCoupon] = useState('');
  const [selectedGateway, setSelectedGateway] = useState('stripe');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [prods, cart] = await Promise.allSettled([
        productApi.list({ limit: 20 }),
        cartApi.get(DEMO_ACCOUNT_ID).catch(() => ({ items: [] })),
      ]);
      if (prods.status === 'fulfilled') {
        setProducts(Array.isArray(prods.value) ? prods.value : []);
      }
      if (cart.status === 'fulfilled') {
        const c = cart.value;
        setCartItems(Array.isArray(c?.items) ? c.items : []);
      }
    } catch {
      setError('Failed to load cart');
    } finally {
      setLoading(false);
    }
  }

  async function addToCart(product: Product) {
    setAddingId(product.id);
    setError('');
    try {
      await cartApi.add({
        loyalty_account_id: DEMO_ACCOUNT_ID,
        product_id: product.id,
        quantity: 1,
        unit_price: product.price || 0,
      });
      await loadData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || 'Failed to add item');
    } finally {
      setAddingId(null);
    }
  }

  async function removeItem(itemId: number) {
    try {
      await cartApi.remove(itemId);
      setCartItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch {
      setError('Failed to remove item');
    }
  }

  async function checkout() {
    if (cartItems.length === 0) return;
    setCheckingOut(true);
    setError('');
    try {
      const result = await cartApi.checkout({
        loyalty_account_id: DEMO_ACCOUNT_ID,
        coupon_code: coupon || undefined,
      });
      setCheckoutResult({ order_id: result?.order_id, total: result?.total_amount });
      setCartItems([]);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || 'Checkout failed');
    } finally {
      setCheckingOut(false);
    }
  }

  const cartTotal = cartItems.reduce((sum, i) => sum + i.unit_price * i.quantity, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (checkoutResult?.order_id) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center">
        <div className="bg-emerald-600/10 border border-emerald-600/30 rounded-2xl p-10">
          <div className="text-5xl mb-4">✅</div>
          <h2 className="text-2xl font-bold text-emerald-400 mb-2">Order Placed!</h2>
          <p className="text-slate-400 mb-1">Order <span className="text-white font-semibold">#{checkoutResult.order_id}</span> confirmed</p>
          {checkoutResult.total !== undefined && (
            <p className="text-slate-400 mb-6">Total: <span className="text-emerald-400 font-semibold">${checkoutResult.total?.toFixed(2)}</span></p>
          )}
          <button
            onClick={() => { setCheckoutResult(null); loadData(); }}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors"
          >
            Continue Shopping
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ShoppingCart className="text-blue-400" size={24} />
            Shopping Cart
          </h1>
          <p className="text-slate-400 mt-1">{cartItems.length} item{cartItems.length !== 1 ? 's' : ''} in your cart</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg px-4 py-3 flex items-center gap-2 text-red-300">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cart Items */}
        <div className="lg:col-span-2 space-y-3">
          {cartItems.length === 0 ? (
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-12 text-center">
              <ShoppingCart size={48} className="text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400 text-lg">Your cart is empty</p>
              <p className="text-slate-500 text-sm mt-1">Add products from the catalog below</p>
            </div>
          ) : (
            cartItems.map((item) => {
              const product = products.find((p) => p.id === item.product_id);
              return (
                <div key={item.id} className="bg-slate-800/50 rounded-xl border border-slate-700 p-4 flex items-center gap-4">
                  <div className="w-12 h-12 bg-slate-700 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Package size={20} className="text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-white truncate">
                      {item.product_name || product?.name || `Product #${item.product_id}`}
                    </p>
                    {product?.sku && <p className="text-sm text-slate-400">SKU: {product.sku}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-400">Qty: {item.quantity}</span>
                  </div>
                  <div className="text-right min-w-[80px]">
                    <p className="font-semibold text-white">${(item.unit_price * item.quantity).toFixed(2)}</p>
                    <p className="text-xs text-slate-400">${item.unit_price.toFixed(2)} each</p>
                  </div>
                  <button
                    onClick={() => removeItem(item.id)}
                    className="text-slate-500 hover:text-red-400 transition-colors p-1"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              );
            })
          )}

          {/* Product Catalog */}
          <div className="mt-8">
            <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              <Package size={18} className="text-blue-400" />
              Add Products
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {products.slice(0, 10).map((product) => (
                <div key={product.id} className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-white text-sm truncate">{product.name}</p>
                    <p className="text-xs text-slate-400">{product.sku}</p>
                    <p className="text-sm text-emerald-400 font-semibold mt-1">${(product.price || 0).toFixed(2)}</p>
                  </div>
                  <button
                    onClick={() => addToCart(product)}
                    disabled={addingId === product.id}
                    className="ml-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white p-2 rounded-lg transition-colors flex-shrink-0"
                  >
                    {addingId === product.id ? (
                      <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                    ) : (
                      <Plus size={16} />
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Order Summary */}
        <div className="lg:col-span-1">
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6 sticky top-6">
            <h2 className="text-lg font-semibold text-white mb-4">Order Summary</h2>

            <div className="space-y-3 mb-4">
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Subtotal ({cartItems.length} items)</span>
                <span className="text-white">${cartTotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Shipping</span>
                <span className="text-emerald-400">Free</span>
              </div>
              <div className="border-t border-slate-700 pt-3 flex justify-between font-semibold">
                <span className="text-white">Total</span>
                <span className="text-white text-lg">${cartTotal.toFixed(2)}</span>
              </div>
            </div>

            {/* Coupon */}
            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-1">Coupon Code</label>
              <input
                type="text"
                value={coupon}
                onChange={(e) => setCoupon(e.target.value)}
                placeholder="Enter coupon code"
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-400 focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* Payment Gateway */}
            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-1">Payment via</label>
              <select
                value={selectedGateway}
                onChange={(e) => setSelectedGateway(e.target.value)}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="stripe">Stripe</option>
                <option value="razorpay">Razorpay</option>
                <option value="mock">Demo (Mock)</option>
              </select>
            </div>

            <button
              onClick={checkout}
              disabled={cartItems.length === 0 || checkingOut}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white py-3 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
            >
              {checkingOut ? (
                <>
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                  Processing...
                </>
              ) : (
                <>
                  <CreditCard size={18} />
                  Checkout
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            <p className="text-xs text-slate-500 text-center mt-3">
              Secure checkout via {selectedGateway === 'stripe' ? 'Stripe' : selectedGateway === 'razorpay' ? 'Razorpay' : 'Demo Mode'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
