"use client";

import { useState } from "react";
import { Check, Copy, ChevronLeft, CreditCard, Wallet, Percent, ShieldCheck } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Product, ProductVariant } from "@/lib/products";
import { Button } from "@/components/ui/button";

interface CheckoutModalProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  product: Product;
  variant: ProductVariant;
  walletBalance: number;
}

export default function CheckoutModal({ isOpen, setIsOpen, product, variant, walletBalance }: CheckoutModalProps) {
  const [paymentMethod, setPaymentMethod] = useState<'wallet' | 'online' | 'tether'>('wallet');
  const [discountCode, setDiscountCode] = useState('');
  const [copied, setCopied] = useState(false);

  // Fallback programmatic clipboard access for secure environments
  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Clipboard operation failed", err);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogContent className="bg-[#0f0f13] border border-zinc-800 text-white rounded-3xl w-[95%] max-w-md mx-auto overflow-y-auto max-h-[90vh] p-0 font-sans dir-rtl">
        
        {/* Sticky Header */}
        <DialogHeader className="p-4 border-b border-zinc-800/60 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-3">
            <button onClick={() => setIsOpen(false)} className="p-2 bg-zinc-800 rounded-full hover:bg-zinc-700 transition-colors">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <DialogTitle className="text-lg font-bold">تسویه حساب</DialogTitle>
          </div>
        </DialogHeader>

        <div className="p-5 space-y-6">
          {/* Order Summary Card */}
          <div className="space-y-3">
            <h3 className="text-sm text-zinc-400 font-medium">سفارش شما</h3>
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-2xl p-4 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-3">
                <div className={`bg-gradient-to-br ${product.gradient} p-2.5 rounded-full shadow-lg`}>
                  {product.icon}
                </div>
                <div>
                  <h4 className="font-bold text-sm">{product.brand}</h4>
                  <p className="text-xs text-zinc-400 mt-1">{variant.duration} - {product.subtitle}</p>
                </div>
              </div>
              <span className="font-bold text-emerald-400">{variant.priceLabel}</span>
            </div>
          </div>

          {/* Discount Code Section */}
          <div className="space-y-3">
            <h3 className="text-sm text-zinc-400 font-medium">کد تخفیف</h3>
            <div className="flex gap-2">
              <input 
                type="text" 
                placeholder="کد تخفیف را وارد کنید" 
                value={discountCode}
                onChange={(e) => setDiscountCode(e.target.value)}
                className="flex-1 bg-zinc-900/60 border border-zinc-800 rounded-xl px-4 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50 transition-all placeholder:text-zinc-600"
              />
              <Button variant="outline" className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700 rounded-xl px-6">
                اعمال
              </Button>
            </div>
          </div>

          {/* Payment Methods */}
          <div className="space-y-3">
            <h3 className="text-sm text-zinc-400 font-medium">روش پرداخت</h3>
            <div className="space-y-2">
              
              {/* Wallet Option */}
              <button 
                onClick={() => setPaymentMethod('wallet')}
                className={`w-full flex items-center justify-between p-4 rounded-2xl border transition-all ${
                  paymentMethod === 'wallet' ? 'border-red-500 bg-red-500/5' : 'border-zinc-800 bg-zinc-900/40 hover:bg-zinc-800/60'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'wallet' ? 'border-red-500' : 'border-zinc-600'}`}>
                    {paymentMethod === 'wallet' && <div className="w-2.5 h-2.5 bg-red-500 rounded-full" />}
                  </div>
                  <div className="text-right">
                    <span className="block text-sm font-bold">کیف پول هوشمند</span>
                    <span className="block text-[10px] text-zinc-500 mt-0.5">موجودی: {walletBalance.toLocaleString()} تومان</span>
                  </div>
                </div>
                <Wallet className={`w-5 h-5 ${paymentMethod === 'wallet' ? 'text-red-500' : 'text-zinc-500'}`} />
              </button>

              {/* Tether/Crypto Option */}
              <button 
                onClick={() => setPaymentMethod('tether')}
                className={`w-full flex items-center justify-between p-4 rounded-2xl border transition-all ${
                  paymentMethod === 'tether' ? 'border-emerald-500 bg-emerald-500/5' : 'border-zinc-800 bg-zinc-900/40 hover:bg-zinc-800/60'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'tether' ? 'border-emerald-500' : 'border-zinc-600'}`}>
                    {paymentMethod === 'tether' && <div className="w-2.5 h-2.5 bg-emerald-500 rounded-full" />}
                  </div>
                  <span className="text-sm font-medium">پرداخت با تتر (USDT)</span>
                </div>
                <CreditCard className={`w-5 h-5 ${paymentMethod === 'tether' ? 'text-emerald-500' : 'text-zinc-500'}`} />
              </button>

            </div>
          </div>

          {/* Secure Information Copy Example (e.g. for Crypto Wallet Address) */}
          {paymentMethod === 'tether' && (
            <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-2xl p-4 flex items-center justify-between animate-in fade-in zoom-in duration-300">
              <div className="text-right">
                <span className="block text-xs text-zinc-400 mb-1 flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-emerald-400" /> آدرس ولت اختصاصی شما</span>
                <span className="font-mono text-xs text-emerald-300">TDxY...9Kmq</span>
              </div>
              <Button onClick={() => handleCopy("TDxY9Kmq...")} size="icon" className="bg-emerald-500/20 hover:bg-emerald-500/40 text-emerald-400 rounded-xl">
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
          )}

          {/* Payment Summary */}
          <div className="pt-4 border-t border-zinc-800/60 space-y-3">
            <div className="flex justify-between text-sm text-zinc-400">
              <span>مبلغ کل</span>
              <span className="font-mono">{variant.priceLabel}</span>
            </div>
            <div className="flex justify-between text-sm font-bold text-white">
              <span>مبلغ قابل پرداخت</span>
              <span className="font-mono text-emerald-400 text-lg">{variant.priceLabel}</span>
            </div>
          </div>

          {/* Checkout Action */}
          <Button className="w-full bg-red-600 hover:bg-red-500 text-white py-6 rounded-2xl text-md font-bold shadow-lg shadow-red-600/20 transition-all active:scale-95">
            پرداخت و تکمیل سفارش
          </Button>

        </div>
      </DialogContent>
    </Dialog>
  );
}