export type ProductCategory =
  | "vpn"
  | "music"
  | "video"
  | "ai"
  | "social"
  | "gaming"
  | "tools"
  | "edu"
  | "finance";

export interface ProductVariant {
  id: string;
  duration: string;
  priceLabel: string;
  rawPrice: number;
  stockCount?: number;
}

export interface Product {
  id: string;
  title: string;
  brand: string;
  subtitle: string;
  variants: ProductVariant[];
  icon: string;
  assetUrl?: string | null;
  gradient: string;
  category: ProductCategory;
}