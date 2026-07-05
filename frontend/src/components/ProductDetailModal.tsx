"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronRight, CheckCircle2, Clock, Headphones, Shield, Zap } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import ProductIcon from "@/components/ProductIcon";
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

const FEATURE_ICONS = [
  <Shield key="0" className="w-4 h-4 text-emerald-400" />,
  <Zap key="1" className="w-4 h-4 text-yellow-400" />,
  <Clock key="2" className="w-4 h-4 text-blue-400" />,
  <Headphones key="3" className="w-4 h-4 text-purple-400" />,
];

const DEFAULT_FEATURES = [
  { icon: FEATURE_ICONS[0], label: "تحویل امن" },
  { icon: FEATURE_ICONS[1], label: "تحویل فوری" },
  { icon: FEATURE_ICONS[2], label: "گارانتی ۷ روزه" },
  { icon: FEATURE_ICONS[3], label: "پشتیبانی ۲۴ ساعته" },
];

function displayTypeLabel(type: string): string {
  const normalized = type.trim().toLowerCase();
  if (normalized === "individual" || normalized === "personal" || normalized === "single") return "انفرادی";
  if (normalized === "family") return "خانوادگی";
  return type || "استاندارد";
}

export default function ProductDetailModal({ isOpen, onClose, product, onProceedToCheckout }: ProductDetailModalProps) {
  const [selectedType, setSelectedType] = useState("");
  const [selectedDuration, setSelectedDuration] = useState("");

  useEffect(() => {
    setSelectedType("");
    setSelectedDuration("");
  }, [product?.id, isOpen]);

  const selectableVariants = useMemo<SelectableVariant[]>(() => product?.variants || [], [product]);

  const typeOptions = useMemo(() => {
    return Array.from(new Set(selectableVariants.map((variant) => variant.optionType || "استاندارد")));
  }, [selectableVariants]);

  const durationOptions = useMemo(() => {
    if (!selectedType) return [];
    return Array.from(
      new Set(
        selectableVariants
          .filter((variant) => (variant.optionType || "استاندارد") === selectedType)
          .map((variant) => variant.duration),
      ),
    );
  }, [selectableVariants, selectedType]);

  const activeVariant = useMemo(() => {
    if (!selectedType || !selectedDuration) return null;
    return (
      selectableVariants.find(
        (variant) => (variant.optionType || "استاندارد") === selectedType && variant.duration === selectedDuration,
      ) || null
    );
  }, [selectableVariants, selectedType, selectedDuration]);

  if (!product) return null;

  const selectionComplete = Boolean(selectedType && selectedDuration && activeVariant);
  const outOfStock = selectionComplete && activeVariant ? (activeVariant.stockCount ?? 0) <= 0 : false;

  const features =
    product.features && product.features.length > 0
      ? product.features.map((label, i) => ({
          icon: FEATURE_ICONS[i] ?? <CheckCircle2 key={i} className="w-4 h-4 text-emerald-400" />,
          label,
        }))
      : DEFAULT_FEATURES;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="bg-[#0A0A0B] border-none text-[#F5F5F5] w-full h-[100dvh] max-w-md mx-auto p-0 font-sans dir-rtl rounded-none flex flex-col">
        <DialogTitle className="sr-only">{product.title}</DialogTitle>

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
            onClick={onClose}
            className="p-2 rounded-full transition-colors hover:bg-white/10 active:scale-95"
            style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.1)" }}
          >
            <ChevronRight className="w-4 h-4 text-[#F5F5F5]/80" />
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

            <div className="flex gap-2 mt-4">
              <span
                className="text-[10px] px-3 py-1 rounded-full font-semibold"
                style={{ background: "rgba(16,185,129,0.12)", color: "#10b981", border: "1px solid rgba(16,185,129,0.2)" }}
              >
                گارانتی ۷ روزه
              </span>
              <span
                className="text-[10px] px-3 py-1 rounded-full font-semibold"
                style={{ background: "rgba(230,57,70,0.12)", color: "#E63946", border: "1px solid rgba(230,57,70,0.2)" }}
              >
                تحویل فوری
              </span>
            </div>
          </div>

          {/* Feature chips */}
          <div className="px-5 mb-6">
            <div className="grid grid-cols-2 gap-2">
              {features.map((f) => (
                <div
                  key={f.label}
                  className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl"
                  style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
                >
                  {f.icon}
                  <span className="text-xs text-[#F5F5F5]/70 font-medium">{f.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Plan selector */}
          <div className="px-5">
            <h3 className="text-sm font-bold text-[#F5F5F5] mb-3">انتخاب نوع</h3>
            <div className="grid grid-cols-2 gap-2 mb-5">
              {typeOptions.map((type) => {
                const isSelected = selectedType === type;
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

            {selectedType && (
              <>
                <h3 className="text-sm font-bold text-[#F5F5F5] mb-3">انتخاب مدت</h3>
                <div className="grid grid-cols-2 gap-2">
                  {durationOptions.map((duration) => {
                    const isSelected = selectedDuration === duration;
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
          className="p-5 flex-shrink-0"
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
