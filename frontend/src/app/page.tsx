"use client";

import { useEffect, useState } from "react";
import { 
  Zap, Users, Flame, ChevronRight, ChevronLeft, 
  MoreVertical, X, Music, Crown, CheckCircle2, CreditCard
} from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, 
  DialogTitle, DialogTrigger, DialogClose
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import Image from "next/image";
import { PRODUCTS } from "@/lib/products";

export default function Home() {
  // State variables for the spin wheel mechanics and UI feedback
  const [isSpinning, setIsSpinning] = useState(false);
  const [spinResult, setSpinResult] = useState<string | null>(null);
  const [spinDisplayNumber, setSpinDisplayNumber] = useState<number>(0);

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

  // Execute the spin wheel logic with visual number rolling
  const handleSpin = () => {
    if (isSpinning) return;
    setIsSpinning(true);
    setSpinResult(null);

    // Create a visual rolling effect before showing the final result
    const duration = 3000;
    const intervalTime = 100;
    let elapsed = 0;

    const rollInterval = setInterval(() => {
      elapsed += intervalTime;
      // Display random numbers between 5 and 50 during the spin
      setSpinDisplayNumber(Math.floor(Math.random() * 10 + 1) * 5);
      
      if (elapsed >= duration) {
        clearInterval(rollInterval);
        setIsSpinning(false);
        // Calculate final actual discount (5% to 50% in steps of 5)
        const finalDiscount = Math.floor(Math.random() * 10 + 1) * 5;
        setSpinResult(`شما ${finalDiscount}٪ تخفیف برنده شدید!`);
        setSpinDisplayNumber(finalDiscount);
      }
    }, intervalTime);
  };

  // Navigate to the next product in the array
  const handleNextProduct = () => {
    setCurrentProductIndex((prev) => (prev + 1) % PRODUCTS.length);
  };

  // Navigate to the previous product in the array
  const handlePrevProduct = () => {
    setCurrentProductIndex((prev) => (prev === 0 ? PRODUCTS.length - 1 : prev - 1));
  };

  // Securely close the Telegram Mini App instance
  const handleCloseApplication = () => {
    if (typeof window !== "undefined" && window.Telegram?.WebApp?.close) {
      window.Telegram.WebApp.close();
    }
  };

  // Process the checkout flow and enforce input validation
  const handleCheckoutProcess = () => {
    // Basic validation guardrail for personal account routing
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
    
    // Reset form state securely upon successful transaction bridge
    setIsPurchaseModalOpen(false);
    setAccountEmail('');
    setAccountPassword('');
    setActivationMethod('random');
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 font-sans pb-32 relative selection:bg-cyan-500 selection:text-white overflow-y-auto">
      
      {/* Top Navigation Header */}
      <header className="flex justify-between items-center p-4 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-slate-800/50">
        <div className="flex items-center gap-2 text-slate-400">
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
            <span className="text-purple-400 drop-shadow-md">زود</span>
            <span className="text-cyan-400 drop-shadow-md">ساب</span>
          </h1>
          
          <div className="relative w-36 h-12"> 
            <Image 
              src="/logo.png" 
              alt="ZoodSub Logo" 
              fill
              className="object-contain" 
              priority
            />
          </div>
        </div>
      </header>

      <main className="p-4 space-y-6 max-w-lg mx-auto">
        
        {/* Dynamic Product Card Carousel */}
        <div className="bg-gradient-to-b from-[#1e1b4b] via-[#312e81] to-[#0f172a] rounded-3xl p-6 text-white shadow-2xl relative overflow-hidden border border-indigo-500/20 mt-2 transition-all duration-500">
          
          <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>

          <div className="flex justify-between items-start mb-6 relative z-10">
            <span className="bg-indigo-500/20 px-3 py-1 rounded-full text-xs font-semibold border border-indigo-400/30 text-indigo-200 flex items-center gap-1">
              <Zap className="w-3 h-3 text-yellow-400" /> تحویل فوری
            </span>
            <div className="flex items-center gap-2">
              <div className="text-right">
                <h2 className="text-sm font-bold text-white">{activeProduct.brand}</h2>
                <p className="text-[10px] text-cyan-400 font-mono tracking-widest uppercase">Premium</p>
              </div>
              <div className={`bg-gradient-to-br ${activeProduct.gradient} p-2 rounded-full shadow-lg ${activeProduct.shadow} transition-colors duration-500`}>
                {activeProduct.icon}
              </div>
            </div>
          </div>

          <div className="text-center mb-6 relative z-10 h-32 flex flex-col justify-center">
            <h1 className="text-4xl font-extrabold mb-2 text-white drop-shadow-md">{activeProduct.title}</h1>
            <p className="text-sm text-indigo-200/70">{activeProduct.subtitle}</p>
            <div className="mt-4 text-3xl font-bold text-cyan-400 flex items-center justify-center gap-2">
              {defaultVariant.priceLabel} <span className="text-base font-normal text-cyan-400/60">تومان</span>
            </div>
          </div>

          <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl p-4 mb-6 border border-slate-700/50">
            <div className="flex justify-between items-center pb-3 border-b border-slate-700/50 text-xs text-slate-400">
              <span>پلن‌های تخفیفی ({defaultVariant.duration})</span>
            </div>
            
            <div className="space-y-4 pt-4 text-sm font-medium">
              <div className="flex justify-between items-center text-cyan-400 hover:bg-slate-800/50 p-2 rounded-lg transition-colors cursor-pointer">
                <span>{defaultVariant.priceLabel} تومان</span>
                <span className="flex items-center gap-2">خرید عادی <Zap className="w-4 h-4 fill-current" /></span>
              </div>
              <div className="flex justify-between items-center text-purple-400 hover:bg-slate-800/50 p-2 rounded-lg transition-colors cursor-pointer">
                <span>{(defaultVariant.rawPrice * 0.85).toLocaleString('fa-IR')} تومان</span>
                <span className="flex items-center gap-2">با ۲ دعوت <Users className="w-4 h-4 fill-current" /></span>
              </div>
              <div className="flex justify-between items-center text-pink-500 hover:bg-slate-800/50 p-2 rounded-lg transition-colors cursor-pointer">
                <span>{(defaultVariant.rawPrice * 0.70).toLocaleString('fa-IR')} تومان</span>
                <span className="flex items-center gap-2">با ۵ دعوت <Flame className="w-4 h-4 fill-current" /></span>
              </div>
            </div>
          </div>

          <Dialog open={isPurchaseModalOpen} onOpenChange={setIsPurchaseModalOpen}>
            <DialogTrigger asChild>
              <button className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 active:scale-95 transition-all text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/30 relative z-10">
                خرید این اکانت <ChevronLeft className="w-5 h-5" />
              </button>
            </DialogTrigger>
            
            <DialogContent className="bg-slate-900 border border-slate-700 text-white rounded-3xl w-[90%] max-w-md mx-auto overflow-y-auto max-h-[90vh]">
              <DialogHeader>
                <DialogTitle className="text-right text-xl font-bold text-cyan-400">تایید سفارش</DialogTitle>
                <DialogDescription className="text-right text-slate-400 mt-2">
                  شما در حال خرید {activeProduct.title} ({defaultVariant.duration}) به مبلغ {defaultVariant.priceLabel} تومان هستید.
                </DialogDescription>
              </DialogHeader>

              {/* Dynamic Account Provisioning Method Selection */}
              <div className="mt-4 border-t border-slate-800 pt-4">
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
                <Button className="w-full bg-green-600 hover:bg-green-500 text-white py-6 rounded-xl text-lg font-bold flex gap-2" onClick={handleCheckoutProcess}>
                  <CreditCard className="w-5 h-5" /> انتقال به درگاه پرداخت
                </Button>
                <DialogClose asChild>
                  <Button variant="ghost" className="w-full text-slate-400 hover:text-white hover:bg-slate-800 py-6 rounded-xl border border-transparent hover:border-slate-700" onClick={() => {
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
              className="bg-slate-800/50 hover:bg-slate-700 hover:scale-110 p-3 rounded-full transition-all border border-slate-600/30 active:scale-95"
            >
              <ChevronRight className="w-5 h-5 text-slate-300" />
            </button>
            <div className="flex items-center gap-2 max-w-[150px] overflow-hidden justify-center">
              {/* Pagination indicators calculating dynamic visible slice */}
              {PRODUCTS.slice(
                Math.max(0, currentProductIndex - 2), 
                Math.min(PRODUCTS.length, currentProductIndex + 3)
              ).map((prod) => {
                const actualIndex = PRODUCTS.indexOf(prod);
                return (
                  <div key={actualIndex} className={`h-1.5 rounded-full transition-all ${actualIndex === currentProductIndex ? 'w-4 bg-cyan-400' : 'w-1.5 bg-slate-600'}`} />
                );
              })}
            </div>
            <button 
              onClick={handlePrevProduct}
              className="bg-slate-800/50 hover:bg-slate-700 hover:scale-110 p-3 rounded-full transition-all border border-slate-600/30 active:scale-95"
            >
              <ChevronLeft className="w-5 h-5 text-slate-300" />
            </button>
          </div>
        </div>

        {/* Upgraded Spin Wheel Component */}
        <div className="bg-slate-800 rounded-3xl p-5 shadow-lg border border-slate-700 flex flex-col gap-4">
          <div className="flex items-center justify-between w-full">
            <button 
              onClick={handleSpin}
              disabled={isSpinning}
              className={`bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-2.5 rounded-full text-sm font-bold shadow-md shadow-purple-500/20 transition-all active:scale-95 flex justify-center items-center ${isSpinning ? 'opacity-70 cursor-not-allowed' : 'hover:shadow-lg hover:shadow-purple-500/40'}`}
            >
              {isSpinning ? "در حال چرخش..." : "چرخاندن گردونه"}
            </button>
            
            <div className="text-right">
              <span className="bg-pink-500/10 text-pink-400 border border-pink-500/20 text-[10px] px-2 py-1 rounded-full font-bold mb-1 inline-block">
                گردونه شانس
              </span>
              <h3 className="font-bold text-sm text-white">تخفیف تا ۵۰٪</h3>
              <p className="text-[10px] text-slate-400 mt-1">هر روز یک اسپین رایگان!</p>
            </div>
          </div>

          <div className={`bg-slate-900 rounded-xl p-6 flex items-center justify-center gap-6 shadow-inner relative border border-slate-700 overflow-hidden transition-all duration-300 ${isSpinning ? 'ring-2 ring-purple-500/50' : ''}`}>
            
            {/* Visual background effect during spin */}
            {isSpinning && (
              <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 via-pink-500/10 to-purple-500/10 animate-pulse"></div>
            )}

            <div className="bg-slate-800 rounded-lg p-3 z-10">
              <Crown className={`w-8 h-8 text-yellow-500 transition-all duration-300 ${isSpinning ? 'animate-bounce scale-110' : ''}`} />
            </div>
            
            <div className="z-10 text-center min-w-[80px]">
              {isSpinning || spinResult ? (
                <div className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-pink-400 to-purple-400 drop-shadow-md">
                  {spinDisplayNumber}%
                </div>
              ) : (
                <div className="text-3xl font-extrabold text-slate-500">
                  ??
                </div>
              )}
            </div>

            <div className="bg-slate-800 rounded-lg p-3 z-10">
              <Flame className={`w-8 h-8 text-pink-500 transition-all duration-300 ${isSpinning ? 'animate-pulse scale-110' : ''}`} />
            </div>
          </div>

          {spinResult && (
            <div className="bg-green-500/10 border border-green-500/30 text-green-400 p-4 rounded-xl text-center text-sm font-bold animate-in fade-in zoom-in duration-300 shadow-inner">
              🎉 {spinResult}
            </div>
          )}
        </div>

        <div className="bg-slate-800 rounded-3xl p-5 shadow-lg border border-slate-700 mb-8">
          <h3 className="font-bold text-lg text-white text-right mb-4 flex items-center justify-end gap-2">
            چرا زودساب؟
            <CheckCircle2 className="w-5 h-5 text-cyan-400" />
          </h3>
          <ul className="text-right space-y-3 text-sm text-slate-300">
            <li className="flex items-center justify-end gap-2">تحویل کاملا خودکار و آنی <Zap className="w-4 h-4 text-yellow-500" /></li>
            <li className="flex items-center justify-end gap-2">پشتیبانی ۲۴ ساعته واقعی <Users className="w-4 h-4 text-blue-400" /></li>
            <li className="flex items-center justify-end gap-2">تضمین بازگشت وجه <CheckCircle2 className="w-4 h-4 text-green-400" /></li>
          </ul>
        </div>

      </main>
    </div>
  );
}