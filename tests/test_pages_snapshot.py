from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

import cd_monitor.pages_snapshot as pages_snapshot
from cd_monitor.pages_snapshot import (
    ALLOWED_IMAGE_HOSTS,
    DownloadedImage,
    SnapshotExportError,
    export_pages_snapshot,
)


def png_bytes(colour: str) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (160, 160), colour).save(output, format="PNG")
    return output.getvalue()


def verified_board() -> dict[str, object]:
    canonical_key = "catalog:nzs955|edition:initial_limited|condition:sealed"
    return {
        "schema_version": 2,
        "generated_at": "2026-09-09T00:20:00+08:00",
        "display_exchange_rate_cny_per_jpy": 0.0455,
        "strategy": {
            "policy_version": "wameiji-xianyu-net-v2",
            "trade_direction": "wameiji_jpy_to_xianyu_cny",
            "minimum_net_margin": 0.0,
            "margin_denominator": "xianyu_sale_price_cny",
        },
        "summary": {
            "evaluated_count": 3,
            "eligible_count": 1,
            "below_margin_count": 1,
            "cost_pending_count": 1,
            "waiting_wameiji_count": 0,
            "waiting_xianyu_count": 0,
        },
        "eligible": [
            {
                "comparison_id": 4,
                "canonical_product_key": canonical_key,
                "debug_cookie": "must-not-publish",
                "xianyu": {
                    "source": "xianyu",
                    "canonical_product_key": canonical_key,
                    "title": "Kiss Plan 初回限定盘B",
                    "price": 121,
                    "currency": "CNY",
                    "url": "https://www.goofish.com/item?id=1",
                    "image_url": "https://img.alicdn.com/example.png",
                    "evidence_level": "search_card",
                    "captured_at": "2026-09-08T23:28:24+08:00",
                    "condition_group": "sealed",
                    "session_cookie": "must-not-publish",
                },
                "wameiji": {
                    "source": "wameiji",
                    "canonical_product_key": canonical_key,
                    "title": "Kiss Plan 初回限定盤B",
                    "price": 2250,
                    "currency": "JPY",
                    "url": "https://meruki.cn/mall/paypay/detail/z1",
                    "image_url": "https://auctions.c.yimg.jp/example.png",
                    "evidence_level": "detail_verified",
                    "captured_at": "2026-09-08T23:28:19+08:00",
                    "condition_group": "sealed",
                },
                "calculation": {
                    "status": "eligible",
                    "sale_price_cny": 121,
                    "landed_cost_cny": 70,
                    "expected_profit_cny": 49.06,
                    "net_margin": 0.40545454545454546,
                    "created_at": "2026-09-09T00:21:00+08:00",
                    "cost_breakdown": {
                        "policy_version": "wameiji-xianyu-net-v2",
                        "minimum_net_margin": 0.0,
                        "missing_fields": [],
                        "xianyu_sale_cny": 121,
                        "xianyu_seller_fee_cny": 1.936,
                        "wameiji_exchange_rate_cny_per_jpy": 0.0455,
                        "wameiji_item_jpy": 850,
                        "wameiji_item_cny": 38.675,
                        "wameiji_domestic_shipping_jpy": 0,
                        "wameiji_domestic_shipping_cny": 0,
                        "wameiji_proxy_fee_jpy": 200,
                        "wameiji_proxy_fee_cny": 9.1,
                        "wameiji_purchase_cny": 47.775,
                        "international_shipping_cny": 15,
                        "china_postage_cny": 5,
                        "packaging_cny": 2,
                        "after_sale_reserve_cny": 0,
                        "risk_reserve_cny": 0,
                        "tax_cny": 0,
                        "landed_cost_cny": 69.775,
                        "net_profit_cny": 49.289,
                        "net_margin": 0.40734710743801655,
                    },
                },
            }
        ],
        "below_margin": [],
        "cost_pending": [],
        "waiting_wameiji": [],
        "waiting_xianyu": [],
        "collector": {"state": "paused"},
    }


