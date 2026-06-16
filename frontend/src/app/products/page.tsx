"use client";

import { useState, useEffect } from "react";
import { SlidersHorizontal, ChevronLeft } from "lucide-react";
import { ProductCategory, Product, ProductVariant } from "@/lib/products";
import { IconMap } from "@/lib/icons";
import ProductDetailModal from "@/components/ProductDetailModal";
import CheckoutModal from "@/components/CheckoutModal";
import { toPersianDigits } from "@/lib/utils";

const CATEGORIES: { id: ProductCategory | 'all', label: string }[] = [
  { id: 'all', label: 'همه' },
  { id: 'video', label: 'استریم' },
  { id: 'ai', label: 'AI' },
  { id: 'music', label: 'موسیقی' },
  { id: 'tools', label: 'طراحی' },
  { id: 'gaming', label: 'برنامه‌نویسی' },
];

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [activeCategory, setActiveCategory] = useState<ProductCategory | 'all'>('all');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const walletBalance = 820000;

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const response = await fetch('/api/products');
        if (response.ok) {
          const data = await response.json();
          setProducts(data);
        }
      } catch (error) {
        console.error("Pipeline failure fetching product catalog", error);
      }
    };
    fetchProducts();
  }, []);

  const filteredProducts = products.filter(product => 
    activeCategory === 'all' || product.category === activeCategory
  );

  const handleProductSelect = (product: Product) => {
    setSelectedProduct(product);
    setIsDetailModalOpen(true);
  };

  const handleProceedToCheckout = (variant: ProductVariant) => {
    setSelectedVariant(variant);
    setIsDetailModalOpen(false);
    setTimeout(() => {
      setIsCheckoutOpen(true);
    }, 150);
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32">
      <header className="p-5 pt-6 pb-2">
        <div className="flex justify-center items-center mb-6 relative">
          <h1 className="text-base font-bold text-[#F5F5F5] absolute left-1/2 -translate-x-1/2">محصولات</h1>
        </div>

        <div className="relative mb-6">
          <input 
            type="text" 
            placeholder="جستجو بین سرویس‌ها..." 
            className="w-full bg-[#0B1D33] border border-[#33383F] rounded-2xl py-3.5 pr-4 pl-12 text-sm text-[#F5F5F5] focus:outline-none focus:border-[#E63946]/50 transition-colors placeholder:text-[#F5F5F5]/50"
          />
          <button className="absolute left-3 top-1/2 -translate-y-1/2 p-1 text-[#F5F5F5]/70 hover:text-[#F5F5F5]">
            <SlidersHorizontal className="w-5 h-5" />
          </button>
        </div>

        <div className="flex gap-2 overflow-x-auto scrollbar-hide dir-rtl pb-2 -mx-5 px-5">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`whitespace-nowrap px-5 py-2 rounded-xl text-xs font-medium transition-all ${
                activeCategory === cat.id 
                  ? 'bg-[#E63946] text-[#F5F5F5]' 
                  : 'bg-[#0B1D33] text-[#F5F5F5]/70 border border-[#33383F] hover:bg-[#33383F]/50'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </header>

      <main className="px-5 space-y-3 mt-2">
        {filteredProducts.map((product) => (
          <div 
            key={product.id}
            onClick={() => handleProductSelect(product)}
            className="bg-[#0B1D33] border border-[#33383F] rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:bg-[#1E3C5A]/50 transition-colors group"
          >
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${product.gradient} flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform`}>
                {IconMap[product.icon] || IconMap["Box"]}
              </div>
              <div className="flex flex-col gap-1">
                <h3 className="text-sm font-bold text-[#F5F5F5]">{product.brand}</h3>
                <p className="text-[10px] text-[#F5F5F5]/50">{product.subtitle}</p>
              </div>
            </div>
            
            <div className="flex flex-col items-end justify-between h-full py-1 gap-4">
              <ChevronLeft className="w-4 h-4 text-[#F5F5F5]/50" />
              <div className="flex flex-col items-end gap-0.5">
                  <span className="text-xs font-bold text-[#F5F5F5]">{toPersianDigits(product.variants[0]?.priceLabel || '0')}</span>
                  <span className="text-[10px] text-[#F5F5F5]/50">تومان</span>
              </div>
            </div>
          </div>
        ))}

        {filteredProducts.length === 0 && (
          <div className="text-center py-12 text-[#F5F5F5]/50 text-sm">
            محصولی یافت نشد.
          </div>
        )}
      </main>

      {/* Render Modals securely */}
      <ProductDetailModal 
        isOpen={isDetailModalOpen} 
        onClose={() => setIsDetailModalOpen(false)} 
        product={selectedProduct} 
        onProceedToCheckout={handleProceedToCheckout} 
      />

      {selectedProduct && selectedVariant && (
        <CheckoutModal 
          isOpen={isCheckoutOpen} 
          setIsOpen={setIsCheckoutOpen} 
          product={selectedProduct} 
          variant={selectedVariant} 
          walletBalance={walletBalance} 
        />
      )}
    </div>
  );
}