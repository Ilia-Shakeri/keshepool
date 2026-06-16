"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
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

export default function ProductDetailModal({ isOpen, onClose, product, onProceedToCheckout }: ProductDetailModalProps) {
  const [activeTab, setActiveTab] = useState<"features" | "details">("details");
  const [selectedVariantId, setSelectedVariantId] = useState("");

  useEffect(() => {
    setSelectedVariantId("");
  }, [product?.id]);

  const activeVariant = useMemo(() => {
    if (!product || product.variants.length === 0) return null;
    return product.variants.find((variant) => variant.id === selectedVariantId) || product.variants[0];
  }, [product, selectedVariantId]);

  if (!product) return null;

  const outOfStock = !activeVariant || (activeVariant.stockCount ?? 0) <= 0;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="bg-[#0F0F10] border-none text-[#F5F5F5] w-full h-[100dvh] max-w-md mx-auto p-0 font-sans dir-rtl rounded-none flex flex-col">
        <DialogTitle className="sr-only">{product.title} Details</DialogTitle>

        <header className="flex justify-between items-center p-5 pt-6 sticky top-0 bg-[#0F0F10]/90 backdrop-blur-md z-20">
          <button onClick={onClose} className="p-2 bg-[#33383F] rounded-full hover:bg-[#33383F]/80 transition-colors">
            <ChevronRight className="w-5 h-5 text-[#F5F5F5]/80" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto pb-28 px-5">
          <div className="flex flex-col items-center text-center mt-2 mb-6">
            <ProductIcon icon={product.icon} assetUrl={product.assetUrl} gradient={product.gradient} sizeClassName="w-20 h-20" />
            <h1 className="text-xl font-bold text-[#F5F5F5] mb-1 mt-4">{product.brand}</h1>
            <p className="text-xs text-[#F5F5F5]/70 mb-3">{product.subtitle}</p>

            <div className="flex gap-2 mt-4">
              <span className="bg-[#33383F]/80 text-[#F5F5F5]/80 text-[10px] px-3 py-1 rounded-full border border-[#33383F]">گارانتی ۷ روزه</span>
              <span className="bg-[#E63946]/10 text-[#E63946] text-[10px] px-3 py-1 rounded-full border border-[#E63946]/20">تحویل فوری</span>
            </div>
          </div>

          <div className="flex gap-4 border-b border-[#33383F] mb-5">
            <button onClick={() => setActiveTab("features")} className={`pb-3 text-sm font-medium transition-all relative ${activeTab === "features" ? "text-[#F5F5F5]" : "text-[#F5F5F5]/50"}`}>
              ویژگی‌ها
              {activeTab === "features" && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-[#F5F5F5] rounded-t-full" />}
            </button>
            <button onClick={() => setActiveTab("details")} className={`pb-3 text-sm font-medium transition-all relative ${activeTab === "details" ? "text-[#E63946]" : "text-[#F5F5F5]/50"}`}>
              جزئیات
              {activeTab === "details" && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-[#E63946] rounded-t-full" />}
            </button>
          </div>

          <div className="mb-8">
            {activeTab === "details" ? (
              <div className="animate-in fade-in zoom-in-95 duration-200">
                <p className="text-xs text-[#F5F5F5]/70 leading-relaxed mb-6">
                  دسترسی کامل به {product.brand} با تحویل امن و پشتیبانی.
                </p>
                <h3 className="text-sm font-bold text-[#F5F5F5] mb-4 text-center">انتخاب مدت زمان</h3>
                <div className="space-y-3">
                  {product.variants.map((variant) => {
                    const isSelected = (selectedVariantId || product.variants[0].id) === variant.id;
                    const variantOutOfStock = (variant.stockCount ?? 0) <= 0;
                    return (
                      <button
                        key={variant.id}
                        onClick={() => setSelectedVariantId(variant.id)}
                        className={`w-full flex items-center justify-between p-4 rounded-2xl border transition-all ${
                          isSelected ? "border-[#E63946] bg-[#E63946]/5" : "border-[#33383F] bg-[#0F0F10]/40 hover:bg-[#33383F]/60"
                        }`}
                      >
                        <div className="flex flex-col items-start gap-1">
                          <span className="text-sm font-bold text-[#F5F5F5]">{variant.duration}</span>
                          <span className={`text-[10px] ${variantOutOfStock ? "text-[#E63946]" : "text-emerald-400"}`}>
                            {variantOutOfStock ? "ناموجود" : `موجودی: ${toPersianDigits(variant.stockCount || 0)}`}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-bold text-[#F5F5F5]">
                            {toPersianDigits(variant.priceLabel)} <span className="text-[10px] font-normal text-[#F5F5F5]/50">تومان</span>
                          </span>
                          <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${isSelected ? "border-[#E63946]" : "border-[#33383F]"}`}>
                            {isSelected && <div className="w-2 h-2 bg-[#E63946] rounded-full" />}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="animate-in fade-in zoom-in-95 duration-200">
                <h3 className="text-sm font-bold text-[#F5F5F5] mb-4 text-center">ویژگی‌های سرویس</h3>
                <div className="grid grid-cols-2 gap-3">
                  {["تحویل امن", "ثبت سفارش خودکار", "بدون اطلاعات ساختگی", "پشتیبانی ۲۴ ساعته", "موجودی لحظه‌ای", "کیف پول امن"].map((feature) => (
                    <div key={feature} className="bg-[#0B1D33] border border-[#33383F] rounded-xl p-3 text-center text-[10px] text-[#F5F5F5]/80">
                      {feature}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="fixed bottom-0 w-full p-5 bg-[#0F0F10] border-t border-[#33383F] z-30 max-w-md left-1/2 -translate-x-1/2">
          <button
            disabled={outOfStock}
            onClick={() => activeVariant && onProceedToCheckout(activeVariant)}
            className={`w-full py-4 rounded-2xl text-sm font-bold shadow-lg transition-all active:scale-95 border-none ${
              outOfStock ? "bg-[#33383F] text-[#F5F5F5]/40 cursor-not-allowed" : "bg-[#E63946] hover:bg-[#E63946]/90 text-[#F5F5F5] shadow-[#E63946]/20"
            }`}
          >
            {outOfStock ? "ناموجود" : `خرید الان ${toPersianDigits(activeVariant?.priceLabel || "0")} تومان`}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}