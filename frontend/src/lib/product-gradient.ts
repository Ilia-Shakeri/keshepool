const DEFAULT_PRODUCT_GRADIENT = "from-gray-600 to-slate-900";

const PRODUCT_GRADIENTS: Record<string, string> = {
  "from-gray-700 to-black": "from-gray-700 to-black",
  "from-gray-600 to-slate-900": "from-gray-600 to-slate-900",
  "from-blue-500 to-indigo-800": "from-blue-500 to-indigo-800",
  "from-pink-500 to-purple-800": "from-pink-500 to-purple-800",
  "from-red-500 to-rose-900": "from-red-500 to-rose-900",
  "from-cyan-500 to-blue-800": "from-cyan-500 to-blue-800",
  "from-green-500 to-teal-800": "from-green-500 to-teal-800",
  "from-violet-500 to-purple-900": "from-violet-500 to-purple-900",
  "from-amber-500 to-orange-800": "from-amber-500 to-orange-800",
  "from-yellow-500 to-amber-800": "from-yellow-500 to-amber-800",
  "from-emerald-500 to-green-800": "from-emerald-500 to-green-800",
};

export function resolveProductGradient(value?: string, categoryFallback?: string): string {
  if (value && PRODUCT_GRADIENTS[value]) return PRODUCT_GRADIENTS[value];
  if (categoryFallback && PRODUCT_GRADIENTS[categoryFallback]) {
    return PRODUCT_GRADIENTS[categoryFallback];
  }
  return DEFAULT_PRODUCT_GRADIENT;
}
