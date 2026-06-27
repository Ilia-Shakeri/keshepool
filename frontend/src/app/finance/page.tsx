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
        <div
          className="rounded-3xl p-6 relative overflow-hidden"
          style={{
            background: "linear-gradient(135deg, #E63946 0%, #b52d38 100%)",
            boxShadow: "0 16px 48px rgba(230,57,70,0.3)",
          }}
        >
          <div className="absolute -right-8 -top-8 w-40 h-40 bg-white/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -left-12 -bottom-12 w-48 h-48 bg-black/15 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10">
            <span className="text-xs text-white/70 font-medium">موجودی کل</span>
            <div className="text-3xl font-bold text-white mt-1 mb-6 tracking-tight dir-ltr text-right">
              {walletBalance !== null ? formatPrice(walletBalance) : "···"}
            </div>

            <button
              onClick={() => setIsChargeModalOpen(true)}
              className="transition-all active:scale-95 text-xs font-bold py-2.5 px-5 rounded-xl flex items-center gap-2 cursor-pointer"
              style={{ background: "rgba(255,255,255,0.18)", color: "white", border: "1px solid rgba(255,255,255,0.25)" }}
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
        <DialogContent
          className="text-[#F5F5F5] rounded-3xl w-[95%] max-w-md mx-auto p-5 font-sans dir-rtl border-none"
          style={{ background: "rgba(12,14,18,0.97)", backdropFilter: "blur(40px)", border: "1px solid rgba(255,255,255,0.09)" }}
        >
          <DialogTitle className="text-lg font-bold flex justify-between items-center mb-4">
            افزایش موجودی
            <button
              onClick={() => setIsChargeModalOpen(false)}
              className="p-1.5 rounded-full hover:bg-white/10 transition-colors"
              style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.1)" }}
            >
              <X className="w-4 h-4" />
            </button>
          </DialogTitle>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-[#F5F5F5]/55 mb-2 block">مبلغ مورد نظر (تومان)</label>
              <input
                type="number"
                value={chargeAmount}
                onChange={(event) => setChargeAmount(event.target.value)}
                placeholder="مثال: ۵۰۰،۰۰۰"
                className="w-full rounded-xl px-4 py-3 text-sm focus:outline-none transition-all dir-ltr text-right"
                style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#F5F5F5" }}
              />
            </div>

            <div
              className="w-full flex items-center justify-between p-4 rounded-2xl"
              style={{ background: "rgba(230,57,70,0.07)", border: "1px solid rgba(230,57,70,0.2)" }}
            >
              <div className="flex items-center gap-3">
                <Wallet className="w-5 h-5 text-[#E63946]" />
                <span className="text-sm font-bold">پرداخت ریالی امن</span>
              </div>
              <CreditCard className="w-5 h-5 text-[#E63946]" />
            </div>

            {errorMessage && (
              <div className="text-xs text-[#E63946] rounded-xl p-3" style={{ background: "rgba(230,57,70,0.1)", border: "1px solid rgba(230,57,70,0.2)" }}>
                {errorMessage}
              </div>
            )}

            <button
              onClick={handleChargeSubmit}
              className="w-full py-4 rounded-2xl text-sm font-bold transition-all active:scale-95"
              style={{ background: "linear-gradient(135deg, #E63946 0%, #c0303c 100%)", color: "white", boxShadow: "0 8px 24px rgba(230,57,70,0.3)" }}
            >
              انتقال به درگاه
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}