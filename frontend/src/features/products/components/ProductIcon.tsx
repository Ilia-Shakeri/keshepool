"use client";

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
      <div className={`${sizeClassName} rounded-2xl bg-[#33383F] overflow-hidden flex items-center justify-center shadow-lg`}>
        <img src={assetUrl} alt="" className="w-full h-full object-cover" loading="lazy" />
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
