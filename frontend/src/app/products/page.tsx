"use client";

import { useState } from "react";
import { Search, SlidersHorizontal, ChevronLeft, Star } from "lucide-react";
import { PRODUCTS, ProductCategory, Product, ProductVariant } from "@/lib/products";
import ProductDetailModal from "@/components/ProductDetailModal";
import CheckoutModal from "@/components/CheckoutModal";

// Adjusted categories to match the UI perfectly
const CATEGORIES: { id: ProductCategory | 'all', label: string }[] = [
  { id: 'all', label: 'همه' },
  { id: 'video', label: 'استریم' },
  { id: 'ai', label: 'AI' },
  { id: 'music', label: 'موسیقی' },
  { id: 'tools', label: 'طراحی' },
  { id: 'gaming', label: 'برنامه‌نویسی' },
];

export default function ProductsPage() {
  const [activeCategory, setActiveCategory] = useState<ProductCategory | 'all'>('all');
  
  // Navigation State Management
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);

  // Mock Wallet Balance
  const walletBalance = 820000;

  const filteredProducts = PRODUCTS.filter(product => 
    activeCategory === 'all' || product.category === activeCategory
  );

  // Flow Step 1: Open Details
  const handleProductSelect = (product: Product) => {
    setSelectedProduct(product);
    setIsDetailModalOpen(true);
  };

  // Flow Step 2: Proceed from Details to Checkout
  const handleProceedToCheckout = (variant: ProductVariant) => {
    setSelectedVariant(variant);
    setIsDetailModalOpen(false);
    
    // Slight delay to allow Detail modal to close smoothly before opening Checkout
    setTimeout(() => {
      setIsCheckoutOpen(true);
    }, 150);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-white font-sans pb-32">
      {/* Header */}
      <header className="p-5 pt-6 pb-2">
        <div className="flex justify-between items-center mb-6">
          <Search className="w-5 h-5 text-zinc-300" />
          <h1 className="text-base font-bold text-white">اکتشاف</h1>
        </div>

        {/* Search Bar */}
        <div className="relative mb-6">
          <input 
            type="text" 
            placeholder="جستجو بین سرویس‌ها..." 
            className="w-full bg-[#121217] border border-zinc-800 rounded-2xl py-3.5 pr-4 pl-12 text-sm text-white focus:outline-none focus:border-red-500/50 transition-colors placeholder:text-zinc-500"
          />
          <button className="absolute left-3 top-1/2 -translate-y-1/2 p-1 text-zinc-400 hover:text-white">
            <SlidersHorizontal className="w-5 h-5" />
          </button>
        </div>

        {/* Category Chips */}
        <div className="flex gap-2 overflow-x-auto scrollbar-hide dir-rtl pb-2 -mx-5 px-5">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`whitespace-nowrap px-5 py-2 rounded-xl text-xs font-medium transition-all ${
                activeCategory === cat.id 
                  ? 'bg-red-600 text-white' 
                  : 'bg-[#121217] text-zinc-400 border border-zinc-800 hover:bg-zinc-800'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </header>

      {/* Product List */}
      <main className="px-5 space-y-3 mt-2">
        {filteredProducts.map((product) => (
          <div 
            key={product.id}
            onClick={() => handleProductSelect(product)}
            className="bg-[#121217] border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:bg-zinc-900 transition-colors group"
          >
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-2xl ${product.gradient} flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform`}>
                {product.icon}
              </div>
              <div className="flex flex-col gap-1">
                <h3 className="text-sm font-bold text-white">{product.brand}</h3>
                <p className="text-[10px] text-zinc-500">{product.subtitle}</p>
                <p className="text-[10px] text-zinc-400 mt-1">از <span className="text-white font-bold">{product.variants[0].priceLabel}</span> تومان</p>
              </div>
            </div>
            
            <div className="flex flex-col items-end justify-between h-full py-1 gap-4">
              <ChevronLeft className="w-4 h-4 text-zinc-500" />
              <div className="flex items-center gap-1 text-[10px] text-zinc-400 font-medium">
                <Star className="w-3 h-3 text-red-500 fill-red-500" />
                4.9
              </div>
            </div>
          </div>
        ))}

        {filteredProducts.length === 0 && (
          <div className="text-center py-12 text-zinc-500 text-sm">
            محصولی یافت نشد.
          </div>
        )}
      </main>

      {/* Layer 1: Product Detail Sheet */}
      <ProductDetailModal 
        isOpen={isDetailModalOpen} 
        onClose={() => setIsDetailModalOpen(false)} 
        product={selectedProduct} 
        onProceedToCheckout={handleProceedToCheckout} 
      />

      {/* Layer 2: Final Checkout Modal */}
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