"use client";

import { useState } from "react";
import { Check, ChevronRight, Copy, Wallet } from "lucide-react";
import { useRouter } from "next/navigation";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import ProductIcon from "@/components/ProductIcon";
import { Button } from "@/components/ui/button";
import { checkoutWithWallet } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { shouldBlockFinancialDismiss } from "@/lib/modal-dismiss";
import { useTelegramBackButton } from "@/hooks/useTelegramBackButton";
import type { Product, ProductVariant } from "@/lib/products";
import { formatPrice, toPersianDigits } from "@/lib/utils";

interface CheckoutModalProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  product: Product;
  variant: ProductVariant;
  walletBalance: number | null;
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

function createCheckoutKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function CheckoutModal({ isOpen, setIsOpen, product, variant, walletBalance, onSuccess }: CheckoutModalProps) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [orderResult, setOrderResult] = useState<OrderResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(createCheckoutKey);

  const isOutOfStock = (variant.stockCount ?? 0) <= 0;
  const canPay = walletBalance !== null && walletBalance >= variant.rawPrice && !isOutOfStock;
  const hasEmptyWallet = walletBalance === 0;
  const shouldOfferCharge = walletBalance !== null && walletBalance < variant.rawPrice && !isOutOfStock;

  const handleSubmit = async () => {
    if (!canPay || isSubmitting) return;
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const result = await checkoutWithWallet(product.id, variant.id, idempotencyKey);
      setOrderResult({
        id: result.order.id,
        credentials: result.order.credentials,
        productBrand: result.order.productBrand,
        variantDuration: result.order.variantDuration,
      });
      setIdempotencyKey(createCheckoutKey());
      onSuccess?.();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "ثبت سفارش ناموفق بود.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!orderResult) return;
    if (await copyText(orderResult.credentials)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } else {
      window.Telegram?.WebApp?.showAlert(`اطلاعات را دستی کپی کنید:\n${orderResult.credentials}`);
    }
  };

  const handleClose = () => {
    if (isSubmitting) return;
    setOrderResult(null);
    setErrorMessage(null);
    setCopied(false);
    setIsOpen(false);
  };

  useTelegramBackButton(handleClose, isOpen);

  const handleChargeWallet = () => {
    handleClose();
    router.push("/finance?deposit=1");
  };

  if (orderResult) {
    return (
      <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent className="dialog-safe-area max-h-[90dvh] w-[95%] max-w-md overflow-y-auto rounded-3xl border-none p-0 font-sans text-[#F5F5F5]" style={DIALOG_STYLE}>
          <DialogDescription className="sr-only">اطلاعات سفارش و دسترسی خریداری‌شده</DialogDescription>
          <DialogHeader className="p-4 sticky top-0 z-20" style={HEADER_STYLE}>
            <div className="flex items-center gap-3">
              <button type="button" onClick={handleClose} className="p-2 rounded-full hover:bg-white/10 transition-colors" style={BACK_BTN_STYLE} aria-label="بستن نتیجه سفارش">
                <ChevronRight className="w-5 h-5" />
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
              <p className="select-text break-all font-mono text-sm leading-relaxed text-emerald-400">{orderResult.credentials}</p>
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
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent
        className="dialog-safe-area max-h-[90dvh] w-[95%] max-w-md overflow-y-auto rounded-3xl border-none p-0 font-sans text-[#F5F5F5]"
        style={DIALOG_STYLE}
        onEscapeKeyDown={(event) => shouldBlockFinancialDismiss(isSubmitting) && event.preventDefault()}
        onPointerDownOutside={(event) => shouldBlockFinancialDismiss(isSubmitting) && event.preventDefault()}
      >
        <DialogDescription className="sr-only">بررسی محصول، موجودی کیف پول و ثبت سفارش</DialogDescription>
        <DialogHeader className="p-4 sticky top-0 z-20" style={HEADER_STYLE}>
          <div className="flex items-center gap-3">
            <button type="button" onClick={handleClose} disabled={isSubmitting} className="p-2 rounded-full hover:bg-white/10 transition-colors disabled:opacity-40" style={BACK_BTN_STYLE}>
              <ChevronRight className="w-5 h-5" />
            </button>
            <DialogTitle className="text-lg font-bold">تسویه حساب</DialogTitle>
          </div>
        </DialogHeader>

        <div className="p-5 space-y-5">
          <div className="flex items-center justify-between gap-3 rounded-2xl p-4" style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)" }}>
            <div className="flex min-w-0 items-center gap-3">
              <ProductIcon icon={product.icon} assetUrl={product.assetUrl} gradient={product.gradient} category={product.category} sizeClassName="w-10 h-10" iconSizeClassName="w-4 h-4" />
              <div className="min-w-0">
                <h4 className="truncate text-sm font-bold">{product.brand}</h4>
                <p className="text-xs text-[#F5F5F5]/55 mt-0.5">{variant.duration}</p>
              </div>
            </div>
            <span className="shrink-0 font-bold text-[#F5F5F5]">{toPersianDigits(variant.priceLabel)}</span>
          </div>

          <div className="rounded-2xl p-4 flex items-center justify-between" style={{ background: "rgba(230,57,70,0.07)", border: "1px solid rgba(230,57,70,0.2)" }}>
            <div className="text-right">
              <span className="block text-sm font-bold">کیف پول</span>
              <span className="block text-[10px] text-[#F5F5F5]/50 mt-0.5">
                {walletBalance === null ? "موجودی در دسترس نیست" : `موجودی: ${formatPrice(walletBalance)} تومان`}
              </span>
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
                {walletBalance === null
                  ? "موجودی کیف پول دریافت نشد. پنجره را ببندید و دوباره تلاش کنید."
                  : isOutOfStock
                    ? "این گزینه اکنون موجود نیست."
                    : hasEmptyWallet
                      ? "موجودی کیف پول صفر است. پیش از خرید، کیف پول را شارژ کنید."
                      : "موجودی کیف پول برای این خرید کافی نیست."}
              </p>
              {shouldOfferCharge && (
                <Button
                  onClick={handleChargeWallet}
                  className="w-full py-4 rounded-xl text-xs font-bold transition-all active:scale-95 border-none gap-2"
                  style={{ background: "rgba(230,57,70,0.18)", color: "#F5F5F5" }}
                >
                  <Wallet className="w-4 h-4" />
                  افزایش موجودی
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
