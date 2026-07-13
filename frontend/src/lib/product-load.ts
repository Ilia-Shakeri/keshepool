import type { Product } from "@/lib/products";

export interface ProductWalletLoadResult {
  products: Product[];
  productError: string | null;
  walletBalance: number | null;
  walletError: string | null;
}

function errorMessage(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

export function resolveProductWalletLoad(
  productResult: PromiseSettledResult<Product[]>,
  walletResult: PromiseSettledResult<{ balance: number }>,
): ProductWalletLoadResult {
  return {
    products: productResult.status === "fulfilled" ? productResult.value : [],
    productError:
      productResult.status === "fulfilled"
        ? null
        : errorMessage(productResult.reason, "خطا در دریافت محصولات."),
    walletBalance: walletResult.status === "fulfilled" ? walletResult.value.balance : null,
    walletError:
      walletResult.status === "fulfilled"
        ? null
        : errorMessage(walletResult.reason, "موجودی کیف پول دریافت نشد."),
  };
}
