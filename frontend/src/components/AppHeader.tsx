"use client";

import Image from "next/image";

export default function AppHeader() {
  return (
    <div
      className="fixed top-0 left-0 w-full z-50 h-[52px]"
      style={{
        background: "rgba(10, 10, 11, 0.82)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="flex items-center justify-center h-full max-w-md mx-auto px-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 flex-shrink-0 rounded-xl overflow-hidden">
            <Image
              src="/logo/main-logo.png"
              alt="Keshepool"
              width={1254}
              height={1254}
              className="w-full h-full object-contain"
              priority
            />
          </div>
          <span className="text-[16px] font-bold tracking-wide select-none leading-none">
            <span style={{ color: "rgba(230,230,230,0.92)" }}>Keshe</span>
            <span style={{ color: "#E63946" }}>Pool</span>
          </span>
        </div>
      </div>
    </div>
  );
}
