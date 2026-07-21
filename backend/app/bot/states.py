from aiogram.fsm.state import State, StatesGroup


class ProductAdminStates(StatesGroup):
    # Navigation
    selecting_brand = State()
    selecting_product = State()
    selecting_action = State()
    # Text-input states for product editing
    awaiting_single_product_json = State()
    guided_title = State()
    guided_brand = State()
    guided_category = State()
    guided_subtitle = State()
    guided_features = State()
    guided_logo = State()
    guided_variant_duration = State()
    guided_variant_price = State()
    guided_variant_active = State()
    guided_variant_stock = State()
    guided_preview = State()
    awaiting_new_price = State()
    awaiting_new_name = State()
    awaiting_new_subtitle = State()
    awaiting_new_features = State()
    # Stock management
    selecting_variant_for_stock = State()
    awaiting_stock_text = State()
    # Bulk import
    awaiting_bulk_import_file = State()
    # Logo upload
    awaiting_logo_upload = State()
    awaiting_product_removal_query = State()
    awaiting_all_products_confirmation = State()


class AdminPanelStates(StatesGroup):
    awaiting_broadcast_message = State()
    awaiting_broadcast_confirmation = State()
    awaiting_search_query = State()
    awaiting_notification_text = State()
    awaiting_cashout_private_message = State()
    awaiting_usdt_rate = State()
    awaiting_transaction_report_range = State()
