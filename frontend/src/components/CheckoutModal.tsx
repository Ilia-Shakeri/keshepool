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
  onSuccess?: () => void;
}

interface OrderResult {
  id: string;
  credentials: string;
  productBrand: string;
  variantDuration: string;
}

const DIALOG_STYLE: React.CSSProperties = {
  background: "rgba(12,14,18,0.97)",
  backdropFilter: "blur(40px)",
  WebkitBackdropFilter: "blur(40px)",
  border: "1px solid rgba(255,255,255,0.09)",
};

const HEADER_STYLE: React.CSSProperties = {
  background: "rgba(12,14,18,0.85)",
  backdropFilter: "blur(20px)",
  borderBottom: "1px solid rgba(255,255,255,0.07)",
};

const BACK_BTN_STYLE: React.CSSProperties = {
  background: "rgba(255,255,255,0.07)",
  border: "1px solid rgba(255,255,255,0.1)",
};

export default function CheckoutModal({ isOpen, setIsOpen, product, variant, walletBalance, onSuccess }: CheckoutModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [orderResult, setOrderResult] = useState<OrderResult | null>(null);
  const [copied, setCopied] = useState(false);

  const canPay = walletBalance >= variant.rawPrice && (variant.stockCount ?? 0) > 0;
  const hasEmptyWallet = walletBalance <= 0;

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
      onSuccess?.();
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

  const handleChargeWallet = () => {
    setIsOpen(false);
    window.location.href = "/finance?deposit=1";
  };

  if (orderResult) {
    return (
      <Dialog open={isOpen} onOpenChange={handleClose}>
        <DialogContent className="text-[#F5F5F5] rounded-3xl w-[95%] max-w-md mx-auto overflow-y-auto max-h-[90vh] p-0 font-sans dir-rtl border-none" style={DIALOG_STYLE}>
          <DialogHeader className="p-4 sticky top-0 z-20" style={HEADER_STYLE}>
            <div className="flex items-center gap-3">
              <button onClick={handleClose} className="p-2 rounded-full hover:bg-white/10 transition-colors" style={BACK_BTN_STYLE}>
                <ChevronLeft className="w-5 h-5" />
              </button>
              <DialogTitle className="text-lg font-bold">سفارش ثبت شد</DialogTitle>
            </div>
          </DialogHeader>

          <div className="p-5 space-y-5">
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="w-14 h-14 rounded-full flex items-center justify-center" style={{ background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)" }}>
                <Check className="w-7 h-7 text-emerald-400" />
              </div>
              <p className="text-sm font-bold text-[#F5F5F5]">{orderResult.productBrand} — {orderResult.variantDuration}</p>
              <p className="text-[10px] text-[#F5F5F5]/40">شناسه سفارش: {orderResult.id}</p>
            </div>

            <div className="rounded-2xl p-4" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <p className="text-[10px] text-[#F5F5F5]/45 mb-2">اطلاعات دسترسی</p>
              <p className="text-sm font-mono text-emerald-400 break-all leading-relaxed">{orderResult.credentials}</p>
            </div>

            <Button
              onClick={handleCopy}
              className="w-full py-5 rounded-2xl text-sm font-bold transition-all active:scale-95 border-none gap-2"
              style={{ background: "rgba(255,255,255,0.08)", color: "#F5F5F5" }}
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              {copied ? "کپی شد" : "کپی اطلاعات"}
            </Button>

            <Button
              onClick={handleClose}
              className="w-full py-5 rounded-2xl text-sm font-bold transition-all active:scale-95 border-none"
              style={{ background: "linear-gradient(135deg, #E63946 0%, #c0303c 100%)", color: "white", boxShadow: "0 8px 24px rgba(230,57,70,0.3)" }}
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
      <DialogContent className="text-[#F5F5F5] rounded-3xl w-[95%] max-w-md mx-auto overflow-y-auto max-h-[90vh] p-0 font-sans dir-rtl border-none" style={DIALOG_STYLE}>
        <DialogHeader className="p-4 sticky top-0 z-20" style={HEADER_STYLE}>
          <div className="flex items-center gap-3">
            <button onClick={handleClose} className="p-2 rounded-full hover:bg-white/10 transition-colors" style={BACK_BTN_STYLE}>
              <ChevronLeft className="w-5 h-5" />
            </button>
            <DialogTitle className="text-lg font-bold">تسویه حساب</DialogTitle>
          </div>
        </DialogHeader>

        <div className="p-5 space-y-5">
          <div className="rounded-2xl p-4 flex items-center justify-between" style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)" }}>
            <div className="flex items-center gap-3">
              <ProductIcon icon={product.icon} assetUrl={product.assetUrl} gradient={product.gradient} category={product.category} sizeClassName="w-10 h-10" iconSizeClassName="w-4 h-4" />
              <div>
                <h4 className="font-bold text-sm">{product.brand}</h4>
                <p className="text-xs text-[#F5F5F5]/55 mt-0.5">{variant.duration}</p>
              </div>
            </div>
            <span className="font-bold text-[#F5F5F5]">{toPersianDigits(variant.priceLabel)}</span>
          </div>

          <div className="rounded-2xl p-4 flex items-center justify-between" style={{ background: "rgba(230,57,70,0.07)", border: "1px solid rgba(230,57,70,0.2)" }}>
            <div className="text-right">
              <span className="block text-sm font-bold">کیف پول</span>
              <span className="block text-[10px] text-[#F5F5F5]/50 mt-0.5">موجودی: {formatPrice(walletBalance)} تومان</span>
            </div>
            <Wallet className="w-5 h-5 text-[#E63946]" />
          </div>

          <div className="pt-4 space-y-3" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
            <div className="flex justify-between text-sm text-[#F5F5F5]/55">
              <span>مبلغ کل</span>
              <span className="font-mono">{toPersianDigits(variant.priceLabel)}</span>
            </div>
            <div className="flex justify-between text-sm font-bold text-[#F5F5F5]">
              <span>مبلغ قابل پرداخت</span>
              <span className="font-mono text-[#E63946] text-lg">{toPersianDigits(variant.priceLabel)}</span>
            </div>
          </div>

          {!canPay && (
            <div className="space-y-3 text-xs rounded-xl p-3" style={{ background: "rgba(230,57,70,0.1)", border: "1px solid rgba(230,57,70,0.2)" }}>
              <p className="text-[#E63946]">
                {hasEmptyWallet
                  ? "Wallet balance is zero. Charge your wallet first to complete this purchase."
                  : "Wallet balance is not enough or the product is unavailable."}
              </p>
              {hasEmptyWallet && (
                <Button
                  onClick={handleChargeWallet}
                  className="w-full py-4 rounded-xl text-xs font-bold transition-all active:scale-95 border-none gap-2"
                  style={{ background: "rgba(230,57,70,0.18)", color: "#F5F5F5" }}
                >
                  <Wallet className="w-4 h-4" />
                  Charge Wallet
                </Button>
              )}
            </div>
          )}

          {errorMessage && (
            <div className="text-xs text-[#E63946] rounded-xl p-3" style={{ background: "rgba(230,57,70,0.1)", border: "1px solid rgba(230,57,70,0.2)" }}>
              {errorMessage}
            </div>
          )}

          <Button
            disabled={!canPay || isSubmitting}
            onClick={handleSubmit}
            className="w-full py-6 rounded-2xl text-base font-bold transition-all active:scale-95 border-none mt-2"
            style={
              !canPay || isSubmitting
                ? { background: "rgba(255,255,255,0.06)", color: "rgba(245,245,245,0.3)", cursor: "not-allowed" }
                : { background: "linear-gradient(135deg, #E63946 0%, #c0303c 100%)", color: "white", boxShadow: "0 8px 32px rgba(230,57,70,0.3)" }
            }
          >
            {isSubmitting ? "در حال ثبت..." : "پرداخت و تکمیل سفارش"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