def test_reference_audit_export_keeps_the_full_coverage_separate_from_profit_cards(
    tmp_path: Path,
) -> None:
    """Pages must expose the audit queue instead of implying four profit cards are all work."""
    db_path = tmp_path / "dual-market.db"
    with __import__("sqlite3").connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE reference_products (
              id INTEGER PRIMARY KEY,
              stable_key TEXT NOT NULL
            );
            CREATE TABLE reference_market_observations (
              id INTEGER PRIMARY KEY,
              reference_product_id INTEGER NOT NULL,
              market TEXT NOT NULL,
              observation_state TEXT NOT NULL,
              observed_at TEXT,
              observed_title TEXT,
              version_evidence TEXT,
              catalog_no TEXT,
              barcode TEXT,
              price REAL,
              currency TEXT,
              source_url TEXT,
              note TEXT
            );
            INSERT INTO reference_products (id, stable_key) VALUES
              (1, 'reference:one'), (2, 'reference:two'), (3, 'reference:three'),
              (4, 'reference:four');
            INSERT INTO reference_market_observations
              (id, reference_product_id, market, observation_state, observed_at, observed_title,
               version_evidence, catalog_no, barcode, price, currency, source_url, note)
            VALUES
              (1, 1, 'wameiji', 'found', '2026-09-14T01:00:00Z', 'Japan first press',
               'CD+BD sealed', 'VVCL-1', '111', 2000, 'JPY', 'https://jp.mercari.com/item/one', 'private note'),
              (2, 1, 'xianyu', 'found', '2026-09-14T01:01:00Z', 'Domestic first press',
               'CD+BD sealed', 'VVCL-1', '111', 220, 'CNY', 'https://www.goofish.com/item?id=one', 'private note'),
              (3, 2, 'wameiji', 'found', '2026-09-14T01:02:00Z', 'Japan second',
               'CD only', NULL, NULL, 500, 'JPY', 'https://jp.mercari.com/item/two', 'private note'),
              (4, 2, 'xianyu', 'not_currently_listed', '2026-09-14T01:03:00Z', NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, 'private note'),
              (5, 3, 'wameiji', 'not_currently_listed', '2026-09-14T01:04:00Z', NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, 'private note'),
              (6, 3, 'xianyu', 'not_currently_listed', '2026-09-14T01:05:00Z', NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, 'private note'),
              (7, 4, 'wameiji', 'price_unfavorable', '2026-09-14T01:06:00Z', 'Japan expensive',
               'Exact LP', 'LP-1', '444', 4600, 'JPY', 'https://meruki.cn/mall/mercari/detail/four', 'private note'),
              (8, 4, 'xianyu', 'not_currently_listed', '2026-09-14T01:07:00Z', NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, 'private note');
            """
        )

    export = getattr(pages_snapshot, "export_reference_audit_snapshot", None)
    assert callable(export), "Pages needs an audit snapshot export, not just profit cards"
    result = export(
        db_path,
        tmp_path / "web",
        generated_at=datetime.fromisoformat("2026-09-15T10:00:00+08:00"),
    )

    payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    assert payload["summary"] == {
        "reference_product_count": 4,
        "both_found_count": 1,
        "both_observed_count": 0,
        "single_observed_count": 2,
        "wameiji_platform_found_count": 1,
        "found_any_count": 3,
        "not_currently_listed_both_count": 1,
    }
    assert payload["state_pairs"] == [
        {"wameiji": "found", "xianyu": "found", "count": 1},
        {"wameiji": "found", "xianyu": "not_currently_listed", "count": 1},
        {
            "wameiji": "not_currently_listed",
            "xianyu": "not_currently_listed",
            "count": 1,
        },
        {"wameiji": "price_unfavorable", "xianyu": "not_currently_listed", "count": 1},
    ]
    assert payload["dual_found_pairs"] == [
        {
            "reference_product_id": 1,
            "stable_key": "reference:one",
            "wameiji": {
                "title": "Japan first press",
                "version_evidence": "CD+BD sealed",
                "catalog_no": "VVCL-1",
                "barcode": "111",
                "price": 2000.0,
                "currency": "JPY",
                "source_url": "https://jp.mercari.com/item/one",
                "observed_at": "2026-09-14T01:00:00Z",
                "marketplace_host": "jp.mercari.com",
                "is_wameiji_platform": False,
            },
            "xianyu": {
                "title": "Domestic first press",
                "version_evidence": "CD+BD sealed",
                "catalog_no": "VVCL-1",
                "barcode": "111",
                "price": 220.0,
                "currency": "CNY",
                "source_url": "https://www.goofish.com/item?id=one",
                "observed_at": "2026-09-14T01:01:00Z",
                "marketplace_host": "www.goofish.com",
                "is_wameiji_platform": False,
            },
        }
    ]
    assert "private note" not in result.snapshot_path.read_text(encoding="utf-8")


def test_reference_audit_export_keeps_a_dual_observation_when_price_is_unfavorable(
    tmp_path: Path,
) -> None:
    """A real listing pair remains public evidence even when it is not profitable."""
    db_path = tmp_path / "dual-market.db"
    with __import__("sqlite3").connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE reference_products (
              id INTEGER PRIMARY KEY,
              stable_key TEXT NOT NULL
            );
            CREATE TABLE reference_market_observations (
              id INTEGER PRIMARY KEY,
              reference_product_id INTEGER NOT NULL,
              market TEXT NOT NULL,
              observation_state TEXT NOT NULL,
              observed_at TEXT,
              observed_title TEXT,
              version_evidence TEXT,
              catalog_no TEXT,
              barcode TEXT,
              price REAL,
              currency TEXT,
              source_url TEXT,
              note TEXT
            );
            INSERT INTO reference_products (id, stable_key)
              VALUES (1, 'reference:unprofitable-but-real'),
                     (2, 'reference:search-results-are-not-listings');
            INSERT INTO reference_market_observations
              (id, reference_product_id, market, observation_state, observed_at,
               observed_title, version_evidence, price, currency, source_url)
            VALUES
              (1, 1, 'wameiji', 'price_unfavorable', '2026-09-15T01:00:00Z',
               'Japan exact item', 'same edition', 4600, 'JPY',
               'https://www.meruki.cn/mall/mercari/detail/one'),
              (2, 1, 'xianyu', 'found', '2026-09-15T01:01:00Z',
               'Domestic exact item', 'same edition', 220, 'CNY',
               'https://www.goofish.com/item?id=one'),
              (3, 2, 'wameiji', 'found', '2026-09-15T01:02:00Z',
               'Search result, not a chosen Japan listing', 'unknown', 800, 'JPY',
               'https://www.meruki.cn/search?keywords=one'),
              (4, 2, 'xianyu', 'found', '2026-09-15T01:03:00Z',
               'Domestic exact item', 'same edition', 220, 'CNY',
               'https://www.goofish.com/item?id=two');
            """
        )

    result = pages_snapshot.export_reference_audit_snapshot(
        db_path,
        tmp_path / "web",
        generated_at=datetime.fromisoformat("2026-09-15T10:00:00+08:00"),
    )

    payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    assert payload["summary"]["both_observed_count"] == 1
    assert [item["stable_key"] for item in payload["dual_observed_pairs"]] == [
        "reference:unprofitable-but-real"
    ]
    assert payload["dual_observed_pairs"] == [
        {
            "reference_product_id": 1,
            "stable_key": "reference:unprofitable-but-real",
            "wameiji": {
                "title": "Japan exact item",
                "version_evidence": "same edition",
                "catalog_no": None,
                "barcode": None,
                "price": 4600.0,
                "currency": "JPY",
                "source_url": "https://www.meruki.cn/mall/mercari/detail/one",
                "observed_at": "2026-09-15T01:00:00Z",
                "marketplace_host": "www.meruki.cn",
                "is_wameiji_platform": True,
            },
            "xianyu": {
                "title": "Domestic exact item",
                "version_evidence": "same edition",
                "catalog_no": None,
                "barcode": None,
                "price": 220.0,
                "currency": "CNY",
                "source_url": "https://www.goofish.com/item?id=one",
                "observed_at": "2026-09-15T01:01:00Z",
                "marketplace_host": "www.goofish.com",
                "is_wameiji_platform": False,
            },
        }
    ]


