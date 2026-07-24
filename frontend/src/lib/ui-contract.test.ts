import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

function source(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), "src", "lib", relativePath), "utf8");
}

test("products search is accessible, visible, deferred, and dialogs are lazy", () => {
  const products = source("../app/products/page.tsx");
  assert.match(products, /type="search"/);
  assert.match(products, /aria-label="جستجوی محصولات"/);
  assert.match(products, /<Search /);
  assert.match(products, /useDeferredValue/);
  assert.match(products, /dynamic\(\s*\(\) => import\("@\/features\/products\/components\/ProductDetailModal"\)/);
  assert.match(products, /dynamic\(\s*\(\) => import\("@\/features\/products\/components\/CheckoutModal"\)/);
});

test("notification panel uses an accessible dialog and explicit mark-read control", () => {
  const home = source("../app/page.tsx");
  assert.match(home, /<Dialog open=\{isNotifOpen\}/);
  assert.match(home, /<DialogTitle/);
  assert.match(home, /<DialogDescription/);
  assert.match(home, /aria-label="بستن اعلان‌ها"/);
  assert.match(home, /خواندن همه اعلان‌ها/);
  assert.match(home, /notificationLoading/);
  assert.match(home, /notificationError/);
});

test("cashout copy avoids contact promise and warns against secrets", () => {
  const finance = source("../app/finance/page.tsx");
  assert.doesNotMatch(
    finance,
    /درخواست ثبت کن — ادمین مستقیم در تلگرام باهات تماس می‌گیره\./,
  );
  assert.match(finance, /رمز عبور، کد بازیابی، کلید خصوصی، کد ورود/);
  assert.match(finance, /وضعیت درخواست از طریق اعلان‌های داخل برنامه در دسترس است/);
});
