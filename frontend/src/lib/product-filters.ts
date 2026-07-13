import type { ProductCategory, ProductVariant } from "@/lib/products";

export type ProductSort = "newest" | "price-asc" | "price-desc" | "alphabetical";
export type AvailabilityFilter = "all" | "in-stock";

export interface ProductFilterState {
  availability: AvailabilityFilter;
  sort: ProductSort;
  minPrice: string;
  maxPrice: string;
}

export interface FilterableProduct {
  title: string;
  brand: string;
  category: ProductCategory;
  variants: Array<ProductVariant & { optionLabel?: string }>;
}

export const DEFAULT_PRODUCT_FILTERS: ProductFilterState = {
  availability: "all",
  sort: "newest",
  minPrice: "",
  maxPrice: "",
};

export const PRODUCT_CATEGORIES: ReadonlySet<string> = new Set([
  "all",
  "vpn",
  "music",
  "video",
  "ai",
  "social",
  "gaming",
  "tools",
  "edu",
  "finance",
]);

export const PRODUCT_SORTS: ReadonlySet<string> = new Set([
  "newest",
  "price-asc",
  "price-desc",
  "alphabetical",
]);

export function validateProductCategory(value: string | null): ProductCategory | "all" {
  return value && PRODUCT_CATEGORIES.has(value) ? (value as ProductCategory | "all") : "all";
}

export function validateProductSort(value: string | null): ProductSort {
  return value && PRODUCT_SORTS.has(value) ? (value as ProductSort) : "newest";
}

export function normalizeDigits(value: string): string {
  return value
    .replace(/[۰-۹]/g, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)))
    .replace(/[^\d]/g, "");
}

export function parsePrice(value: string): number | null {
  const normalized = normalizeDigits(value);
  if (!normalized) return null;
  const amount = Number(normalized);
  return Number.isSafeInteger(amount) && amount >= 0 ? amount : null;
}

export function getLowestPrice(product: FilterableProduct): number {
  return product.variants.reduce(
    (lowest, variant) => Math.min(lowest, variant.rawPrice),
    Number.POSITIVE_INFINITY,
  );
}

export function productIsInStock(product: FilterableProduct): boolean {
  return product.variants.some((variant) => (variant.stockCount ?? 0) > 0);
}

export function countActiveProductFilters(filters: ProductFilterState): number {
  return (
    Number(filters.availability !== "all") +
    Number(filters.sort !== "newest") +
    Number(Boolean(filters.minPrice || filters.maxPrice))
  );
}

export function filterAndSortProducts<T extends FilterableProduct>(
  products: T[],
  options: ProductFilterState & { category: ProductCategory | "all"; query: string },
): T[] {
  const query = options.query.trim().toLocaleLowerCase("fa");
  const minPrice = parsePrice(options.minPrice);
  const maxPrice = parsePrice(options.maxPrice);

  const filtered = products.filter((product) => {
    const lowestPrice = getLowestPrice(product);
    const matchesQuery =
      !query ||
      product.title.toLocaleLowerCase("fa").includes(query) ||
      product.brand.toLocaleLowerCase("fa").includes(query) ||
      product.variants.some((variant) =>
        (variant.optionLabel ?? variant.duration).toLocaleLowerCase("fa").includes(query),
      );

    return (
      (options.category === "all" || product.category === options.category) &&
      matchesQuery &&
      (options.availability === "all" || productIsInStock(product)) &&
      (minPrice === null || lowestPrice >= minPrice) &&
      (maxPrice === null || lowestPrice <= maxPrice)
    );
  });

  return filtered
    .map((product, index) => ({ product, index }))
    .sort((left, right) => {
      if (options.sort === "price-asc") return getLowestPrice(left.product) - getLowestPrice(right.product);
      if (options.sort === "price-desc") return getLowestPrice(right.product) - getLowestPrice(left.product);
      if (options.sort === "alphabetical") {
        return left.product.brand.localeCompare(right.product.brand, "fa");
      }
      return left.index - right.index;
    })
    .map(({ product }) => product);
}
