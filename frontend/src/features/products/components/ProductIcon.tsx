"use client";

import Image from "next/image";
import { IconMap, CATEGORY_ICON_MAP } from "@/lib/icons";
import type { ProductCategory } from "@/features/products/types";

interface ProductIconProps {
  icon?: string;
  assetUrl?: string | null;
  gradient?: string;
  sizeClassName?: string;
  category?: ProductCategory;
  iconSizeClassName?: string;
}

export default function ProductIcon({
  icon = "Box",
  assetUrl,
  gradient,
  sizeClassName = "w-12 h-12",
  category,
  iconSizeClassName,
}: ProductIconProps) {
  if (assetUrl) {
    return (
      <div className={`${sizeClassName} relative rounded-2xl bg-[#33383F] overflow-hidden flex items-center justify-center shadow-lg`}>
        <Image src={assetUrl} alt="" fill sizes="48px" className="object-cover" loading="lazy" unoptimized />
      </div>
    );
  }

  const categoryDefaults = category ? CATEGORY_ICON_MAP[category] : null;
  const resolvedGradient = gradient || categoryDefaults?.gradient || "from-gray-600 to-slate-900";
  const resolvedIcon = icon !== "Box" ? icon : (categoryDefaults?.icon || icon);

  return (
    <div className={`${sizeClassName} rounded-2xl bg-gradient-to-br ${resolvedGradient} flex items-center justify-center shadow-lg`}>
      {IconMap[resolvedIcon]?.(iconSizeClassName) || IconMap.Box(iconSizeClassName)}
    </div>
  );
}
