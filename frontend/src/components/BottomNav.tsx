"use client";

import { Home, Search, FileText, Wallet, User } from "lucide-react";
import { usePathname } from "next/navigation";
import Link from "next/link";

export default function BottomNav() {
  const pathname = usePathname();

  // Navigation schema operational map
  const navItems = [
    { name: "پروفایل", path: "/profile", icon: <User className="w-[22px] h-[22px]" /> },
    { name: "کیف پول", path: "/finance", icon: <Wallet className="w-[22px] h-[22px]" /> },
    { name: "سفارش‌ها", path: "/orders", icon: <FileText className="w-[22px] h-[22px]" /> },
    { name: "محصولات", path: "/products", icon: <Search className="w-[22px] h-[22px]" /> },
    { name: "خانه", path: "/", icon: <Home className="w-[22px] h-[22px]" /> },
  ];

  return (
    <div className="fixed bottom-0 left-0 w-full bg-[#0F0F10]/95 backdrop-blur-xl border-t border-[#33383F]/60 z-50 pb-2">
      <nav className="flex justify-between items-center px-6 py-3 max-w-md mx-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.path || (item.path === '/products' && pathname.startsWith('/products'));
          
          return (
            <Link 
              key={item.path}
              href={item.path}
              className={`flex flex-col items-center justify-center gap-1.5 transition-all duration-300 ease-in-out ${
                isActive ? 'text-[#E63946]' : 'text-[#F5F5F5]/50 hover:text-[#F5F5F5]/70'
              }`}
            >
              {item.icon}
              <span className={`text-[10px] font-medium transition-opacity duration-300 ${isActive ? 'font-bold' : ''}`}>
                {item.name}
              </span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}