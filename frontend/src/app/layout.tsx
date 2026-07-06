import type { Metadata } from "next";
import Script from "next/script";
import AppHeader from "@/components/layout/AppHeader";
import BottomNav from "@/components/layout/BottomNav";
import TelegramBootstrap from "@/components/layout/TelegramBootstrap";
import "./globals.css";

export const metadata: Metadata = {
  title: "Keshepool | Premium Accounts",
  description: "Buy premium accounts, secure VPN configs, and foreign payment services.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <body className="font-sans antialiased bg-[#0F0F10] text-[#F5F5F5]" suppressHydrationWarning>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <TelegramBootstrap />
        <div className="min-h-screen overflow-x-hidden relative max-w-md mx-auto bg-[#0F0F10] shadow-2xl border-x border-[#33383F]/50">
          <AppHeader />
          <main className="pt-[52px]">
            {children}
          </main>
          <BottomNav />
        </div>
      </body>
    </html>
  );
}
