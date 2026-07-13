import type { UserOrder } from "@/lib/api";

export type OrderStatus = UserOrder["status"];
export type OrderStatusFilter = "all" | OrderStatus;

const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  active: "فعال",
  expired: "منقضی",
  cancelled: "لغوشده",
  refunded: "بازپرداخت‌شده",
};

export function getOrderStatusLabel(status: OrderStatus): string {
  return ORDER_STATUS_LABELS[status];
}

export function filterOrdersByStatus(orders: UserOrder[], status: OrderStatusFilter): UserOrder[] {
  return status === "all" ? orders : orders.filter((order) => order.status === status);
}
