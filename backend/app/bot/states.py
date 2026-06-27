from aiogram.fsm.state import State, StatesGroup


class ProductAdminStates(StatesGroup):
    # Navigation
    selecting_brand = State()
    selecting_product = State()
    selecting_action = State()
    # Text-input states for product editing
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


class AdminPanelStates(StatesGroup):
    awaiting_broadcast_message = State()
    awaiting_search_query = State()
    awaiting_notification_text = State()
