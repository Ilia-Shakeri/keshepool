import type { UserOrder } from "./types";


export function appendUniqueOrders(current: UserOrder[], incoming: UserOrder[]): UserOrder[] {
  const knownIds = new Set(current.map((order) => order.id));
  const merged = [...current];
  for (const order of incoming) {
    if (knownIds.has(order.id)) continue;
    knownIds.add(order.id);
    merged.push(order);
  }
  return merged;
}
