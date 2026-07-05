"use client";

import { useEffect, useState } from "react";
import {
  ArrowDownToLine,
  Bitcoin,
  CheckCircle2,
  ChevronDown,
  Copy,
  CreditCard,
  DollarSign,
  Home,
  Loader2,
  Plus,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import {
  createCashoutRequest,
  createTetra98Payment,
  getCashoutPlatforms,
  getUsdtRate,
  getWalletBalance,
  getWalletTransactions,
  initiateCryptoDeposit,
  type CashoutPlatform,
  type WalletTransaction,
} from "@/lib/api";
import { formatPrice, toPersianDigits } from "@/lib/utils";

// ── helpers ──────────────────────────────────────────────────────────────────

type DepositMethod = "irr" | "usdt";
type ActiveTab = "wallet" | "cashout";

function txIcon(type: string) {
  if (type.includes("deposit")) return <ArrowDownToLine className="w-4 h-4" />;
  if (type === "purchase") return <Home className="w-4 h-4" />;
  if (type === "refund") return <Sparkles className="w-4 h-4" />;
  return <DollarSign className="w-4 h-4" />;
}

function txLabel(type: string): string {
  const map: Record<string, string> = {
    deposit_irr: "واریز تومانی",
    deposit_crypto: "واریز رمزارز",
    purchase: "خرید",
    refund: "استرداد",
    cashout: "برداشت",
    referral_bonus: "پاداش دعوت",
  };
  return map[type] ?? type;
}

function txStatusBadge(status: string) {
  if (status === "success")
    return <span className="text-[9px] text-emerald-400 font-bold px-1.5 py-0.5 rounded-full bg-emerald-400/10">موفق</span>;
  if (status === "failed")
    return <span className="text-[9px] text-rose-400 font-bold px-1.5 py-0.5 rounded-full bg-rose-400/10">ناموفق</span>;
  return <span className="text-[9px] text-amber-400 font-bold px-1.5 py-0.5 rounded-full bg-amber-400/10">در انتظار</span>;
}

// ── main component ────────────────────────────────────────────────────────────

function formatTransactionAmount(tx: WalletTransaction): string {
  const sign = tx.amount >= 0 ? "+" : "";
  const currency = (tx.currency || "IRR").toUpperCase();

  if (currency === "USDT" || currency === "USD") {
    return `${sign}$${Math.abs(tx.amount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  return `${sign}${formatPrice(tx.amount)} تومان`;
}


export default function FinancePage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("wallet");

  // Wallet state
  const [walletBalance, setWalletBalance] = useState<number | null>(null);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);

  // Deposit modal state
  const [isDepositOpen, setIsDepositOpen] = useState(false);
  const [depositMethod, setDepositMethod] = useState<DepositMethod>("irr");
  const [irrAmount, setIrrAmount] = useState("");
  const [usdtAmount, setUsdtAmount] = useState("");
  const [depositLoading, setDepositLoading] = useState(false);
  const [depositError, setDepositError] = useState<string | null>(null);
  const [cryptoDepositInfo, setCryptoDepositInfo] = useState<{
    address: string;
    network: string;
    expectedAmount: string;
    txId: number;
  } | null>(null);
  const [copiedAddress, setCopiedAddress] = useState(false);
  const [usdtRate, setUsdtRate] = useState<number | null>(null);

  // Cashout state
  const [platforms, setPlatforms] = useState<CashoutPlatform[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState("");
  const [customSource, setCustomSource] = useState("");
  const [cashoutDetails, setCashoutDetails] = useState("");
  const [cashoutLoading, setCashoutLoading] = useState(false);
  const [cashoutError, setCashoutError] = useState<string | null>(null);
  const [cashoutSuccess, setCashoutSuccess] = useState(false);

  // Load wallet data
  const refreshWallet = async () => {
    try {
      const [balanceData, txData] = await Promise.all([getWalletBalance(), getWalletTransactions()]);
      setWalletBalance(balanceData.balance);
      setTransactions(txData);
    } catch {
      setWalletBalance(0);
    }
  };

  useEffect(() => {
    void Promise.resolve().then(refreshWallet);
  }, []);

  // Load platforms when cashout tab activates
  useEffect(() => {
    if (activeTab === "cashout" && platforms.length === 0) {
      getCashoutPlatforms()
        .then((data) => setPlatforms(data.platforms))
        .catch(() => {});
    }
  }, [activeTab, platforms.length]);

  // ── deposit handlers ────────────────────────────────────────────────────────

  const handleOpenDeposit = () => {
    setDepositError(null);
    setCryptoDepositInfo(null);
    setIrrAmount("");
    setUsdtAmount("");
    setDepositMethod("irr");
    setIsDepositOpen(true);
    // Pull the live USDT rate so the user sees the equivalent value upfront
    getUsdtRate()
      .then((data) => setUsdtRate(data.tomanPerUsdt))
      .catch(() => setUsdtRate(null));
  };

  useEffect(() => {
    if (typeof window === "undefined") return;

    // Product checkout redirects here with this flag when the wallet needs funds.
    const searchParams = new URLSearchParams(window.location.search);
    if (searchParams.get("deposit") !== "1") return;

    window.setTimeout(handleOpenDeposit, 0);
    searchParams.delete("deposit");
    const query = searchParams.toString();
    const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
    window.history.replaceState(null, "", nextUrl);
  }, []);

  const handleIrrDeposit = async () => {
    const amount = Number(irrAmount);
    if (!Number.isFinite(amount) || amount < 10000) {
      setDepositError("حداقل مبلغ ۱۰٬۰۰۰ تومان است.");
      return;
    }
    setDepositError(null);
    setDepositLoading(true);
    try {
      const res = await createTetra98Payment(amount);
      const webApp = window.Telegram?.WebApp;
      if (res.paymentUrlBot && webApp) {
        // t.me links must open via openTelegramLink to stay within Telegram
        webApp.openTelegramLink(res.paymentUrlBot);
      } else if (res.paymentUrlWeb) {
        webApp?.openLink(res.paymentUrlWeb);
      }
      setIsDepositOpen(false);
      setTimeout(refreshWallet, 4000);
    } catch (err) {
      setDepositError(err instanceof Error ? err.message : "اتصال به درگاه ناموفق بود.");
    } finally {
      setDepositLoading(false);
    }
  };

  const handleUsdtDeposit = async () => {
    const amount = Number(usdtAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setDepositError("مقدار USDT را وارد کنید.");
      return;
    }
    setDepositError(null);
    setDepositLoading(true);
    try {
      const res = await initiateCryptoDeposit(amount);
      setCryptoDepositInfo({
        address: res.depositAddress,
        network: res.network,
        expectedAmount: res.expectedAmount,
        txId: res.transactionId,
      });
    } catch (err) {
      setDepositError(err instanceof Error ? err.message : "خطا در ثبت واریز.");
    } finally {
      setDepositLoading(false);
    }
  };

  const handleCopyAddress = async (address: string) => {
    try {
      await navigator.clipboard.writeText(address);
      setCopiedAddress(true);
      setTimeout(() => setCopiedAddress(false), 2000);
    } catch {
      window.Telegram?.WebApp?.showAlert(address);
    }
  };

  // ── cashout handler ─────────────────────────────────────────────────────────

  const handleCashoutSubmit = async () => {
    if (!selectedPlatform) {
      setCashoutError("لطفاً منبع درآمد را انتخاب کنید.");
      return;
    }
    if (selectedPlatform === "other" && !customSource.trim()) {
      setCashoutError("لطفاً نام منبع را وارد کنید.");
      return;
    }
    if (cashoutDetails.trim().length < 10) {
      setCashoutError("توضیحات باید حداقل ۱۰ کاراکتر باشد.");
      return;
    }
    setCashoutError(null);
    setCashoutLoading(true);
    try {
      await createCashoutRequest(
        selectedPlatform,
        cashoutDetails.trim(),
        selectedPlatform === "other" ? customSource.trim() : null,
      );
      setCashoutSuccess(true);
      setSelectedPlatform("");
      setCustomSource("");
      setCashoutDetails("");
    } catch (err) {
      setCashoutError(err instanceof Error ? err.message : "خطا در ثبت درخواست.");
    } finally {
      setCashoutLoading(false);
    }
  };

  // ── render ──────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0F0F10] text-[#F5F5F5] font-sans pb-32">
      {/* Page header */}
      <header className="p-5 pt-6 flex justify-center items-center">
        <h1 className="text-base font-bold">مالی و کیف پول</h1>
      </header>

      {/* Tab switcher */}
      <div className="px-5 mb-4">
        <div
          className="flex rounded-2xl p-1 gap-1"
          style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          {(
            [
              { key: "wallet", label: "کیف پول" },
              { key: "cashout", label: "نقد کردن درآمد ارزی" },
            ] as { key: ActiveTab; label: string }[]
          ).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className="flex-1 py-2.5 text-xs font-bold rounded-xl transition-all"
              style={
                activeTab === key
                  ? {
                      background: "linear-gradient(135deg, #E63946 0%, #b52d38 100%)",
                      color: "white",
                      boxShadow: "0 4px 12px rgba(230,57,70,0.3)",
                    }
                  : { color: "rgba(245,245,245,0.5)" }
              }
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <main className="px-5 space-y-5">
        {/* ── WALLET TAB ── */}
        {activeTab === "wallet" && (
          <>
            {/* Balance card */}
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
                  onClick={handleOpenDeposit}
                  className="transition-all active:scale-95 text-xs font-bold py-2.5 px-5 rounded-xl flex items-center gap-2 cursor-pointer"
                  style={{
                    background: "rgba(255,255,255,0.18)",
                    color: "white",
                    border: "1px solid rgba(255,255,255,0.25)",
                  }}
                >
                  <Plus className="w-4 h-4" /> افزایش موجودی
                </button>
              </div>
            </div>

            {/* Transaction history */}
            <div>
              <h2 className="text-sm font-bold mb-3">تاریخچه تراکنش‌ها</h2>
              <div className="space-y-1">
                {transactions.length === 0 ? (
                  <div className="text-center py-10 text-[#F5F5F5]/40 text-sm">
                    تراکنشی ثبت نشده است.
                  </div>
                ) : (
                  transactions.map((tx) => (
                    <div
                      key={tx.id}
                      className="flex items-center justify-between p-3 rounded-2xl hover:bg-white/5 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                            tx.amount >= 0
                              ? "bg-emerald-500/15 text-emerald-400"
                              : "bg-white/10 text-[#F5F5F5]/60"
                          }`}
                        >
                          {txIcon(tx.type)}
                        </div>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-sm font-bold truncate">{txLabel(tx.type)}</span>
                            {txStatusBadge(tx.status)}
                          </div>
                          <span className="text-[10px] text-[#F5F5F5]/45 mt-0.5">
                            {new Date(tx.createdAt).toLocaleDateString("fa-IR")}
                          </span>
                        </div>
                      </div>
                      <span
                        className={`text-sm font-bold dir-ltr flex-shrink-0 ${
                          tx.amount >= 0 ? "text-emerald-400" : "text-[#F5F5F5]/70"
                        }`}
                      >
                        {formatTransactionAmount(tx)}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </>
        )}

        {/* ── CASHOUT TAB ── */}
        {activeTab === "cashout" && (
          <div className="space-y-5">
            <div
              className="rounded-3xl p-5"
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0"
                  style={{ background: "linear-gradient(135deg, #E63946 0%, #b52d38 100%)" }}
                >
                  <DollarSign className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-sm font-bold">نقد کردن درآمد ارزی</h2>
                  <p className="text-[11px] text-[#F5F5F5]/45 mt-0.5">
                    درخواست ثبت کن — ادمین مستقیم در تلگرام باهات تماس می‌گیره.
                  </p>
                </div>
              </div>

              {/* Admin contact notice */}
              <div
                className="flex items-start gap-2.5 p-3.5 rounded-2xl mb-4"
                style={{ background: "rgba(230,57,70,0.07)", border: "1px solid rgba(230,57,70,0.15)" }}
              >
                <span className="text-base leading-none mt-0.5">💬</span>
                <p className="text-[11px] text-[#F5F5F5]/70 leading-relaxed">
                  بعد از ثبت درخواست، یکی از ادمین‌های ما از طریق تلگرام با شما ارتباط می‌گیرد تا روند نقد کردن را راهنمایی کند.
                  نیازی به ارائه شماره حساب یا کیف پول در اینجا نیست.
                </p>
              </div>

              {cashoutSuccess ? (
                <div className="flex flex-col items-center py-8 gap-4">
                  <CheckCircle2 className="w-14 h-14 text-emerald-400" />
                  <p className="text-sm font-bold text-center text-emerald-400">
                    درخواست شما با موفقیت ثبت شد.
                  </p>
                  <p className="text-xs text-[#F5F5F5]/50 text-center">
                    تیم ما به زودی با شما تماس خواهد گرفت.
                  </p>
                  <button
                    onClick={() => setCashoutSuccess(false)}
                    className="mt-2 text-xs text-[#E63946] font-bold"
                  >
                    ثبت درخواست جدید
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Platform dropdown */}
                  <div>
                    <label className="text-xs text-[#F5F5F5]/55 mb-2 block">منبع درآمد</label>
                    <div className="relative">
                      <select
                        value={selectedPlatform}
                        onChange={(e) => {
                          setSelectedPlatform(e.target.value);
                          setCustomSource("");
                        }}
                        className="w-full rounded-xl px-4 py-3 text-sm appearance-none focus:outline-none transition-all"
                        style={{
                          background: "rgba(255,255,255,0.05)",
                          border: "1px solid rgba(255,255,255,0.1)",
                          color: selectedPlatform ? "#F5F5F5" : "rgba(245,245,245,0.35)",
                        }}
                      >
                        <option value="" disabled>
                          انتخاب منبع...
                        </option>
                        {platforms.map((p) => (
                          <option key={p.value} value={p.value} style={{ background: "#1a1a1a" }}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#F5F5F5]/40 pointer-events-none" />
                    </div>
                  </div>

                  {/* Custom source input (shown only when "other" is selected) */}
                  {selectedPlatform === "other" && (
                    <div>
                      <label className="text-xs text-[#F5F5F5]/55 mb-2 block">نام منبع</label>
                      <input
                        type="text"
                        value={customSource}
                        onChange={(e) => setCustomSource(e.target.value)}
                        placeholder="نام سرویس یا پلتفرم خود را وارد کنید"
                        maxLength={200}
                        className="w-full rounded-xl px-4 py-3 text-sm focus:outline-none transition-all"
                        style={{
                          background: "rgba(255,255,255,0.05)",
                          border: "1px solid rgba(255,255,255,0.1)",
                          color: "#F5F5F5",
                        }}
                      />
                    </div>
                  )}

                  {/* Details textarea */}
                  <div>
                    <label className="text-xs text-[#F5F5F5]/55 mb-2 block">
                      توضیحات درخواست
                    </label>
                    <textarea
                      value={cashoutDetails}
                      onChange={(e) => setCashoutDetails(e.target.value)}
                      placeholder="توضیح بده که چه مقدار درآمد ارزی داری و از کجا. ادمین بعداً با تو در تلگرام هماهنگ می‌کنه..."
                      rows={5}
                      maxLength={2000}
                      className="w-full rounded-xl px-4 py-3 text-sm focus:outline-none transition-all resize-none leading-relaxed"
                      style={{
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        color: "#F5F5F5",
                      }}
                    />
                    <div className="text-right mt-1">
                      <span className="text-[10px] text-[#F5F5F5]/30">
                        {toPersianDigits(String(cashoutDetails.length))}/۲۰۰۰
                      </span>
                    </div>
                  </div>

                  {cashoutError && (
                    <div
                      className="text-xs text-[#E63946] rounded-xl p-3"
                      style={{
                        background: "rgba(230,57,70,0.1)",
                        border: "1px solid rgba(230,57,70,0.2)",
                      }}
                    >
                      {cashoutError}
                    </div>
                  )}

                  <button
                    onClick={handleCashoutSubmit}
                    disabled={cashoutLoading}
                    className="w-full py-4 rounded-2xl text-sm font-bold transition-all active:scale-95 flex items-center justify-center gap-2 disabled:opacity-60"
                    style={{
                      background: "linear-gradient(135deg, #E63946 0%, #c0303c 100%)",
                      color: "white",
                      boxShadow: "0 8px 24px rgba(230,57,70,0.3)",
                    }}
                  >
                    {cashoutLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      "ثبت درخواست"
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* ── DEPOSIT MODAL ── */}
      <Dialog
        open={isDepositOpen}
        onOpenChange={(open) => {
          if (!open) {
            setCryptoDepositInfo(null);
            setDepositError(null);
          }
          setIsDepositOpen(open);
        }}
      >
        <DialogContent
          className="text-[#F5F5F5] rounded-3xl w-[95%] max-w-md mx-auto p-5 font-sans dir-rtl border-none"
          style={{
            background: "rgba(12,14,18,0.97)",
            backdropFilter: "blur(40px)",
            border: "1px solid rgba(255,255,255,0.09)",
          }}
        >
          <DialogTitle className="text-lg font-bold flex justify-between items-center mb-4">
            افزایش موجودی
            <button
              onClick={() => setIsDepositOpen(false)}
              className="p-1.5 rounded-full hover:bg-white/10 transition-colors"
              style={{
                background: "rgba(255,255,255,0.07)",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            >
              <X className="w-4 h-4" />
            </button>
          </DialogTitle>

          {/* Method selector */}
          <div
            className="flex rounded-xl p-1 gap-1 mb-4"
            style={{ background: "rgba(255,255,255,0.05)" }}
          >
            {(
              [
                { key: "irr", label: "تومانی (Tetra98)", icon: <CreditCard className="w-3.5 h-3.5" /> },
                { key: "usdt", label: "رمزارز (USDT)", icon: <Bitcoin className="w-3.5 h-3.5" /> },
              ] as { key: DepositMethod; label: string; icon: React.ReactNode }[]
            ).map(({ key, label, icon }) => (
              <button
                key={key}
                onClick={() => {
                  setDepositMethod(key);
                  setDepositError(null);
                  setCryptoDepositInfo(null);
                }}
                className="flex-1 py-2 text-[11px] font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all"
                style={
                  depositMethod === key
                    ? {
                        background: "linear-gradient(135deg, #E63946 0%, #b52d38 100%)",
                        color: "white",
                      }
                    : { color: "rgba(245,245,245,0.45)" }
                }
              >
                {icon} {label}
              </button>
            ))}
          </div>

          {/* ── IRR deposit form ── */}
          {depositMethod === "irr" && (
            <div className="space-y-4">
              <div>
                <label className="text-xs text-[#F5F5F5]/55 mb-2 block">مبلغ (تومان)</label>
                <input
                  type="number"
                  value={irrAmount}
                  onChange={(e) => setIrrAmount(e.target.value)}
                  placeholder="مثال: ۵۰۰،۰۰۰"
                  className="w-full rounded-xl px-4 py-3 text-sm focus:outline-none transition-all dir-ltr text-right"
                  style={{
                    background: "rgba(255,255,255,0.05)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    color: "#F5F5F5",
                  }}
                />
              </div>
              <div
                className="flex items-center gap-3 p-3.5 rounded-2xl"
                style={{
                  background: "rgba(230,57,70,0.07)",
                  border: "1px solid rgba(230,57,70,0.15)",
                }}
              >
                <Wallet className="w-4 h-4 text-[#E63946] flex-shrink-0" />
                <p className="text-[11px] text-[#F5F5F5]/60 leading-relaxed">
                  مبلغ پرداخت شده مستقیماً به کیف پول داخلی شما واریز می‌شود.
                </p>
              </div>
              {depositError && (
                <p
                  className="text-xs text-[#E63946] rounded-xl p-3"
                  style={{
                    background: "rgba(230,57,70,0.1)",
                    border: "1px solid rgba(230,57,70,0.2)",
                  }}
                >
                  {depositError}
                </p>
              )}
              <button
                onClick={handleIrrDeposit}
                disabled={depositLoading}
                className="w-full py-4 rounded-2xl text-sm font-bold transition-all active:scale-95 flex items-center justify-center gap-2 disabled:opacity-60"
                style={{
                  background: "linear-gradient(135deg, #E63946 0%, #c0303c 100%)",
                  color: "white",
                  boxShadow: "0 8px 24px rgba(230,57,70,0.3)",
                }}
              >
                {depositLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "انتقال به درگاه"}
              </button>
            </div>
          )}

          {/* ── USDT deposit form ── */}
          {depositMethod === "usdt" && !cryptoDepositInfo && (
            <div className="space-y-4">
              <div>
                <label className="text-xs text-[#F5F5F5]/55 mb-2 block">مقدار USDT</label>
                <input
                  type="number"
                  value={usdtAmount}
                  onChange={(e) => setUsdtAmount(e.target.value)}
                  placeholder="مثال: 10.00"
                  step="0.01"
                  min="0.01"
                  className="w-full rounded-xl px-4 py-3 text-sm focus:outline-none transition-all dir-ltr text-left"
                  style={{
                    background: "rgba(255,255,255,0.05)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    color: "#F5F5F5",
                  }}
                />
                {/* Live USDT rate — prominent separate block */}
                <div
                  className="mt-3 rounded-2xl p-3.5"
                  style={{
                    background: "rgba(59,130,246,0.08)",
                    border: "1px solid rgba(59,130,246,0.2)",
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-[#F5F5F5]/50 font-medium">نرخ لحظه‌ای USDT</span>
                  </div>
                  <p className="text-xl font-bold text-blue-400 dir-ltr text-right">
                    {usdtRate ? `${formatPrice(usdtRate)} تومان` : "···"}
                  </p>
                  <p className="text-[10px] text-[#F5F5F5]/40 mt-0.5">به ازای هر ۱ USDT</p>
                  {usdtRate && Number(usdtAmount) > 0 && (
                    <div
                      className="mt-2.5 pt-2.5 flex items-center justify-between"
                      style={{ borderTop: "1px solid rgba(59,130,246,0.15)" }}
                    >
                      <span className="text-[11px] text-[#F5F5F5]/50">معادل تومانی</span>
                      <span className="text-base font-bold text-emerald-400 dir-ltr">
                        ≈ {formatPrice(Math.round(Number(usdtAmount) * usdtRate))} تومان
                      </span>
                    </div>
                  )}
                </div>
              </div>
              <div
                className="flex items-start gap-3 p-3.5 rounded-2xl"
                style={{
                  background: "rgba(59,130,246,0.07)",
                  border: "1px solid rgba(59,130,246,0.15)",
                }}
              >
                <Bitcoin className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                <p className="text-[11px] text-[#F5F5F5]/60 leading-relaxed">
                  پس از ثبت، آدرس کیف پول USDT (شبکه TRC20) نمایش داده می‌شود. پس از تأیید تراکنش در شبکه، موجودی شما به‌روزرسانی می‌شود.
                </p>
              </div>
              {depositError && (
                <p
                  className="text-xs text-[#E63946] rounded-xl p-3"
                  style={{
                    background: "rgba(230,57,70,0.1)",
                    border: "1px solid rgba(230,57,70,0.2)",
                  }}
                >
                  {depositError}
                </p>
              )}
              <button
                onClick={handleUsdtDeposit}
                disabled={depositLoading}
                className="w-full py-4 rounded-2xl text-sm font-bold transition-all active:scale-95 flex items-center justify-center gap-2 disabled:opacity-60"
                style={{
                  background: "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
                  color: "white",
                  boxShadow: "0 8px 24px rgba(59,130,246,0.25)",
                }}
              >
                {depositLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "دریافت آدرس واریز"}
              </button>
            </div>
          )}

          {/* ── USDT deposit address display ── */}
          {depositMethod === "usdt" && cryptoDepositInfo && (
            <div className="space-y-4">
              <div
                className="flex items-center gap-2 p-3 rounded-2xl"
                style={{
                  background: "rgba(16,185,129,0.07)",
                  border: "1px solid rgba(16,185,129,0.2)",
                }}
              >
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <p className="text-[11px] text-emerald-400 font-bold">
                  درخواست واریز ثبت شد — آدرس زیر را کپی کنید.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] text-[#F5F5F5]/45">آدرس کیف پول USDT</span>
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(59,130,246,0.15)", color: "#60a5fa" }}
                  >
                    {cryptoDepositInfo.network}
                  </span>
                </div>
                <div
                  className="flex items-center gap-2 p-3 rounded-xl"
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                >
                  <span className="text-[11px] text-[#F5F5F5]/80 dir-ltr flex-1 break-all font-mono select-all">
                    {cryptoDepositInfo.address}
                  </span>
                  <button
                    onClick={() => handleCopyAddress(cryptoDepositInfo.address)}
                    className="flex-shrink-0 px-3 py-2 rounded-lg transition-colors hover:bg-white/10 flex items-center gap-1.5 text-[11px] font-bold"
                    title="کپی آدرس"
                  >
                    {copiedAddress ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Copy className="w-4 h-4 text-[#F5F5F5]/50" />
                    )}
                    <span>{copiedAddress ? "Copied" : "Copy"}</span>
                  </button>
                </div>
              </div>

              <div
                className="grid grid-cols-2 gap-2 p-3 rounded-xl text-center"
                style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                <div>
                  <p className="text-[10px] text-[#F5F5F5]/40 mb-0.5">مبلغ مورد انتظار</p>
                  <p className="text-sm font-bold text-blue-400 dir-ltr">
                    {cryptoDepositInfo.expectedAmount} USDT
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-[#F5F5F5]/40 mb-0.5">شماره تراکنش</p>
                  <p className="text-sm font-bold text-[#F5F5F5]/70">#{cryptoDepositInfo.txId}</p>
                </div>
              </div>

              <p className="text-[11px] text-[#F5F5F5]/40 text-center leading-relaxed">
                دقیقاً همین مقدار USDT را به آدرس بالا ارسال کنید. پس از تأیید شبکه، موجودی کیف پول شما اعتبار می‌گیرد.
              </p>

              <button
                onClick={() => {
                  setIsDepositOpen(false);
                  refreshWallet();
                }}
                className="w-full py-3 rounded-2xl text-sm font-bold transition-all active:scale-95"
                style={{
                  background: "rgba(255,255,255,0.07)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "#F5F5F5",
                }}
              >
                متوجه شدم
              </button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
