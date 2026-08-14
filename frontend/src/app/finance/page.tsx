"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownToLine,
  Bitcoin,
  CheckCircle2,
  ChevronDown,
  Copy,
  CreditCard,
  DollarSign,
  FileCheck2,
  Home,
  ImageUp,
  Loader2,
  Plus,
  ShieldCheck,
  Sparkles,
  Wallet,
  Wifi,
  X,
} from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { DialogDescription } from "@/components/ui/dialog";
import PageHeader from "@/components/PageHeader";
import { useTelegramBackButton } from "@/hooks/useTelegramBackButton";
import {
  createCashoutRequest,
  getCashoutPlatforms,
  getPublicConfig,
  getUsdtRate,
  getWalletBalance,
  getWalletTransactions,
  initiateCryptoDeposit,
  submitCardTransfer,
  type CashoutPlatform,
  type PublicConfig,
  type WalletTransaction,
} from "@/lib/api";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { copyText } from "@/lib/clipboard";
import { shouldBlockFinancialDismiss } from "@/lib/modal-dismiss";
import { formatTransactionAmount } from "@/lib/transaction-format";

// ── helpers ──────────────────────────────────────────────────────────────────

type DepositMethod = "card" | "usdt";
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

export default function FinancePage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("wallet");

  // Wallet state
  const [walletBalance, setWalletBalance] = useState<number | null>(null);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [walletError, setWalletError] = useState<string | null>(null);

  // Deposit modal state
  const [isDepositOpen, setIsDepositOpen] = useState(false);
  const [depositMethod, setDepositMethod] = useState<DepositMethod>("card");
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
  const [copiedCard, setCopiedCard] = useState(false);
  const [usdtRate, setUsdtRate] = useState<number | null>(null);
  const [paymentConfig, setPaymentConfig] = useState<PublicConfig["payments"] | null>(null);
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [cardTransferSuccess, setCardTransferSuccess] = useState<{
    transactionId: number;
    adminDelivery: "sent" | "queued";
  } | null>(null);

  // Cashout state
  const [platforms, setPlatforms] = useState<CashoutPlatform[]>([]);
  const [platformError, setPlatformError] = useState<string | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState("");
  const [customSource, setCustomSource] = useState("");
  const [cashoutDetails, setCashoutDetails] = useState("");
  const [cashoutLoading, setCashoutLoading] = useState(false);
  const [cashoutError, setCashoutError] = useState<string | null>(null);
  const [cashoutSuccess, setCashoutSuccess] = useState(false);

  // Load wallet data
  const refreshWallet = async () => {
    setWalletError(null);
    const [balanceData, txData] = await Promise.allSettled([getWalletBalance(), getWalletTransactions()]);
    if (balanceData.status === "fulfilled") setWalletBalance(balanceData.value.balance);
    else setWalletError("موجودی کیف پول دریافت نشد.");
    if (txData.status === "fulfilled") setTransactions(txData.value);
    else setWalletError("همه اطلاعات کیف پول دریافت نشد. دوباره تلاش کنید.");
  };

  const loadPlatforms = useCallback(async () => {
    setPlatformError(null);
    try {
      const data = await getCashoutPlatforms();
      setPlatforms(data.platforms);
    } catch (error) {
      setPlatformError(error instanceof Error ? error.message : "فهرست منابع دریافت نشد.");
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(refreshWallet);
    void getPublicConfig()
      .then((config) => {
        setPaymentConfig(config.payments);
        if (!config.payments.cardToCard.enabled) setDepositMethod("usdt");
      })
      .catch(() => setPaymentConfig(null));
  }, []);

  // Load platforms when cashout tab activates
  useEffect(() => {
    if (activeTab === "cashout" && platforms.length === 0) {
      void Promise.resolve().then(loadPlatforms);
    }
  }, [activeTab, loadPlatforms, platforms.length]);

  // ── deposit handlers ────────────────────────────────────────────────────────

  const handleOpenDeposit = useCallback(() => {
    setDepositError(null);
    setCryptoDepositInfo(null);
    setIrrAmount("");
    setUsdtAmount("");
    setReceiptFile(null);
    setCardTransferSuccess(null);
    setCopiedCard(false);
    setDepositMethod(paymentConfig?.cardToCard.enabled === false ? "usdt" : "card");
    setIsDepositOpen(true);
    // Pull the live USDT rate so the user sees the equivalent value upfront
    getUsdtRate()
      .then((data) => setUsdtRate(data.tomanPerUsdt))
      .catch(() => setUsdtRate(null));
  }, [paymentConfig]);

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
  }, [handleOpenDeposit]);

  const handleCardTransfer = async () => {
    const amount = Number(irrAmount);
    if (!Number.isFinite(amount) || amount < 10000) {
      setDepositError("حداقل مبلغ ۱۰٬۰۰۰ تومان است.");
      return;
    }
    if (!receiptFile) {
      setDepositError("لطفاً عکس رسید بانکی را انتخاب کنید.");
      return;
    }
    const maxBytes = paymentConfig?.cardToCard.maxReceiptBytes ?? 5_000_000;
    if (receiptFile.size > maxBytes) {
      setDepositError(`حجم عکس رسید باید کمتر از ${Math.floor(maxBytes / 1_000_000)} مگابایت باشد.`);
      return;
    }
    setDepositError(null);
    setDepositLoading(true);
    try {
      const result = await submitCardTransfer(amount, receiptFile);
      setCardTransferSuccess({
        transactionId: result.transactionId,
        adminDelivery: result.adminDelivery,
      });
      await refreshWallet();
    } catch (err) {
      setDepositError(err instanceof Error ? err.message : "ثبت رسید ناموفق بود.");
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
    if (await copyText(address)) {
      setCopiedAddress(true);
      setTimeout(() => setCopiedAddress(false), 2000);
    } else {
      window.Telegram?.WebApp?.showAlert(address);
    }
  };

  const handleCopyCard = async () => {
    const cardNumber = paymentConfig?.cardToCard.cardNumber;
    if (!cardNumber) return;
    if (await copyText(cardNumber)) {
      setCopiedCard(true);
      setTimeout(() => setCopiedCard(false), 2000);
    } else {
      window.Telegram?.WebApp?.showAlert(cardNumber);
    }
  };

  const handleReceiptChange = (file: File | null) => {
    setDepositError(null);
    if (!file) {
      setReceiptFile(null);
      return;
    }
    if (!new Set(["image/jpeg", "image/png", "image/webp"]).has(file.type)) {
      setReceiptFile(null);
      setDepositError("فقط عکس JPG، PNG یا WebP پذیرفته می‌شود.");
      return;
    }
    setReceiptFile(file);
  };

  const closeDeposit = () => {
    if (shouldBlockFinancialDismiss(depositLoading)) return;
    setCryptoDepositInfo(null);
    setReceiptFile(null);
    setCardTransferSuccess(null);
    setDepositError(null);
    setIsDepositOpen(false);
  };

  useTelegramBackButton(closeDeposit, isDepositOpen);

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
    <div className="min-h-[100dvh] bg-[#0F0F10] pb-32 font-sans text-[#F5F5F5]">
      <PageHeader title="مالی و کیف پول" />

      {/* Tab switcher */}
      <div className="mx-auto mb-4 max-w-2xl px-5">
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

      <main className="mx-auto max-w-2xl space-y-5 px-5">
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
              {walletError && (
                <div className="mb-3 flex items-center justify-between gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/[0.07] p-3 text-xs text-amber-200">
                  <span>{walletError}</span>
                  <button type="button" onClick={() => void refreshWallet()} className="shrink-0 rounded-xl px-3 font-bold">تلاش دوباره</button>
                </div>
              )}
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
                      <div className="flex min-w-0 items-center gap-3">
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
                            <span className="text-sm font-bold truncate">
                              {tx.gateway === "card_to_card" ? "شارژ کارت‌به‌کارت" : txLabel(tx.type)}
                            </span>
                            {txStatusBadge(tx.status)}
                          </div>
                          <span className="text-[10px] text-[#F5F5F5]/45 mt-0.5">
                            {new Date(tx.createdAt).toLocaleDateString("fa-IR")}
                          </span>
                          {tx.hasReceipt && (
                            <span className="mt-0.5 flex items-center gap-1 text-[9px] font-medium text-blue-300/75">
                              <FileCheck2 className="h-3 w-3" /> رسید ثبت شده
                            </span>
                          )}
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
                  <h2 className="text-xl font-black tracking-tight">نقد کردن درآمد ارزی</h2>
                  <p className="mt-1 text-xs text-[#F5F5F5]/50">
                    اطلاعات درخواست را دقیق و بدون داده‌های محرمانه ثبت کنید.
                  </p>
                </div>
              </div>

              <div
                className="flex items-start gap-2.5 p-3.5 rounded-2xl mb-4"
                style={{ background: "rgba(230,57,70,0.07)", border: "1px solid rgba(230,57,70,0.15)" }}
              >
                <span className="text-base leading-none mt-0.5">⚠️</span>
                <p className="text-[11px] text-[#F5F5F5]/70 leading-relaxed">
                  رمز عبور، کد بازیابی، کلید خصوصی، کد ورود یا هر اطلاعات محرمانه دیگری را در این فرم وارد نکنید.
                </p>
              </div>

              {cashoutSuccess ? (
                <div className="flex flex-col items-center py-8 gap-4">
                  <CheckCircle2 className="w-14 h-14 text-emerald-400" />
                  <p className="text-sm font-bold text-center text-emerald-400">
                    درخواست شما با موفقیت ثبت شد.
                  </p>
                  <p className="text-xs text-[#F5F5F5]/50 text-center">
                    وضعیت درخواست از طریق اعلان‌های داخل برنامه در دسترس است.
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

                  {platformError && (
                    <div className="flex items-center justify-between gap-3 rounded-xl bg-[#E63946]/10 p-3 text-xs text-[#E63946]">
                      <span>{platformError}</span>
                      <button type="button" onClick={() => {
                        void loadPlatforms();
                      }} className="shrink-0 rounded-lg px-3 font-bold">تلاش دوباره</button>
                    </div>
                  )}

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
                      placeholder="مقدار، ارز، منبع درآمد و توضیحات لازم برای بررسی را بنویسید. اطلاعات محرمانه وارد نکنید."
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
          if (!open) closeDeposit();
        }}
      >
        <DialogContent
          className="dialog-safe-area max-h-[90dvh] w-[95%] max-w-md overflow-y-auto rounded-3xl border-none p-5 font-sans text-[#F5F5F5]"
          style={{
            background: "rgba(12,14,18,0.97)",
            backdropFilter: "blur(40px)",
            border: "1px solid rgba(255,255,255,0.09)",
          }}
          onEscapeKeyDown={(event) => shouldBlockFinancialDismiss(depositLoading) && event.preventDefault()}
          onPointerDownOutside={(event) => shouldBlockFinancialDismiss(depositLoading) && event.preventDefault()}
        >
          <DialogDescription className="sr-only">انتخاب روش و مبلغ افزایش موجودی کیف پول</DialogDescription>
          <DialogTitle className="text-lg font-bold flex justify-between items-center mb-4">
            افزایش موجودی
            <button
              onClick={closeDeposit}
              disabled={depositLoading}
              className="p-1.5 rounded-full hover:bg-white/10 transition-colors disabled:opacity-40"
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
                ...(paymentConfig?.cardToCard.enabled !== false
                  ? [{ key: "card" as const, label: "کارت‌به‌کارت", icon: <CreditCard className="w-3.5 h-3.5" /> }]
                  : []),
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

          {/* ── Card transfer form ── */}
          {depositMethod === "card" && !cardTransferSuccess && (
            <div className="space-y-4">
              {paymentConfig?.cardToCard.enabled && paymentConfig.cardToCard.cardNumber && paymentConfig.cardToCard.cardHolder ? (
                <button
                  type="button"
                  onClick={() => void handleCopyCard()}
                  aria-label="کپی شماره کارت"
                  className="group relative block w-full overflow-hidden rounded-[1.6rem] p-5 text-right shadow-[0_22px_55px_rgba(14,91,255,0.32)] transition-all active:scale-[0.985]"
                  style={{
                    aspectRatio: "1.586 / 1",
                    background: "linear-gradient(145deg, #0b76ff 0%, #0755db 48%, #0533a3 100%)",
                    border: "1px solid rgba(255,255,255,0.24)",
                  }}
                >
                  <span className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-cyan-300/25 blur-2xl" />
                  <span className="pointer-events-none absolute -bottom-24 -left-12 h-52 w-52 rounded-full bg-blue-950/50 blur-2xl" />
                  <span className="pointer-events-none absolute inset-0 bg-[linear-gradient(115deg,transparent_20%,rgba(255,255,255,0.16)_42%,transparent_56%)] opacity-60" />

                  <span className="relative flex h-full flex-col justify-between text-white">
                    <span className="flex items-start justify-between">
                      <span className="flex items-center gap-2">
                        <span className="text-lg font-black tracking-tight">کِش‌پول</span>
                        <span className="rounded-full border border-white/25 bg-white/10 px-2 py-0.5 text-[8px] font-bold tracking-widest text-white/80">
                          BANK CARD
                        </span>
                      </span>
                      <Wifi className="h-6 w-6 rotate-90 text-white/75" />
                    </span>

                    <span className="flex items-center justify-between">
                      <span className="grid h-10 w-12 grid-cols-3 overflow-hidden rounded-lg border border-amber-100/65 bg-gradient-to-br from-amber-100 via-yellow-300 to-amber-500 shadow-inner">
                        {Array.from({ length: 9 }).map((_, index) => (
                          <span key={index} className="border border-amber-700/25" />
                        ))}
                      </span>
                      <span className="flex items-center gap-1.5 rounded-full bg-black/15 px-3 py-1.5 text-[10px] font-bold text-white/90 backdrop-blur-sm">
                        {copiedCard ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                        {copiedCard ? "کپی شد" : "برای کپی لمس کنید"}
                      </span>
                    </span>

                    <span>
                      <span className="block text-left font-mono text-[clamp(1.05rem,5vw,1.45rem)] font-semibold tracking-[0.12em] text-white drop-shadow-sm" dir="ltr">
                        {paymentConfig.cardToCard.cardNumber.replace(/(\d{4})(?=\d)/g, "$1 ")}
                      </span>
                      <span className="mt-3 flex items-end justify-between">
                        <span>
                          <span className="block text-[8px] font-medium uppercase tracking-widest text-white/50">CARD HOLDER</span>
                          <span className="mt-0.5 block text-sm font-bold tracking-wide text-white/95">
                            {paymentConfig.cardToCard.cardHolder}
                          </span>
                        </span>
                        <ShieldCheck className="h-6 w-6 text-white/75" />
                      </span>
                    </span>
                  </span>
                </button>
              ) : (
                <div className="rounded-2xl border border-amber-400/20 bg-amber-400/[0.07] p-4 text-xs leading-6 text-amber-200">
                  اطلاعات کارت در دسترس نیست. روش USDT را انتخاب کنید.
                </div>
              )}

              <div>
                <label className="text-xs text-[#F5F5F5]/55 mb-2 block">مبلغ (تومان)</label>
                <input
                  type="number"
                  inputMode="numeric"
                  min={10000}
                  max={50000000}
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

              <div>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <label htmlFor="card-transfer-receipt" className="text-xs text-[#F5F5F5]/65">
                    لطفاً بعد از واریز، عکس رسید را بارگذاری کنید.
                  </label>
                  <span className="shrink-0 text-[9px] text-[#F5F5F5]/35">حداکثر ۵ مگابایت</span>
                </div>
                <label
                  htmlFor="card-transfer-receipt"
                  className={`flex min-h-28 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed px-4 py-5 text-center transition-all active:scale-[0.99] ${
                    receiptFile
                      ? "border-emerald-400/35 bg-emerald-400/[0.07]"
                      : "border-blue-400/30 bg-blue-500/[0.06] hover:bg-blue-500/[0.1]"
                  }`}
                >
                  {receiptFile ? (
                    <>
                      <FileCheck2 className="h-8 w-8 text-emerald-400" />
                      <span className="max-w-full truncate text-xs font-bold text-emerald-300">{receiptFile.name}</span>
                      <span className="text-[10px] text-[#F5F5F5]/45">برای تغییر عکس، دوباره لمس کنید</span>
                    </>
                  ) : (
                    <>
                      <span className="rounded-2xl bg-blue-500/15 p-3 text-blue-300">
                        <ImageUp className="h-6 w-6" />
                      </span>
                      <span className="text-xs font-bold text-[#F5F5F5]/80">انتخاب عکس رسید بانکی</span>
                      <span className="text-[10px] text-[#F5F5F5]/40">JPG، PNG یا WebP</span>
                    </>
                  )}
                </label>
                <input
                  id="card-transfer-receipt"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="sr-only"
                  onChange={(event) => handleReceiptChange(event.target.files?.[0] ?? null)}
                />
              </div>

              <div className="flex items-start gap-3 rounded-2xl border border-blue-400/15 bg-blue-400/[0.06] p-3.5">
                <Wallet className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-300" />
                <p className="text-[11px] leading-relaxed text-[#F5F5F5]/60">
                  رسید برای مدیران فرستاده می‌شود. موجودی فقط بعد از بررسی و تایید مدیر شارژ می‌شود.
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
                onClick={handleCardTransfer}
                disabled={depositLoading || !paymentConfig?.cardToCard.enabled}
                className="w-full py-4 rounded-2xl text-sm font-bold transition-all active:scale-95 flex items-center justify-center gap-2 disabled:opacity-60"
                style={{
                  background: "linear-gradient(135deg, #0b76ff 0%, #0647c8 100%)",
                  color: "white",
                  boxShadow: "0 8px 24px rgba(11,118,255,0.28)",
                }}
              >
                {depositLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "ثبت رسید و ارسال برای بررسی"}
              </button>
            </div>
          )}

          {depositMethod === "card" && cardTransferSuccess && (
            <div className="space-y-4 py-2 text-center">
              <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-400/10 text-emerald-400">
                <CheckCircle2 className="h-9 w-9" />
              </span>
              <div>
                <h3 className="text-base font-black text-emerald-300">رسید با موفقیت ثبت شد</h3>
                <p className="mt-2 text-xs leading-6 text-[#F5F5F5]/55">
                  تراکنش #{toPersianDigits(cardTransferSuccess.transactionId)} در انتظار بررسی مدیر است.
                  نتیجه در همین بخش تراکنش‌ها دیده می‌شود.
                </p>
                {cardTransferSuccess.adminDelivery === "queued" && (
                  <p className="mt-2 text-[10px] leading-5 text-amber-300/80">
                    پیام مدیر در صف ارسال است و خودکار دوباره فرستاده می‌شود.
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={closeDeposit}
                className="w-full rounded-2xl border border-white/10 bg-white/[0.07] py-3 text-sm font-bold"
              >
                بستن
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
                    <span>{copiedAddress ? "کپی شد" : "کپی"}</span>
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
