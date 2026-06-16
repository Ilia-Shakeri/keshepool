import type { Metadata } from "next";
import localFont from "next/font/local";
import Script from "next/script";
import BottomNav from "@/components/BottomNav";
import "./globals.css";

// Configure local font mapping
const vazir = localFont({
  src: [
    { path: "../fonts/Vazir-Regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/Vazir-Bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-vazir",
  display: "swap",
});

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
      <body className={`${vazir.variable} font-sans antialiased bg-[#0F0F10] text-[#F5F5F5]`} suppressHydrationWarning>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <main className="min-h-screen overflow-x-hidden relative max-w-md mx-auto bg-[#0F0F10] shadow-2xl border-x border-[#33383F]/50">
          {children}
          <BottomNav />
        </main>
      </body>
    </html>
  );
}