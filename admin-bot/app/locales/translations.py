UI_TEXT = {
    "en": {
        "users_title": "👥 User Management",
        "inventory_title": "📦 Inventory Management",
        "tickets_title": "🎫 Support Tickets",
        "report_generated": "📊 Report successfully generated and dispatched.",
        "unauthorized": "⛔ Unauthorized action.",
        "back": "🔙 Back",
        "back_to_menu": "🔙 Back to Menu",
        "toggle_lang": "🇮🇷 تغییر به فارسی",
        "main_menu": "🛡 **Keshepool Admin Panel**\nSystem online. Select an administrative module.",
        "product_mgmt_title": "🛠 **Product Management**\nSelect a product to configure:",
        "config_product": "⚙️ **Configuring Product**",
        "select_action": "Select operation:",
        "edit_title": "📝 Edit Title",
        "edit_price": "💵 Update Price",
        "add_stock": "📥 Add Stock",
        "enter_new_price": "Please reply with the new price in Toman (e.g., 250000):",
        "invalid_format": "❌ Invalid format. Please enter numbers only.",
        "price_updated": "✅ Price successfully updated to {price} Toman.",
        "not_found": "❌ Failed to locate product variant in database."
    },
    "fa": {
        "users_title": "👥 مدیریت کاربران",
        "inventory_title": "📦 مدیریت موجودی",
        "tickets_title": "🎫 تیکت‌های پشتیبانی",
        "report_generated": "📊 گزارش با موفقیت تولید و به گروه عملیات ارسال شد.",
        "unauthorized": "⛔ دسترسی غیرمجاز.",
        "back": "🔙 بازگشت",
        "back_to_menu": "🔙 بازگشت به منو",
        "toggle_lang": "🇬🇧 Switch to English",
        "main_menu": "🛡 **پنل مدیریت کش‌پول**\nسیستم آنلاین است. یک ماژول را انتخاب کنید.",
        "product_mgmt_title": "🛠 **مدیریت محصولات**\nیک محصول را برای پیکربندی انتخاب کنید:",
        "config_product": "⚙️ **پیکربندی محصول**",
        "select_action": "عملیات مورد نظر را انتخاب کنید:",
        "edit_title": "📝 ویرایش عنوان",
        "edit_price": "💵 تغییر قیمت",
        "add_stock": "📥 افزودن موجودی",
        "enter_new_price": "لطفاً قیمت جدید را به تومان وارد کنید (مثال: 250000):",
        "invalid_format": "❌ فرمت نامعتبر است. لطفاً فقط عدد وارد کنید.",
        "price_updated": "✅ قیمت با موفقیت به {price} تومان بروزرسانی شد.",
        "not_found": "❌ متاسفانه محصول مورد نظر در پایگاه داده یافت نشد."
    }
}

def get_text(lang: str, key: str) -> str:
    return UI_TEXT.get(lang, UI_TEXT["fa"]).get(key, key)