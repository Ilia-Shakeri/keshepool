"use client";

import { useEffect, useMemo } from "react";
import { useState } from "react";
import { ChevronRight, CheckCircle2, Clock, Headphones, Shield, Zap } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import ProductIcon from "@/components/ProductIcon";
import type { Product, ProductVariant } from "@/lib/products";
import { toPersianDigits } from "@/lib/utils";

interface ProductDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  product: Product | null;
  initialVariantId?: string;
  onProceedToCheckout: (variant: ProductVariant) => void;
}

// Default feature icons assigned by index position
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

export default function ProductDetailModal({ isOpen, onClose, product, initialVariantId, onProceedToCheckout }: ProductDetailModalProps) {
  const [selectedVariantId, setSelectedVariantId] = useState("");

  useEffect(() => {
    void Promise.resolve().then(() => setSelectedVariantId(initialVariantId || ""));
  }, [product?.id, initialVariantId]);

  const activeVariant = useMemo(() => {
    if (!product || product.variants.length === 0) return null;
    return product.variants.find((v) => v.id === selectedVariantId) || product.variants[0];
  }, [product, selectedVariantId]);

  if (!product) return null;

  const outOfStock = !activeVariant || (activeVariant.stockCount ?? 0) <= 0;

  // Use product-specific features from DB if set, otherwise fall back to defaults
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
            <h3 className="text-sm font-bold text-[#F5F5F5] mb-3">انتخاب پلن</h3>
            <div className="space-y-2.5">
              {product.variants.map((variant) => {
                const isSelected = (selectedVariantId || product.variants[0].id) === variant.id;
                const variantOutOfStock = (variant.stockCount ?? 0) <= 0;

                return (
                  <button
                    key={variant.id}
                    onClick={() => setSelectedVariantId(variant.id)}
                    className="w-full flex items-center justify-between p-4 rounded-2xl transition-all duration-200"
                    style={
                      isSelected
                        ? {
                            background: "rgba(230,57,70,0.08)",
                            border: "1.5px solid rgba(230,57,70,0.6)",
                            boxShadow: "0 0 20px rgba(230,57,70,0.08)",
                          }
                        : {
                            background: "rgba(255,255,255,0.04)",
                            border: "1px solid rgba(255,255,255,0.08)",
                          }
                    }
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all"
                        style={
                          isSelected
                            ? { borderColor: "#E63946", background: "#E63946" }
                            : { borderColor: "rgba(255,255,255,0.2)" }
                        }
                      >
                        {isSelected && <div className="w-2 h-2 bg-white rounded-full" />}
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-bold text-[#F5F5F5]">{variant.duration}</p>
                        <p
                          className="text-[10px] mt-0.5"
                          style={{ color: variantOutOfStock ? "#E63946" : "#10b981" }}
                        >
                          {variantOutOfStock ? "ناموجود" : `موجودی: ${toPersianDigits(variant.stockCount || 0)}`}
                        </p>
                      </div>
                    </div>

                    <div className="text-left">
                      <p className="text-base font-bold text-[#F5F5F5]">{toPersianDigits(variant.priceLabel)}</p>
                      <p className="text-[10px] text-[#F5F5F5]/40">تومان</p>
                    </div>
                  </button>
                );
              })}
            </div>
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
            disabled={outOfStock}
            onClick={() => activeVariant && onProceedToCheckout(activeVariant)}
            className="w-full py-4 rounded-2xl text-sm font-bold transition-all active:scale-95"
            style={
              outOfStock
                ? { background: "rgba(255,255,255,0.06)", color: "rgba(245,245,245,0.3)", cursor: "not-allowed" }
                : {
                    background: "linear-gradient(135deg, #E63946 0%, #c0303c 100%)",
                    color: "white",
                    boxShadow: "0 8px 32px rgba(230,57,70,0.35)",
                  }
            }
          >
            {outOfStock
              ? "ناموجود"
              : `خرید — ${toPersianDigits(activeVariant?.priceLabel || "0")} تومان`}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