def test_reference_audit_export_keeps_a_concrete_one_sided_listing_visible(
    tmp_path: Path,
) -> None:
    """A current listing must remain in the public queue while its other market is missing."""
    db_path = tmp_path / "dual-market.db"
    with __import__("sqlite3").connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE reference_products (
              id INTEGER PRIMARY KEY,
              stable_key TEXT NOT NULL
            );
            CREATE TABLE reference_market_observations (
              id INTEGER PRIMARY KEY,
              reference_product_id INTEGER NOT NULL,
              market TEXT NOT NULL,
              observation_state TEXT NOT NULL,
              observed_at TEXT,
              observed_title TEXT,
              version_evidence TEXT,
              catalog_no TEXT,
              barcode TEXT,
              price REAL,
              currency TEXT,
              source_url TEXT,
              note TEXT
            );
            INSERT INTO reference_products (id, stable_key)
              VALUES (1, 'reference:one-sided-but-real');
            INSERT INTO reference_market_observations
              (id, reference_product_id, market, observation_state, observed_at,
               observed_title, version_evidence, price, currency, source_url)
            VALUES
              (1, 1, 'wameiji', 'found', '2026-09-15T01:00:00Z',
               'Japan exact item', 'initial edition', 4600, 'JPY',
               'https://www.meruki.cn/mall/mercari/detail/one'),
              (2, 1, 'xianyu', 'not_currently_listed', '2026-09-15T01:01:00Z',
               'No current domestic listing', 'exact search empty', NULL, NULL,
               'https://www.goofish.com/search?q=one');
            """
        )

    result = pages_snapshot.export_reference_audit_snapshot(
        db_path,
        tmp_path / "web",
        generated_at=datetime.fromisoformat("2026-09-15T10:00:00+08:00"),
    )

    payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    assert payload["summary"]["single_observed_count"] == 1
    assert payload["single_observed_records"] == [
        {
            "reference_product_id": 1,
            "stable_key": "reference:one-sided-but-real",
            "available_market": "wameiji",
            "missing_market": "xianyu",
            "counterpart_state": "not_currently_listed",
            "observation": {
                "title": "Japan exact item",
                "version_evidence": "initial edition",
                "catalog_no": None,
                "barcode": None,
                "price": 4600.0,
                "currency": "JPY",
                "source_url": "https://www.meruki.cn/mall/mercari/detail/one",
                "observed_at": "2026-09-15T01:00:00Z",
                "marketplace_host": "www.meruki.cn",
                "is_wameiji_platform": True,
            },
        }
    ]


def test_reference_audit_export_publishes_the_user_reference_image(
    tmp_path: Path,
) -> None:
    """Observed listing cards must retain the user's original sample image."""
    db_path = tmp_path / "dual-market.db"
    source_image = tmp_path / "IMG_1730.PNG"
    source_image.write_bytes(png_bytes("gold"))
    with __import__("sqlite3").connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE reference_products (
              id INTEGER PRIMARY KEY,
              stable_key TEXT NOT NULL
            );
            CREATE TABLE reference_product_samples (
              id INTEGER PRIMARY KEY,
              product_id INTEGER NOT NULL,
              source_path TEXT NOT NULL
            );
            CREATE TABLE reference_market_observations (
              id INTEGER PRIMARY KEY,
              reference_product_id INTEGER NOT NULL,
              market TEXT NOT NULL,
              observation_state TEXT NOT NULL,
              observed_at TEXT,
              observed_title TEXT,
              version_evidence TEXT,
              catalog_no TEXT,
              barcode TEXT,
              price REAL,
              currency TEXT,
              source_url TEXT,
              note TEXT
            );
            INSERT INTO reference_products (id, stable_key)
              VALUES (1, 'reference:illustrated');
            INSERT INTO reference_market_observations
              (id, reference_product_id, market, observation_state, observed_at,
               observed_title, version_evidence, price, currency, source_url)
            VALUES
              (1, 1, 'wameiji', 'found', '2026-09-16T01:00:00Z',
               'Japanese exact listing', 'first press', 4600, 'JPY',
               'https://www.meruki.cn/mall/mercari/detail/one'),
              (2, 1, 'xianyu', 'found', '2026-09-16T01:01:00Z',
               'Domestic exact listing', 'first press', 220, 'CNY',
               'https://www.goofish.com/item?id=one');
            """
        )
        conn.execute(
            "INSERT INTO reference_product_samples (id, product_id, source_path) VALUES (1, 1, ?)",
            (str(source_image),),
        )

    result = pages_snapshot.export_reference_audit_snapshot(
        db_path,
        tmp_path / "web",
        generated_at=datetime.fromisoformat("2026-09-16T10:00:00+08:00"),
    )

    payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    image_url = payload["dual_observed_pairs"][0]["reference_image_url"]
    source_digest = hashlib.sha256(source_image.read_bytes()).hexdigest()[:16]
    assert image_url == f"assets/reference-samples/1-{source_digest}.webp"
    image_path = result.snapshot_path.parent.parent / image_url
    assert image_path.is_file()
    with Image.open(image_path) as image:
        image.verify()


def test_reference_audit_export_extracts_verified_market_image_from_note(
    tmp_path: Path,
) -> None:
    """Manual first-image URLs in notes become card image URLs without notes leaking."""
    db_path = tmp_path / "dual-market.db"
    with __import__("sqlite3").connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE reference_products (id INTEGER PRIMARY KEY, stable_key TEXT NOT NULL);
            CREATE TABLE reference_market_observations (
              id INTEGER PRIMARY KEY,
              reference_product_id INTEGER NOT NULL,
              market TEXT NOT NULL,
              observation_state TEXT NOT NULL,
              observed_at TEXT,
              observed_title TEXT,
              version_evidence TEXT,
              catalog_no TEXT,
              barcode TEXT,
              price REAL,
              currency TEXT,
              source_url TEXT,
              note TEXT
            );
            INSERT INTO reference_products (id, stable_key)
              VALUES (1, 'reference:manual-image');
            INSERT INTO reference_market_observations
              (id, reference_product_id, market, observation_state, observed_at,
               observed_title, version_evidence, price, currency, source_url, note)
            VALUES
              (1, 1, 'xianyu', 'found', '2026-09-17T01:00:00Z',
               'Domestic listing', 'first press', 220, 'CNY',
               'https://www.goofish.com/item?id=one',
               '人工 Chrome 核验；内部上下文不公开。第一张商品主图：https://img.alicdn.com/bao/uploaded/i1/123/item.jpg_Q90.jpg_.webp。');
            """
        )

    result = pages_snapshot.export_reference_audit_snapshot(
        db_path,
        tmp_path / "web",
        generated_at=datetime.fromisoformat("2026-09-17T10:00:00+08:00"),
    )
    payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    observation = payload["single_observed_records"][0]["observation"]
    assert observation["image_url"] == (
        "https://img.alicdn.com/bao/uploaded/i1/123/item.jpg_Q90.jpg_.webp"
    )
    assert "内部上下文不公开" not in result.snapshot_path.read_text(encoding="utf-8")


