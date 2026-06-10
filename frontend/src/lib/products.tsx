import { 
  Music, MonitorPlay, Smartphone, Bot, Sparkles, Send, Gamepad2, Shield
} from "lucide-react";
import React from "react";

// Define strict types for categories
export type ProductCategory = 'music' | 'video' | 'ai' | 'tools' | 'gaming' | 'vpn';

// Define variant structure for different subscription durations
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
  icon: React.ReactNode;
  gradient: string;
  shadow: string;
  category: ProductCategory;
}

// Exporting all premium products including missing categories to prevent empty fallback states
export const PRODUCTS: Product[] = [
  {
    id: "spotify",
    title: "اسپاتیفای پرمیوم", 
    brand: "اسپاتیفای",
    subtitle: "بدون قطعی • ریجن ترکیه",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۶۰,۰۰۰", rawPrice: 160000 },
      { id: "3m", duration: "۳ ماهه", priceLabel: "۴۵۰,۰۰۰", rawPrice: 450000 },
      { id: "1y", duration: "۱ ساله", priceLabel: "۱,۶۰۰,۰۰۰", rawPrice: 1600000 },
    ],
    icon: <Music className="w-5 h-5 text-white" />,
    gradient: "from-green-400 to-green-600",
    shadow: "shadow-green-500/30",
    category: "music"
  },
  {
    id: "netflix",
    title: "نتفلیکس پرمیوم", 
    brand: "نتفلیکس",
    subtitle: "کیفیت 4K • پروفایل اختصاصی",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۲۵۰,۰۰۰", rawPrice: 250000 },
      { id: "3m", duration: "۳ ماهه", priceLabel: "۷۰۰,۰۰۰", rawPrice: 700000 },
    ],
    icon: <MonitorPlay className="w-5 h-5 text-white" />,
    gradient: "from-red-500 to-red-700",
    shadow: "shadow-red-500/30",
    category: "video"
  },
  {
    id: "apple",
    title: "اپل موزیک", 
    brand: "اپل",
    subtitle: "ریجن آمریکا • فامیلی",
    variants: [
      { id: "3m", duration: "۳ ماهه", priceLabel: "۱۸۰,۰۰۰", rawPrice: 180000 },
      { id: "6m", duration: "۶ ماهه", priceLabel: "۳۴۰,۰۰۰", rawPrice: 340000 },
    ],
    icon: <Smartphone className="w-5 h-5 text-white" />,
    gradient: "from-slate-400 to-slate-600",
    shadow: "shadow-slate-500/30",
    category: "music"
  },
  {
    id: "chatgpt",
    title: "چت جی‌پی‌تی پلاس", 
    brand: "OpenAI",
    subtitle: "دسترسی به GPT-4",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱,۲۰۰,۰۰۰", rawPrice: 1200000 },
    ],
    icon: <Bot className="w-5 h-5 text-white" />,
    gradient: "from-teal-400 to-teal-600",
    shadow: "shadow-teal-500/30",
    category: "ai"
  },
  {
    id: "gemini",
    title: "جمینای ادونسد", 
    brand: "Google",
    subtitle: "هوش مصنوعی پیشرفته گوگل",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱,۱۰۰,۰۰۰", rawPrice: 1100000 },
    ],
    icon: <Sparkles className="w-5 h-5 text-white" />,
    gradient: "from-blue-400 to-indigo-600",
    shadow: "shadow-blue-500/30",
    category: "ai"
  },
  {
    id: "telegram",
    title: "تلگرام پرمیوم", 
    brand: "Telegram",
    subtitle: "بدون قطعی • فعالسازی آنی",
    variants: [
      { id: "3m", duration: "۳ ماهه", priceLabel: "۸۵۰,۰۰۰", rawPrice: 850000 },
      { id: "6m", duration: "۶ ماهه", priceLabel: "۱,۶۰۰,۰۰۰", rawPrice: 1600000 },
      { id: "1y", duration: "۱ ساله", priceLabel: "۲,۹۰۰,۰۰۰", rawPrice: 2900000 },
    ],
    icon: <Send className="w-5 h-5 text-white" />,
    gradient: "from-sky-400 to-blue-500",
    shadow: "shadow-sky-500/30",
    category: "tools"
  },
  {
    id: "xbox",
    title: "ایکس باکس گیم پس", 
    brand: "Xbox",
    subtitle: "گیم پس آلتیمیت ظرفیتی",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۳۲۰,۰۰۰", rawPrice: 320000 },
      { id: "3m", duration: "۳ ماهه", priceLabel: "۹۰۰,۰۰۰", rawPrice: 900000 }
    ],
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-green-600 to-emerald-700",
    shadow: "shadow-green-600/30",
    category: "gaming"
  },
  {
    id: "psplus",
    title: "پلی استیشن پلاس", 
    brand: "PlayStation",
    subtitle: "ظرفیت اختصاصی اکانت ترکیه",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۴۵۰,۰۰۰", rawPrice: 450000 },
      { id: "1y", duration: "۱ ساله", priceLabel: "۳,۸۰۰,۰۰۰", rawPrice: 3800000 }
    ],
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-blue-600 to-indigo-700",
    shadow: "shadow-blue-600/30",
    category: "gaming"
  },
  {
    id: "nordvpn",
    title: "نورد وی‌پی‌ان", 
    brand: "NordVPN",
    subtitle: "اکانت اشتراکی مچ شده با رترکت",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۴۰,۰۰۰", rawPrice: 140000 },
      { id: "6m", duration: "۶ ماهه", priceLabel: "۶۸۰,۰۰۰", rawPrice: 680000 }
    ],
    icon: <Shield className="w-5 h-5 text-white" />,
    gradient: "from-cyan-500 to-blue-600",
    shadow: "shadow-cyan-500/30",
    category: "vpn"
  },
  {
    id: "expressvpn",
    title: "اکسپرس وی‌پی‌ان", 
    brand: "ExpressVPN",
    subtitle: "اکانت اختصاصی پرمیوم ثابت",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۹۰,۰۰۰", rawPrice: 190000 }
    ],
    icon: <Shield className="w-5 h-5 text-white" />,
    gradient: "from-red-500 to-orange-600",
    shadow: "shadow-red-500/30",
    category: "vpn"
  }
];