"use client";

import { useState } from "react";
import { Check, ChevronLeft, Copy, Wallet } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import ProductIcon from "@/components/ProductIcon";
import { Button } from "@/components/ui/button";
import { checkoutWithWallet } from "@/lib/api";
import type { Product, ProductVariant } from "@/lib/products";
import { formatPrice, toPersianDigits } from "@/lib/utils";

interface CheckoutModalProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  product: Product;
  variant: ProductVariant;
  walletBalance: number;
}

interface OrderResult {
  id: string;
  credentials: string;
  productBrand: string;
  variantDuration: string;
}

export default function CheckoutModal({ isOpen, setIsOpen, product, variant, walletBalance }: CheckoutModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [orderResult, setOrderResult] = useState<OrderResult | null>(null);
  const [copied, setCopied] = useState(false);

  const canPay = walletBalance >= variant.rawPrice && (variant.stockCount ?? 0) > 0;

  const handleSubmit = async () => {
    if (!canPay || isSubmitting) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const result = await checkoutWithWallet(product.id, variant.id);
      setOrderResult({
        id: result.order.id,
        credentials: result.order.credentials,
        productBrand: result.order.productBrand,
        variantDuration: result.order.variantDuration,
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "ثبت سفارش ناموفق بود.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopy = () => {
    if (!orderResult) return;
    navigator.clipboard.writeText(orderResult.credentials).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleClose = () => {
    setOrderResult(null);
    setErrorMessage(null);
    setCopied(false);
    setIsOpen(false);
  };

  if (orderResult) {
    return (
      <Dialog open={isOpen} onOpenChange={handleClose}>
        <DialogContent className="bg-[#0F0F10] border border-[#33383F] text-[#F5F5F5] rounded-3xl w-[95%] max-w-md mx-auto overflow-y-auto max-h-[90vh] p-0 font-sans dir-rtl">
          <DialogHeader className="p-4 border-b border-[#33383F] bg-[#0F0F10]/80 backdrop-blur-md sticky top-0 z-20">
            <div className="flex items-center gap-3">
              <button onClick={handleClose} className="p-2 bg-[#33383F] rounded-full hover:bg-[#33383F]/80 transition-colors">
                <ChevronLeft className="w-5 h-5" />
              </button>
              <DialogTitle className="text-lg font-bold">سفارش ثبت شد</DialogTitle>
            </div>
          </DialogHeader>

          <div className="p-5 space-y-5">
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="w-14 h-14 bg-emerald-500/10 border border-emerald-500/30 rounded-full flex items-center justify-center">
                <Check className="w-7 h-7 text-emerald-400" />
              </div>
              <p className="text-sm font-bold text-[#F5F5F5]">{orderResult.productBrand} — {orderResult.variantDuration}</p>
              <p className="text-[10px] text-[#F5F5F5]/50">شناسه سفارش: {orderResult.id}</p>
            </div>

            <div className="bg-[#0B1D33] border border-[#33383F] rounded-2xl p-4">
              <p className="text-[10px] text-[#F5F5F5]/50 mb-2">اطلاعات دسترسی</p>
              <p className="text-sm font-mono text-emerald-400 break-all leading-relaxed">{orderResult.credentials}</p>
            </div>

            <Button
              onClick={handleCopy}
              className="w-full bg-[#33383F] hover:bg-[#33383F]/80 text-[#F5F5F5] py-5 rounded-2xl text-sm font-bold transition-all active:scale-95 border-none gap-2"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              {copied ? "کپی شد" : "کپی اطلاعات"}
            </Button>

            <Button
              onClick={handleClose}
              className="w-full bg-[#E63946] hover:bg-[#E63946]/90 text-[#F5F5F5] py-5 rounded-2xl text-sm font-bold transition-all active:scale-95 border-none"
            >
              بستن
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="bg-[#0F0F10] border border-[#33383F] text-[#F5F5F5] rounded-3xl w-[95%] max-w-md mx-auto overflow-y-auto max-h-[90vh] p-0 font-sans dir-rtl">
        <DialogHeader className="p-4 border-b border-[#33383F] bg-[#0F0F10]/80 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-3">
            <button onClick={handleClose} className="p-2 bg-[#33383F] rounded-full hover:bg-[#33383F]/80 transition-colors">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <DialogTitle className="text-lg font-bold">تسویه حساب</DialogTitle>
          </div>
        </DialogHeader>

        <div className="p-5 space-y-6">
          <div className="bg-[#0B1D33] border border-[#33383F] rounded-2xl p-4 flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3">
              <ProductIcon icon={product.icon} assetUrl={product.assetUrl} gradient={product.gradient} sizeClassName="w-10 h-10" />
              <div>
                <h4 className="font-bold text-sm">{product.brand}</h4>
                <p className="text-xs text-[#F5F5F5]/70 mt-1">{variant.duration}</p>
              </div>
            </div>
            <span className="font-bold text-[#F5F5F5]">{toPersianDigits(variant.priceLabel)}</span>
          </div>

          <div className="w-full flex items-center justify-between p-4 rounded-2xl border border-[#E63946] bg-[#E63946]/5">
            <div className="text-right">
              <span className="block text-sm font-bold">کیف پول</span>
              <span className="block text-[10px] text-[#F5F5F5]/50 mt-0.5">موجودی: {formatPrice(walletBalance)} تومان</span>
            </div>
            <Wallet className="w-5 h-5 text-[#E63946]" />
          </div>

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

          {!canPay && (
            <div className="text-xs text-[#E63946] bg-[#E63946]/10 border border-[#E63946]/20 rounded-xl p-3">
              موجودی کیف پول کافی نیست یا محصول ناموجود است.
            </div>
          )}

          {errorMessage && (
            <div className="text-xs text-[#E63946] bg-[#E63946]/10 border border-[#E63946]/20 rounded-xl p-3">
              {errorMessage}
            </div>
          )}

          <Button
            disabled={!canPay || isSubmitting}
            onClick={handleSubmit}
            className="w-full bg-[#E63946] hover:bg-[#E63946]/90 disabled:bg-[#33383F] disabled:text-[#F5F5F5]/40 text-[#F5F5F5] py-6 rounded-2xl text-md font-bold shadow-lg shadow-[#E63946]/20 transition-all active:scale-95 border-none"
          >
            {isSubmitting ? "در حال ثبت..." : "پرداخت و تکمیل سفارش"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}