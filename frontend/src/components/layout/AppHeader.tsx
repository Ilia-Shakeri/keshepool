"use client";

import Image from "next/image";

export default function AppHeader() {
  return (
    <div
      className="app-topbar fixed z-50"
      style={{
        background: "rgba(10, 10, 11, 0.82)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="flex h-full items-center justify-center px-5">
        {/* dir=ltr: forces icon-left / text-right regardless of the RTL page direction */}
        <div className="flex items-center gap-2" dir="ltr">
          <Image
            src="/logo/main-logo.png"
            alt=""
            width={32}
            height={32}
            priority
            style={{ width: 32, height: 32, objectFit: "contain", flexShrink: 0, borderRadius: 8 }}
          />
          {/*
           * text-logo.png raw size: 2752×1535.
           * Text zone: rows 619–919 (300 raw px tall).
           * Scale so text renders at 18px: factor = 18/300 = 0.06
           *   display w = 2752 × 0.06 = 165px
           *   display h = 1535 × 0.06 = 92px
           *   text top  =  619 × 0.06 = 37px  → marginTop = -37px
           */}
          <div style={{ width: 165, height: 18, overflow: "hidden", position: "relative", flexShrink: 0 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo/text-logo.png"
              alt="Keshepool"
              style={{ width: 165, height: 92, position: "absolute", top: -37, left: 0 }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
