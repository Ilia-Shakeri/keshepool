"use client";

import { useState } from "react";
import { ChevronRight, Share2, Heart, Star } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Product, ProductVariant } from "@/lib/products";

interface ProductDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  product: Product | null;
  onProceedToCheckout: (variant: ProductVariant) => void;
}

export default function ProductDetailModal({ isOpen, onClose, product, onProceedToCheckout }: ProductDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'features' | 'details'>('details');
  const [selectedVariantId, setSelectedVariantId] = useState<string>('');

  if (!product) return null;

  // Set default variant on load if none selected
  const activeVariant = product.variants.find(v => v.id === selectedVariantId) || product.variants[0];

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="bg-[#0a0a0c] border-none text-white w-full h-[100dvh] max-w-md mx-auto p-0 font-sans dir-rtl rounded-none flex flex-col">
        
        {/* Hidden Title for Accessibility compliance */}
        <DialogTitle className="sr-only">{product.title} Details</DialogTitle>

        {/* Header */}
        <header className="flex justify-between items-center p-5 pt-6 sticky top-0 bg-[#0a0a0c]/90 backdrop-blur-md z-20">
          <button onClick={onClose} className="p-2 bg-zinc-900 rounded-full hover:bg-zinc-800 transition-colors">
            <ChevronRight className="w-5 h-5 text-zinc-300" />
          </button>
          <div className="flex gap-3">
            <button className="p-2 bg-zinc-900 rounded-full hover:bg-zinc-800 transition-colors">
              <Share2 className="w-5 h-5 text-zinc-300" />
            </button>
            <button className="p-2 bg-zinc-900 rounded-full hover:bg-zinc-800 transition-colors">
              <Heart className="w-5 h-5 text-zinc-300" />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto pb-28 px-5">
          {/* Product Hero */}
          <div className="flex flex-col items-center text-center mt-2 mb-6">
            <div className={`w-20 h-20 rounded-full ${product.gradient} flex items-center justify-center shadow-lg mb-4`}>
              {product.icon}
            </div>
            <h1 className="text-xl font-bold text-white mb-1">{product.brand}</h1>
            <p className="text-xs text-zinc-400 mb-3">{product.subtitle}</p>
            <div className="flex items-center gap-1 text-xs text-zinc-300 font-medium bg-zinc-900 px-3 py-1 rounded-full">
              <Star className="w-3.5 h-3.5 text-red-500 fill-red-500" />
              4.9 <span className="text-zinc-500">(128)</span>
            </div>
            
            <div className="flex gap-2 mt-4">
              <span className="bg-zinc-800 text-zinc-300 text-[10px] px-3 py-1 rounded-full border border-zinc-700">گارانتی ۷ روزه</span>
              <span className="bg-red-500/10 text-red-500 text-[10px] px-3 py-1 rounded-full border border-red-500/20">تحویل فوری</span>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-4 border-b border-zinc-800 mb-5">
            <button 
              onClick={() => setActiveTab('features')}
              className={`pb-3 text-sm font-medium transition-all relative ${activeTab === 'features' ? 'text-white' : 'text-zinc-500'}`}
            >
              ویژگی‌ها
            </button>
            <button 
              onClick={() => setActiveTab('details')}
              className={`pb-3 text-sm font-medium transition-all relative ${activeTab === 'details' ? 'text-red-500' : 'text-zinc-500'}`}
            >
              جزئیات
              {activeTab === 'details' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-red-600 rounded-t-full" />}
            </button>
          </div>

          {/* Details Content */}
          <div className="mb-8">
            <p className="text-xs text-zinc-400 leading-relaxed mb-6">
              دسترسی کامل به {product.brand} با جدیدترین ورژن مناسب کارهای حرفه‌ای، برنامه‌نویسی، تحلیل داده و...
            </p>

            {/* Feature Grid */}
            <div className="grid grid-cols-2 gap-3 mb-8">
              {[
                "اکانت اشتراکی", "دسترسی به وب", 
                "بدون محدودیت پیام", "۵ کاربر در هر اکانت", 
                "تحویل فوری", "گارانتی ۷ روزه"
              ].map((feature, i) => (
                <div key={i} className="bg-[#121217] border border-zinc-800/80 rounded-xl p-3 text-center text-[10px] text-zinc-300">
                  {feature}
                </div>
              ))}
            </div>

            {/* Duration Selection */}
            <h3 className="text-sm font-bold text-white mb-4 text-center">انتخاب مدت زمان</h3>
            <div className="space-y-3">
              {product.variants.map((variant) => {
                const isSelected = (selectedVariantId || product.variants[0].id) === variant.id;
                return (
                  <button 
                    key={variant.id}
                    onClick={() => setSelectedVariantId(variant.id)}
                    className={`w-full flex items-center justify-between p-4 rounded-2xl border transition-all ${
                      isSelected ? 'border-red-600 bg-red-600/5' : 'border-zinc-800 bg-zinc-900/40 hover:bg-zinc-800/60'
                    }`}
                  >
                    <div className="flex flex-col items-start gap-1">
                      <span className="text-sm font-bold text-white">{variant.duration}</span>
                      {/* Mocking dynamic discounts based on variant index for UI matching */}
                      {product.variants.indexOf(variant) === 1 && <span className="text-[9px] text-zinc-500 line-through">۱,۲۰۰,۰۰۰</span>}
                      {product.variants.indexOf(variant) === 2 && <span className="text-[9px] text-zinc-500 line-through">۲,۴۰۰,۰۰۰</span>}
                    </div>
                    <div className="flex items-center gap-3">
                       <div className="flex flex-col items-end gap-1">
                          <span className="text-sm font-bold text-white">{variant.priceLabel} <span className="text-[10px] font-normal text-zinc-500">تومان</span></span>
                          {product.variants.indexOf(variant) === 1 && <span className="text-[10px] text-red-500 font-bold">%۷ تخفیف</span>}
                          {product.variants.indexOf(variant) === 2 && <span className="text-[10px] text-red-500 font-bold">%۱۲ تخفیف</span>}
                       </div>
                       <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${isSelected ? 'border-red-600' : 'border-zinc-600'}`}>
                         {isSelected && <div className="w-2 h-2 bg-red-600 rounded-full" />}
                       </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Fixed Bottom Action Bar */}
        <div className="fixed bottom-0 left-0 w-full p-5 bg-[#0a0a0c] border-t border-zinc-800/80 z-30 max-w-md left-1/2 -translate-x-1/2">
          <button 
            onClick={() => onProceedToCheckout(activeVariant)}
            className="w-full bg-red-600 hover:bg-red-500 text-white py-4 rounded-2xl text-sm font-bold shadow-lg shadow-red-600/20 transition-all active:scale-95"
          >
            خرید الان {activeVariant.priceLabel} تومان
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}