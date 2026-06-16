"use client";

import { useEffect, useState } from "react";
import { ArrowDownToLine, CreditCard, Home, Plus, Sparkles, Wallet, X } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { createTetra98Payment, getWalletBalance, getWalletTransactions, type WalletTransaction } from "@/lib/api";
import { formatPrice, toPersianDigits } from "@/lib/utils";

function transactionIcon(type: string) {
  if (type.includes("deposit")) return <ArrowDownToLine className="w-4 h-4" />;
  if (type === "purchase") return <Home className="w-4 h-4" />;
  return <Sparkles className="w-4 h-4" />;
}

export default function WalletPage() {
  const [isChargeModalOpen, setIsChargeModalOpen] = useState(false);
  const [chargeAmount, setChargeAmount] = useState("");
  const [walletBalance, setWalletBalance] = useState<number | null>(null);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refreshWallet = async () => {
    try {
      const [balanceData, transactionData] = await Promise.all([getWalletBalance(), getWalletTransactions()]);
      setWalletBalance(balanceData.balance);
      setTransactions(transactionData);
    } catch (error) {
      console.error("Wallet load failed:", error);
      setWalletBalance(0);
    }
  };

  useEffect(() => {
    refreshWallet();
  }, []);

  const handleChargeSubmit = async () => {
    const amount = Number(chargeAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setErrorMessage("مبلغ وارد شده معتبر نیست.");
      return;
    }

    try {
      setErrorMessage(null);
      const response = await createTetra98Payment(amount);
      window.Telegram?.WebApp?.openLink(response.paymentUrl);
      setIsChargeModalOpen(false);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "اتصال به درگاه پرداخت ناموفق بود.");
    }
  };

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32">
      <header className="p-5 pt-6 flex justify-center items-center relative">
        <h1 className="text-base font-bold text-[#F5F5F5]">کیف پول</h1>
      </header>

      <main className="px-5 mt-2 space-y-8">
        <div className="bg-[#E63946] rounded-3xl p-6 shadow-lg shadow-[#E63946]/20 relative overflow-hidden">
          <div className="absolute -right-6 -top-6 w-32 h-32 bg-[#F5F5F5]/10 rounded-full blur-2xl pointer-events-none" />
          <div className="absolute -left-10 -bottom-10 w-40 h-40 bg-[#0F0F10]/10 rounded-full blur-2xl pointer-events-none" />

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
            {transactions.length === 0 ? (
              <div className="text-center py-8 text-[#F5F5F5]/50 text-sm">تراکنشی ثبت نشده است.</div>
            ) : (
              transactions.map((tx) => (
                <div key={tx.id} className="flex items-center justify-between p-3 rounded-2xl hover:bg-[#0B1D33] transition-colors">
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${tx.amount >= 0 ? "bg-[#1E3C5A]/20 text-[#1E3C5A]" : "bg-[#33383F] text-[#F5F5F5]/70"}`}>
                      {transactionIcon(tx.type)}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-sm font-bold text-[#F5F5F5]">{tx.description || tx.type}</span>
                      <span className="text-[10px] text-[#F5F5F5]/50 mt-0.5">{new Date(tx.createdAt).toLocaleDateString("fa-IR")}</span>
                    </div>
                  </div>
                  <span className={`text-sm font-bold dir-ltr ${tx.amount >= 0 ? "text-emerald-400" : "text-[#F5F5F5]/70"}`}>
                    {tx.amount >= 0 ? "+" : "-"}{formatPrice(Math.abs(tx.amount))}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </main>

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
                onChange={(event) => setChargeAmount(event.target.value)}
                placeholder={toPersianDigits("مثلا: 500000")}
                className="w-full bg-[#0F0F10]/60 border border-[#33383F] rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#E63946] focus:ring-1 focus:ring-[#E63946]/50 transition-all dir-ltr text-right"
              />
            </div>

            <div className="w-full flex items-center justify-between p-4 rounded-2xl border border-[#E63946] bg-[#E63946]/5">
              <div className="flex items-center gap-3">
                <Wallet className="w-5 h-5 text-[#E63946]" />
                <span className="text-sm font-bold">پرداخت ریالی امن</span>
              </div>
              <CreditCard className="w-5 h-5 text-[#E63946]" />
            </div>

            {errorMessage && <div className="text-xs text-[#E63946] bg-[#E63946]/10 border border-[#E63946]/20 rounded-xl p-3">{errorMessage}</div>}

            <button onClick={handleChargeSubmit} className="w-full bg-[#E63946] hover:bg-[#E63946]/90 text-[#F5F5F5] py-4 rounded-xl text-sm font-bold shadow-lg shadow-[#E63946]/20 transition-all active:scale-95 cursor-pointer mt-2">
              انتقال به درگاه
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}