"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, FileText, MessageSquare, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import PageHeader from "@/components/PageHeader";
import UserAvatar from "@/components/UserAvatar";
import { getProfile, type BootstrapProfile } from "@/lib/api";
import { formatPrice, toPersianDigits } from "@/lib/utils";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<BootstrapProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    setProfileError(null);
    try {
      setProfile(await getProfile());
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "پروفایل دریافت نشد.");
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadProfile);
  }, [loadProfile]);

  const fullName = `${profile?.user.firstName || "کاربر"} ${profile?.user.lastName || ""}`.trim();

  return (
    <div className="min-h-[100dvh] pb-32 font-sans text-[#F5F5F5]">
      <PageHeader title="پروفایل" />

      <main className="mx-auto mt-2 max-w-2xl px-5">
        {profileError && (
          <div className="mb-5 rounded-2xl border border-[#E63946]/20 bg-[#E63946]/[0.06] p-4 text-center text-xs text-[#E63946]">
            <p>{profileError}</p>
            <button type="button" onClick={() => void loadProfile()} className="mt-2 rounded-xl px-4 font-bold">تلاش دوباره</button>
          </div>
        )}
        {/* Avatar + name */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <UserAvatar
            firstName={profile?.user.firstName}
            username={profile?.user.username}
            telegramId={profile?.user.telegramId}
            className="size-20 text-3xl"
            style={{
              background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.04) 100%)",
              border: "2px solid rgba(255,255,255,0.12)",
              boxShadow: "0 0 40px rgba(230,57,70,0.12)",
            }}
          />
          <div className="text-center">
            <h2 className="text-lg font-bold text-[#F5F5F5]">{fullName}</h2>
            {profile?.user.username && (
              <p className="text-xs text-[#F5F5F5]/40 mt-1">@{profile.user.username}</p>
            )}
          </div>
        </div>

        {/* Stats */}
        <div
          className="flex justify-between items-center rounded-2xl px-5 py-4 mb-8"
          style={{
            background: "linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)",
            border: "1px solid rgba(255,255,255,0.09)",
          }}
        >
          <div className="flex min-w-0 flex-1 flex-col items-center gap-1">
            <span className="max-w-full truncate text-base font-bold text-[#F5F5F5] sm:text-xl">{toPersianDigits(profile?.orderCount || 0)}</span>
            <span className="text-[10px] text-[#F5F5F5]/45">سفارش</span>
          </div>

          <div className="h-10 w-px" style={{ background: "rgba(255,255,255,0.08)" }} />

          <div className="flex min-w-0 flex-1 flex-col items-center gap-1">
            <span className="max-w-full truncate text-base font-bold text-emerald-400 sm:text-xl">{toPersianDigits(profile?.activeOrderCount || 0)}</span>
            <span className="text-[10px] text-[#F5F5F5]/45">سرویس فعال</span>
          </div>

          <div className="h-10 w-px" style={{ background: "rgba(255,255,255,0.08)" }} />

          <button
            className="flex min-w-0 flex-1 flex-col items-center gap-1 transition-transform active:scale-95"
            onClick={() => router.push("/finance")}
          >
            <span className="max-w-full truncate text-base font-bold text-[#F5F5F5] sm:text-xl">{formatPrice(profile?.walletBalance || 0)}</span>
            <span className="text-[10px] text-[#F5F5F5]/45">موجودی</span>
          </button>
        </div>

        {/* Menu items */}
        <div className="space-y-1 mb-8">
          {[
            { icon: FileText, label: "سفارش‌های من", path: "/orders" },
            { icon: MessageSquare, label: "تیکت‌های پشتیبانی", path: "/support" },
          ].map(({ icon: Icon, label, path }) => (
            <button
              key={path}
              onClick={() => router.push(path)}
              className="w-full flex items-center justify-between p-4 rounded-2xl transition-all active:scale-[0.98] hover:bg-white/[0.04]"
            >
              <div className="flex items-center gap-4">
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
                >
                  <Icon className="w-4 h-4 text-[#F5F5F5]/60" />
                </div>
                <span className="text-sm font-medium text-[#F5F5F5]/80">{label}</span>
              </div>
              <ChevronLeft className="w-4 h-4 text-[#F5F5F5]/30" />
            </button>
          ))}

          <button
            onClick={() => router.push("/invite")}
            className="w-full flex items-center justify-between p-4 rounded-2xl transition-all active:scale-[0.98] hover:bg-white/[0.04]"
          >
            <div className="flex items-center gap-4">
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center"
                style={{ background: "rgba(230,57,70,0.1)", border: "1px solid rgba(230,57,70,0.15)" }}
              >
                <Users className="w-4 h-4 text-[#E63946]" />
              </div>
              <span className="text-sm font-medium text-[#F5F5F5]/80">دعوت از دوستان</span>
            </div>
            <span className="text-[10px] font-bold text-[#E63946]">دعوت دوستان</span>
          </button>
        </div>

        <button
          onClick={() => window.Telegram?.WebApp?.close()}
          className="w-full text-[#E63946]/70 font-semibold text-sm py-4 rounded-2xl hover:bg-[#E63946]/[0.06] transition-all active:scale-95"
        >
          بستن برنامه
        </button>
      </main>
    </div>
  );
}
