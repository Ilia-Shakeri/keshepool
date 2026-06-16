"use client";

import { IconMap } from "@/lib/icons";

interface ProductIconProps {
  icon?: string;
  assetUrl?: string | null;
  gradient?: string;
  sizeClassName?: string;
}

export default function ProductIcon({
  icon = "Box",
  assetUrl,
  gradient = "from-gray-700 to-black",
  sizeClassName = "w-12 h-12",
}: ProductIconProps) {
  if (assetUrl) {
    return (
      <div className={`${sizeClassName} rounded-2xl bg-[#33383F] overflow-hidden flex items-center justify-center shadow-lg`}>
        <img src={assetUrl} alt="" className="w-full h-full object-cover" loading="lazy" />
      </div>
    );
  }

  return (
    <div className={`${sizeClassName} rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-lg`}>
      {IconMap[icon] || IconMap.Box}
    </div>
  );
}