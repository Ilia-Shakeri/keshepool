import assert from "node:assert/strict";
import test from "node:test";
import {
  countActiveProductFilters,
  DEFAULT_PRODUCT_FILTERS,
  filterAndSortProducts,
  normalizeDigits,
  validateProductCategory,
  validateProductSort,
  type FilterableProduct,
} from "./product-filters.ts";

const products: FilterableProduct[] = [
  {
    title: "سپید",
    brand: "سپید",
    category: "music",
    variants: [{ id: "1", duration: "یک ماه", priceLabel: "200", rawPrice: 200, stockCount: 0 }],
  },
  {
    title: "آبان",
    brand: "آبان",
    category: "music",
    variants: [{ id: "2", duration: "سه ماه", priceLabel: "100", rawPrice: 100, stockCount: 2 }],
  },
  {
    title: "بهار",
    brand: "بهار",
    category: "video",
    variants: [{ id: "3", duration: "یک ماه", priceLabel: "300", rawPrice: 300, stockCount: 1 }],
  },
];

test("filter combines category, stock, query, and price", () => {
  const result = filterAndSortProducts(products, {
    category: "music",
    query: "آبان",
    availability: "in-stock",
    sort: "newest",
    minPrice: "۵۰",
    maxPrice: "۱۵۰",
  });
  assert.deepEqual(result.map((product) => product.brand), ["آبان"]);
});

test("sort and zero-result behavior stay deterministic", () => {
  const sorted = filterAndSortProducts(products, {
    ...DEFAULT_PRODUCT_FILTERS,
    category: "all",
    query: "",
    sort: "price-desc",
  });
  assert.deepEqual(sorted.map((product) => product.brand), ["بهار", "سپید", "آبان"]);

  const empty = filterAndSortProducts(products, {
    ...DEFAULT_PRODUCT_FILTERS,
    category: "all",
    query: "پیدا نمی‌شود",
  });
  assert.equal(empty.length, 0);
});

test("URL values and reset defaults are validated", () => {
  assert.equal(validateProductCategory("music"), "music");
  assert.equal(validateProductCategory("bad-value"), "all");
  assert.equal(validateProductSort("alphabetical"), "alphabetical");
  assert.equal(validateProductSort("bad-value"), "newest");
  assert.equal(normalizeDigits("۱۲۳٬۴۵۶"), "123456");
  assert.equal(countActiveProductFilters(DEFAULT_PRODUCT_FILTERS), 0);
});
