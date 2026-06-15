import { 
  Music, MonitorPlay, Bot, Sparkles, Gamepad2, Shield, 
  MessageCircle, Twitter, Video, PenTool, BookOpen, 
  Briefcase, LineChart
} from "lucide-react";
import React from "react";

export type ProductCategory = 'vpn' | 'music' | 'video' | 'ai' | 'social' | 'gaming' | 'tools' | 'edu' | 'finance';

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

// Database of all products based on the exact provided pricing list
export const PRODUCTS: Product[] = [
  // --- HOT ITEMS / HIGH PROFIT ---
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

  // --- MUSIC ---
  {
    id: "spotify",
    title: "اسپاتیفای پرمیوم", 
    brand: "Spotify",
    subtitle: "آمریکا🇺🇸 • Individual",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۲۲۹,۰۰۰", rawPrice: 229000 },
      { id: "2m", duration: "۲ ماهه", priceLabel: "۴۱۸,۰۰۰", rawPrice: 418000 },
      { id: "3m", duration: "۳ ماهه", priceLabel: "۵۴۷,۰۰۰", rawPrice: 547000 },
      { id: "4m", duration: "۴ ماهه", priceLabel: "۶۹۷,۰۰۰", rawPrice: 697000 },
      { id: "artist", duration: "اکانت آرتیست", priceLabel: "۹۸۹,۰۰۰", rawPrice: 989000 },
    ],
    icon: <Music className="w-5 h-5 text-white" />,
    gradient: "from-green-400 to-green-600",
    shadow: "shadow-green-500/30",
    category: "music"
  },
  {
    id: "apple_music",
    title: "اپل موزیک", 
    brand: "Apple Music",
    subtitle: "آمریکا🇺🇸",
    variants: [
      { id: "1m_fam", duration: "۱ ماهه فمیلی ممبر", priceLabel: "۱۴۹,۰۰۰", rawPrice: 149000 },
      { id: "1m_solo", duration: "۱ ماهه سولو", priceLabel: "۱۷۹,۰۰۰", rawPrice: 179000 },
      { id: "2m_solo", duration: "۲ ماهه سولو", priceLabel: "۲۹۷,۰۰۰", rawPrice: 297000 },
      { id: "3m_solo", duration: "۳ ماهه سولو", priceLabel: "۴۲۸,۰۰۰", rawPrice: 428000 },
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
  {
    id: "radio_javan",
    title: "رادیو جوان", 
    brand: "Radio Javan",
    subtitle: "پرمیوم",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۹۸,۰۰۰", rawPrice: 198000 },
      { id: "3m", duration: "۳ ماهه", priceLabel: "۳۹۸,۰۰۰", rawPrice: 398000 }
    ],
    icon: <Music className="w-5 h-5 text-white" />,
    gradient: "from-red-600 to-red-800",
    shadow: "shadow-red-500/30",
    category: "music"
  },
  {
    id: "tidal",
    title: "تیدال", 
    brand: "Tidal",
    subtitle: "100% Hi-fi",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۱۸,۰۰۰", rawPrice: 118000 }
    ],
    icon: <Music className="w-5 h-5 text-white" />,
    gradient: "from-zinc-800 to-black",
    shadow: "shadow-zinc-800/30",
    category: "music"
  },

  // --- VIDEO & STREAMING ---
  {
    id: "netflix",
    title: "نتفلیکس پرمیوم", 
    brand: "Netflix",
    subtitle: "کیفیت 4K",
    variants: [
      { id: "1m_profile", duration: "۱ ماهه 4K تک پروفایل", priceLabel: "۲۸۳,۰۰۰", rawPrice: 283000 },
      { id: "1m_basic", duration: "۱ ماهه بیسیک پلن کامل", priceLabel: "۵۸۴,۰۰۰", rawPrice: 584000 },
      { id: "1m_standard", duration: "۱ ماهه استاندارد پلن کامل", priceLabel: "۸۸۹,۰۰۰", rawPrice: 889000 },
      { id: "1m_4k", duration: "۱ ماهه 4K پلن کامل", priceLabel: "۱,۲۱۰,۰۰۰", rawPrice: 1210000 },
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
  {
    id: "amazon_prime",
    title: "آمازون پرایم ویدئو", 
    brand: "Amazon Prime",
    subtitle: "۵ کاربره",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۲۹۸,۰۰۰", rawPrice: 298000 }
    ],
    icon: <MonitorPlay className="w-5 h-5 text-white" />,
    gradient: "from-cyan-600 to-blue-800",
    shadow: "shadow-cyan-600/30",
    category: "video"
  },
  {
    id: "hulu",
    title: "هولو", 
    brand: "Hulu",
    subtitle: "پرمیوم",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۹۰,۰۰۰", rawPrice: 190000 }
    ],
    icon: <MonitorPlay className="w-5 h-5 text-white" />,
    gradient: "from-green-400 to-emerald-600",
    shadow: "shadow-green-500/30",
    category: "video"
  },
  {
    id: "crunchyroll",
    title: "کرانچی رول", 
    brand: "Crunchyroll",
    subtitle: "پرمیوم انیمه",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۹۵,۰۰۰", rawPrice: 195000 }
    ],
    icon: <MonitorPlay className="w-5 h-5 text-white" />,
    gradient: "from-orange-400 to-orange-600",
    shadow: "shadow-orange-500/30",
    category: "video"
  },

  // --- SOCIAL & COMMUNICATION ---
  {
    id: "telegram_premium",
    title: "تلگرام پرمیوم", 
    brand: "Telegram",
    subtitle: "پلن محتاط (بدون لاگین)",
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
    brand: "Telegram Stars",
    subtitle: "پرداخت درون برنامه‌ای",
    variants: [
      { id: "100", duration: "۱۰۰ استارز", priceLabel: "۳۹۹,۰۰۰", rawPrice: 399000 },
      { id: "200", duration: "۲۰۰ استارز", priceLabel: "۸۹۹,۰۰۰", rawPrice: 899000 },
      { id: "500", duration: "۵۰۰ استارز", priceLabel: "۱,۶۹۹,۰۰۰", rawPrice: 1699000 },
      { id: "1000", duration: "۱۰۰۰ استارز", priceLabel: "۳,۴۹۹,۰۰۰", rawPrice: 3499000 },
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
      { id: "1y_basic", duration: "۱ ساله بیسیک", priceLabel: "۸۹۷,۰۰۰", rawPrice: 897000 },
      { id: "1m_boost", duration: "۱ ماهه بوست", priceLabel: "۳۳۰,۰۰۰", rawPrice: 330000 },
      { id: "1y_boost", duration: "۱ ساله بوست", priceLabel: "۲,۹۸۰,۰۰۰", rawPrice: 2980000 },
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

  // --- AI TOOLS ---
  {
    id: "chatgpt",
    title: "چت جی‌پی‌تی پلاس", 
    brand: "OpenAI",
    subtitle: "دسترسی به GPT-4",
    variants: [
      { id: "1m_shared", duration: "۱ ماهه پلاس اشتراکی", priceLabel: "۳۴۹,۰۰۰", rawPrice: 349000 },
      { id: "1m_team", duration: "۱ ماهه تیم روی ایمیل", priceLabel: "۴۹۹,۰۰۰", rawPrice: 499000 },
      { id: "1m_create", duration: "۱ ماهه پلاس ساخت اکانت", priceLabel: "۱,۹۹۹,۰۰۰", rawPrice: 1999000 },
      { id: "1m_personal", duration: "۱ ماهه پلاس روی ایمیل", priceLabel: "۲,۴۴۶,۰۰۰", rawPrice: 2446000 },
      { id: "1m_manager", duration: "۱ ماهه تیم منیجر ۵ نفره", priceLabel: "۲,۹۹۹,۰۰۰", rawPrice: 2999000 },
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
    subtitle: "هوش مصنوعی پیشرفته",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۲۵۹,۰۰۰", rawPrice: 259000 },
      { id: "1y", duration: "۱ ساله", priceLabel: "۱,۲۹۹,۰۰۰", rawPrice: 1299000 },
    ],
    icon: <Sparkles className="w-5 h-5 text-white" />,
    gradient: "from-blue-400 to-indigo-600",
    shadow: "shadow-blue-500/30",
    category: "ai"
  },
  {
    id: "perplexity",
    title: "پرپلکسیتی", 
    brand: "Perplexity",
    subtitle: "جستجوی هوشمند",
    variants: [
      { id: "1y", duration: "۱ ساله", priceLabel: "۶۹۸,۰۰۰", rawPrice: 698000 },
    ],
    icon: <Bot className="w-5 h-5 text-white" />,
    gradient: "from-zinc-600 to-zinc-900",
    shadow: "shadow-zinc-600/30",
    category: "ai"
  },

  // --- GAMING ---
  {
    id: "xbox",
    title: "ایکس باکس گیم پس", 
    brand: "Xbox",
    subtitle: "ریجن ترکیه • ظرفیت کامل",
    variants: [
      { id: "1m_pc", duration: "۱ ماهه PC", priceLabel: "۳۲۸,۰۰۰", rawPrice: 328000 },
      { id: "1m_console", duration: "۱ ماهه Console", priceLabel: "۳۲۸,۰۰۰", rawPrice: 328000 },
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
    subtitle: "اسنشیال، اکسترا، دیلاکس",
    variants: [
      { id: "1m_ess", duration: "۱ ماهه Essential", priceLabel: "۳۵۸,۰۰۰", rawPrice: 358000 },
      { id: "1m_ext", duration: "۱ ماهه Extra", priceLabel: "۵۳۸,۰۰۰", rawPrice: 538000 },
      { id: "1m_dlx", duration: "۱ ماهه Deluxe", priceLabel: "۶۲۴,۰۰۰", rawPrice: 624000 },
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
      { id: "2800", duration: "۲,۸۰۰ وی‌باکس", priceLabel: "۶۰۸,۰۰۰", rawPrice: 608000 },
      { id: "5000", duration: "۵,۰۰۰ وی‌باکس", priceLabel: "۱,۰۲۸,۰۰۰", rawPrice: 1028000 },
      { id: "13500", duration: "۱۳,۵۰۰ وی‌باکس", priceLabel: "۲,۴۲۲,۰۰۰", rawPrice: 2422000 }
    ],
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-cyan-400 to-blue-600",
    shadow: "shadow-cyan-500/30",
    category: "gaming"
  },
  {
    id: "valorant",
    title: "ولورانت پوینت", 
    brand: "Riot Games",
    subtitle: "ریجن ترکیه",
    variants: [
      { id: "150", duration: "۱۵۰ پوینت", priceLabel: "۶۸,۰۰۰", rawPrice: 68000 },
      { id: "600", duration: "۶۰۰ پوینت", priceLabel: "۲۶۹,۰۰۰", rawPrice: 269000 },
      { id: "1200", duration: "۱,۲۰۰ پوینت", priceLabel: "۵۲۷,۰۰۰", rawPrice: 527000 },
      { id: "7300", duration: "۷,۳۰۰ پوینت", priceLabel: "۲,۸۷۸,۰۰۰", rawPrice: 2878000 },
    ],
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-red-500 to-red-600",
    shadow: "shadow-red-500/30",
    category: "gaming"
  },

  // --- TOOLS & EDU ---
  {
    id: "canva",
    title: "کانوا", 
    brand: "Canva",
    subtitle: "ادیت و گرافیک",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۹۸,۰۰۰", rawPrice: 198000 }
    ],
    icon: <PenTool className="w-5 h-5 text-white" />,
    gradient: "from-purple-500 to-blue-500",
    shadow: "shadow-purple-500/30",
    category: "tools"
  },
  {
    id: "microsoft365",
    title: "مایکروسافت 365", 
    brand: "Microsoft",
    subtitle: "پرمیوم یکماهه",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۵۳,۰۰۰", rawPrice: 153000 }
    ],
    icon: <Briefcase className="w-5 h-5 text-white" />,
    gradient: "from-blue-500 to-cyan-500",
    shadow: "shadow-blue-500/30",
    category: "tools"
  },
  {
    id: "skillshare",
    title: "اسکیل شیر", 
    brand: "Skillshare",
    subtitle: "آموزش و تحصیلی",
    variants: [
      { id: "1m", duration: "۱ ماهه", priceLabel: "۱۲۹,۰۰۰", rawPrice: 129000 }
    ],
    icon: <BookOpen className="w-5 h-5 text-white" />,
    gradient: "from-teal-400 to-emerald-600",
    shadow: "shadow-teal-500/30",
    category: "edu"
  },
  
  // --- FINANCE / TRADING ---
  {
    id: "tradingview",
    title: "تریدینگ ویو", 
    brand: "TradingView",
    subtitle: "اکانت پرمیوم",
    variants: [
      { id: "1m", duration: "۱ ماهه پرمیوم", priceLabel: "۳۹۹,۰۰۰", rawPrice: 399000 }
    ],
    icon: <LineChart className="w-5 h-5 text-white" />,
    gradient: "from-zinc-700 to-black",
    shadow: "shadow-zinc-700/30",
    category: "finance"
  }
];