def test_publish_image_allowlist_covers_verified_wameiji_marketplace_cdns() -> None:
    assert {
        "auctions.c.yimg.jp",
        "thumbnail.image.rakuten.co.jp",
        "assets.mercari-shops-static.com",
        "static.312588698.com",
        "static.mercdn.net",
        "img.fril.jp",
    }.issubset(ALLOWED_IMAGE_HOSTS)
    assert "meruki.cn" not in ALLOWED_IMAGE_HOSTS


def test_export_rewrites_both_images_and_writes_hash_manifest(tmp_path: Path) -> None:
    images = {
        "https://img.alicdn.com/example.png": png_bytes("gold"),
        "https://auctions.c.yimg.jp/example.png": png_bytes("pink"),
    }

    def fetch(url: str) -> DownloadedImage:
        return DownloadedImage(body=images[url], content_type="image/png")

    result = export_pages_snapshot(
        verified_board(),
        tmp_path / "web",
        generated_at=datetime.fromisoformat("2026-09-09T00:30:00+08:00"),
        fetch_image=fetch,
    )

    snapshot_text = result.snapshot_path.read_text(encoding="utf-8")
    payload = json.loads(snapshot_text)
    card = payload["eligible"][0]
    asset_prefix = "assets/dual-market/20260909T003000+0800/"
    assert card["xianyu"]["image_url"].startswith(asset_prefix)
    assert card["wameiji"]["image_url"].startswith(asset_prefix)
    assert "img.alicdn.com" not in snapshot_text
    assert "auctions.c.yimg.jp" not in snapshot_text
    assert "must-not-publish" not in snapshot_text
    assert payload["mode"] == "verified_static_snapshot"
    assert payload["schema_version"] == 2
    assert payload["display_exchange_rate_cny_per_jpy"] == 0.0455
    assert payload["strategy"]["policy_version"] == "wameiji-xianyu-net-v2"
    assert payload["summary"] == verified_board()["summary"]
    assert payload["below_margin"] == []
    assert payload["cost_pending"] == []
    assert payload["summary"]["cost_pending_count"] == 1
    assert card["calculation"]["cost_breakdown"]["international_shipping_cny"] == 15

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["published_comparisons"] == 1
    assert len(manifest["assets"]) == 2
    for asset in manifest["assets"]:
        body = (tmp_path / "web" / asset["path"]).read_bytes()
        assert asset["sha256"] == hashlib.sha256(body).hexdigest()
        assert asset["width"] == 160
        assert asset["height"] == 160


