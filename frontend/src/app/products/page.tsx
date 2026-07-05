"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, SlidersHorizontal } from "lucide-react";
import ProductDetailModal from "@/components/ProductDetailModal";
import CheckoutModal from "@/components/CheckoutModal";
import ProductIcon from "@/components/ProductIcon";
import { getProducts, getWalletBalance } from "@/lib/api";
import type { Product, ProductCategory, ProductVariant } from "@/lib/products";
import { toPersianDigits } from "@/lib/utils";

type CardVariant = ProductVariant & {
  sourceProductId: string;
  optionLabel: string;
  optionType: string;
  optionFeatures?: string[] | null;
};

type ProductCardModel = Omit<Product, "variants"> & {
  variants: CardVariant[];
};

const CATEGORIES: { id: ProductCategory | "all"; label: string }[] = [
  { id: "all", label: "همه" },
  { id: "vpn", label: "تحریم‌شکن" },
  { id: "video", label: "استریم" },
  { id: "ai", label: "ابزارهای هوشمند" },
  { id: "music", label: "موسیقی" },
  { id: "tools", label: "ابزار" },
  { id: "gaming", label: "گیمینگ" },
  { id: "social", label: "اجتماعی" },
  { id: "edu", label: "آموزشی" },
  { id: "finance", label: "مالی" },
];

function getParentProductName(product: Product): string {
  return product.brand.replace(/\b(Family|Individual|Personal|Single)\b/gi, "").replace(/\s+/g, " ").trim();
}

function getVariantOptionLabel(product: Product, variant: ProductVariant): string {
  const parentName = getParentProductName(product);
  const productOption = product.brand.replace(parentName, "").trim();
  return [productOption, variant.duration].filter(Boolean).join(" - ");
}

function getProductOptionType(product: Product): string {
  const parentName = getParentProductName(product);
  return product.brand.replace(parentName, "").trim() || "استاندارد";
}

function getStartingVariant(product: ProductCardModel): CardVariant | null {
  return product.variants.reduce<CardVariant | null>((lowest, variant) => {
    if (!lowest) return variant;
    return variant.rawPrice < lowest.rawPrice ? variant : lowest;
  }, null);
}

