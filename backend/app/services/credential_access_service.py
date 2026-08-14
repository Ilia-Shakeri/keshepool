from app.models import ItemStatus, Order, OrderStatus


MASKED_CREDENTIAL_PREVIEW = "\u2022" * 8


def credential_is_revealable(order: Order) -> bool:
    item = order.inventory_item
    return bool(
        order.status == OrderStatus.ACTIVE
        and item
        and item.status == ItemStatus.ASSIGNED
        and item.assigned_to_user_id == order.user_id
        and item.credentials
    )
