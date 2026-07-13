"use client";

import { Home, Search, FileText, Wallet, User } from "lucide-react";
import { usePathname } from "next/navigation";
import Link from "next/link";

const NAV_ITEMS = [
  { name: "پروفایل", path: "/profile", icon: User },
  { name: "کیف پول", path: "/finance", icon: Wallet },
  { name: "سفارش‌ها", path: "/orders", icon: FileText },
  { name: "محصولات", path: "/products", icon: Search },
  { name: "خانه", path: "/", icon: Home },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <div
      className="app-bottom-nav fixed z-40"
      style={{
        background: "rgba(10, 10, 11, 0.90)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        borderTop: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      <nav className="flex items-end justify-between px-2 pb-[calc(0.5rem+var(--safe-area-bottom))] pt-2 sm:px-6">
        {NAV_ITEMS.map(({ name, path, icon: Icon }) => {
          const isActive = path === "/" ? pathname === "/" : pathname.startsWith(path);

          return (
            <Link
              key={path}
              href={path}
              className="flex min-w-[52px] flex-col items-center gap-1 rounded-xl"
            >
              <div className="relative flex items-center justify-center w-11 h-8">
                {isActive && (
                  <div
                    className="absolute inset-0 rounded-xl"
                    style={{ background: "rgba(230,57,70,0.14)" }}
                  />
                )}
                <Icon
                  className="relative transition-all duration-200"
                  style={{
                    width: 20,
                    height: 20,
                    color: isActive ? "#E63946" : "rgba(245,245,245,0.4)",
                    strokeWidth: isActive ? 2.5 : 1.8,
                  }}
                />
              </div>
              <span
                className="text-[9px] font-medium transition-all duration-200"
                style={{ color: isActive ? "#E63946" : "rgba(245,245,245,0.38)" }}
              >
                {name}
              </span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