def test_export_drops_a_card_when_either_source_image_fails(tmp_path: Path) -> None:
    board = verified_board()
    second = copy.deepcopy(board["eligible"][0])
    second["comparison_id"] = 5
    second["xianyu"]["image_url"] = "https://img.alicdn.com/second.png"
    second["wameiji"]["image_url"] = "https://auctions.c.yimg.jp/second.png"
    board["eligible"].append(second)
    board["summary"]["evaluated_count"] = 4
    board["summary"]["eligible_count"] = 2

    def fetch(url: str) -> DownloadedImage:
        if url.endswith("/second.png") and "yimg.jp" in url:
            raise SnapshotExportError("image download failed")
        return DownloadedImage(png_bytes("blue"), "image/png")

    result = export_pages_snapshot(
        board,
        tmp_path / "web",
        generated_at=datetime.fromisoformat("2026-09-09T00:30:00+08:00"),
        fetch_image=fetch,
    )

    payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    assert [item["comparison_id"] for item in payload["eligible"]] == [4]
    assert result.dropped_comparison_ids == (5,)
    assert not list(result.snapshot_path.parents[1].glob("assets/dual-market/*/5-*"))


def test_export_rejects_an_invalid_image_body(tmp_path: Path) -> None:
    def fetch(_url: str) -> DownloadedImage:
        return DownloadedImage(b"not an image" * 32, "image/png")

    with pytest.raises(SnapshotExportError, match="no publishable comparisons"):
        export_pages_snapshot(
            verified_board(),
            tmp_path / "web",
            generated_at=datetime.fromisoformat("2026-09-09T00:30:00+08:00"),
            fetch_image=fetch,
        )


