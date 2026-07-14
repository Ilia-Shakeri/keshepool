import type { Metadata, Viewport } from "next";
import Script from "next/script";
import AppHeader from "@/components/layout/AppHeader";
import BottomNav from "@/components/layout/BottomNav";
import TelegramBootstrap from "@/components/layout/TelegramBootstrap";
import "./globals.css";

export const metadata: Metadata = {
  title: "Keshepool | Premium Accounts",
  description: "Buy premium accounts, secure VPN configs, and foreign payment services.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  themeColor: "#0A0A0B",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <body className="bg-[#0F0F10] font-sans text-[#F5F5F5] antialiased" suppressHydrationWarning>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <div className="app-shell relative overflow-x-clip bg-[#0F0F10] shadow-2xl lg:border-x lg:border-[#33383F]/50">
          <AppHeader />
          <main className="app-main">
            <TelegramBootstrap />
            {children}
          </main>
          <BottomNav />
        </div>
      </body>
    </html>
  );
}
