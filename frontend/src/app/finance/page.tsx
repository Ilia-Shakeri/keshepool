"use client";

import { Wallet, ArrowLeftRight, Landmark, FileText, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function FinancePage() {
  const router = useRouter();
  const [amount, setAmount] = useState('');
  const [sourceType, setSourceType] = useState('youtube');

  // Submit handling for financial requests
  const handleCashoutRequest = () => {
    if (!amount) {
      alert("لطفاً مبلغ مورد نظر را وارد کنید.");
      return;
    }
    alert("درخواست شما ثبت شد. پشتیبانی به زودی با شما تماس خواهد گرفت.");
    setAmount('');
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans pb-32 relative">
      
      {/* Sticky Top Header Configuration */}
      <header className="flex justify-between items-center p-4 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-zinc-800/50 mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-amber-400 flex items-center gap-2">
          <Wallet className="w-5 h-5" /> خدمات ارزی
        </h1>
        <button onClick={() => router.back()} className="text-zinc-400 hover:text-white transition-colors bg-zinc-800/50 px-4 py-1.5 rounded-xl text-sm font-medium">
          بازگشت
        </button>
      </header>

      <main className="flex flex-col gap-6 w-full px-4 max-w-lg mx-auto">
        
        {/* Intro Section */}
        <div className="bg-gradient-to-b from-amber-900/30 to-orange-900/10 rounded-3xl p-6 border border-amber-500/20 text-center shadow-lg relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>
          <ArrowLeftRight className="w-10 h-10 text-amber-400 mx-auto mb-4" />
          <h2 className="font-bold text-white mb-2 text-lg">نقد کردن درآمد ارزی</h2>
          <p className="text-sm text-zinc-400 leading-relaxed">
            ما درآمدهای یوتیوب، فریلنسری و سایر پرداختی‌های بین‌المللی شما را با بهترین نرخ و در سریع‌ترین زمان به تومان یا تتر تبدیل می‌کنیم.
          </p>
        </div>

        {/* Input Form Section */}
        <div className="bg-zinc-900/60 backdrop-blur-sm rounded-3xl p-6 border border-zinc-800 shadow-md">
          <div className="flex flex-col gap-5">
            
            <div>
              <label className="text-sm font-bold text-zinc-300 block text-right mb-2 flex items-center gap-2">
                <Landmark className="w-4 h-4 text-amber-500" /> نوع درآمد یا پلتفرم:
              </label>
              <select 
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-amber-500 transition-all dir-rtl"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
              >
                <option value="youtube">درآمد یوتیوب (AdSense)</option>
                <option value="freelance">سایت‌های فریلنسری (Upwork, Fiverr)</option>
                <option value="paypal">موجودی پی‌پال (PayPal)</option>
                <option value="crypto">تبدیل ارز دیجیتال (Crypto)</option>
                <option value="other">سایر موارد</option>
              </select>
            </div>

            <div>
              <label className="text-sm font-bold text-zinc-300 block text-right mb-2 flex items-center gap-2">
                <FileText className="w-4 h-4 text-amber-500" /> مبلغ حدودی ارزی:
              </label>
              <div className="relative">
                <input 
                  type="number" 
                  placeholder="مثال: 500" 
                  className="w-full bg-zinc-950 border border-zinc-700 rounded-xl p-3 pl-12 text-sm text-left text-white focus:outline-none focus:border-amber-500 transition-all dir-ltr" 
                  onChange={e => setAmount(e.target.value)} 
                  value={amount} 
                />
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 font-bold text-sm">USD/EUR</span>
              </div>
            </div>

            <Button onClick={handleCashoutRequest} className="w-full bg-amber-600 hover:bg-amber-500 text-white py-6 rounded-xl text-md font-bold flex gap-2 shadow-lg shadow-amber-500/20 mt-2 transition-all">
              <Send className="w-5 h-5" /> ثبت درخواست مشاوره و نقد کردن
            </Button>
          </div>
        </div>

      </main>
    </div>
  );
}