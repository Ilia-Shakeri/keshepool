"use client";

import { useEffect, useState } from "react";
import { 
  Zap, Users, Flame, ChevronRight, ChevronLeft, 
  MoreVertical, X, CheckCircle2, CreditCard, Shield, Wallet
} from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, 
  DialogTitle, DialogTrigger, DialogClose
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { PRODUCTS } from "@/lib/products";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  // State variables for the product carousel and purchase modal
  const [isPurchaseModalOpen, setIsPurchaseModalOpen] = useState(false);
  const [currentProductIndex, setCurrentProductIndex] = useState(0);

  // State variables for account provisioning logic
  const [activationMethod, setActivationMethod] = useState<'random' | 'personal'>('random');
  const [accountEmail, setAccountEmail] = useState('');
  const [accountPassword, setAccountPassword] = useState('');

  // Retrieve current active product and its default subscription variant
  const activeProduct = PRODUCTS[currentProductIndex] || PRODUCTS[0];
  const defaultVariant = activeProduct.variants[0];

  useEffect(() => {
    // Safely initialize the Telegram Web App SDK on the client side
    const initTelegramApp = async () => {
      if (typeof window !== "undefined") {
        try {
          const WebApp = (await import("@twa-dev/sdk")).default;
          WebApp.expand();
          WebApp.ready();
        } catch (error) {
          console.error("Telegram Web App SDK initialization failed:", error);
        }
      }
    };
    initTelegramApp();
  }, []);

  const handleNextProduct = () => setCurrentProductIndex((prev) => (prev + 1) % PRODUCTS.length);
  const handlePrevProduct = () => setCurrentProductIndex((prev) => (prev === 0 ? PRODUCTS.length - 1 : prev - 1));

  const handleCloseApplication = () => {
    if (typeof window !== "undefined" && window.Telegram?.WebApp?.close) {
      window.Telegram.WebApp.close();
    }
  };

  const handleCheckoutProcess = () => {
    if (activationMethod === 'personal' && (!accountEmail || !accountPassword)) {
      alert("لطفاً مشخصات را وارد کنید.");
      return;
    }

    // Generate Tetra98 Tether Payment Gateway URL (Placeholder using required URL constraint)
    const paymentTargetUrl = `https://tetra98.com/gateway/mock-session?amount=${defaultVariant.rawPrice}&currency=USDT`;
    
    if (typeof window !== "undefined" && window.Telegram?.WebApp?.openLink) {
      window.Telegram.WebApp.openLink(paymentTargetUrl);
    } else {
      window.open(paymentTargetUrl, "_blank");
    }
    
    setIsPurchaseModalOpen(false);
    setAccountEmail('');
    setAccountPassword('');
    setActivationMethod('random');
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans pb-32 relative selection:bg-emerald-500 selection:text-white overflow-y-auto">
      
      {/* Top Navigation Header */}
      <header className="flex justify-between items-center p-4 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-zinc-800/50">
        <div className="flex items-center gap-2 text-zinc-400">
          <button onClick={handleCloseApplication} className="hover:text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
          <button className="hover:text-white transition-colors">
            <MoreVertical className="w-6 h-6" />
          </button>
        </div>
        
        {/* Adjusted Logo and Title Alignment */}
        <div className="flex items-center gap-1">
          <h1 className="text-2xl font-extrabold tracking-wide flex items-center">
            <span className="text-emerald-400 drop-shadow-md">کشه</span>
            <span className="text-cyan-400 drop-shadow-md">پول</span>
          </h1>
        </div>
      </header>

      <main className="p-4 space-y-6 max-w-lg mx-auto">
        
        {/* Hot Items Section */}
        <div className="bg-gradient-to-r from-emerald-900/40 to-teal-900/40 rounded-2xl p-1 border border-emerald-500/20 shadow-lg mb-2">
          <div className="flex justify-between items-center px-4 py-2 border-b border-emerald-500/20 mb-2">
            <button onClick={() => router.push('/products')} className="text-xs text-emerald-400 hover:text-emerald-300 font-bold">مشاهده همه</button>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              محصولات ویژه <Flame className="w-4 h-4 text-orange-500 animate-pulse" />
            </h3>
          </div>
          <div className="grid grid-cols-2 gap-2 p-2">
            <div onClick={() => router.push('/products')} className="bg-zinc-900/80 p-3 rounded-xl border border-zinc-700 hover:border-emerald-500/50 cursor-pointer transition-all flex flex-col items-center gap-2 text-center shadow-inner">
              <Shield className="w-6 h-6 text-emerald-400" />
              <span className="text-xs font-bold text-zinc-200">کانفیگ V2Ray</span>
              <span className="text-[9px] text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full">بدون قطعی</span>
            </div>
            <div onClick={() => router.push('/finance')} className="bg-zinc-900/80 p-3 rounded-xl border border-zinc-700 hover:border-amber-500/50 cursor-pointer transition-all flex flex-col items-center gap-2 text-center shadow-inner">
              <Wallet className="w-6 h-6 text-amber-400" />
              <span className="text-xs font-bold text-zinc-200">خدمات ارزی</span>
              <span className="text-[9px] text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full">نقد کردن درآمد</span>
            </div>
          </div>
        </div>

        {/* Dynamic Product Card Carousel */}
        <div className="bg-gradient-to-b from-zinc-800 via-zinc-900 to-black rounded-3xl p-6 text-white shadow-2xl relative overflow-hidden border border-zinc-700 mt-2 transition-all duration-500">
          
          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>

          <div className="flex justify-between items-start mb-6 relative z-10">
            <span className="bg-zinc-800/80 px-3 py-1 rounded-full text-xs font-semibold border border-zinc-700 text-zinc-300 flex items-center gap-1">
              <Zap className="w-3 h-3 text-yellow-400" /> تحویل سریع
            </span>
            <div className="flex items-center gap-2">
              <div className="text-right">
                <h2 className="text-sm font-bold text-white">{activeProduct.brand}</h2>
                <p className="text-[10px] text-emerald-400 font-mono tracking-widest uppercase">Premium</p>
              </div>
              <div className={`bg-gradient-to-br ${activeProduct.gradient} p-2 rounded-full shadow-lg ${activeProduct.shadow} transition-colors duration-500`}>
                {activeProduct.icon}
              </div>
            </div>
          </div>

          <div className="text-center mb-6 relative z-10 h-32 flex flex-col justify-center">
            <h1 className="text-3xl font-extrabold mb-2 text-white drop-shadow-md">{activeProduct.title}</h1>
            <p className="text-sm text-zinc-400">{activeProduct.subtitle}</p>
            <div className="mt-4 text-3xl font-bold text-emerald-400 flex items-center justify-center gap-2">
              {defaultVariant.priceLabel} <span className="text-base font-normal text-emerald-400/60">تومان</span>
            </div>
          </div>

          <Dialog open={isPurchaseModalOpen} onOpenChange={setIsPurchaseModalOpen}>
            <DialogTrigger asChild>
              <button className="w-full bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 active:scale-95 transition-all text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/30 relative z-10">
                خرید این سرویس <ChevronLeft className="w-5 h-5" />
              </button>
            </DialogTrigger>
            
            <DialogContent className="bg-zinc-900 border border-zinc-800 text-white rounded-3xl w-[90%] max-w-md mx-auto overflow-y-auto max-h-[90vh]">
              <DialogHeader>
                <DialogTitle className="text-right text-xl font-bold text-emerald-400">تایید سفارش</DialogTitle>
                <DialogDescription className="text-right text-zinc-400 mt-2">
                  شما در حال خرید {activeProduct.title} ({defaultVariant.duration}) هستید.
                </DialogDescription>
              </DialogHeader>

              {/* Price configuration with Crypto Context */}
              <div className="bg-zinc-800/50 p-4 rounded-xl border border-zinc-700/50 mt-2 flex justify-between items-center w-full">
                <span className="text-sm font-bold text-zinc-300">مبلغ قابل پرداخت:</span>
                <div className="flex flex-col items-end">
                  <span className="text-emerald-400 font-bold text-lg flex items-center gap-1 dir-ltr text-left">
                    {defaultVariant.priceLabel} <span className="text-sm font-normal text-zinc-400">تومان</span>
                  </span>
                  <span className="text-xs text-zinc-500 mt-1">پرداخت معادل تتری (USDT)</span>
                </div>
              </div>

              <div className="mt-4 border-t border-zinc-800 pt-4">
                <label className="text-sm font-bold text-zinc-300 block text-right mb-3">نوع انجام سفارش:</label>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <button 
                    onClick={() => setActivationMethod('random')} 
                    className={`p-3 rounded-xl text-xs font-bold transition-all border flex flex-col items-center justify-center gap-2 ${activationMethod === 'random' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.3)]' : 'bg-zinc-800 text-zinc-400 border-zinc-700'}`}
                  >
                    <Zap className="w-5 h-5" />
                    تحویل سریع
                  </button>
                  <button 
                    onClick={() => setActivationMethod('personal')} 
                    className={`p-3 rounded-xl text-xs font-bold transition-all border flex flex-col items-center justify-center gap-2 ${activationMethod === 'personal' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.3)]' : 'bg-zinc-800 text-zinc-400 border-zinc-700'}`}
                  >
                    <Users className="w-5 h-5" />
                    روی اکانت شخصی
                  </button>
                </div>
                
                {activationMethod === 'personal' && (
                  <div className="flex flex-col gap-3 mb-2 animate-in fade-in zoom-in duration-300">
                    <input 
                      type="text" 
                      placeholder="ایمیل یا آیدی جهت فعالسازی" 
                      className="w-full bg-zinc-950 border border-zinc-700 rounded-xl p-3 text-sm text-left text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all placeholder:text-right" 
                      onChange={e => setAccountEmail(e.target.value)} 
                      value={accountEmail} 
                    />
                    <input 
                      type="password" 
                      placeholder="رمز عبور (در صورت نیاز)" 
                      className="w-full bg-zinc-950 border border-zinc-700 rounded-xl p-3 text-sm text-left text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all placeholder:text-right" 
                      onChange={e => setAccountPassword(e.target.value)} 
                      value={accountPassword} 
                    />
                    <p className="text-[10px] text-zinc-500 text-right pr-1">اطلاعات شما با پروتکل‌های امنیتی محافظت می‌شود.</p>
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-3 mt-4 relative z-10">
                <Button className="w-full bg-emerald-600 hover:bg-emerald-500 text-white py-6 rounded-xl text-lg font-bold flex gap-2" onClick={handleCheckoutProcess}>
                  <CreditCard className="w-5 h-5" /> پرداخت تتری (Tetra98)
                </Button>
                <DialogClose asChild>
                  <Button variant="ghost" className="w-full text-zinc-400 hover:text-white hover:bg-zinc-800 py-6 rounded-xl border border-transparent hover:border-zinc-700" onClick={() => {
                    setAccountEmail('');
                    setAccountPassword('');
                    setActivationMethod('random');
                  }}>
                    انصراف
                  </Button>
                </DialogClose>
              </div>
            </DialogContent>
          </Dialog>

          <div className="flex justify-center gap-6 mt-6 relative z-10">
            <button 
              onClick={handleNextProduct}
              className="bg-zinc-800/50 hover:bg-zinc-700 hover:scale-110 p-3 rounded-full transition-all border border-zinc-600/30 active:scale-95"
            >
              <ChevronRight className="w-5 h-5 text-zinc-300" />
            </button>
            <div className="flex items-center gap-2 max-w-[150px] overflow-hidden justify-center">
              {PRODUCTS.slice(
                Math.max(0, currentProductIndex - 2), 
                Math.min(PRODUCTS.length, currentProductIndex + 3)
              ).map((prod) => {
                const actualIndex = PRODUCTS.indexOf(prod);
                return (
                  <div key={actualIndex} className={`h-1.5 rounded-full transition-all ${actualIndex === currentProductIndex ? 'w-4 bg-emerald-400' : 'w-1.5 bg-zinc-600'}`} />
                );
              })}
            </div>
            <button 
              onClick={handlePrevProduct}
              className="bg-zinc-800/50 hover:bg-zinc-700 hover:scale-110 p-3 rounded-full transition-all border border-zinc-600/30 active:scale-95"
            >
              <ChevronLeft className="w-5 h-5 text-zinc-300" />
            </button>
          </div>
        </div>

        {/* Fixed Natural RTL Alignment using standard flex flow */}
        <div className="bg-zinc-900 rounded-3xl p-5 shadow-lg border border-zinc-800 mb-8">
          <h3 className="font-bold text-lg text-white mb-4 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            چرا کشه‌پول؟
          </h3>
          <ul className="space-y-3 text-sm text-zinc-300">
            <li className="flex items-center gap-2"><Zap className="w-4 h-4 text-yellow-500" /> تحویل سریع سرویس‌ها</li>
            <li className="flex items-center gap-2"><Users className="w-4 h-4 text-blue-400" /> تضمین پایداری اکانت‌ها</li>
            <li className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-400" /> انجام خدمات ارزی و کانفیگ امن</li>
          </ul>
        </div>

      </main>
    </div>
  );
}