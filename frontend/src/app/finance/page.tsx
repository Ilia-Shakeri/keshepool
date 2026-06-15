// ==================================================
// FILE: frontend/src/app/finance/page.tsx
// ==================================================

"use client";

import { useState, useEffect } from "react";
import { Plus, Home, ArrowDownToLine, Sparkles, X, Wallet, CreditCard, Image as ImageIcon } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

const TRANSACTIONS = [
  { id: 1, title: "Claude Pro", date: "1403/11/20", amount: "-390,000", type: "expense", icon: <Home className="w-4 h-4" /> },
  { id: 2, title: "افزایش موجودی", date: "1403/11/18", amount: "+500,000", type: "income", icon: <ArrowDownToLine className="w-4 h-4" /> },
  { id: 3, title: "ChatGPT Plus", date: "1403/11/15", amount: "-390,000", type: "expense", icon: <Sparkles className="w-4 h-4" /> },
];

export default function WalletPage() {
  const [isChargeModalOpen, setIsChargeModalOpen] = useState(false);
  const [chargeAmount, setChargeAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<'tetra' | 'tether'>('tetra');
  const [walletBalance, setWalletBalance] = useState<number | null>(null);

  // Securely fetch wallet balance from the backend API using Telegram initData
  useEffect(() => {
    const fetchWalletBalance = async () => {
      if (typeof window !== "undefined" && window.Telegram?.WebApp) {
        const initData = window.Telegram.WebApp.initData;
        
        try {
          const response = await fetch("/api/wallet/balance", {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              "X-Telegram-Init-Data": initData
            }
          });
          
          if (response.ok) {
            const data = await response.json();
            setWalletBalance(data.balance);
          } else {
            console.error("Failed to authenticate or fetch wallet balance");
            setWalletBalance(0);
          }
        } catch (error) {
          console.error("Network error fetching balance:", error);
          setWalletBalance(0);
        }
      }
    };
    
    fetchWalletBalance();
  }, []);

  // Triggered when standard increase balance is clicked
  const handleChargeSubmit = () => {
    if (!chargeAmount) return;
    if (paymentMethod === 'tetra') {
      // Logic for IRR payment via Tetra98 API execution
      console.log("Routing to Tetra98 API with payload", chargeAmount);
    } else {
      // Logic for Crypto payment
      console.log("Generating crypto payment sequence");
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-white font-sans pb-32">
      <header className="p-5 pt-6 flex justify-center items-center relative">
        <h1 className="text-base font-bold text-white">کیف پول</h1>
      </header>

      <main className="px-5 mt-2 space-y-8">
        {/* Wallet Balance Card */}
        <div className="bg-red-600 rounded-3xl p-6 shadow-lg shadow-red-600/20 relative overflow-hidden">
          <div className="absolute -right-6 -top-6 w-32 h-32 bg-white/10 rounded-full blur-2xl pointer-events-none"></div>
          <div className="absolute -left-10 -bottom-10 w-40 h-40 bg-black/10 rounded-full blur-2xl pointer-events-none"></div>
          
          <div className="relative z-10">
            <span className="text-xs text-red-100/80 font-medium">موجودی کل</span>
            <div className="text-3xl font-bold text-white mt-1 mb-6 tracking-tight dir-ltr text-right">
              {walletBalance !== null ? walletBalance.toLocaleString() : "..."}
            </div>
            
            <button 
              onClick={() => setIsChargeModalOpen(true)}
              className="bg-white text-red-600 hover:bg-zinc-100 transition-all active:scale-95 text-xs font-bold py-2.5 px-4 rounded-xl flex items-center gap-2 cursor-pointer shadow-md"
            >
              <Plus className="w-4 h-4" /> افزایش موجودی
            </button>
          </div>
        </div>

        {/* Recent Transactions */}
        <div>
          <h2 className="text-sm font-bold text-white mb-4">تراکنش‌های اخیر</h2>
          <div className="space-y-1">
            {TRANSACTIONS.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between p-3 rounded-2xl hover:bg-[#121217] cursor-pointer transition-colors active:scale-[0.98]">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${tx.type === 'income' ? 'bg-green-500/10 text-green-500' : 'bg-zinc-800 text-zinc-400'}`}>
                    {tx.icon}
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-white">{tx.title}</span>
                    <span className="text-[10px] text-zinc-500 mt-0.5">{tx.date}</span>
                  </div>
                </div>
                <span className={`text-sm font-bold dir-ltr ${tx.type === 'income' ? 'text-white' : 'text-zinc-300'}`}>
                  {tx.amount}
                </span>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Charge Wallet Modal */}
      <Dialog open={isChargeModalOpen} onOpenChange={setIsChargeModalOpen}>
        <DialogContent className="bg-[#0f0f13] border border-zinc-800 text-white rounded-3xl w-[95%] max-w-md mx-auto p-5 font-sans dir-rtl">
          <DialogTitle className="text-lg font-bold flex justify-between items-center mb-2">
            افزایش موجودی
            <button onClick={() => setIsChargeModalOpen(false)} className="p-1.5 bg-zinc-800 rounded-full hover:bg-zinc-700 transition-colors cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </DialogTitle>

          <div className="space-y-5">
            <div>
              <label className="text-xs text-zinc-400 mb-2 block">مبلغ مورد نظر (تومان)</label>
              <input 
                type="number" 
                value={chargeAmount}
                onChange={(e) => setChargeAmount(e.target.value)}
                placeholder="مثلا: 500000" 
                className="w-full bg-zinc-900/60 border border-zinc-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500/50 transition-all dir-ltr text-right"
              />
            </div>

            <div className="space-y-3">
              <label className="text-xs text-zinc-400 block">انتخاب درگاه پرداخت</label>
              
              {/* Tetra98 Option */}
              <button 
                onClick={() => setPaymentMethod('tetra')}
                className={`w-full flex flex-col p-4 rounded-2xl border transition-all cursor-pointer active:scale-[0.98] ${
                  paymentMethod === 'tetra' ? 'border-red-500 bg-red-500/5' : 'border-zinc-800 bg-zinc-900/40 hover:bg-zinc-800/60'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'tetra' ? 'border-red-500' : 'border-zinc-600'}`}>
                      {paymentMethod === 'tetra' && <div className="w-2.5 h-2.5 bg-red-500 rounded-full" />}
                    </div>
                    <span className="text-sm font-bold">پرداخت ریالی (تترا پی)</span>
                  </div>
                  <Wallet className={`w-5 h-5 ${paymentMethod === 'tetra' ? 'text-red-500' : 'text-zinc-500'}`} />
                </div>
                {paymentMethod === 'tetra' && (
                  <div className="mt-3 text-[10px] text-red-400 bg-red-500/10 p-2 rounded-lg flex items-center gap-2 border border-red-500/20">
                    <ImageIcon className="w-3.5 h-3.5" />
                    لطفا طبق دستورالعمل عکس ضمیمه شده اقدام کنید.
                  </div>
                )}
              </button>

              {/* Tether Option */}
              <button 
                onClick={() => setPaymentMethod('tether')}
                className={`w-full flex flex-col p-4 rounded-2xl border transition-all cursor-pointer active:scale-[0.98] ${
                  paymentMethod === 'tether' ? 'border-emerald-500 bg-emerald-500/5' : 'border-zinc-800 bg-zinc-900/40 hover:bg-zinc-800/60'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'tether' ? 'border-emerald-500' : 'border-zinc-600'}`}>
                      {paymentMethod === 'tether' && <div className="w-2.5 h-2.5 bg-emerald-500 rounded-full" />}
                    </div>
                    <span className="text-sm font-bold">پرداخت با تتر (USDT)</span>
                  </div>
                  <CreditCard className={`w-5 h-5 ${paymentMethod === 'tether' ? 'text-emerald-500' : 'text-zinc-500'}`} />
                </div>
                {paymentMethod === 'tether' && (
                  <div className="mt-3 text-[10px] text-emerald-400 bg-emerald-500/10 p-2 rounded-lg border border-emerald-500/20">
                    توجه: تایید پرداخت از طریق ولت ممکن است بیشتر طول بکشد.
                  </div>
                )}
              </button>
            </div>

            <button 
              onClick={handleChargeSubmit}
              className="w-full bg-red-600 hover:bg-red-500 text-white py-4 rounded-xl text-sm font-bold shadow-lg shadow-red-600/20 transition-all active:scale-95 cursor-pointer mt-2"
            >
              انتقال به درگاه
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}