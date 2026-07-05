# Admin Product Manual

## Shared Catalog Source

The admin bot and mini-app use the same backend database. The admin bot writes to `products`, `product_variants`, and `inventory_items`. The mini-app reads active products from `GET /api/products`, which uses the same SQLAlchemy models and database session.

Admin product changes clear the catalog cache key `cache:products:all`, so active product changes are visible to the mini-app without manual syncing.

## Product Tables

- `products`: product identity, title, brand, category, icon, image URL, features, active flag.
- `product_variants`: duration and price options for each product.
- `inventory_items`: sellable credentials/configs attached to a product variant.

## Bot Product Menu

Open `مدیریت محصولات`. The bot shows exactly three actions:

- `افزودن تکی محصول`: send one product as JSON text.
- `افزودن گروهی محصول`: upload a `.json`, `.csv`, or `.txt` file.
- `محصولات`: view existing products by brand and edit title, subtitle, price, features, stock, logo, or active status.

## Add One Product

Choose `افزودن تکی محصول`, then paste one JSON object:

```json
{
  "id": "music_premium_individual",
  "title": "Music Premium Individual",
  "brand": "Music Premium Individual",
  "subtitle": "Single-user premium music plan",
  "category": "music",
  "features": ["Instant delivery", "Support included"],
  "variants": [
    {
      "id": "music_premium_individual_1m",
      "duration": "1 month",
      "rawPrice": 250000,
      "credentials": ["music-user-001:music-pass-001"]
    }
  ]
}
```

Required product fields: `id`, `title`, `brand`, `category`, `variants`.

Required variant fields: `id`, `duration`, `rawPrice`.

Optional fields: `subtitle`, `icon`, `assetUrl`, `gradient`, `features`, `priceLabel`, `credentials`.

## Add Products in Bulk

Choose `افزودن گروهی محصول`, then upload one of these formats.

JSON:

```json
{
  "products": [
    {
      "id": "secure_vpn_personal",
      "title": "Secure VPN Personal",
      "brand": "Secure VPN Individual",
      "category": "vpn",
      "variants": [
        {
          "id": "secure_vpn_personal_1m",
          "duration": "1 month",
          "rawPrice": 180000,
          "credentials": ["vless://example-personal-config"]
        }
      ]
    }
  ]
}
```

TXT or CSV:

```text
product_id|title|brand|subtitle|category|variant_id|duration|raw_price|credential1;credential2
```

Example:

```text
secure_vpn_personal|Secure VPN Personal|Secure VPN Individual|Private VPN config|vpn|secure_vpn_personal_1m|1 month|180000|vless://config-1;vless://config-2
```

## Mini-App Sync Check

After saving through the bot, open the mini-app products page. The mini-app should show only active products that have at least one active variant. Stock counts come from available inventory rows.
