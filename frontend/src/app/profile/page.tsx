"use client";

import { User, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function ProfilePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans pb-32 relative">
      <header className="flex justify-between items-center p-4 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-40 border-b border-zinc-800/50 mb-6 max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-emerald-400">پروفایل کاربری</h1>
        <button onClick={() => router.back()} className="text-zinc-400 hover:text-white transition-colors bg-zinc-800/50 px-4 py-1.5 rounded-xl text-sm font-medium">
          بازگشت
        </button>
      </header>

      <main className="flex flex-col items-center gap-6 w-full px-4 max-w-lg mx-auto">
        <div className="relative mt-4">
          <div className="w-24 h-24 bg-zinc-900 rounded-full border-2 border-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <User className="w-12 h-12 text-emerald-400" />
          </div>
          <div className="absolute bottom-0 right-0 bg-emerald-500 text-white text-[10px] px-2 py-1 rounded-full font-bold shadow-md">VIP</div>
        </div>
        
        <div className="text-center w-full">
          <h3 className="text-xl font-bold text-white mb-1">کاربر کشه‌پول</h3>
          <p className="text-sm text-zinc-400 font-mono">0912***1234</p>
        </div>
        
        <div className="w-full bg-zinc-900/60 backdrop-blur-sm rounded-2xl p-5 border border-zinc-800 flex justify-between items-center shadow-md mt-2">
          <span className="text-sm text-zinc-300">موجودی کیف پول</span>
          <span className="text-lg font-bold text-emerald-400 flex items-center gap-1">
            ۰ <span className="text-xs font-normal">تومان</span>
          </span>
        </div>
        
        <Button className="w-full bg-zinc-900/40 hover:bg-zinc-800 text-red-400 border border-red-500/20 hover:border-red-500/40 flex items-center gap-2 py-6 rounded-2xl mt-4 transition-all">
          <LogOut className="w-5 h-5" /> خروج از حساب
        </Button>
      </main>
    </div>
  );
}