def test_export_rejects_wrong_source_evidence_levels(tmp_path: Path) -> None:
    board = verified_board()
    board["eligible"][0]["xianyu"]["evidence_level"] = "detail_verified"

    with pytest.raises(SnapshotExportError, match="no publishable comparisons"):
        export_pages_snapshot(
            board,
            tmp_path / "web",
            generated_at=datetime.fromisoformat("2026-09-09T00:30:00+08:00"),
            fetch_image=lambda _url: DownloadedImage(png_bytes("green"), "image/png"),
        )


def test_all_failed_cards_preserve_the_previous_snapshot(tmp_path: Path) -> None:
    web_dir = tmp_path / "web"
    snapshot_path = web_dir / "data" / "dual-market-snapshot.json"
    manifest_path = web_dir / "data" / "dual-market-snapshot.manifest.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text('{"previous": true}', encoding="utf-8")
    manifest_path.write_text('{"previous_manifest": true}', encoding="utf-8")

    def fail(_url: str) -> DownloadedImage:
        raise SnapshotExportError("blocked")

    with pytest.raises(SnapshotExportError, match="no publishable comparisons"):
        export_pages_snapshot(
            verified_board(),
            web_dir,
            generated_at=datetime.fromisoformat("2026-09-09T00:30:00+08:00"),
            fetch_image=fail,
        )

    assert snapshot_path.read_text(encoding="utf-8") == '{"previous": true}'
    assert manifest_path.read_text(encoding="utf-8") == '{"previous_manifest": true}'


def test_zero_eligible_board_publishes_an_honest_zero_state_without_assets(
    tmp_path: Path,
) -> None:
    board = verified_board()
    board["eligible"] = []
    board["summary"]["eligible_count"] = 0

    result = export_pages_snapshot(
        board,
        tmp_path / "web",
        generated_at=datetime.fromisoformat("2026-09-09T00:30:00+08:00"),
        fetch_image=lambda _url: (_ for _ in ()).throw(
            AssertionError("zero-state attempted to download an image")
        ),
    )

    payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    assert payload["eligible"] == []
    assert payload["summary"]["evaluated_count"] == 3
    assert payload["summary"]["below_margin_count"] == 1
    assert payload["summary"]["cost_pending_count"] == 1
    assert result.asset_paths == ()


