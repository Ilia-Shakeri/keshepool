from aiogram.fsm.state import State, StatesGroup

class ProductAdminStates(StatesGroup):
    """
    State machine for tracking the operational flow of product catalog edits.
    """
    selecting_product = State()
    selecting_action = State()
    awaiting_new_price = State()
    awaiting_new_name = State()
    awaiting_new_inventory = State()