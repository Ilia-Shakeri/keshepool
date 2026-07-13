import assert from "node:assert/strict";
import test from "node:test";
import type { UserOrder } from "./api.ts";
import { filterOrdersByStatus, getOrderStatusLabel } from "./order-status.ts";

test("each order state has its own Persian label", () => {
  assert.equal(getOrderStatusLabel("active"), "فعال");
  assert.equal(getOrderStatusLabel("expired"), "منقضی");
  assert.equal(getOrderStatusLabel("cancelled"), "لغوشده");
  assert.equal(getOrderStatusLabel("refunded"), "بازپرداخت‌شده");
});

test("order status filter does not merge terminal states", () => {
  const orders = [
    { id: "1", status: "expired" },
    { id: "2", status: "cancelled" },
    { id: "3", status: "refunded" },
  ] as UserOrder[];
  assert.deepEqual(filterOrdersByStatus(orders, "cancelled").map((order) => order.id), ["2"]);
  assert.equal(filterOrdersByStatus(orders, "all").length, 3);
});
