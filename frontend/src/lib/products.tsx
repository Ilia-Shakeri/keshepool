import { 
  Music, MonitorPlay, Smartphone, Bot, Sparkles, Send, Gamepad2, Shield, 
  Wallet, MessageCircle, Twitter, Video, FileText
} from "lucide-react";
import React from "react";

// Expanded category definitions
export type ProductCategory = 'music' | 'video' | 'ai' | 'tools' | 'gaming' | 'vpn' | 'social' | 'financial';

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

export const PRODUCTS: Product[] = [
  // VPN & Configs (Hot Items)
  {
    id: "vpn_config",
    title: "کانفیگ اختصاصی V2Ray", 
    brand: "Keshepool VPN",
    subtitle: "آی‌پی ثابت • بدون قطعی",
    variants: [
      { id: "plan1", duration: "پلن استاندارد", priceLabel: "۱۵۰,۰۰۰", rawPrice: 150000 },
      { id: "plan2", duration: "پلن پرو (حجم بالا)", priceLabel: "۲۸۰,۰۰۰", rawPrice: 280000 }
    ],
    icon: <Shield className="w-5 h-5 text-white" />,
    gradient: "from-emerald-500 to-teal-700",
    shadow: "shadow-emerald-500/40",
    category: "vpn"
  },
  // Financial Services
  {
    id: "currency_exchange",
    title: "پرداخت و نقد کردن ارزی", 
    brand: "Finance",
    subtitle: "تتر • پی‌پال • مسترکارت",
    variants: [
      { id: "payment", duration: "پرداخت فاکتور ارزی", priceLabel: "تماس بگیرید", rawPrice: 0 },
      { id: "cashout", duration: "نقد کردن درآمد", priceLabel: "تماس بگیرید", rawPrice: 0 }
    ],
    icon: <Wallet className="w-5 h-5 text-white" />,
    gradient: "from-amber-400 to-orange-600",
    shadow: "shadow-amber-500/30",
    category: "financial"
  },
  // Music & Audio
  {
    id: "spotify",
    title: "اسپاتیفای پرمیوم", 
    brand: "Spotify",
    subtitle: "آمریکا • Individual",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۲۲۹,۰۰۰", rawPrice: 229000 },
      { id: "2m", duration: "۲ ماهه", priceLabel: "۴۱۸,۰۰۰", rawPrice: 418000 },
      { id: "3m", duration: "۳ ماهه", priceLabel: "۵۴۷,۰۰۰", rawPrice: 547000 },
    ],
    icon: <Music className="w-5 h-5 text-white" />,
    gradient: "from-green-400 to-green-600",
    shadow: "shadow-green-500/30",
    category: "music"
  },
  {
    id: "apple_music",
    title: "اپل موزیک", 
    brand: "Apple",
    subtitle: "آمریکا • فمیلی و سولو",
    variants: [
      { id: "1m_fam", duration: "۱ ماهه (فمیلی)", priceLabel: "۱۴۹,۰۰۰", rawPrice: 149000 },
      { id: "1m_solo", duration: "۱ ماهه (سولو)", priceLabel: "۱۷۹,۰۰۰", rawPrice: 179000 },
      { id: "3m_solo", duration: "۳ ماهه (سولو)", priceLabel: "۴۲۸,۰۰۰", rawPrice: 428000 },
    ],
    icon: <Music className="w-5 h-5 text-white" />,
    gradient: "from-red-400 to-rose-600",
    shadow: "shadow-rose-500/30",
    category: "music"
  },
  {
    id: "soundcloud",
    title: "ساندکلاد پرمیوم", 
    brand: "SoundCloud",
    subtitle: "بدون تبلیغات",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۴۸,۰۰۰", rawPrice: 148000 }
    ],
    icon: <Music className="w-5 h-5 text-white" />,
    gradient: "from-orange-400 to-orange-600",
    shadow: "shadow-orange-500/30",
    category: "music"
  },
  // Video & Streaming
  {
    id: "netflix",
    title: "نتفلیکس پرمیوم", 
    brand: "Netflix",
    subtitle: "کیفیت 4K",
    variants: [
      { id: "1m_profile", duration: "۱ ماهه تک پروفایل", priceLabel: "۲۸۳,۰۰۰", rawPrice: 283000 },
      { id: "1m_basic", duration: "۱ ماهه بیسیک", priceLabel: "۵۸۴,۰۰۰", rawPrice: 584000 },
      { id: "1m_4k", duration: "۱ ماهه 4K کامل", priceLabel: "۱,۲۱۰,۰۰۰", rawPrice: 1210000 },
    ],
    icon: <MonitorPlay className="w-5 h-5 text-white" />,
    gradient: "from-red-600 to-red-800",
    shadow: "shadow-red-600/30",
    category: "video"
  },
  {
    id: "youtube",
    title: "یوتیوب پرمیوم", 
    brand: "YouTube",
    subtitle: "شامل یوتیوب موزیک",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۲۸,۰۰۰", rawPrice: 128000 }
    ],
    icon: <Video className="w-5 h-5 text-white" />,
    gradient: "from-red-500 to-red-700",
    shadow: "shadow-red-500/30",
    category: "video"
  },
  // Social & Communication
  {
    id: "telegram_premium",
    title: "تلگرام پرمیوم", 
    brand: "Telegram",
    subtitle: "فعالسازی روی شماره شخصی",
    variants: [
      { id: "3m", duration: "۳ ماهه", priceLabel: "۱,۹۹۹,۰۰۰", rawPrice: 1999000 },
      { id: "6m", duration: "۶ ماهه", priceLabel: "۲,۵۹۹,۰۰۰", rawPrice: 2599000 },
      { id: "1y", duration: "۱ ساله", priceLabel: "۴,۹۹۹,۰۰۰", rawPrice: 4999000 },
    ],
    icon: <MessageCircle className="w-5 h-5 text-white" />,
    gradient: "from-sky-400 to-blue-600",
    shadow: "shadow-sky-500/30",
    category: "social"
  },
  {
    id: "telegram_stars",
    title: "تلگرام استارز", 
    brand: "Telegram",
    subtitle: "پرداخت درون برنامه‌ای",
    variants: [
      { id: "100", duration: "۱۰۰ استارز", priceLabel: "۳۹۹,۰۰۰", rawPrice: 399000 },
      { id: "500", duration: "۵۰۰ استارز", priceLabel: "۱,۶۹۹,۰۰۰", rawPrice: 1699000 },
    ],
    icon: <Sparkles className="w-5 h-5 text-white" />,
    gradient: "from-yellow-400 to-orange-500",
    shadow: "shadow-yellow-500/30",
    category: "social"
  },
  {
    id: "discord_nitro",
    title: "دیسکورد نیترو", 
    brand: "Discord",
    subtitle: "بوست و بیسیک",
    variants: [
      { id: "1m_basic", duration: "۱ ماهه بیسیک", priceLabel: "۹۷,۰۰۰", rawPrice: 97000 },
      { id: "1m_boost", duration: "۱ ماهه بوست", priceLabel: "۳۳۰,۰۰۰", rawPrice: 330000 },
    ],
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-indigo-400 to-purple-600",
    shadow: "shadow-indigo-500/30",
    category: "social"
  },
  {
    id: "twitter_blue",
    title: "توییتر بلو", 
    brand: "X (Twitter)",
    subtitle: "تیک آبی توییتر",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۵۹۴,۰۰۰", rawPrice: 594000 },
      { id: "1y", duration: "۱ ساله", priceLabel: "۴,۹۸۵,۰۰۰", rawPrice: 4985000 },
    ],
    icon: <Twitter className="w-5 h-5 text-white" />,
    gradient: "from-gray-700 to-black",
    shadow: "shadow-gray-600/30",
    category: "social"
  },
  // AI Tools
  {
    id: "chatgpt",
    title: "چت جی‌پی‌تی پلاس", 
    brand: "OpenAI",
    subtitle: "دسترسی به GPT-4",
    variants: [
      { id: "1m_shared", duration: "۱ ماهه اشتراکی", priceLabel: "۳۴۹,۰۰۰", rawPrice: 349000 },
      { id: "1m_personal", duration: "۱ ماهه ایمیل شخصی", priceLabel: "۲,۴۴۶,۰۰۰", rawPrice: 2446000 },
    ],
    icon: <Bot className="w-5 h-5 text-white" />,
    gradient: "from-teal-500 to-emerald-700",
    shadow: "shadow-teal-500/30",
    category: "ai"
  },
  {
    id: "gemini",
    title: "جمینای ادونسد", 
    brand: "Google",
    subtitle: "هوش مصنوعی پیشرفته گوگل",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۲۵۹,۰۰۰", rawPrice: 259000 },
      { id: "1y", duration: "۱ ساله", priceLabel: "۱,۲۹۹,۰۰۰", rawPrice: 1299000 },
    ],
    icon: <Sparkles className="w-5 h-5 text-white" />,
    gradient: "from-blue-400 to-indigo-600",
    shadow: "shadow-blue-500/30",
    category: "ai"
  },
  // Gaming
  {
    id: "xbox",
    title: "ایکس باکس گیم پس", 
    brand: "Xbox",
    subtitle: "ریجن ترکیه • ظرفیت کامل",
    variants: [
      { id: "1m_pc", duration: "۱ ماهه PC", priceLabel: "۳۲۸,۰۰۰", rawPrice: 328000 },
      { id: "1m_ult", duration: "۱ ماهه Ultimate", priceLabel: "۴۲۸,۰۰۰", rawPrice: 428000 }
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
    subtitle: "اسنشیال و اکسترا",
    variants: [
      { id: "1m_ess", duration: "۱ ماهه Essential", priceLabel: "۳۵۸,۰۰۰", rawPrice: 358000 },
      { id: "1m_ext", duration: "۱ ماهه Extra", priceLabel: "۵۳۸,۰۰۰", rawPrice: 538000 },
    ],
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-blue-600 to-indigo-800",
    shadow: "shadow-blue-600/30",
    category: "gaming"
  },
  {
    id: "vbucks",
    title: "وی‌باکس فورتنایت", 
    brand: "Epic Games",
    subtitle: "ریجن ترکیه",
    variants: [
      { id: "1000", duration: "۱,۰۰۰ وی‌باکس", priceLabel: "۲۴۲,۰۰۰", rawPrice: 242000 },
      { id: "2800", duration: "۲,۸۰۰ وی‌باکس", priceLabel: "۶۰۸,۰۰۰", rawPrice: 608000 }
    ],
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-cyan-400 to-blue-600",
    shadow: "shadow-cyan-500/30",
    category: "gaming"
  }
];