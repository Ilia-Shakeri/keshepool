export type ProductCategory =
  | 'vpn'
  | 'music'
  | 'video'
  | 'ai'
  | 'social'
  | 'gaming'
  | 'tools'
  | 'edu'
  | 'finance';

export interface ProductVariant {
  id: string;
  duration: string;
  priceLabel: string;
  rawPrice: number;
}

export interface Product {
  id: string;
  title: string;
  brand: string;
  subtitle: string;
  variants: ProductVariant[];
  icon: string;
  gradient: string;
  category: ProductCategory;
}

export const PRODUCTS: Product[] = [
  {
    id: "vpn_config",
    title: "کانفیگ VPN",
    brand: "VPN Config",
    subtitle: "تحریم‌شکن پرسرعت و پایدار",
    icon: "Shield",
    gradient: "from-blue-700 to-slate-900",
    category: "vpn",
    variants: [
      {
        id: "vpn_1m",
        duration: "۱ ماهه",
        priceLabel: "250,000",
        rawPrice: 250000
      }
    ]
  },
  {
    id: "telegram_premium",
    title: "تلگرام پرمیوم",
    brand: "Telegram Premium",
    subtitle: "اکانت پرمیوم تلگرام",
    icon: "MessageCircle",
    gradient: "from-sky-600 to-blue-900",
    category: "social",
    variants: [
      {
        id: "telegram_1m",
        duration: "۱ ماهه",
        priceLabel: "390,000",
        rawPrice: 390000
      }
    ]
  },
  {
    id: "spotify",
    title: "اسپاتیفای",
    brand: "Spotify",
    subtitle: "اکانت پرمیوم موسیقی",
    icon: "Music",
    gradient: "from-emerald-600 to-black",
    category: "music",
    variants: [
      {
        id: "spotify_1m",
        duration: "۱ ماهه",
        priceLabel: "290,000",
        rawPrice: 290000
      }
    ]
  }
];