from aiogram.fsm.state import State, StatesGroup

class ProductAdminStates(StatesGroup):
    selecting_product = State()
    selecting_action = State()
    awaiting_new_price = State()
    awaiting_new_name = State()
    awaiting_stock_text = State()
    awaiting_bulk_import_file = State()
    awaiting_logo_upload = State()