function ProductsContent() {
  const searchParams = useSearchParams();
  const initialCategory = (searchParams.get("category") as ProductCategory | "all") || "all";

  const [products, setProducts] = useState<Product[]>([]);
  const [activeCategory, setActiveCategory] = useState<ProductCategory | "all">(initialCategory);
  const [query, setQuery] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<ProductCardModel | null>(null);
  const [checkoutProduct, setCheckoutProduct] = useState<Product | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [walletBalance, setWalletBalance] = useState(0);
  const [productError, setProductError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Load products from the catalog API instead of rendering local product fixtures.
    Promise.all([getProducts(), getWalletBalance()])
      .then(([productData, balanceData]) => {
        setProducts(productData);
        setWalletBalance(balanceData.balance);
        setProductError(null);
      })
      .catch((error) => {
        setProducts([]);
        setProductError("خطا در دریافت محصولات.");
        console.error("Product page data load failed:", error);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const groupedProducts = useMemo<ProductCardModel[]>(() => {
    const groups = new Map<string, ProductCardModel>();

    for (const product of products) {
      const parentName = getParentProductName(product);
      const groupKey = `${product.category}:${parentName.toLowerCase()}`;
      const existing = groups.get(groupKey);
      const variants = product.variants.map((variant) => ({
        ...variant,
        sourceProductId: product.id,
        optionLabel: getVariantOptionLabel(product, variant),
        optionType: getProductOptionType(product),
        optionFeatures: product.features,
      }));

      if (existing) {
        existing.variants.push(...variants);
        existing.features = existing.features?.length ? existing.features : product.features;
      } else {
        groups.set(groupKey, {
          ...product,
          id: groupKey,
          brand: parentName || product.brand,
          title: parentName || product.title,
          subtitle: "",
          variants,
        });
      }
    }

    return Array.from(groups.values());
  }, [products]);

  const productById = useMemo(() => new Map(products.map((product) => [product.id, product])), [products]);

  const filteredProducts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return groupedProducts.filter((product) => {
      const categoryMatches = activeCategory === "all" || product.category === activeCategory;
      const queryMatches =
        !normalizedQuery ||
        product.title.toLowerCase().includes(normalizedQuery) ||
        product.brand.toLowerCase().includes(normalizedQuery) ||
        product.variants.some((variant) => variant.optionLabel.toLowerCase().includes(normalizedQuery));
      return categoryMatches && queryMatches;
    });
  }, [groupedProducts, activeCategory, query]);

  const handleProductSelect = (product: ProductCardModel) => {
    setSelectedVariant(null);
    setCheckoutProduct(null);
    setSelectedProduct(product);
    setIsDetailModalOpen(true);
  };

  const handleProceedToCheckout = (variant: ProductVariant) => {
    const sourceProductId = (variant as CardVariant).sourceProductId;
    const sourceProduct = sourceProductId ? productById.get(sourceProductId) : null;
    if (!sourceProduct) return;

    setCheckoutProduct(sourceProduct);
    setSelectedVariant(variant);
    setIsDetailModalOpen(false);
    setTimeout(() => setIsCheckoutOpen(true), 150);
  };

  return (
    <div className="min-h-screen text-[#F5F5F5] font-sans pb-32">
      <header className="px-5 pt-4 pb-2">
        <h1 className="text-base font-bold text-[#F5F5F5] text-center mb-4">محصولات</h1>
        <div className="relative mb-5">
          <Search className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#F5F5F5]/40 pointer-events-none" />
          <input
            type="text"
            placeholder="جستجو بین سرویس‌ها..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="w-full bg-white/[0.05] border border-white/10 rounded-2xl py-3 pr-10 pl-11 text-sm text-[#F5F5F5] focus:outline-none focus:border-[#E63946]/50 focus:bg-white/[0.07] transition-all placeholder:text-[#F5F5F5]/35 backdrop-blur-sm"
          />
          <button className="absolute left-3.5 top-1/2 -translate-y-1/2 p-1 text-[#F5F5F5]/40 hover:text-[#F5F5F5]/70 transition-colors">
            <SlidersHorizontal className="w-4 h-4" />
          </button>
        </div>

        <div className="flex gap-2 overflow-x-auto scrollbar-hide dir-rtl pb-1 -mx-5 px-5">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`whitespace-nowrap px-4 py-1.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
                activeCategory === cat.id
                  ? "bg-[#E63946] text-white shadow-lg shadow-[#E63946]/25"
                  : "bg-white/[0.06] text-[#F5F5F5]/60 border border-white/[0.08] hover:bg-white/[0.1] hover:text-[#F5F5F5]/80"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </header>

      <main className="px-4 mt-4">
        <div className="grid grid-cols-2 gap-3">
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="aspect-square rounded-3xl bg-white/[0.04] border border-white/[0.08] animate-pulse"
                />
              ))
            : productError ? (
                <div className="col-span-2 rounded-3xl p-8 text-center text-sm text-[#E63946] bg-white/[0.04] border border-white/[0.08]">
                  {productError}
                </div>
              )
            : filteredProducts.map((product) => {
                const startingVariant = getStartingVariant(product);

                return (
                <div
                  key={product.id}
                  className="group relative aspect-square rounded-3xl overflow-hidden cursor-pointer transition-all duration-300 active:scale-95 hover:scale-[1.02]"
                  style={{
                    background: "linear-gradient(135deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 100%)",
                    backdropFilter: "blur(20px)",
                    WebkitBackdropFilter: "blur(20px)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    boxShadow: "0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.08)",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => handleProductSelect(product)}
                    className="absolute inset-0 z-10"
                    aria-label={product.brand}
                  />
                  <div className="absolute inset-0 bg-gradient-to-br from-white/[0.04] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

                  <div className="relative h-full flex flex-col items-center justify-center p-4 gap-3 text-center">
                    <ProductIcon
                      icon={product.icon}
                      assetUrl={product.assetUrl}
                      gradient={product.gradient}
                      category={product.category}
                      sizeClassName="w-16 h-16"
                      iconSizeClassName="w-7 h-7"
                    />

                    <div className="flex flex-col gap-2 w-full">
                      <h3 className="text-lg font-black text-[#F5F5F5] leading-tight truncate">{product.brand}</h3>
                    </div>

                    <div className="w-full pt-1 border-t border-white/[0.08]">
                      <span className="text-[10px] text-[#F5F5F5]/40 ml-1">از</span>
                      <span className="text-xs font-bold text-emerald-400">{toPersianDigits(startingVariant?.priceLabel || "0")}</span>
                      <span className="text-[9px] text-[#F5F5F5]/40 mr-1">تومان</span>
                    </div>
                  </div>

                  <div className="absolute inset-0 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                    style={{ boxShadow: "0 0 0 1px rgba(230,57,70,0.3), 0 0 20px rgba(230,57,70,0.08)" }} />
                </div>
                );
              })}
        </div>

        {!isLoading && !productError && filteredProducts.length === 0 && (
          <div className="text-center py-20">
            <p className="text-[#F5F5F5]/30 text-sm">محصولی یافت نشد.</p>
          </div>
        )}
      </main>

      <ProductDetailModal
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        product={selectedProduct}
        onProceedToCheckout={handleProceedToCheckout}
      />

      {checkoutProduct && selectedVariant && (
        <CheckoutModal
          isOpen={isCheckoutOpen}
          setIsOpen={setIsCheckoutOpen}
          product={checkoutProduct}
          variant={selectedVariant}
          walletBalance={walletBalance}
          onSuccess={() => getWalletBalance().then((d) => setWalletBalance(d.balance)).catch(() => {})}
        />
      )}
    </div>
  );
}

export default function ProductsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#E63946]/30 border-t-[#E63946] rounded-full animate-spin" />
      </div>
    }>
      <ProductsContent />
    </Suspense>
  );
}
