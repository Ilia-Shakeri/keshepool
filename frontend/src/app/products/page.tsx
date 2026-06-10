"use client";

import { useState } from "react";
import { ChevronRight, CreditCard, Zap, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { PRODUCTS, ProductCategory, Product } from "@/lib/products";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, 
  DialogTitle, DialogTrigger, DialogClose
} from "@/components/ui/dialog";

// Category definitions for the filter pill bar
const CATEGORIES: { id: ProductCategory | 'all', label: string }[] = [
  { id: 'all', label: 'همه محصولات' },
  { id: 'video', label: 'فیلم و سریال' },
  { id: 'music', label: 'موسیقی' },
  { id: 'ai', label: 'هوش مصنوعی' },
  { id: 'gaming', label: 'گیمینگ' },
  { id: 'tools', label: 'ابزارها' },
  { id: 'vpn', label: 'وی‌پی‌ان' },
];

export default function ProductsPage() {
  const router = useRouter();
  const [activeCategory, setActiveCategory] = useState<ProductCategory | 'all'>('all');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedVariantIndex, setSelectedVariantIndex] = useState(0);

  // Filter products based on selected category
  const filteredProducts = PRODUCTS.filter(product => 
    activeCategory === 'all' || product.category === activeCategory
  );

  // Handle product selection to reset variant index
  const handleProductSelect = (product: Product) => {
    setSelectedProduct(product);
    setSelectedVariantIndex(0);
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans pb-40 relative">
      
      {/* Sticky Header with Backdrop Blur */}
      <header className="flex justify-between items-center p-4 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-slate-800/50 mb-4 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-cyan-400">محصولات پرمیوم</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1 bg-slate-800/50 px-3 py-1.5 rounded-xl">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      <main className="px-4 max-w-lg mx-auto">
        {/* Categories Filter (Horizontal Scroll) */}
        <div className="flex gap-2 overflow-x-auto pb-4 mb-4 scrollbar-hide dir-rtl">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`whitespace-nowrap px-4 py-2 rounded-full text-xs font-bold transition-all border ${
                activeCategory === cat.id 
                  ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50 shadow-lg shadow-cyan-500/10' 
                  : 'bg-slate-800/50 text-slate-400 border-slate-700 hover:bg-slate-800'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Products Grid */}
        <div className="grid grid-cols-2 gap-4">
          {filteredProducts.map((product) => (
            <Dialog key={product.id}>
              <DialogTrigger asChild>
                <div 
                  onClick={() => handleProductSelect(product)}
                  className="group bg-slate-800/40 border border-slate-700 hover:border-cyan-500/50 rounded-3xl p-5 flex flex-col items-center text-center cursor-pointer transition-all hover:bg-slate-800 active:scale-95 shadow-lg relative overflow-hidden"
                >
                  <div className="absolute top-0 right-0 w-20 h-20 bg-white/5 rounded-full blur-2xl group-hover:bg-cyan-500/10 transition-colors pointer-events-none"></div>
                  
                  <div className={`bg-gradient-to-br ${product.gradient} p-4 rounded-2xl shadow-xl ${product.shadow} mb-4 transform group-hover:scale-110 transition-transform duration-300 relative z-10`}>
                    {product.icon}
                  </div>
                  <h3 className="text-sm font-bold text-white mb-1 relative z-10">{product.brand}</h3>
                  <p className="text-[10px] text-slate-400 line-clamp-1 mb-4 relative z-10">{product.title}</p>
                  
                  <div className="mt-auto w-full bg-slate-900/80 py-2 rounded-xl border border-slate-700/50 text-cyan-400 font-bold text-xs flex items-center justify-center gap-1 relative z-10 group-hover:bg-slate-900 group-hover:border-cyan-500/30 transition-colors">
                    شروع از {product.variants[0].priceLabel} <span className="font-normal text-[9px] text-slate-500">تومان</span>
                  </div>
                </div>
              </DialogTrigger>

              {/* Reusable Purchase Modal with Variants */}
              <DialogContent className="bg-slate-900 border border-slate-700 text-white rounded-3xl w-[90%] mx-auto overflow-hidden">
                <div className="absolute top-0 right-0 w-full h-32 bg-gradient-to-b from-cyan-500/10 to-transparent pointer-events-none"></div>
                {selectedProduct && (
                  <>
                    <DialogHeader className="pt-2 relative z-10">
                      <div className="flex items-center gap-4 mb-4 justify-end">
                        <div className="text-right">
                          <DialogTitle className="text-xl font-bold text-white">{selectedProduct.title}</DialogTitle>
                          <p className="text-xs text-slate-400 mt-1">{selectedProduct.subtitle}</p>
                        </div>
                        <div className={`bg-gradient-to-br ${selectedProduct.gradient} p-3 rounded-2xl shadow-lg`}>
                          {selectedProduct.icon}
                        </div>
                      </div>
                      
                      {/* Subscription Duration Selector */}
                      <div className="mt-4">
                        <label className="text-xs text-slate-400 block text-right mb-2">انتخاب مدت زمان اشتراک:</label>
                        <div className="grid grid-cols-3 gap-2">
                          {selectedProduct.variants.map((variant, idx) => (
                            <button
                              key={variant.id}
                              onClick={() => setSelectedVariantIndex(idx)}
                              className={`py-2 px-1 rounded-xl text-xs font-bold transition-all border flex flex-col items-center gap-1 ${
                                selectedVariantIndex === idx 
                                  ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50' 
                                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
                              }`}
                            >
                              <span>{variant.duration}</span>
                              {selectedVariantIndex === idx && <CheckCircle2 className="w-3 h-3" />}
                            </button>
                          ))}
                        </div>
                      </div>

                      <DialogDescription className="text-right text-slate-300 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50 mt-4 flex justify-between items-center">
                        <span className="text-cyan-400 font-bold text-lg">{selectedProduct.variants[selectedVariantIndex].priceLabel} <span className="text-sm font-normal text-slate-400">تومان</span></span>
                        <span className="text-sm">مبلغ قابل پرداخت:</span>
                      </DialogDescription>
                    </DialogHeader>
                    
                    <div className="flex flex-col gap-3 mt-4 relative z-10">
                      <Button className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white py-6 rounded-xl text-md font-bold flex gap-2 shadow-lg shadow-cyan-500/20" onClick={() => {
                        alert(`Redirecting to secure payment gateway for ${selectedProduct.variants[selectedVariantIndex].duration}...`);
                      }}>
                        <CreditCard className="w-5 h-5" /> پرداخت و تحویل آنی <Zap className="w-4 h-4 text-yellow-400 fill-current" />
                      </Button>
                      <DialogClose asChild>
                        <Button variant="ghost" className="w-full text-slate-400 hover:text-white hover:bg-slate-800 py-6 rounded-xl border border-transparent hover:border-slate-700">
                          انصراف
                        </Button>
                      </DialogClose>
                    </div>
                  </>
                )}
              </DialogContent>
            </Dialog>
          ))}
        </div>

        {/* Empty State Fallback */}
        {filteredProducts.length === 0 && (
          <div className="text-center py-12 text-slate-500 text-sm">
            محصولی در این دسته‌بندی یافت نشد.
          </div>
        )}
      </main>
    </div>
  );
}