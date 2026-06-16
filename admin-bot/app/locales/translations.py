UI_TEXT = {
    "en": {
        "users_title": "👥 User Management",
        "inventory_title": "📦 Inventory Management",
        "tickets_title": "🎫 Support Tickets",
        "report_generated": "📊 Report successfully generated and dispatched.",
        "unauthorized": "⛔ Unauthorized action.",
        "back": "🔙 Back",
        "toggle_lang": "🇮🇷 تغییر به فارسی",
        "main_menu": "🛡 **Keshepool admin pannel**\nSystem online. Select an administrative module."
    },
    "fa": {
        "users_title": "👥 مدیریت کاربران",
        "inventory_title": "📦 مدیریت موجودی",
        "tickets_title": "🎫 تیکت‌های پشتیبانی",
        "report_generated": "📊 گزارش با موفقیت تولید و به گروه عملیات ارسال شد.",
        "unauthorized": "⛔ دسترسی غیرمجاز.",
        "back": "🔙 بازگشت",
        "toggle_lang": "🇬🇧 Switch to English",
        "main_menu": "🛡 **Keshepool admin pannel**\nسیستم آنلاین است. یک ماژول را انتخاب کنید."
    }
}

def get_text(lang: str, key: str) -> str:
    return UI_TEXT.get(lang, UI_TEXT["fa"]).get(key, key)