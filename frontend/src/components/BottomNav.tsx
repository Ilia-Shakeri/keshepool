"use client";

import { Gift, User, FileText, Send, LayoutGrid, Home } from "lucide-react";
import { usePathname } from "next/navigation";
import Link from "next/link";

export default function BottomNav() {
  const pathname = usePathname();

  // Navigation configuration array - Order matters for RTL
  // RTL render order from right to left: Profile -> Orders -> Home -> Products -> Support
  const navItems = [
    { name: "پروفایل", path: "/profile", icon: <User className="w-[18px] h-[18px]" /> },
    { name: "سفارشات", path: "/orders", icon: <FileText className="w-[18px] h-[18px]" /> },
    { name: "خانه", path: "/", icon: <Home className="w-5 h-5" /> },
    { name: "محصولات", path: "/products", icon: <LayoutGrid className="w-[18px] h-[18px]" /> },
    { name: "پشتیبانی", path: "/support", icon: <Send className="w-[18px] h-[18px]" /> },
  ];

  return (
    <div className="fixed bottom-0 left-0 w-full px-4 pb-4 z-50 pointer-events-none">
      {/* Floating Invite Banner */}
      <Link 
        href="/invite"
        className="w-full pointer-events-auto bg-indigo-950/95 backdrop-blur-md mx-auto max-w-lg rounded-2xl p-3 mb-3 flex justify-between items-center border border-indigo-500/50 shadow-xl shadow-indigo-500/10 hover:bg-indigo-900 transition-all active:scale-95"
      >
        <Gift className="w-5 h-5 text-cyan-400 animate-pulse" />
        <span className="font-bold text-xs text-cyan-100">دوستات رو دعوت کن و تخفیف بگیر!</span>
      </Link>

      {/* Navigation Bar */}
      <nav className="pointer-events-auto bg-slate-900/95 backdrop-blur-xl border border-slate-700 mx-auto max-w-lg rounded-2xl p-2 flex justify-between items-center shadow-2xl relative">
        
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          const isHome = item.path === '/';

          return (
            <Link 
              key={item.path}
              href={item.path}
              className={`flex flex-col items-center justify-center gap-1 w-14 transition-all duration-300 ease-in-out active:scale-95 ${
                isHome ? 'py-2 px-3 rounded-xl shadow-md z-10' : 'p-2'
              } ${
                isActive && !isHome ? 'text-cyan-400 scale-110 -translate-y-1' : ''
              } ${
                isActive && isHome ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50 scale-105' : ''
              } ${
                !isActive && isHome ? 'bg-cyan-500/10 text-cyan-400/80 border border-cyan-500/30 hover:bg-cyan-500/20' : ''
              } ${
                !isActive && !isHome ? 'text-slate-400 hover:text-cyan-400' : ''
              }`}
            >
              <div className="transition-transform duration-300">
                {item.icon}
              </div>
              <span className={`text-[9px] font-medium transition-opacity duration-300 ${isActive ? 'opacity-100 font-bold' : 'opacity-70'}`}>
                {item.name}
              </span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}