def test_export_rejects_a_card_without_positive_profit_even_when_v2_margin_is_zero(
    tmp_path: Path,
) -> None:
    board = verified_board()
    board["eligible"][0]["calculation"]["expected_profit_cny"] = 0

    with pytest.raises(SnapshotExportError, match="no publishable eligible comparisons"):
        export_pages_snapshot(
            board,
            tmp_path / "web",
            generated_at=datetime.fromisoformat("2026-09-09T00:30:00+08:00"),
            fetch_image=lambda _url: DownloadedImage(png_bytes("green"), "image/png"),
        )


def test_export_cli_accepts_a_local_board_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    board_file = tmp_path / "board.json"
    board_file.write_text(
        json.dumps(verified_board(), ensure_ascii=False),
        encoding="utf-8",
    )
    script_path = Path("scripts/export_dual_market_pages_snapshot.py")
    spec = importlib.util.spec_from_file_location("pages_snapshot_cli", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def fetch(_url: str) -> DownloadedImage:
        return DownloadedImage(png_bytes("purple"), "image/png")

    exit_code = module.main(
        [
            "--board-file",
            str(board_file),
            "--web-dir",
            str(tmp_path / "web"),
            "--generated-at",
            "2026-09-09T00:30:00+08:00",
        ],
        fetch_image=fetch,
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["published_comparisons"] == 1
    assert output["dropped_comparison_ids"] == []


def test_published_reference_audit_keeps_direct_images_and_links_for_observed_sides() -> None:
    """The public audit must not regress to screenshot placeholders or empty cards."""
    snapshot_path = Path("web/data/reference-audit-snapshot.json")
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

    observed = list(payload["dual_observed_pairs"])
    observed.extend(
        {
            "reference_product_id": record["reference_product_id"],
            record["available_market"]: record["observation"],
        }
        for record in payload["single_observed_records"]
    )

    assert payload["summary"]["reference_product_count"] == 125
    assert len(payload["dual_observed_pairs"]) == 112
    assert len(payload["single_observed_records"]) == 11
    for record in observed:
        for market in ("xianyu", "wameiji"):
            side = record.get(market)
            if side is not None:
                assert side["source_url"].startswith("https://")
                assert side["image_url"].startswith("https://")


def test_single_and_unavailable_records_keep_manual_browser_evidence_labels() -> None:
    """Every non-dual record must identify its manual browser evidence source."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    records = list(payload["single_observed_records"])
    records.extend(payload["unavailable_records"])

    assert len(records) == 13
    for record in records:
        observations = []
        if record.get("observation"):
            observations.append(record["observation"])
        observations.extend(
            side for side in (record.get("wameiji"), record.get("xianyu")) if side
        )
        assert observations
        for observation in observations:
            evidence = observation.get("version_evidence", "")
            assert any(marker in evidence for marker in ("Chrome", "浏览器", "IAB", "内置"))


def test_all_reference_audit_cards_have_a_local_reference_image() -> None:
    """Every public audit card must retain its supplied sample image asset."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    records = list(payload["dual_observed_pairs"])
    records.extend(payload["single_observed_records"])
    records.extend(payload["unavailable_records"])

    assert len(records) == payload["summary"]["reference_product_count"]
    for record in records:
        relative_path = record["reference_image_url"]
        assert relative_path.startswith("assets/reference-samples/")
        assert (Path("web/data") / relative_path).is_file()


def test_unavailable_cards_keep_both_market_links_and_reference_evidence() -> None:
    """Unavailable samples still need two navigable search/detail links, not blank sides."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    assert len(payload["unavailable_records"]) == 2
    for record in payload["unavailable_records"]:
        assert record["reference_image_url"].startswith("assets/reference-samples/")
        for market in ("xianyu", "wameiji"):
            side = record[market]
            assert side["source_url"].startswith("https://")
            assert side["version_evidence"]
        assert side["state"] in {"not_currently_listed", "blocked", "observed_related"}


def test_reference_audit_covers_each_sample_once_and_uses_wameiji_for_observed_japan_sides() -> None:
    """The published audit must be a complete 1..125 partition, not a padded subset."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    records = list(payload["dual_observed_pairs"])
    records.extend(payload["single_observed_records"])
    records.extend(payload["unavailable_records"])
    ids = [record["reference_product_id"] for record in records]

    assert len(ids) == 125
    assert sorted(ids) == list(range(1, 126))
    for record in payload["dual_observed_pairs"]:
        assert record["wameiji"]["is_wameiji_platform"] is True
