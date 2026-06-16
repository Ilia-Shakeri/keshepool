"use client";

import { useState } from "react";
import { Check, Copy, ChevronLeft, CreditCard, Wallet, ShieldCheck } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Product, ProductVariant } from "@/lib/products";
import { IconMap } from "@/lib/icons";
import { Button } from "@/components/ui/button";
import { formatPrice, toPersianDigits } from "@/lib/utils";

interface CheckoutModalProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  product: Product;
  variant: ProductVariant;
  walletBalance: number;
}

export default function CheckoutModal({ isOpen, setIsOpen, product, variant, walletBalance }: CheckoutModalProps) {
  const [paymentMethod, setPaymentMethod] = useState<'wallet' | 'tether'>('wallet');
  const [discountCode, setDiscountCode] = useState('');
  const [copied, setCopied] = useState(false);

  // Safely copy text to the system clipboard
  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Clipboard write operation failed", err);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogContent className="bg-[#0F0F10] border border-[#33383F] text-[#F5F5F5] rounded-3xl w-[95%] max-w-md mx-auto overflow-y-auto max-h-[90vh] p-0 font-sans dir-rtl">
        
        {/* Sticky top navigation bar */}
        <DialogHeader className="p-4 border-b border-[#33383F] bg-[#0F0F10]/80 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-3">
            <button onClick={() => setIsOpen(false)} className="p-2 bg-[#33383F] rounded-full hover:bg-[#33383F]/80 transition-colors">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <DialogTitle className="text-lg font-bold">تسویه حساب</DialogTitle>
          </div>
        </DialogHeader>

        <div className="p-5 space-y-6">
          <div className="space-y-3">
            <h3 className="text-sm text-[#F5F5F5]/70 font-medium">سفارش شما</h3>
            <div className="bg-[#0B1D33] border border-[#33383F] rounded-2xl p-4 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-3">
                <div className={`bg-gradient-to-br ${product.gradient} p-2.5 rounded-full shadow-lg`}>
                   {/* Dynamically render the mapped icon */}
                  {IconMap[product.icon] || IconMap["Box"]}
                </div>
                <div>
                  <h4 className="font-bold text-sm">{product.brand}</h4>
                  <p className="text-xs text-[#F5F5F5]/70 mt-1">{variant.duration} - {product.subtitle}</p>
                </div>
              </div>
              <span className="font-bold text-[#1E3C5A]">{toPersianDigits(variant.priceLabel)}</span>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm text-[#F5F5F5]/70 font-medium">کد تخفیف</h3>
            <div className="flex gap-2">
              <input 
                type="text" 
                placeholder="کد تخفیف را وارد کنید" 
                value={discountCode}
                onChange={(e) => setDiscountCode(e.target.value)}
                className="flex-1 bg-[#0F0F10]/60 border border-[#33383F] rounded-xl px-4 text-sm focus:outline-none focus:border-[#E63946] focus:ring-1 focus:ring-[#E63946]/50 transition-all placeholder:text-[#F5F5F5]/50"
              />
              <Button variant="outline" className="bg-[#33383F] border-[#33383F]/80 hover:bg-[#33383F]/80 rounded-xl px-6">
                اعمال
              </Button>
            </div>
          </div>

          {/* Payment Method Selector */}
          <div className="space-y-3">
            <h3 className="text-sm text-[#F5F5F5]/70 font-medium">روش پرداخت</h3>
            <div className="space-y-2">
              <button 
                onClick={() => setPaymentMethod('wallet')}
                className={`w-full flex items-center justify-between p-4 rounded-2xl border transition-all ${
                  paymentMethod === 'wallet' ? 'border-[#E63946] bg-[#E63946]/5' : 'border-[#33383F] bg-[#0F0F10]/40 hover:bg-[#33383F]/60'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'wallet' ? 'border-[#E63946]' : 'border-[#33383F]'}`}>
                    {paymentMethod === 'wallet' && <div className="w-2.5 h-2.5 bg-[#E63946] rounded-full" />}
                  </div>
                  <div className="text-right">
                    <span className="block text-sm font-bold">کیف پول هوشمند</span>
                    <span className="block text-[10px] text-[#F5F5F5]/50 mt-0.5">موجودی: {formatPrice(walletBalance)} تومان</span>
                  </div>
                </div>
                <Wallet className={`w-5 h-5 ${paymentMethod === 'wallet' ? 'text-[#E63946]' : 'text-[#F5F5F5]/50'}`} />
              </button>

              <button 
                onClick={() => setPaymentMethod('tether')}
                className={`w-full flex items-center justify-between p-4 rounded-2xl border transition-all ${
                  paymentMethod === 'tether' ? 'border-[#1E3C5A] bg-[#1E3C5A]/5' : 'border-[#33383F] bg-[#0F0F10]/40 hover:bg-[#33383F]/60'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'tether' ? 'border-[#1E3C5A]' : 'border-[#33383F]'}`}>
                    {paymentMethod === 'tether' && <div className="w-2.5 h-2.5 bg-[#1E3C5A] rounded-full" />}
                  </div>
                  <span className="text-sm font-medium">پرداخت با تتر (USDT)</span>
                </div>
                <CreditCard className={`w-5 h-5 ${paymentMethod === 'tether' ? 'text-[#1E3C5A]' : 'text-[#F5F5F5]/50'}`} />
              </button>
            </div>
          </div>

          {/* Conditional Tether Dropdown Info */}
          {paymentMethod === 'tether' && (
            <div className="bg-[#1E3C5A]/10 border border-[#1E3C5A]/20 rounded-2xl p-4 flex items-center justify-between animate-in fade-in zoom-in duration-300">
              <div className="text-right">
                <span className="block text-xs text-[#F5F5F5]/70 mb-1 flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-[#1E3C5A]" /> آدرس ولت اختصاصی شما</span>
                <span className="font-mono text-xs text-[#1E3C5A]">TDxY...9Kmq</span>
              </div>
              <Button onClick={() => handleCopy("TDxY9Kmq...")} size="icon" className="bg-[#1E3C5A]/20 hover:bg-[#1E3C5A]/40 text-[#1E3C5A] rounded-xl border-none">
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
          )}

          <div className="pt-4 border-t border-[#33383F]/60 space-y-3">
            <div className="flex justify-between text-sm text-[#F5F5F5]/70">
              <span>مبلغ کل</span>
              <span className="font-mono">{toPersianDigits(variant.priceLabel)}</span>
            </div>
            <div className="flex justify-between text-sm font-bold text-[#F5F5F5]">
              <span>مبلغ قابل پرداخت</span>
              <span className="font-mono text-[#E63946] text-lg">{toPersianDigits(variant.priceLabel)}</span>
            </div>
          </div>

          <Button className="w-full bg-[#E63946] hover:bg-[#E63946]/90 text-[#F5F5F5] py-6 rounded-2xl text-md font-bold shadow-lg shadow-[#E63946]/20 transition-all active:scale-95 border-none">
            پرداخت و تکمیل سفارش
          </Button>

        </div>
      </DialogContent>
    </Dialog>
  );
}