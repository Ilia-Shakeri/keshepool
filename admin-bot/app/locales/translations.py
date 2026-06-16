# Centralized UI dictionary for supported languages
UI_TEXT = {
    "en": {
        "users_title": "👥 User Management",
        "inventory_title": "📦 Inventory Management",
        "tickets_title": "🎫 Support Tickets",
        "report_generated": "📊 Report successfully generated and dispatched.",
        "unauthorized": "⛔ Unauthorized action.",
        "back": "🔙 Back",
        "main_menu": "🛡 **Aegis Node Control Panel**\nSystem online. Select an administrative module."
    },
    "fa": {
        "users_title": "👥 مدیریت کاربران",
        "inventory_title": "📦 مدیریت موجودی",
        "tickets_title": "🎫 تیکت‌های پشتیبانی",
        "report_generated": "📊 گزارش با موفقیت تولید و به گروه عملیات ارسال شد.",
        "unauthorized": "⛔ دسترسی غیرمجاز.",
        "back": "🔙 بازگشت",
        "main_menu": "🛡 **Aegis Node Control Panel**\nسیستم آنلاین است. یک ماژول را انتخاب کنید."
    }
}

def get_text(lang: str, key: str) -> str:
    """
    Retrieves the localized text string. Falls back to the raw key if not found.
    """
    return UI_TEXT.get(lang, UI_TEXT["en"]).get(key, key)