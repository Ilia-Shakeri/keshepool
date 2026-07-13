"use client";

import { useMemo, useState } from "react";
import { ChevronRight, CheckCircle2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import ProductIcon from "@/components/ProductIcon";
import { useTelegramBackButton } from "@/hooks/useTelegramBackButton";
import type { Product, ProductVariant } from "@/lib/products";
import { toPersianDigits } from "@/lib/utils";

interface ProductDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  product: Product | null;
  onProceedToCheckout: (variant: ProductVariant) => void;
}

type SelectableVariant = ProductVariant & {
  optionType?: string;
  optionFeatures?: string[] | null;
};

function displayTypeLabel(type: string): string {
  const normalized = type.trim().toLowerCase();
  if (normalized === "individual" || normalized === "personal" || normalized === "single") return "انفرادی";
  if (normalized === "family") return "خانوادگی";
  return type || "استاندارد";
}

export default function ProductDetailModal({ isOpen, onClose, product, onProceedToCheckout }: ProductDetailModalProps) {
  const [selectedType, setSelectedType] = useState("");
  const [selectedDuration, setSelectedDuration] = useState("");
  useTelegramBackButton(onClose, isOpen);

  const selectableVariants = useMemo<SelectableVariant[]>(() => product?.variants || [], [product]);

  const typeOptions = useMemo(() => {
    return Array.from(new Set(selectableVariants.map((variant) => variant.optionType || "استاندارد")));
  }, [selectableVariants]);

  const effectiveType = selectedType || (typeOptions.length === 1 ? typeOptions[0] : "");

  const durationOptions = useMemo(() => {
    if (!effectiveType) return [];
    return Array.from(
      new Set(
        selectableVariants
          .filter((variant) => (variant.optionType || "استاندارد") === effectiveType)
          .map((variant) => variant.duration),
      ),
    );
  }, [selectableVariants, effectiveType]);

  const effectiveDuration = selectedDuration || (durationOptions.length === 1 ? durationOptions[0] : "");

  const activeVariant = useMemo(() => {
    if (!effectiveType || !effectiveDuration) return null;
    return (
      selectableVariants.find(
        (variant) => (variant.optionType || "استاندارد") === effectiveType && variant.duration === effectiveDuration,
      ) || null
    );
  }, [selectableVariants, effectiveType, effectiveDuration]);

  if (!product) return null;

  const selectionComplete = Boolean(effectiveType && effectiveDuration && activeVariant);
  const outOfStock = selectionComplete && activeVariant ? (activeVariant.stockCount ?? 0) <= 0 : false;

  const featureLabels = activeVariant?.optionFeatures?.length
    ? activeVariant.optionFeatures
    : product.features || [];

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="dialog-safe-area flex h-[100dvh] w-full max-w-md flex-col rounded-none border-none bg-[#0A0A0B] p-0 font-sans text-[#F5F5F5] sm:h-auto sm:max-h-[min(90dvh,46rem)] sm:rounded-3xl">
        <DialogTitle className="sr-only">{product.title}</DialogTitle>
        <DialogDescription className="sr-only">انتخاب نوع، مدت و موجودی محصول</DialogDescription>

        {/* Sticky back button */}
        <header
          className="sticky top-0 z-20 flex items-center px-5 py-3"
          style={{
            background: "rgba(10,10,11,0.85)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-full transition-colors hover:bg-white/10 active:scale-95"
            style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.1)" }}
          >
            <ChevronRight className="w-4 h-4 text-[#F5F5F5]/80" />
            <span className="sr-only">بستن جزئیات محصول</span>
          </button>
        </header>

        <div className="flex-1 overflow-y-auto">
          {/* Hero section */}
          <div className="flex flex-col items-center text-center px-5 pt-6 pb-6">
            <ProductIcon
              icon={product.icon}
              assetUrl={product.assetUrl}
              gradient={product.gradient}
              category={product.category}
              sizeClassName="w-24 h-24"
              iconSizeClassName="w-10 h-10"
            />
            <h1 className="text-2xl font-bold text-[#F5F5F5] mt-4 mb-1">{product.brand}</h1>
            <p className="text-sm text-[#F5F5F5]/50 leading-relaxed max-w-xs">{product.subtitle}</p>

          </div>

          {featureLabels.length > 0 && <div className="px-5 mb-6">
            <div className="grid grid-cols-2 gap-2">
              {featureLabels.map((label, index) => (
                <div
                  key={`${label}-${index}`}
                  className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl"
                  style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
                >
                  <CheckCircle2 className="size-4 text-emerald-400" />
                  <span className="text-xs text-[#F5F5F5]/70 font-medium">{label}</span>
                </div>
              ))}
            </div>
          </div>}

          {/* Plan selector */}
          <div className="px-5">
            <h3 className="text-sm font-bold text-[#F5F5F5] mb-3">انتخاب نوع</h3>
            <div className="grid grid-cols-2 gap-2 mb-5">
              {typeOptions.map((type) => {
                const isSelected = effectiveType === type;
                return (
                  <button
                    key={type}
                    onClick={() => {
                      setSelectedType(type);
                      setSelectedDuration("");
                    }}
                    className="py-3 px-3 rounded-2xl text-xs font-bold transition-all"
                    style={
                      isSelected
                        ? { background: "rgba(230,57,70,0.1)", border: "1.5px solid rgba(230,57,70,0.65)", color: "#F5F5F5" }
                        : { background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "rgba(245,245,245,0.62)" }
                    }
                  >
                    {displayTypeLabel(type)}
                  </button>
                );
              })}
            </div>

            {effectiveType && (
              <>
                <h3 className="text-sm font-bold text-[#F5F5F5] mb-3">انتخاب مدت</h3>
                <div className="grid grid-cols-2 gap-2">
                  {durationOptions.map((duration) => {
                    const isSelected = effectiveDuration === duration;
                    return (
                      <button
                        key={duration}
                        onClick={() => setSelectedDuration(duration)}
                        className="py-3 px-3 rounded-2xl text-xs font-bold transition-all"
                        style={
                          isSelected
                            ? { background: "rgba(230,57,70,0.1)", border: "1.5px solid rgba(230,57,70,0.65)", color: "#F5F5F5" }
                            : { background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "rgba(245,245,245,0.62)" }
                        }
                      >
                        {duration}
                      </button>
                    );
                  })}
                </div>
              </>
            )}

            {selectionComplete && activeVariant && (
              <div
                className="mt-5 flex items-center justify-between rounded-2xl p-4"
                style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
              >
                <div>
                  <p className="text-[10px] text-[#F5F5F5]/45 mb-1">قیمت نهایی</p>
                  <p className="text-lg font-bold text-[#F5F5F5]">
                    {toPersianDigits(activeVariant.priceLabel)} <span className="text-[10px] text-[#F5F5F5]/40">تومان</span>
                  </p>
                </div>
                <p className="text-[10px] font-bold" style={{ color: outOfStock ? "#E63946" : "#10b981" }}>
                  {outOfStock ? "ناموجود" : `موجودی: ${toPersianDigits(activeVariant.stockCount || 0)}`}
                </p>
              </div>
            )}

            {!selectionComplete && (
              <p className="mt-5 text-[11px] text-[#F5F5F5]/45 text-center">برای نمایش قیمت، نوع و مدت را انتخاب کنید.</p>
            )}
          </div>
        </div>

        {/* Sticky bottom buy button - flex sibling, no positioning */}
        <div
          className="flex-shrink-0 px-5 pb-[max(1.25rem,var(--safe-area-bottom))] pt-5"
          style={{
            background: "rgba(10,10,11,0.95)",
            borderTop: "1px solid rgba(255,255,255,0.07)",
          }}
        >
          <button
            disabled={!selectionComplete || outOfStock}
            onClick={() => activeVariant && onProceedToCheckout(activeVariant)}
            className="w-full py-4 rounded-2xl text-sm font-bold transition-all active:scale-95"
            style={
              !selectionComplete || outOfStock
                ? { background: "rgba(255,255,255,0.06)", color: "rgba(245,245,245,0.3)", cursor: "not-allowed" }
                : {
                    background: "linear-gradient(135deg, #E63946 0%, #c0303c 100%)",
                    color: "white",
                    boxShadow: "0 8px 32px rgba(230,57,70,0.35)",
                  }
            }
          >
            {!selectionComplete ? "انتخاب نوع و مدت" : outOfStock ? "ناموجود" : `خرید — ${toPersianDigits(activeVariant?.priceLabel || "0")} تومان`}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
