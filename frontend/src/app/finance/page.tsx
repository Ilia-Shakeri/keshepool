"use client";

import { useState, useEffect } from "react";
import { Plus, Home, ArrowDownToLine, Sparkles, X, Wallet, CreditCard, Image as ImageIcon } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { toPersianDigits, formatPrice } from "@/lib/utils";

// Mock Data structure for external ledger
const TRANSACTIONS = [
  { id: 1, title: "Claude Pro", date: "۱۴۰۳/۱۱/۲۰", amount: "-۳۹۰,۰۰۰", type: "expense", icon: <Home className="w-4 h-4" /> },
  { id: 2, title: "افزایش موجودی", date: "۱۴۰۳/۱۱/۱۸", amount: "+۵۰۰,۰۰۰", type: "income", icon: <ArrowDownToLine className="w-4 h-4" /> },
  { id: 3, title: "ChatGPT Plus", date: "۱۴۰۳/۱۱/۱۵", amount: "-۳۹۰,۰۰۰", type: "expense", icon: <Sparkles className="w-4 h-4" /> },
];

export default function WalletPage() {
  const [isChargeModalOpen, setIsChargeModalOpen] = useState(false);
  const [chargeAmount, setChargeAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<'tetra' | 'tether'>('tetra');
  const [walletBalance, setWalletBalance] = useState<number | null>(null);

  // Securely retrieve runtime wallet execution parameters
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
            console.error("Infrastructure authentication failure");
            setWalletBalance(0);
          }
        } catch (error) {
          console.error("Network layer anomaly:", error);
          setWalletBalance(0);
        }
      }
    };
    
    fetchWalletBalance();
  }, []);

  const handleChargeSubmit = () => {
    if (!chargeAmount) return;
    if (paymentMethod === 'tetra') {
      console.log("Routing to Tetra98 API with payload", chargeAmount);
    } else {
      console.log("Generating crypto payment sequence");
    }
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32">
      <header className="p-5 pt-6 flex justify-center items-center relative">
        <h1 className="text-base font-bold text-[#F5F5F5]">کیف پول</h1>
      </header>

      <main className="px-5 mt-2 space-y-8">
        <div className="bg-[#E63946] rounded-3xl p-6 shadow-lg shadow-[#E63946]/20 relative overflow-hidden">
          <div className="absolute -right-6 -top-6 w-32 h-32 bg-[#F5F5F5]/10 rounded-full blur-2xl pointer-events-none"></div>
          <div className="absolute -left-10 -bottom-10 w-40 h-40 bg-[#0F0F10]/10 rounded-full blur-2xl pointer-events-none"></div>
          
          <div className="relative z-10">
            <span className="text-xs text-[#F5F5F5]/80 font-medium">موجودی کل</span>
            <div className="text-3xl font-bold text-[#F5F5F5] mt-1 mb-6 tracking-tight dir-ltr text-right">
              {walletBalance !== null ? formatPrice(walletBalance) : "..."}
            </div>
            
            <button 
              onClick={() => setIsChargeModalOpen(true)}
              className="bg-[#F5F5F5] text-[#E63946] hover:bg-[#F5F5F5]/90 transition-all active:scale-95 text-xs font-bold py-2.5 px-4 rounded-xl flex items-center gap-2 cursor-pointer shadow-md"
            >
              <Plus className="w-4 h-4" /> افزایش موجودی
            </button>
          </div>
        </div>

        <div>
          <h2 className="text-sm font-bold text-[#F5F5F5] mb-4">تراکنش‌های اخیر</h2>
          <div className="space-y-1">
            {TRANSACTIONS.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between p-3 rounded-2xl hover:bg-[#0B1D33] cursor-pointer transition-colors active:scale-[0.98]">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${tx.type === 'income' ? 'bg-[#1E3C5A]/20 text-[#1E3C5A]' : 'bg-[#33383F] text-[#F5F5F5]/70'}`}>
                    {tx.icon}
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-[#F5F5F5]">{tx.title}</span>
                    <span className="text-[10px] text-[#F5F5F5]/50 mt-0.5">{tx.date}</span>
                  </div>
                </div>
                <span className={`text-sm font-bold dir-ltr ${tx.type === 'income' ? 'text-[#F5F5F5]' : 'text-[#F5F5F5]/70'}`}>
                  {tx.amount}
                </span>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* State Interface Container */}
      <Dialog open={isChargeModalOpen} onOpenChange={setIsChargeModalOpen}>
        <DialogContent className="bg-[#0B1D33] border border-[#33383F] text-[#F5F5F5] rounded-3xl w-[95%] max-w-md mx-auto p-5 font-sans dir-rtl">
          <DialogTitle className="text-lg font-bold flex justify-between items-center mb-2">
            افزایش موجودی
            <button onClick={() => setIsChargeModalOpen(false)} className="p-1.5 bg-[#33383F] rounded-full hover:bg-[#33383F]/80 transition-colors cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </DialogTitle>

          <div className="space-y-5">
            <div>
              <label className="text-xs text-[#F5F5F5]/70 mb-2 block">مبلغ مورد نظر (تومان)</label>
              <input 
                type="number" 
                value={chargeAmount}
                onChange={(e) => setChargeAmount(e.target.value)}
                placeholder={toPersianDigits("مثلا: 500000")} 
                className="w-full bg-[#0F0F10]/60 border border-[#33383F] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#E63946] focus:ring-1 focus:ring-[#E63946]/50 transition-all dir-ltr text-right"
              />
            </div>

            <div className="space-y-3">
              <label className="text-xs text-[#F5F5F5]/70 block">انتخاب درگاه پرداخت</label>
              
              <button 
                onClick={() => setPaymentMethod('tetra')}
                className={`w-full flex flex-col p-4 rounded-2xl border transition-all cursor-pointer active:scale-[0.98] ${
                  paymentMethod === 'tetra' ? 'border-[#E63946] bg-[#E63946]/5' : 'border-[#33383F] bg-[#0F0F10]/40 hover:bg-[#33383F]/60'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'tetra' ? 'border-[#E63946]' : 'border-[#33383F]'}`}>
                      {paymentMethod === 'tetra' && <div className="w-2.5 h-2.5 bg-[#E63946] rounded-full" />}
                    </div>
                    <span className="text-sm font-bold">پرداخت ریالی (تترا پی)</span>
                  </div>
                  <Wallet className={`w-5 h-5 ${paymentMethod === 'tetra' ? 'text-[#E63946]' : 'text-[#F5F5F5]/50'}`} />
                </div>
                {paymentMethod === 'tetra' && (
                  <div className="mt-3 text-[10px] text-[#E63946] bg-[#E63946]/10 p-2 rounded-lg flex items-center gap-2 border border-[#E63946]/20">
                    <ImageIcon className="w-3.5 h-3.5" />
                    لطفا طبق دستورالعمل عکس ضمیمه شده اقدام کنید.
                  </div>
                )}
              </button>

              <button 
                onClick={() => setPaymentMethod('tether')}
                className={`w-full flex flex-col p-4 rounded-2xl border transition-all cursor-pointer active:scale-[0.98] ${
                  paymentMethod === 'tether' ? 'border-[#1E3C5A] bg-[#1E3C5A]/5' : 'border-[#33383F] bg-[#0F0F10]/40 hover:bg-[#33383F]/60'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${paymentMethod === 'tether' ? 'border-[#1E3C5A]' : 'border-[#33383F]'}`}>
                      {paymentMethod === 'tether' && <div className="w-2.5 h-2.5 bg-[#1E3C5A] rounded-full" />}
                    </div>
                    <span className="text-sm font-bold">پرداخت با تتر (USDT)</span>
                  </div>
                  <CreditCard className={`w-5 h-5 ${paymentMethod === 'tether' ? 'text-[#1E3C5A]' : 'text-[#F5F5F5]/50'}`} />
                </div>
                {paymentMethod === 'tether' && (
                  <div className="mt-3 text-[10px] text-[#1E3C5A] bg-[#1E3C5A]/10 p-2 rounded-lg border border-[#1E3C5A]/20">
                    توجه: تایید پرداخت از طریق ولت ممکن است بیشتر طول بکشد.
                  </div>
                )}
              </button>
            </div>

            <button 
              onClick={handleChargeSubmit}
              className="w-full bg-[#E63946] hover:bg-[#E63946]/90 text-[#F5F5F5] py-4 rounded-xl text-sm font-bold shadow-lg shadow-[#E63946]/20 transition-all active:scale-95 cursor-pointer mt-2"
            >
              انتقال به درگاه
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}