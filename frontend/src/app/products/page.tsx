"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, RotateCcw, Search, SlidersHorizontal, X } from "lucide-react";
import ProductDetailModal from "@/features/products/components/ProductDetailModal";
import CheckoutModal from "@/features/products/components/CheckoutModal";
import ProductIcon from "@/features/products/components/ProductIcon";
import PageHeader from "@/components/PageHeader";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useTelegramBackButton } from "@/hooks/useTelegramBackButton";
import { getProducts, getWalletBalance } from "@/lib/api";
import type { Product, ProductCategory, ProductVariant } from "@/features/products/types";
import { resolveProductWalletLoad } from "@/lib/product-load";
import {
  countActiveProductFilters,
  DEFAULT_PRODUCT_FILTERS,
  filterAndSortProducts,
  normalizeDigits,
  parsePrice,
  validateProductCategory,
  validateProductSort,
  type ProductFilterState,
} from "@/lib/product-filters";
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialCategory = validateProductCategory(searchParams.get("category"));
  const initialFilters: ProductFilterState = {
    availability: searchParams.get("stock") === "in" ? "in-stock" : "all",
    sort: validateProductSort(searchParams.get("sort")),
    minPrice: normalizeDigits(searchParams.get("min") || ""),
    maxPrice: normalizeDigits(searchParams.get("max") || ""),
  };

  const [products, setProducts] = useState<Product[]>([]);
  const [activeCategory, setActiveCategory] = useState<ProductCategory | "all">(initialCategory);
  const [query, setQuery] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<ProductCardModel | null>(null);
  const [checkoutProduct, setCheckoutProduct] = useState<Product | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [walletBalance, setWalletBalance] = useState<number | null>(null);
  const [walletError, setWalletError] = useState<string | null>(null);
  const [isWalletLoading, setIsWalletLoading] = useState(true);
  const [productError, setProductError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<ProductFilterState>(initialFilters);
  const [draftFilters, setDraftFilters] = useState<ProductFilterState>(initialFilters);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  const loadPageData = useCallback(async () => {
    setIsLoading(true);
    setIsWalletLoading(true);
    setProductError(null);
    setWalletError(null);

    const [productData, balanceData] = await Promise.allSettled([getProducts(), getWalletBalance()]);
    const result = resolveProductWalletLoad(productData, balanceData);
    setProducts(result.products);
    setProductError(result.productError);
    setIsLoading(false);

    setWalletBalance(result.walletBalance);
    setWalletError(result.walletError);
    setIsWalletLoading(false);
  }, []);

  const refreshWallet = useCallback(async () => {
    setIsWalletLoading(true);
    setWalletError(null);
    try {
      const balanceData = await getWalletBalance();
      setWalletBalance(balanceData.balance);
    } catch (error) {
      setWalletBalance(null);
      setWalletError(error instanceof Error ? error.message : "موجودی کیف پول دریافت نشد.");
    } finally {
      setIsWalletLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadPageData);
  }, [loadPageData]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      const nextCategory = validateProductCategory(searchParams.get("category"));
      const nextFilters: ProductFilterState = {
        availability: searchParams.get("stock") === "in" ? "in-stock" : "all",
        sort: validateProductSort(searchParams.get("sort")),
        minPrice: normalizeDigits(searchParams.get("min") || ""),
        maxPrice: normalizeDigits(searchParams.get("max") || ""),
      };

      setActiveCategory(nextCategory);
      setFilters(nextFilters);
      setDraftFilters(nextFilters);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [searchParams]);

  useTelegramBackButton(() => setIsFilterOpen(false), isFilterOpen);

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
          subtitle: product.subtitle,
          variants,
        });
      }
    }

    return Array.from(groups.values());
  }, [products]);

  const productById = useMemo(() => new Map(products.map((product) => [product.id, product])), [products]);

  const filteredProducts = useMemo(() => {
    return filterAndSortProducts(groupedProducts, {
      ...filters,
      category: activeCategory,
      query,
    });
  }, [groupedProducts, activeCategory, filters, query]);

  const activeFilterCount = countActiveProductFilters(filters);

  const syncFilterQuery = useCallback((category: ProductCategory | "all", nextFilters: ProductFilterState) => {
    const params = new URLSearchParams(searchParams.toString());
    if (category === "all") params.delete("category");
    else params.set("category", category);
    if (nextFilters.availability === "in-stock") params.set("stock", "in");
    else params.delete("stock");
    if (nextFilters.sort === "newest") params.delete("sort");
    else params.set("sort", nextFilters.sort);
    if (nextFilters.minPrice) params.set("min", nextFilters.minPrice);
    else params.delete("min");
    if (nextFilters.maxPrice) params.set("max", nextFilters.maxPrice);
    else params.delete("max");
    const queryString = params.toString();
    router.replace(queryString ? `/products?${queryString}` : "/products", { scroll: false });
  }, [router, searchParams]);

  const selectCategory = (category: ProductCategory | "all") => {
    setActiveCategory(category);
    syncFilterQuery(category, filters);
  };

  const openFilters = () => {
    setDraftFilters(filters);
    setFilterError(null);
    setIsFilterOpen(true);
  };

  const applyFilters = () => {
    const minPrice = normalizeDigits(draftFilters.minPrice);
    const maxPrice = normalizeDigits(draftFilters.maxPrice);
    const parsedMin = parsePrice(minPrice);
    const parsedMax = parsePrice(maxPrice);
    if (parsedMin !== null && parsedMax !== null && parsedMin > parsedMax) {
      setFilterError("کمترین قیمت باید از بیشترین قیمت کمتر باشد.");
      return;
    }

    const nextFilters = { ...draftFilters, minPrice, maxPrice };
    setFilters(nextFilters);
    setDraftFilters(nextFilters);
    setFilterError(null);
    setIsFilterOpen(false);
    syncFilterQuery(activeCategory, nextFilters);
  };

  const resetFilters = () => {
    setFilters(DEFAULT_PRODUCT_FILTERS);
    setDraftFilters(DEFAULT_PRODUCT_FILTERS);
    setFilterError(null);
    syncFilterQuery(activeCategory, DEFAULT_PRODUCT_FILTERS);
  };

  const clearAllFilters = () => {
    setQuery("");
    setActiveCategory("all");
    setFilters(DEFAULT_PRODUCT_FILTERS);
    setDraftFilters(DEFAULT_PRODUCT_FILTERS);
    setFilterError(null);
    syncFilterQuery("all", DEFAULT_PRODUCT_FILTERS);
  };

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

  const refreshAfterCheckout = useCallback(async () => {
    const [productData, balanceData] = await Promise.allSettled([getProducts(), getWalletBalance()]);
    if (productData.status === "fulfilled") setProducts(productData.value);
    if (balanceData.status === "fulfilled") {
      setWalletBalance(balanceData.value.balance);
      setWalletError(null);
    } else {
      setWalletBalance(null);
      setWalletError("موجودی کیف پول به‌روزرسانی نشد. دوباره تلاش کنید.");
    }
  }, []);

  return (
    <div className="min-h-[100dvh] pb-32 font-sans text-[#F5F5F5]">
      <PageHeader title="محصولات" />
      <header className="mx-auto max-w-5xl px-5 pb-2">
        <div className="relative mb-5">
          <Search className="absolute right-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#F5F5F5]/40 pointer-events-none" />
          <input
            type="text"
            placeholder="جستجو بین سرویس‌ها..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="w-full bg-white/[0.05] border border-white/10 rounded-2xl py-3 pr-10 pl-11 text-sm text-[#F5F5F5] focus:outline-none focus:border-[#E63946]/50 focus:bg-white/[0.07] transition-all placeholder:text-[#F5F5F5]/35 backdrop-blur-sm"
          />
          <button
            type="button"
            onClick={openFilters}
            className="absolute left-2 top-1/2 flex size-11 -translate-y-1/2 items-center justify-center rounded-xl text-[#F5F5F5]/50 transition-colors hover:bg-white/[0.06] hover:text-[#F5F5F5]/80"
            aria-label={`فیلتر محصولات${activeFilterCount ? `، ${toPersianDigits(activeFilterCount)} فیلتر فعال` : ""}`}
          >
            <SlidersHorizontal className="w-4 h-4" />
            {activeFilterCount > 0 && (
              <span className="absolute left-0.5 top-0.5 flex size-4 min-h-0 min-w-0 items-center justify-center rounded-full bg-[#E63946] text-[9px] font-bold text-white">
                {toPersianDigits(activeFilterCount)}
              </span>
            )}
          </button>
        </div>

        <div className="flex gap-2 overflow-x-auto scrollbar-hide dir-rtl pb-1 -mx-5 px-5">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => selectCategory(cat.id)}
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

      <main className="mx-auto mt-4 max-w-5xl px-4">
        {isWalletLoading && !walletError && (
          <p className="mb-3 text-xs text-[#F5F5F5]/40">در حال دریافت موجودی کیف پول...</p>
        )}
        {walletError && (
          <div className="mb-4 flex items-center justify-between gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/[0.07] px-4 py-3 text-xs text-amber-200">
            <span>محصولات آماده‌اند، اما موجودی کیف پول دریافت نشد.</span>
            <button type="button" onClick={() => void refreshWallet()} className="shrink-0 rounded-xl px-3 font-bold text-amber-300">
              تلاش دوباره
            </button>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="aspect-square rounded-3xl bg-white/[0.04] border border-white/[0.08] animate-pulse"
                />
              ))
            : productError ? (
                <div className="col-span-full rounded-3xl border border-white/[0.08] bg-white/[0.04] p-8 text-center text-sm text-[#E63946]">
                  <p>{productError}</p>
                  <button type="button" onClick={() => void loadPageData()} className="mt-3 rounded-xl bg-[#E63946]/15 px-4 py-2 font-bold">
                    تلاش دوباره
                  </button>
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

                  <div className="relative flex h-full flex-col items-center justify-center gap-1.5 p-2 text-center sm:gap-3 sm:p-4">
                    <ProductIcon
                      icon={product.icon}
                      assetUrl={product.assetUrl}
                      gradient={product.gradient}
                      category={product.category}
                      sizeClassName="w-11 h-11 sm:w-16 sm:h-16"
                      iconSizeClassName="w-5 h-5 sm:w-7 sm:h-7"
                    />

                    <div className="flex w-full flex-col gap-0.5 sm:gap-2">
                      <h3 className="truncate text-sm font-black leading-tight text-[#F5F5F5] sm:text-lg">{product.brand}</h3>
                      {product.subtitle && (
                        <p className="hidden line-clamp-1 text-[10px] text-[#F5F5F5]/45 sm:block">{product.subtitle}</p>
                      )}
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
            <p className="text-sm text-[#F5F5F5]/40">
              {groupedProducts.length === 0
                ? "هنوز محصول فعالی برای نمایش وجود ندارد."
                : "هیچ محصولی با جستجو و فیلترهای فعلی پیدا نشد."}
            </p>
            {groupedProducts.length > 0 && (
              <button
                type="button"
                onClick={clearAllFilters}
                className="mt-4 rounded-xl bg-white/[0.07] px-4 py-2 text-xs font-bold text-[#F5F5F5]/80"
              >
                پاک کردن فیلترها
              </button>
            )}
          </div>
        )}
      </main>

      <ProductDetailModal
        key={selectedProduct?.id || "no-product"}
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        product={selectedProduct}
        onProceedToCheckout={handleProceedToCheckout}
      />

      {checkoutProduct && selectedVariant && (
        <CheckoutModal
          key={`${checkoutProduct.id}:${selectedVariant.id}`}
          isOpen={isCheckoutOpen}
          setIsOpen={setIsCheckoutOpen}
          product={checkoutProduct}
          variant={selectedVariant}
          walletBalance={walletBalance}
          onSuccess={() => void refreshAfterCheckout()}
        />
      )}

      <Dialog open={isFilterOpen} onOpenChange={setIsFilterOpen}>
        <DialogContent className="dialog-safe-area top-auto bottom-0 w-full max-w-none translate-y-0 gap-0 rounded-b-none rounded-t-3xl border-white/10 bg-[#111318] p-0 text-[#F5F5F5] sm:bottom-auto sm:top-1/2 sm:max-w-lg sm:-translate-y-1/2 sm:rounded-3xl">
          <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-3">
            <div>
              <DialogTitle className="text-base font-bold">فیلتر و مرتب‌سازی</DialogTitle>
              <DialogDescription className="mt-1 text-xs text-[#F5F5F5]/45">
                نتیجه‌ها با جستجو و دسته‌بندی فعلی ترکیب می‌شوند.
              </DialogDescription>
            </div>
            <button type="button" onClick={() => setIsFilterOpen(false)} className="flex size-11 items-center justify-center rounded-full bg-white/[0.06]" aria-label="بستن فیلتر">
              <X className="size-4" />
            </button>
          </div>

          <div className="max-h-[min(65dvh,34rem)] space-y-6 overflow-y-auto px-5 py-5">
            <fieldset>
              <legend className="mb-3 text-sm font-bold">موجودی</legend>
              <div className="grid grid-cols-2 gap-2">
                {([
                  ["all", "همه محصولات"],
                  ["in-stock", "فقط موجود"],
                ] as const).map(([value, label]) => (
                  <button
                    type="button"
                    key={value}
                    onClick={() => setDraftFilters((current) => ({ ...current, availability: value }))}
                    className={`flex items-center justify-center gap-2 rounded-2xl border px-3 py-3 text-xs font-bold ${
                      draftFilters.availability === value
                        ? "border-[#E63946]/70 bg-[#E63946]/10 text-white"
                        : "border-white/[0.08] bg-white/[0.04] text-[#F5F5F5]/55"
                    }`}
                    aria-pressed={draftFilters.availability === value}
                  >
                    {draftFilters.availability === value && <Check className="size-4 text-[#E63946]" />}
                    {label}
                  </button>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-3 text-sm font-bold">مرتب‌سازی</legend>
              <div className="grid grid-cols-2 gap-2">
                {([
                  ["newest", "جدیدترین"],
                  ["price-asc", "کمترین قیمت"],
                  ["price-desc", "بیشترین قیمت"],
                  ["alphabetical", "حروف الفبا"],
                ] as const).map(([value, label]) => (
                  <button
                    type="button"
                    key={value}
                    onClick={() => setDraftFilters((current) => ({ ...current, sort: value }))}
                    className={`rounded-2xl border px-3 py-3 text-xs font-bold ${
                      draftFilters.sort === value
                        ? "border-[#E63946]/70 bg-[#E63946]/10 text-white"
                        : "border-white/[0.08] bg-white/[0.04] text-[#F5F5F5]/55"
                    }`}
                    aria-pressed={draftFilters.sort === value}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-3 text-sm font-bold">بازه قیمت به تومان</legend>
              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-2 text-xs text-[#F5F5F5]/50">
                  کمترین
                  <input
                    type="text"
                    inputMode="numeric"
                    value={draftFilters.minPrice}
                    onChange={(event) => setDraftFilters((current) => ({ ...current, minPrice: event.target.value }))}
                    placeholder="بدون حد"
                    className="mt-2 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3 text-[#F5F5F5] outline-none"
                  />
                </label>
                <label className="space-y-2 text-xs text-[#F5F5F5]/50">
                  بیشترین
                  <input
                    type="text"
                    inputMode="numeric"
                    value={draftFilters.maxPrice}
                    onChange={(event) => setDraftFilters((current) => ({ ...current, maxPrice: event.target.value }))}
                    placeholder="بدون حد"
                    className="mt-2 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3 text-[#F5F5F5] outline-none"
                  />
                </label>
              </div>
            </fieldset>

            {filterError && <p className="rounded-xl bg-[#E63946]/10 p-3 text-xs text-[#E63946]">{filterError}</p>}
          </div>

          <div className="grid grid-cols-[auto_1fr] gap-3 border-t border-white/[0.07] px-5 pt-4">
            <button
              type="button"
              onClick={() => {
                resetFilters();
                setIsFilterOpen(false);
              }}
              className="flex items-center justify-center gap-2 rounded-2xl border border-white/10 px-4 text-xs font-bold text-[#F5F5F5]/65"
            >
              <RotateCcw className="size-4" /> بازنشانی
            </button>
            <button type="button" onClick={applyFilters} className="rounded-2xl bg-[#E63946] px-5 py-3 text-sm font-bold text-white">
              اعمال فیلتر
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function ProductsPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-[100dvh] items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#E63946]/30 border-t-[#E63946] rounded-full animate-spin" />
      </div>
    }>
      <ProductsContent />
    </Suspense>
  );
}
