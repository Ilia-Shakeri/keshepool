"use client";

import { useState } from "react";
import { CreditCard, Zap, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { PRODUCTS, ProductCategory, Product } from "@/lib/products";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, 
  DialogTitle, DialogTrigger, DialogClose
} from "@/components/ui/dialog";

// Define strict categories for the top filter bar
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

  // State variables for account provisioning logic
  const [activationMethod, setActivationMethod] = useState<'random' | 'personal'>('random');
  const [accountEmail, setAccountEmail] = useState('');
  const [accountPassword, setAccountPassword] = useState('');

  // Filter product catalog based on the selected category filter
  const filteredProducts = PRODUCTS.filter(product => 
    activeCategory === 'all' || product.category === activeCategory
  );

  // Set selected product state and default variant index to zero securely
  const handleProductSelect = (product: Product) => {
    setSelectedProduct(product);
    setSelectedVariantIndex(0);
    setActivationMethod('random'); // Reset form cleanly
    setAccountEmail('');
    setAccountPassword('');
  };

  // Process checkout redirection via Telegram SDK safely with validation
  const handleCheckoutProcess = () => {
    if (!selectedProduct) return;
    
    // Form validation before proceeding
    if (activationMethod === 'personal' && (!accountEmail || !accountPassword)) {
      alert("لطفاً ایمیل و رمز عبور اکانت خود را برای فعالسازی وارد کنید.");
      return;
    }

    const paymentTargetUrl = "https://your-domain.com/pay/gateway";
    
    if (typeof window !== "undefined" && window.Telegram?.WebApp?.openLink) {
      window.Telegram.WebApp.openLink(paymentTargetUrl);
    } else {
      window.open(paymentTargetUrl, "_blank");
    }
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans pb-40 relative">
      
      {/* Sticky Top Header Configuration */}
      <header className="flex justify-between items-center p-4 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-slate-800/50 mb-4 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-cyan-400">محصولات پرمیوم</h1>
        <button onClick={() => router.back()} className="text-slate-400 hover:text-white transition-colors bg-slate-800/50 px-4 py-1.5 rounded-xl text-sm font-medium">
          بازگشت
        </button>
      </header>

      <main className="px-4 max-w-lg mx-auto">
        {/* Horizontal Category Scroll View */}
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

        {/* Dynamic Product Grid */}
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

              {/* Shared Dialog Component for Product Subscriptions */}
              <DialogContent className="bg-slate-900 border border-slate-700 text-white rounded-3xl w-[90%] max-w-md mx-auto overflow-y-auto max-h-[90vh]">
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
                      
                      {/* Subscription Variant Selector Grid (Checkmarks Removed, Added Glow) */}
                      <div className="mt-4">
                        <label className="text-sm font-bold text-slate-300 block text-right mb-3">انتخاب مدت زمان اشتراک:</label>
                        <div className="grid grid-cols-3 gap-2">
                          {selectedProduct.variants.map((variant, idx) => (
                            <button
                              key={variant.id}
                              onClick={() => setSelectedVariantIndex(idx)}
                              className={`py-3 px-1 rounded-xl text-xs font-bold transition-all border flex flex-col items-center gap-1 ${
                                selectedVariantIndex === idx 
                                  ? 'bg-cyan-500/20 text-cyan-400 border-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.3)]' 
                                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
                              }`}
                            >
                              <span>{variant.duration}</span>
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Total Price Layout with correct Right-to-Left alignment */}
                      <DialogDescription className="text-slate-300 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50 mt-4 flex justify-between items-center w-full">
                        <span className="text-sm font-bold text-right">مبلغ قابل پرداخت:</span>
                        <span className="text-cyan-400 font-bold text-lg flex items-center gap-1 dir-ltr text-left">
                          {selectedProduct.variants[selectedVariantIndex].priceLabel} <span className="text-sm font-normal text-slate-400">تومان</span>
                        </span>
                      </DialogDescription>
                    </DialogHeader>
                    
                    {/* Dynamic Account Provisioning Method Selection */}
                    <div className="mt-4 border-t border-slate-800 pt-4 relative z-10">
                      <label className="text-sm font-bold text-slate-300 block text-right mb-3">نوع فعالسازی اکانت:</label>
                      <div className="grid grid-cols-2 gap-3 mb-4">
                        <button 
                          onClick={() => setActivationMethod('random')} 
                          className={`p-3 rounded-xl text-xs font-bold transition-all border flex flex-col items-center justify-center gap-2 ${activationMethod === 'random' ? 'bg-cyan-500/20 text-cyan-400 border-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.3)]' : 'bg-slate-800 text-slate-400 border-slate-700'}`}
                        >
                          <Zap className="w-5 h-5" />
                          اکانت آماده (تحویل فوری)
                        </button>
                        <button 
                          onClick={() => setActivationMethod('personal')} 
                          className={`p-3 rounded-xl text-xs font-bold transition-all border flex flex-col items-center justify-center gap-2 ${activationMethod === 'personal' ? 'bg-cyan-500/20 text-cyan-400 border-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.3)]' : 'bg-slate-800 text-slate-400 border-slate-700'}`}
                        >
                          <Users className="w-5 h-5" />
                          روی اکانت شخصی خودم
                        </button>
                      </div>
                      
                      {/* Conditional rendering for personal account payload */}
                      {activationMethod === 'personal' && (
                        <div className="flex flex-col gap-3 mb-2 animate-in fade-in zoom-in duration-300">
                          <input 
                            type="email" 
                            placeholder="ایمیل اکانت (example@gmail.com)" 
                            className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-sm text-left text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all placeholder:text-right" 
                            onChange={e => setAccountEmail(e.target.value)} 
                            value={accountEmail} 
                          />
                          <input 
                            type="password" 
                            placeholder="رمز عبور اکانت" 
                            className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-sm text-left text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all placeholder:text-right" 
                            onChange={e => setAccountPassword(e.target.value)} 
                            value={accountPassword} 
                          />
                          <p className="text-[10px] text-slate-500 text-right pr-1">اطلاعات ورود شما نزد ما کاملاً محفوظ و رمزنگاری می‌شود.</p>
                        </div>
                      )}
                    </div>

                    <div className="flex flex-col gap-3 mt-4 relative z-10">
                      <Button className="w-full bg-green-600 hover:bg-green-500 text-white py-6 rounded-xl text-md font-bold flex gap-2 shadow-lg shadow-cyan-500/20" onClick={handleCheckoutProcess}>
                        <CreditCard className="w-5 h-5" /> پرداخت و تحویل آنی
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

        {/* Fallback Empty State Display */}
        {filteredProducts.length === 0 && (
          <div className="text-center py-12 text-slate-500 text-sm">
            محصولی در این دسته‌بندی یافت نشد.
          </div>
        )}
      </main>
    </div>
  );
}