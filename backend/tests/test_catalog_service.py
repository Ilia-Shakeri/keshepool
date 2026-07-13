import asyncio
from types import SimpleNamespace

import pytest

from app.bot.handlers.products_admin import (
    _button_label,
    _callback_value_map,
    _group_product_import_rows,
)
from app.services import catalog_service


def test_feature_parsing_accepts_only_nonempty_json_lists():
    assert catalog_service.parse_product_features('["Fast", "", 3]') == ["Fast", "3"]
    assert catalog_service.parse_product_features('{"bad": true}') is None
    assert catalog_service.parse_product_features("not-json") is None
    assert catalog_service.parse_product_features(None) is None


@pytest.mark.parametrize(
    ("values", "reason"),
    [
        ({"active": False, "active_variant_count": 1}, "inactive_product"),
        ({"title": "", "active_variant_count": 1}, "invalid_product_data"),
        ({"category": "bad", "active_variant_count": 1}, "invalid_category"),
        ({"active_variant_count": 0}, "no_active_variant"),
        ({"active_variant_count": 1}, "visible"),
    ],
)
def test_catalog_visibility_rules(values, reason):
    defaults = {
        "active": True,
        "title": "Product",
        "brand": "Brand",
        "category": "tools",
        "active_variant_count": 1,
    }
    defaults.update(values)
    assert catalog_service.catalog_visibility_reason(**defaults) == reason


def test_product_mapping_rejects_duplicate_variant_ids():
    payload = {
        "id": "product-one",
        "title": "Product",
        "brand": "Brand",
        "category": "tools",
        "variants": [
            {"id": "same", "duration": "1 month", "rawPrice": 10},
            {"id": "same", "duration": "3 months", "rawPrice": 20},
        ],
    }
    with pytest.raises(catalog_service.CatalogMutationError, match="more than once"):
        catalog_service.product_mutation_from_mapping(payload)


def test_flat_import_groups_variants_without_disabling_omitted_rows():
    rows = [
        {
            "product_id": "product-one",
            "title": "Product",
            "brand": "Brand",
            "subtitle": "",
            "category": "tools",
            "variant_id": "variant-one",
            "duration": "1 month",
            "raw_price": 100,
            "credentials": ["first"],
        },
        {
            "product_id": "product-one",
            "title": "Product",
            "brand": "Brand",
            "subtitle": "",
            "category": "tools",
            "variant_id": "variant-one",
            "duration": "1 month",
            "raw_price": 100,
            "credentials": ["second"],
        },
    ]
    grouped = _group_product_import_rows(rows)
    assert len(grouped) == 1
    assert grouped[0]["variants"][0]["credentials"] == ["first", "second"]


def test_long_catalog_ids_use_short_callback_tokens_and_bounded_button_text():
    product_id = "product_" + "x" * 112
    variant_id = "variant_" + "y" * 112
    callback_map = _callback_value_map([product_id, variant_id])

    assert set(callback_map.values()) == {product_id, variant_id}
    assert all(len(f"edit_prod_{token}".encode("utf-8")) <= 64 for token in callback_map)
    assert all(len(f"pick_variant_{token}".encode("utf-8")) <= 64 for token in callback_map)
    assert len(_button_label("عنوان " * 30)) <= 60


def test_variant_cannot_move_between_products():
    class ScalarRows:
        def all(self):
            return [SimpleNamespace(id="variant-one", product_id="other-product")]

    class Result:
        def scalars(self):
            return ScalarRows()

    class Session:
        async def execute(self, statement):
            return Result()

    payload = {
        "id": "new-product",
        "title": "Product",
        "brand": "Brand",
        "category": "tools",
        "variants": [
            {"id": "variant-one", "duration": "1 month", "rawPrice": 100}
        ],
    }
    with pytest.raises(catalog_service.VariantOwnershipError, match="other-product"):
        asyncio.run(
            catalog_service.upsert_product(
                Session(),
                payload,
                replace_variants=True,
                commit=False,
            )
        )


def test_cache_outage_after_commit_does_not_turn_save_into_failure(monkeypatch):
    class Session:
        committed = False
        rolled_back = False

        async def commit(self):
            self.committed = True

        async def rollback(self):
            self.rolled_back = True

    async def failed_invalidation():
        return False

    monkeypatch.setattr(catalog_service, "invalidate_catalog_cache", failed_invalidation)
    session = Session()
    result = asyncio.run(catalog_service.commit_catalog_change(session))
    assert result is False
    assert session.committed is True
    assert session.rolled_back is False
