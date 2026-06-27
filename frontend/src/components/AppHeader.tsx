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
          <div
            className="w-7 h-7 rounded-xl overflow-hidden flex-shrink-0"
            style={{ boxShadow: "0 0 14px rgba(230,57,70,0.25)" }}
          >
            <Image
              src="/logo/main-logo.png"
              alt="Keshepool"
              width={28}
              height={28}
              className="w-full h-full object-contain"
              priority
            />
          </div>
          <Image
            src="/logo/text-logo.png"
            alt="Keshepool"
            width={110}
            height={22}
            className="h-[22px] w-auto object-contain select-none"
            priority
          />
        </div>
      </div>
    </div>
  );
}
