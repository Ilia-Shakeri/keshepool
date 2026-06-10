"use client";

import { useState } from "react";
import { ChevronRight, CreditCard, Zap } from "lucide-react";
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

  // Filter products based on selected category
  const filteredProducts = PRODUCTS.filter(product => 
    activeCategory === 'all' || product.category === activeCategory
  );

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans p-4 max-w-lg mx-auto pb-40">
      <header className="flex justify-between items-center mb-6 border-b border-slate-800/50 pb-4">
        <h1 className="text-xl font-bold text-cyan-400">محصولات پرمیوم</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors flex items-center gap-1">
          بازگشت <ChevronRight className="w-5 h-5" />
        </button>
      </header>

      {/* Categories Filter (Horizontal Scroll) */}
      <div className="flex gap-2 overflow-x-auto pb-4 mb-2 scrollbar-hide dir-rtl">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            className={`whitespace-nowrap px-4 py-2 rounded-full text-xs font-bold transition-all border ${
              activeCategory === cat.id 
                ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50' 
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
                onClick={() => setSelectedProduct(product)}
                className="bg-slate-800/40 border border-slate-700 hover:border-cyan-500/30 rounded-2xl p-4 flex flex-col items-center text-center cursor-pointer transition-all hover:bg-slate-800 active:scale-95 shadow-lg"
              >
                <div className={`bg-gradient-to-br ${product.gradient} p-3 rounded-2xl shadow-lg ${product.shadow} mb-3`}>
                  {product.icon}
                </div>
                <h3 className="text-sm font-bold text-white mb-1">{product.brand}</h3>
                <p className="text-[10px] text-slate-400 line-clamp-1 mb-3">{product.title}</p>
                <div className="mt-auto w-full bg-slate-900/50 py-1.5 rounded-lg border border-slate-700 text-cyan-400 font-bold text-xs flex items-center justify-center gap-1">
                  {product.price} <span className="font-normal text-[9px] text-slate-500">تومان</span>
                </div>
              </div>
            </DialogTrigger>

            {/* Reusable Purchase Modal */}
            <DialogContent className="bg-slate-900 border border-slate-700 text-white rounded-2xl w-[90%] mx-auto">
              {selectedProduct && (
                <>
                  <DialogHeader className="pt-2">
                    <div className="flex items-center gap-3 mb-4 justify-end">
                      <div className="text-right">
                        <DialogTitle className="text-xl font-bold text-white">{selectedProduct.title}</DialogTitle>
                        <p className="text-xs text-cyan-400 mt-1">{selectedProduct.subtitle}</p>
                      </div>
                      <div className={`bg-gradient-to-br ${selectedProduct.gradient} p-2 rounded-xl shadow-lg`}>
                        {selectedProduct.icon}
                      </div>
                    </div>
                    <DialogDescription className="text-right text-slate-400 bg-slate-800/50 p-3 rounded-lg border border-slate-700">
                      مبلغ قابل پرداخت: <span className="text-cyan-400 font-bold">{selectedProduct.price} تومان</span>
                    </DialogDescription>
                  </DialogHeader>
                  <div className="flex flex-col gap-3 mt-2">
                    <Button className="w-full bg-green-600 hover:bg-green-500 text-white py-6 rounded-xl text-md font-bold flex gap-2" onClick={() => {
                      alert("Redirecting to secure payment gateway...");
                    }}>
                      <CreditCard className="w-5 h-5" /> پرداخت و تحویل آنی <Zap className="w-4 h-4 text-yellow-400 fill-current" />
                    </Button>
                    <DialogClose asChild>
                      <Button variant="ghost" className="w-full text-slate-400 hover:text-white hover:bg-slate-800 py-6 rounded-xl">
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
    </div>
  );
}