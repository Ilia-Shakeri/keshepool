import type { Metadata } from "next";
import localFont from "next/font/local";
import Script from "next/script";
import BottomNav from "@/components/BottomNav";
import "./globals.css";

// Configure local font mapping
const vazir = localFont({
  src: [
    {
      path: "../fonts/Vazir-Regular.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../fonts/Vazir-Bold.woff2",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--font-vazir",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ZoodSub | Premium Accounts",
  description: "Buy premium accounts for Spotify, Netflix, Apple Music and more.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <body className={`${vazir.variable} font-sans antialiased bg-slate-950`} suppressHydrationWarning>
        
        {/* Load Telegram Web App SDK */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
        
        <main className="min-h-screen text-slate-100 overflow-x-hidden relative">
          {children}
          {/* Global Bottom Navigation integrated here */}
          <BottomNav />
        </main>
      </body>
    </html>
  );
}