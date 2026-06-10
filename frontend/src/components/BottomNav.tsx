"use client";

import { Gift, User, FileText, Send, LayoutGrid, Home } from "lucide-react";
import { usePathname } from "next/navigation";
import Link from "next/link";

export default function BottomNav() {
  const pathname = usePathname();

  // Navigation configuration array
  const navItems = [
    { name: "پروفایل", path: "/profile", icon: <User className="w-5 h-5" /> },
    { name: "سفارشات", path: "/orders", icon: <FileText className="w-5 h-5" /> },
    { name: "محصولات", path: "/products", icon: <LayoutGrid className="w-5 h-5" /> },
    { name: "پشتیبانی", path: "/support", icon: <Send className="w-5 h-5" /> },
  ];

  return (
    <div className="fixed bottom-0 left-0 w-full px-4 pb-4 z-50 pointer-events-none">
      {/* Floating Invite Banner */}
      <Link 
        href="/invite"
        className="w-full pointer-events-auto bg-indigo-950/95 backdrop-blur-md mx-auto max-w-lg rounded-2xl p-3 mb-3 flex justify-between items-center border border-indigo-500/50 shadow-xl shadow-indigo-500/10 hover:bg-indigo-900 transition-all active:scale-95"
      >
        <Gift className="w-6 h-6 text-cyan-400 animate-pulse" />
        <span className="font-bold text-sm text-cyan-100">دوستات رو دعوت کن و تخفیف بگیر!</span>
      </Link>

      {/* Navigation Bar */}
      <nav className="pointer-events-auto bg-slate-900/95 backdrop-blur-xl border border-slate-700 mx-auto max-w-lg rounded-3xl p-2 flex justify-between items-center shadow-2xl">
        
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          return (
            <Link 
              key={item.path}
              href={item.path}
              className={`flex flex-col items-center gap-1 p-2 w-16 transition-colors active:scale-95 ${
                isActive ? 'text-cyan-400' : 'text-slate-400 hover:text-cyan-400'
              }`}
            >
              {item.icon}
              <span className="text-[10px] font-medium">{item.name}</span>
            </Link>
          );
        })}

        {/* Highlighted Home Button */}
        <Link 
          href="/"
          className={`flex flex-col items-center gap-1 py-2 px-5 rounded-2xl shadow-sm transition-colors active:scale-95 ${
            pathname === '/' 
              ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50' 
              : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/20'
          }`}
        >
          <Home className="w-5 h-5 mb-1 mx-auto" />
          <span className="text-[10px] font-bold">خانه</span>
        </Link>
      </nav>
    </div>
  );
}