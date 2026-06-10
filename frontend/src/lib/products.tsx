import { 
  Music, MonitorPlay, Smartphone, Bot, Sparkles, Send, 
  Gamepad2, Palette, Code, ShoppingCart, Film, 
  Tv, Play, BookOpen, FileText, Brush, Gamepad, Shield, LineChart 
} from "lucide-react";
import React from "react";

// Define strict types for categories
export type ProductCategory = 'music' | 'video' | 'ai' | 'tools' | 'gaming' | 'vpn';

export interface Product {
  id: string;
  title: string;
  brand: string;
  subtitle: string;
  price: string;
  rawPrice: number;
  icon: React.ReactNode;
  gradient: string;
  shadow: string;
  category: ProductCategory; // Added category field
}

// Exporting all premium products with their respective categories
export const PRODUCTS: Product[] = [
  {
    id: "spotify",
    title: "اسپاتیفای پرمیوم", 
    brand: "اسپاتیفای",
    subtitle: "اکانت ۱ ماهه • بدون قطعی • ریجن ترکیه",
    price: "۱۶۰,۰۰۰",
    rawPrice: 160000,
    icon: <Music className="w-5 h-5 text-white" />,
    gradient: "from-green-400 to-green-600",
    shadow: "shadow-green-500/30",
    category: "music"
  },
  {
    id: "netflix",
    title: "نتفلیکس پرمیوم", 
    brand: "نتفلیکس",
    subtitle: "اکانت ۱ ماهه • کیفیت 4K • پروفایل اختصاصی",
    price: "۲۵۰,۰۰۰",
    rawPrice: 250000,
    icon: <MonitorPlay className="w-5 h-5 text-white" />,
    gradient: "from-red-500 to-red-700",
    shadow: "shadow-red-500/30",
    category: "video"
  },
  {
    id: "apple",
    title: "اپل موزیک", 
    brand: "اپل",
    subtitle: "اکانت ۳ ماهه • ریجن آمریکا • فامیلی",
    price: "۱۸۰,۰۰۰",
    rawPrice: 180000,
    icon: <Smartphone className="w-5 h-5 text-white" />,
    gradient: "from-slate-400 to-slate-600",
    shadow: "shadow-slate-500/30",
    category: "music"
  },
  {
    id: "chatgpt",
    title: "چت جی‌پی‌تی پلاس", 
    brand: "OpenAI",
    subtitle: "اکانت ۱ ماهه • دسترسی به GPT-4",
    price: "۱,۲۰۰,۰۰۰",
    rawPrice: 1200000,
    icon: <Bot className="w-5 h-5 text-white" />,
    gradient: "from-teal-400 to-teal-600",
    shadow: "shadow-teal-500/30",
    category: "ai"
  },
  {
    id: "gemini",
    title: "جمینای ادونسد", 
    brand: "Google",
    subtitle: "اکانت ۱ ماهه • هوش مصنوعی پیشرفته گوگل",
    price: "۱,۱۰۰,۰۰۰",
    rawPrice: 1100000,
    icon: <Sparkles className="w-5 h-5 text-white" />,
    gradient: "from-blue-400 to-indigo-600",
    shadow: "shadow-blue-500/30",
    category: "ai"
  },
  {
    id: "telegram",
    title: "تلگرام پرمیوم", 
    brand: "Telegram",
    subtitle: "اکانت ۳ ماهه • بدون قطعی • فعالسازی آنی",
    price: "۸۵۰,۰۰۰",
    rawPrice: 850000,
    icon: <Send className="w-5 h-5 text-white" />,
    gradient: "from-sky-400 to-blue-500",
    shadow: "shadow-sky-500/30",
    category: "tools"
  },
  {
    id: "youtube",
    title: "یوتیوب پرمیوم", 
    brand: "Google",
    subtitle: "اکانت ۱ ماهه • بدون تبلیغات • موزیک",
    price: "۲۲۰,۰۰۰",
    rawPrice: 220000,
    icon: <Play className="w-5 h-5 text-white" />,
    gradient: "from-red-600 to-red-800",
    shadow: "shadow-red-600/30",
    category: "video"
  },
  {
    id: "discord",
    title: "دیسکورد نیترو", 
    brand: "Discord",
    subtitle: "اکانت ۱ ماهه • نیترو کامل با بوست",
    price: "۴۵۰,۰۰۰",
    rawPrice: 450000,
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-indigo-400 to-purple-600",
    shadow: "shadow-indigo-500/30",
    category: "gaming"
  },
  {
    id: "canva",
    title: "کانوا پرو", 
    brand: "Canva",
    subtitle: "اکانت ۱ ساله • دسترسی کامل به ابزارها",
    price: "۳۵۰,۰۰۰",
    rawPrice: 350000,
    icon: <Palette className="w-5 h-5 text-white" />,
    gradient: "from-cyan-400 to-blue-600",
    shadow: "shadow-cyan-500/30",
    category: "tools"
  },
  {
    id: "github",
    title: "گیت‌هاب کوپایلت", 
    brand: "GitHub",
    subtitle: "اکانت ۱ ماهه • دستیار هوشمند برنامه نویسی",
    price: "۵۵۰,۰۰۰",
    rawPrice: 550000,
    icon: <Code className="w-5 h-5 text-white" />,
    gradient: "from-gray-700 to-gray-900",
    shadow: "shadow-gray-700/30",
    category: "tools"
  },
  {
    id: "amazon",
    title: "آمازون پرایم ویدیو", 
    brand: "Amazon",
    subtitle: "اکانت ۱ ماهه • تماشای فیلم و سریال",
    price: "۱۵۰,۰۰۰",
    rawPrice: 150000,
    icon: <ShoppingCart className="w-5 h-5 text-white" />,
    gradient: "from-blue-300 to-blue-500",
    shadow: "shadow-blue-400/30",
    category: "video"
  },
  {
    id: "disney",
    title: "دیزنی پلاس", 
    brand: "Disney",
    subtitle: "اکانت ۱ ماهه • پروفایل اختصاصی",
    price: "۲۸۰,۰۰۰",
    rawPrice: 280000,
    icon: <Film className="w-5 h-5 text-white" />,
    gradient: "from-blue-700 to-indigo-900",
    shadow: "shadow-blue-800/30",
    category: "video"
  },
  {
    id: "hbo",
    title: "اچ‌بی‌او مکس", 
    brand: "HBO",
    subtitle: "اکانت ۱ ماهه • کیفیت 4K",
    price: "۲۶۰,۰۰۰",
    rawPrice: 260000,
    icon: <Tv className="w-5 h-5 text-white" />,
    gradient: "from-purple-700 to-purple-900",
    shadow: "shadow-purple-800/30",
    category: "video"
  },
  {
    id: "crunchyroll",
    title: "کرانچی‌رول مگا فن", 
    brand: "Crunchyroll",
    subtitle: "اکانت ۱ ماهه • مخصوص انیمه",
    price: "۱۹۰,۰۰۰",
    rawPrice: 190000,
    icon: <Play className="w-5 h-5 text-white" />,
    gradient: "from-orange-400 to-orange-600",
    shadow: "shadow-orange-500/30",
    category: "video"
  },
  {
    id: "adobe",
    title: "ادوبی کریتیو کلود", 
    brand: "Adobe",
    subtitle: "اکانت ۱ ماهه • دسترسی به تمامی نرم افزارها",
    price: "۱,۵۰۰,۰۰۰",
    rawPrice: 1500000,
    icon: <Brush className="w-5 h-5 text-white" />,
    gradient: "from-red-500 to-red-700",
    shadow: "shadow-red-600/30",
    category: "tools"
  },
  {
    id: "duolingo",
    title: "دولینگو سوپر", 
    brand: "Duolingo",
    subtitle: "اکانت ۱ ساله • یادگیری زبان بدون محدودیت",
    price: "۴۰۰,۰۰۰",
    rawPrice: 400000,
    icon: <BookOpen className="w-5 h-5 text-white" />,
    gradient: "from-green-500 to-green-700",
    shadow: "shadow-green-600/30",
    category: "tools"
  },
  {
    id: "notion",
    title: "نوشن هوش مصنوعی", 
    brand: "Notion",
    subtitle: "اکانت ۱ ماهه • مدیریت پروژه با AI",
    price: "۴۵۰,۰۰۰",
    rawPrice: 450000,
    icon: <FileText className="w-5 h-5 text-white" />,
    gradient: "from-slate-700 to-slate-900",
    shadow: "shadow-slate-800/30",
    category: "tools"
  },
  {
    id: "midjourney",
    title: "میدجورنی استاندارد", 
    brand: "Midjourney",
    subtitle: "اکانت ۱ ماهه • تولید تصویر با هوش مصنوعی",
    price: "۱,۸۰۰,۰۰۰",
    rawPrice: 1800000,
    icon: <Palette className="w-5 h-5 text-white" />,
    gradient: "from-indigo-500 to-purple-700",
    shadow: "shadow-indigo-600/30",
    category: "ai"
  },
  {
    id: "psplus",
    title: "پلی استیشن پلاس", 
    brand: "Sony",
    subtitle: "اکانت ۱ ماهه • ریجن ترکیه • اکسترا",
    price: "۶۵۰,۰۰۰",
    rawPrice: 650000,
    icon: <Gamepad className="w-5 h-5 text-white" />,
    gradient: "from-blue-600 to-blue-800",
    shadow: "shadow-blue-700/30",
    category: "gaming"
  },
  {
    id: "xbox",
    title: "ایکس باکس گیم پس", 
    brand: "Microsoft",
    subtitle: "اکانت ۱ ماهه • آلتیمیت ظرفیت کامل",
    price: "۵۰۰,۰۰۰",
    rawPrice: 500000,
    icon: <Gamepad2 className="w-5 h-5 text-white" />,
    gradient: "from-green-600 to-green-800",
    shadow: "shadow-green-700/30",
    category: "gaming"
  },
  {
    id: "nordvpn",
    title: "نورد وی‌پی‌ان", 
    brand: "NordVPN",
    subtitle: "اکانت ۱ ساله • امنیت بالا و بدون قطعی",
    price: "۳۵۰,۰۰۰",
    rawPrice: 350000,
    icon: <Shield className="w-5 h-5 text-white" />,
    gradient: "from-blue-500 to-blue-700",
    shadow: "shadow-blue-600/30",
    category: "vpn"
  },
  {
    id: "tradingview",
    title: "تریدینگ ویو پرمیوم", 
    brand: "TradingView",
    subtitle: "اکانت ۱ ماهه • تحلیل تکنیکال بدون محدودیت",
    price: "۹۰۰,۰۰۰",
    rawPrice: 900000,
    icon: <LineChart className="w-5 h-5 text-white" />,
    gradient: "from-gray-800 to-black",
    shadow: "shadow-gray-900/30",
    category: "tools"
  }
];