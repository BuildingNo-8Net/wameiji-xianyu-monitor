from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import re
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
        "tshop.r10s.jp",
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
    assert payload["summary"]["both_found_count"] == len(payload["dual_found_pairs"])
    assert len(payload["dual_observed_pairs"]) == 110
    assert len(payload["single_observed_records"]) == 13
    for record in observed:
        for market in ("xianyu", "wameiji"):
            side = record.get(market)
            if side is not None:
                assert side["source_url"].startswith("https://")
                if side.get("image_state") in {"source_no_image", "first_gallery_image_link_unverified", "reference_only", "no_verified_item_photo"}:
                    assert side.get("image_url") is None
                elif side.get("image_state") == "historical_first_gallery_image":
                    assert side.get("image_url") is None or side["image_url"].startswith("https://")
                else:
                    assert side["image_url"].startswith("https://")


def test_wameiji_mercari_photo_id_matches_the_linked_detail_item() -> None:
    """Catch cross-item image links in the public reference audit."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    records = list(payload["dual_observed_pairs"])
    records.extend(
        {
            "reference_product_id": record["reference_product_id"],
            record["available_market"]: record["observation"],
        }
        for record in payload["single_observed_records"]
    )
    records.extend(payload["unavailable_records"])

    for record in records:
        side = record.get("wameiji")
        if not side or not side.get("image_url"):
            continue
        detail_hex = re.search(r"/detail/([0-9a-fA-F]{40,})/?", side["source_url"])
        if not detail_hex:
            continue
        detail_url = bytes.fromhex(detail_hex.group(1)).decode("utf-8")
        item_id = re.search(r"/(m\d{8,})/?$", detail_url)
        photo_id = re.search(r"/photos/(m\d{8,})_\d+\.", side["image_url"])
        if item_id and photo_id:
            assert photo_id.group(1) == item_id.group(1), (
                f"sample #{record['reference_product_id']} links Mercari item "
                f"{item_id.group(1)} to photo {photo_id.group(1)}"
            )


def test_sample_17_multivariant_candidate_price_conflict_is_not_a_single_quote() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 17
    )

    assert pair["same_product_verified"] is True
    assert pair["xianyu"]["price"] is None
    assert pair["xianyu"]["price_range"] == {"min": 198, "max": 398, "currency": "CNY"}
    assert pair["xianyu"]["state"] == "observed_related"
    assert pair["xianyu"]["image_url"] == "https://img.alicdn.com/bao/uploaded/i2/O1CN01TJ2Iov1DiXdj3HUc4_!!0-fleamarket.jpg_790x10000Q90.jpg_.webp"
    assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert pair["xianyu"]["source_url"].endswith("id=628389467723&categoryId=126864811")
    assert "左边2，带原声cd，168" in pair["xianyu"]["version_evidence"]
    assert "¥198–398" in pair["xianyu"]["version_evidence"]
    assert "未选中目标变体" in pair["xianyu"]["version_evidence"]
    assert "旧859421708400" not in pair["relation_note"]
    assert "不能把168当现价" in pair["relation_note"]
    assert "SIDE 2nd" in pair["relation_note"]
    assert pair["wameiji"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/8BFxxaFrjQ4J59b88WvhUk.webp@jpg"
    assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert pair["wameiji"]["state"] == "observed_current"
    assert pair["wameiji"]["price"] == 13800
    assert pair["wameiji"]["last_observed_price"] is None


def test_sample_18_reference_is_single_volume_and_bundle_is_related_only() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 18
    )

    assert pair["same_product_verified"] is False
    assert pair["wameiji"]["price"] == 19199
    assert pair["wameiji"]["state"] == "observed_current"
    assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert pair["xianyu"]["state"] == "observed_related"
    assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert "样本 #18 是《殻ノ少女》广播剧CD第三卷单碟盒装" in pair["relation_note"]
    assert "四碟散碟合售" in pair["relation_note"]
    assert "不是样本的第三卷盒装单碟" in pair["relation_note"]
    assert "闲鱼 1063580553056 当前仍为¥900" in pair["relation_note"]


def test_sample_19_keeps_vol14_unavailable_and_adds_related_live_vol12_listing() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 19
    )

    assert pair["same_product_verified"] is False
    assert "Vol.12" in pair["xianyu"]["title"]
    assert "vol.14" in pair["wameiji"]["title"].lower()
    assert pair["xianyu"]["state"] == "observed_related"
    assert pair["xianyu"]["price"] == 69
    assert pair["xianyu"]["last_observed_price"] is None
    assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert pair["wameiji"]["state"] == "observed_related"
    assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert "Vol.11旧链接已跳转推荐列表" in pair["xianyu"]["version_evidence"]
    assert "精确搜索Vol.14实体无结果" in pair["relation_note"]
    assert "附件状态仍待核" in pair["wameiji"]["version_evidence"]
    assert "不比较利润" in pair["relation_note"]


def test_sample_20_matching_virtual_maiden_drama_cd_is_kept_as_observation() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 20
    )

    assert pair["same_product_verified"] is True
    assert pair["price_comparable"] is False
    assert pair["xianyu"]["state"] == "observed_current"
    assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert "¥400包邮" in pair["xianyu"]["version_evidence"]
    assert "191浏览" in pair["xianyu"]["version_evidence"]
    assert "立即购买" in pair["xianyu"]["version_evidence"]
    assert "主图直链" in pair["wameiji"]["version_evidence"]
    assert pair["xianyu"]["price"] == 400
    assert pair["wameiji"]["price"] == 3200
    assert "同作品/封面" in pair["relation_note"]
    assert "成色不同" in pair["relation_note"]


def test_sample_75_current_xianyu_preorder_is_not_rendered_as_unverified_history() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 75
    )

    assert datetime.fromisoformat(payload["generated_at"]) >= datetime.fromisoformat(
        pair["xianyu"]["observed_at"]
    )
    assert pair["xianyu"]["state"] == "observed_current"
    assert pair["xianyu"]["price"] is None
    assert pair["xianyu"]["price_range"] == {"min": 427, "max": 549, "currency": "CNY"}
    assert pair["xianyu"]["observed_at"] == "2026-10-02T15:32:00+08:00"
    assert "42浏览" in pair["xianyu"]["version_evidence"]
    assert "非卖家实物照" in pair["xianyu"]["version_evidence"]
    assert pair["wameiji"]["state"] == "observed_related"
    assert pair["wameiji"]["price"] == 7777
    assert pair["wameiji"]["image_url"] is None
    assert pair["price_comparable"] is False
    assert pair["same_product_verified"] is False
    assert "不算利润" in pair["relation_note"]


def test_sample_78_matches_wameiji_base_edition_but_keeps_mispress_and_image_unverified() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record for record in payload[collection]
            if record["reference_product_id"] == 78
        )
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] == 620
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "120浏览" in pair["xianyu"]["version_evidence"]
        assert "准确SKU" in pair["xianyu"]["version_evidence"]
        assert pair["wameiji"]["image_state"] == "no_verified_item_photo"
        assert pair["wameiji"]["image_url"] is None
        assert "UIJY-75383" in pair["wameiji"]["version_evidence"]
        assert "仅同专辑相关观察" in pair["relation_note"]
        assert "错版" in pair["relation_note"]
        assert "占位/破图" in pair["wameiji"]["version_evidence"]
        assert "keywords=UIJY-75383" in pair["wameiji"]["search_source_url"]
        assert pair["wameiji"]["price"] == 11000
        assert pair["wameiji"]["last_observed_price"] == 12000
        assert pair["wameiji"]["observed_at"] == "2026-10-02T14:29:00+08:00"
        assert pair["price_comparable"] is False
        assert pair["same_product_verified"] is False


def test_sample_77_records_verified_first_image_but_keeps_match_unconfirmed() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record for record in payload[collection]
            if record["reference_product_id"] == 77
        )
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price_range"] == {"min": 199, "max": 333, "currency": "CNY"}
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["image_url"].endswith("jpg_790x10000Q90.jpg_.webp")
        assert "1443浏览" in pair["xianyu"]["version_evidence"]
        assert pair["wameiji"]["image_state"] == "page_reference_image"
        assert pair["wameiji"]["image_url"].endswith("m41163446629_1.jpg")
        assert "平台占位图" in pair["wameiji"]["version_evidence"]


def test_sample_9_removes_wrong_trial_disc_and_labels_deleted_related_edition() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    assert not any(row["reference_product_id"] == 9 for row in payload["dual_observed_pairs"])
    sample = next(row for row in payload["single_observed_records"] if row["reference_product_id"] == 9)
    assert sample["available_market"] == "xianyu"
    assert sample["missing_market"] == "wameiji"
    assert sample["observation"]["source_url"] == "https://www.goofish.com/item?id=1050892358760&categoryId=126864811"
    assert sample["observation"]["price"] == 450
    assert sample["observation"]["image_state"] == "observed_first_gallery_image"
    candidate = sample["counterpart_candidate"]
    assert candidate["state"] == "search_only"
    assert candidate["price"] is None
    assert candidate["last_observed_price"] is None
    assert candidate["image_url"] is None
    assert candidate["image_state"] == "no_verified_item_photo"
    assert candidate["source_url"] == candidate["search_source_url"]
    assert "已删除" in candidate["version_evidence"]
    assert "eden* PLUS+MOSAIC" in candidate["version_evidence"]
    assert "不展示旧链接、价格或主图" in candidate["relation_note"]
    assert "当前搜索未核实到" in candidate["title"]
    assert "TRIAL DISC" not in candidate["title"]


def test_sample_13_adds_related_moon_princess_cd_without_claiming_moonbox_match() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in payload[collection] if row["reference_product_id"] == 13)
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "search_only"
        assert pair["wameiji"]["price"] is None
        assert pair["wameiji"]["image_state"] == "no_verified_item_photo"
        assert pair["wameiji"]["image_url"] is None
        assert "未找到可核验" in pair["wameiji"]["title"]
        assert "Moonlit archives" not in pair["wameiji"]["title"]


def test_sample_19_adds_live_vol12_related_listing_not_vol14_match() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in payload[collection] if row["reference_product_id"] == 19)
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert pair["xianyu"]["state"] == "observed_related"
        assert pair["xianyu"]["price"] == 69
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["image_url"].endswith("jpg_790x10000Q90.jpg_.webp")
        assert "非Vol.14" in pair["xianyu"]["title"]


def test_sample_21_kanon_ost_records_live_price_and_option_uncertainty() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 21
    )

    assert pair["same_product_verified"] is True
    assert pair["xianyu"]["price"] == 193
    assert pair["wameiji"]["price"] == 2699
    assert "24曲" in pair["relation_note"]
    assert "腰封/成色附件未核齐" in pair["relation_note"]
    assert "价格不可比，不计算利润" in pair["relation_note"]


def test_sample_97_refreshes_both_live_exact_fantome_2lp_listings_and_images() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 97
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 6200
        assert pair["wameiji"]["barcode"] == "4988031466285"
        assert pair["wameiji"]["image_state"] == "page_reference_image"
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] == 305
        assert pair["xianyu"]["barcode"] == "4988031466285"
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["source_url"].endswith("id=675935787245&categoryId=126862152")
        assert pair["xianyu"]["observed_at"] == "2026-10-02T07:12:00+08:00"
        assert pair["wameiji"]["observed_at"] == "2026-10-02T07:12:00+08:00"
        assert "2,526浏览" in pair["xianyu"]["version_evidence"]
        assert "不包邮" in pair["xianyu"]["version_evidence"]
    assert payload["generated_at"] >= "2026-09-30T07:15:00+08:00"


def test_sample_98_records_both_current_the_book_for_listings_without_claiming_profit() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 98
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 5600
        assert pair["wameiji"]["last_observed_price"] is None
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "XSCL-136" in pair["wameiji"]["version_evidence"]
        assert pair["wameiji"]["source_url"].endswith("324a54754e6376707a566653444777777276757438762f")
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] is None
        assert pair["xianyu"]["price_range"] == {
            "min": 255,
            "max": 309,
            "currency": "CNY",
        }
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "O1CN01HhBFfp24f2lsLLoS7" in pair["xianyu"]["image_url"]
        assert pair["xianyu"]["source_url"].endswith("id=1065572288193&categoryId=202061902")
        assert pair["xianyu"]["observed_at"] == "2026-10-02T14:24:00+08:00"
        assert pair["wameiji"]["observed_at"] == "2026-10-02T07:16:00+08:00"
        assert "1143浏览" in pair["xianyu"]["version_evidence"]


def test_sample_99_replaces_login_blocked_rakuma_with_current_exact_mercari_match() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 99
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 5093
        assert pair["wameiji"]["catalog_no"] == "UPJY-9204/5"
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert pair["wameiji"]["image_url"].endswith("qMhn89m8yKqLJCnGXjdh7G.jpg@jpg")
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] == 415
        assert pair["xianyu"]["catalog_no"] == "UPJY-9204"
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["observed_at"] == "2026-10-02T07:21:00+08:00"
        assert pair["wameiji"]["observed_at"] == "2026-10-02T07:21:00+08:00"
        assert "8浏览" in pair["xianyu"]["version_evidence"]


def test_sample_56_marks_wameiji_login_redirect_as_blocked_and_keeps_price_historical() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 56
    )

    assert pair["same_product_verified"] is True
    assert pair["price_comparable"] is False
    assert pair["wameiji"]["state"] == "blocked"
    assert pair["wameiji"]["price"] is None
    assert pair["wameiji"]["last_observed_price"] == 17000
    assert pair["wameiji"]["image_state"] == "page_reference_image"
    assert pair["xianyu"]["state"] == "observed_current"
    assert pair["xianyu"]["price"] == 1800
    assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert "跳转至登录页" in pair["relation_note"]
    assert pair["xianyu"]["observed_at"] == "2026-09-29T05:45:00+08:00"
    assert "4,660浏览" in pair["xianyu"]["version_evidence"]
    assert "商品首图直链直接打开后与页面主图一致" in pair["xianyu"]["version_evidence"]
    assert pair["wameiji"]["observed_at"] == "2026-09-29T05:45:00+08:00"


def test_sample_89_rechecks_both_current_listings_without_comparing_deposit_range() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 89
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 26600
        assert "26,600日元" in pair["wameiji"]["version_evidence"]
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] is None
        assert pair["xianyu"]["last_observed_price"] == 248
        assert pair["xianyu"]["price_range"] == {
            "min": 248,
            "max": 2800,
            "currency": "CNY",
        }
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "先付订金" in pair["xianyu"]["version_evidence"]


def test_sample_90_replaces_login_blocked_history_with_live_matching_item_observations() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 90
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 2500
        assert pair["wameiji"]["catalog_no"] == "ESKL-6"
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "ESKL-6" in pair["wameiji"]["source_url"] or "ESKL-6" in pair["wameiji"]["version_evidence"]
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] == 179
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "海报" in pair["relation_note"]


def test_sample_91_refreshes_both_live_listings_and_keeps_condition_mismatch_explicit() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 91
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 4700
        assert pair["wameiji"]["catalog_no"] is None
        assert pair["wameiji"]["image_url"].endswith("m56941634549_1.jpg?1789917455")
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] == 188
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "成色不同" in pair["relation_note"]


def test_sample_20_current_meruki_record_has_state_and_visible_first_image_link() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 20
        )
        source = pair["wameiji"]
        assert source["state"] == "observed_current"
        assert source["price"] == 3200
        assert source["image_state"] == "observed_first_gallery_image"
        assert source["image_url"] == (
            "https://imghk.doorzo.net/item/detail/orig/photos/"
            "m30556219350_1.jpg?1778052908"
        )
        assert pair["price_comparable"] is False


def test_sample_101_replaces_sold_meruki_link_with_same_catalog_rakuten_listing() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 101)
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 7700
        assert pair["wameiji"]["last_observed_price"] == 2400
        assert pair["wameiji"]["observed_at"] == "2026-10-02T12:51:00+08:00"
        assert pair["wameiji"]["catalog_no"] == "SEJL-86～87"
        assert pair["wameiji"]["source_url"].endswith("jeugia%2Fsejl86-54%2F")
        assert pair["wameiji"]["image_url"].endswith("eyes.jpg?fitin=600:600")
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "缺货可能取消" in pair["wameiji"]["version_evidence"]
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] == 415
        assert pair["xianyu"]["last_observed_price"] == 415
        assert pair["xianyu"]["observed_at"] == "2026-10-02T12:42:00+08:00"
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "1,413浏览" in pair["xianyu"]["version_evidence"]
        assert "SEJL-86" in pair["xianyu"]["version_evidence"]


def test_sample_102_keeps_deposit_price_and_visually_verified_cover_images_distinct() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 102)
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["price"] == 16500
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["price"] == 499
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["state"] == "observed_current"
        assert "\u8ba2\u91d1" in pair["xianyu"]["version_evidence"]
        assert "\u9700\u8865\u5c3e\u6b3e" in pair["xianyu"]["version_evidence"]


def test_sample_103_refreshes_both_live_links_and_keeps_top_up_unresolved() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 103)
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 12980
        assert pair["wameiji"]["barcode"] == "4988002948420"
        assert pair["wameiji"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/2JH4zgJZYDsWLDn3zCnQhW.jpg@jpg"
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] == 399
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "\u8865\u6b3e" in pair["xianyu"]["version_evidence"]


def test_sample_100_refreshes_live_same_edition_listings_without_claiming_profit() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 100)
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 5940
        assert pair["wameiji"]["catalog_no"] == "WPJL-10295"
        assert pair["wameiji"]["barcode"] is None
        assert "可加入购物车/立即购买" in pair["wameiji"]["version_evidence"]
        assert pair["wameiji"]["source_url"].startswith("https://www.meruki.cn/mall/mercari/detail/")
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["price"] == 359
        assert pair["xianyu"]["observed_at"] == "2026-10-02T07:23:00+08:00"
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "2人想要/84浏览" in pair["xianyu"]["version_evidence"]
        assert "红色彩胶" in pair["xianyu"]["version_evidence"]
        assert pair["wameiji"]["observed_at"] == "2026-10-02T07:23:00+08:00"
        assert pair["wameiji"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/2JNfpAnxsayXBdLa7wu8Kw.jpg@jpg"
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "图片可能与实物不同" in pair["wameiji"]["version_evidence"]


def test_same_product_with_unmatched_condition_or_accessories_is_not_price_comparable() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    sample_ids = {4, 8, 16, 23, 34, 39, 51, 52, 54, 56}

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        records = {
            record["reference_product_id"]: record
            for record in payload[collection_name]
            if record["reference_product_id"] in sample_ids
        }
        for sample_id, record in records.items():
            assert record["same_product_verified"] is True, sample_id
            assert record["price_comparable"] is False, sample_id


def test_sample_46_replaces_inactive_xianyu_link_with_visible_current_candidate() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 46
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["price"] == 3413
        assert pair["wameiji"]["last_observed_price"] == 3413
        assert pair["wameiji"]["state"] == "observed_current"
        assert "当前价3,413 JPY" in pair["wameiji"]["version_evidence"]
        assert pair["wameiji"]["image_state"] == "page_reference_image"
        assert pair["xianyu"]["price"] == 350
        assert "687375217838" in pair["xianyu"]["source_url"]
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["image_url"] == "https://img.alicdn.com/bao/uploaded/i2/O1CN016zJoMt21VTHnrOwh9_!!0-fleamarket.jpg_790x10000Q90.jpg_.webp"
        assert pair["xianyu"]["image_state"] == "observed_main_image"
        assert "14人想要" in pair["xianyu"]["version_evidence"]
        assert pair["xianyu"]["observed_at"].startswith("2026-09-29T22:30")
        assert "2,078浏览" in pair["xianyu"]["version_evidence"]
        assert "1085787502992" in pair["relation_note"]


def test_sample_47_uses_live_exact_edition_candidates_without_claiming_full_bundle_match() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 47
        )
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert pair["xianyu"]["price"] == 130
        assert "849019159158" in pair["xianyu"]["source_url"]
        assert "455浏览" in pair["xianyu"]["version_evidence"]
        assert pair["wameiji"]["price"] == 2999
        assert "/mall/mercari/detail/" in pair["wameiji"]["source_url"]
        assert "角色卡2张" in pair["wameiji"]["version_evidence"]
        assert pair["wameiji"]["image_url"] == "https://static.312588698.com/thumb/item/webp/m58456548085_1.jpg?1782981491"
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "2,999 JPY" in pair["wameiji"]["version_evidence"]


def test_sample_49_does_not_mistake_single_ost_for_three_cd_reference_bundle() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 49
        )
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert "三张OST合售" in pair["relation_note"]
        assert "UPCI-1047" in pair["wameiji"]["version_evidence"]
        assert "UPCI-1047" in pair["xianyu"]["version_evidence"]
        assert pair["wameiji"]["image_url"] == (
            "https://static.mercdn.net/item/detail/orig/photos/m66659189268_1.jpg"
        )
        assert pair["xianyu"]["image_url"].startswith("https://img.alicdn.com/")
        assert pair["wameiji"]["observed_at"] == "2026-09-29T22:55:00+08:00"
        assert pair["xianyu"]["observed_at"] == "2026-09-29T22:55:00+08:00"


def test_sample_51_records_live_psvita_evidence_and_flags_bad_platform_categories() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 51
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["price"] == 2980
        assert "VLJM-35123" in pair["wameiji"]["version_evidence"]
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["price"] == 240
        assert "273浏览" in pair["xianyu"]["version_evidence"]
        assert "索尼PSP游戏" in pair["xianyu"]["version_evidence"]
        assert "PS5" in pair["relation_note"]
        assert "PSP" in pair["relation_note"]
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert pair["wameiji"]["observed_at"] == "2026-09-29T22:55:00+08:00"
        assert pair["xianyu"]["observed_at"] == "2026-09-29T22:55:00+08:00"


def test_sample_52_links_matching_yorushika_box_first_images_and_keeps_condition_gap() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 52
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["price"] == 30000
        assert pair["xianyu"]["price"] == 480
        assert pair["xianyu"]["image_url"] == (
            "https://img.alicdn.com/bao/uploaded/i1/2203039968859/"
            "O1CN01fK1TMcenR4D3thGS_!!4611686018427383387-0-xy_item.jpg_Q90.jpg_.webp"
        )
        assert pair["wameiji"]["image_url"] == (
            "https://static.mercdn.net/item/detail/orig/photos/m31665633966_1.jpg"
        )
        assert "972浏览" in pair["xianyu"]["version_evidence"]
        assert "外袋破损" in pair["relation_note"]
        assert "未开封" in pair["relation_note"]
        assert pair["wameiji"]["observed_at"] == "2026-09-29T22:55:00+08:00"
        assert pair["xianyu"]["observed_at"] == "2026-09-29T22:55:00+08:00"


def test_sample_53_keeps_aimer_cd_bd_first_edition_and_live_main_images() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 53
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["price"] == 2899
        assert "CD＋Blu-ray" in pair["wameiji"]["title"]
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["price"] == 560
        assert "131浏览" in pair["xianyu"]["version_evidence"]
        assert pair["xianyu"]["observed_at"] == "2026-10-02T06:02:00+08:00"
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "相册特典" in pair["relation_note"]


def test_sample_21_marks_both_live_kanon_pages_current_without_cross_sample_search_link() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 21
        )
        assert pair["same_product_verified"] is True
        assert pair["price_comparable"] is False
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 2699
        assert pair["xianyu"]["price"] == 193
        assert "search_source_url" not in pair["wameiji"]
        assert "179浏览" in pair["xianyu"]["version_evidence"]


def test_sample_24_refreshes_current_live_wameiji_listing_and_matching_first_images() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(
            record
            for record in payload[collection_name]
            if record["reference_product_id"] == 24
        )
        wameiji = pair["wameiji"]
        assert pair["price_comparable"] is False
        assert wameiji["state"] == "observed_current"
        assert wameiji["price"] == 4800
        assert wameiji["last_observed_price"] is None
        assert wameiji["image_state"] == "observed_first_gallery_image"
        assert "3DISCS" in wameiji["version_evidence"]
        assert pair["same_product_verified"] is True
        assert pair["xianyu"]["state"] == "observed_current"
        assert "470浏览" in pair["xianyu"]["version_evidence"]


def test_sample_48_downgrades_signed_card_to_related_cd_observations() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record
        for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 48
    )

    assert pair["same_product_verified"] is False
    assert pair["price_comparable"] is False
    assert pair["wameiji"]["price"] == 7800
    assert pair["wameiji"]["state"] == "observed_related"
    assert "7,800 JPY" in pair["wameiji"]["version_evidence"]
    assert pair["wameiji"]["image_url"].startswith("https://img.fril.jp/")
    assert pair["xianyu"]["state"] == "observed_related"
    assert pair["xianyu"]["price"] is None
    assert pair["xianyu"]["image_state"] == "multi_option_listing_image"
    assert pair["xianyu"]["image_url"].startswith("https://img.alicdn.com/bao/uploaded/")
    assert "1,784浏览" in pair["xianyu"]["version_evidence"]
    assert "宣传图" in pair["xianyu"]["version_evidence"]
    assert pair["xianyu"]["price_range"] == {
        "min": 180,
        "max": 550,
        "currency": "CNY",
    }
    assert "样本本体是" in pair["relation_note"]
    assert "非CD" in pair["relation_note"]
    assert "可惜夜 全员签名 照片" in pair["relation_note"]


def test_sample_60_updates_live_bundle_and_drops_wrong_first_image_link() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in payload[collection] if row["reference_product_id"] == 60)
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert pair["xianyu"]["price"] == 888
        assert pair["xianyu"]["observed_at"] == "2026-10-02T14:21:00+08:00"
        assert pair["xianyu"]["state"] == "observed_current"
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "O1CN01BO0Co8msByL87XIm" in pair["xianyu"]["image_url"]
        assert "185浏览" in pair["xianyu"]["version_evidence"]
        assert pair["wameiji"]["price"] == 6200
        assert pair["wameiji"]["observed_at"] == "2026-10-02T06:45:00+08:00"
        assert pair["wameiji"]["state"] == "observed_related"
        assert pair["wameiji"]["image_state"] == "page_reference_image"
        assert "不含参考样本中的通常版CD" in pair["wameiji"]["version_evidence"]
        assert "首图" in pair["relation_note"]
        assert "第一张原商品图片直链" in pair["relation_note"]


def test_sample_62_corrects_wrong_link_and_refreshes_both_market_observations() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in payload[collection] if row["reference_product_id"] == 62)
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert pair["xianyu"]["source_url"] == (
            "https://www.goofish.com/item?id=1068665483054&categoryId=126860296"
        )
        assert pair["xianyu"]["price"] == 208
        assert pair["xianyu"]["observed_at"] == "2026-09-30T00:20:00+08:00"
        assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert pair["wameiji"]["price"] == 5080
        assert pair["wameiji"]["state"] == "observed_related"
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "1079615195026" in pair["relation_note"]
        assert "错品" in pair["relation_note"]


def test_sample_50_keeps_exact_cd_lp_search_and_related_mercari_item_separate() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record
        for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 50
    )

    assert pair["same_product_verified"] is False
    assert pair["price_comparable"] is False
    assert pair["xianyu"]["state"] == "not_currently_listed"
    assert pair["xianyu"]["observed_at"] == "2026-10-02T04:04:00+08:00"
    assert pair["xianyu"]["price"] is None
    assert pair["xianyu"]["last_observed_price"] == 98
    assert pair["xianyu"]["price_range"] is None
    assert pair["xianyu"]["image_state"] == "no_verified_item_photo"
    assert pair["xianyu"]["image_url"] is None
    assert pair["xianyu"]["source_url"] == pair["xianyu"]["search_source_url"]
    assert "リリィ、さよなら。 約束 CD LP" in pair["xianyu"]["version_evidence"]
    assert "样本¥98仅作历史挂牌证据" in pair["xianyu"]["version_evidence"]
    assert pair["wameiji"]["barcode"] is None
    assert pair["wameiji"]["title"] == "リリィ、さよなら OKKY DVD付き"
    assert pair["wameiji"]["price"] == 300
    assert pair["wameiji"]["last_observed_price"] is None
    assert pair["wameiji"]["state"] == "observed_related"
    assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert pair["wameiji"]["image_url"] == "https://static.mercdn.net/item/detail/orig/photos/m52952260634_1.jpg"
    assert pair["wameiji"]["observed_at"] == "2026-10-02T04:05:00+08:00"
    assert "website=mercari" in pair["wameiji"]["search_source_url"]
    assert "りりあ。" in pair["relation_note"]
    assert "不推断全站无货" in pair["relation_note"]
    assert "黑白汽车场景CD封面" in pair["wameiji"]["version_evidence"]
    assert pair["wameiji"]["source_url"] != pair["wameiji"]["search_source_url"]
    assert "专辑/曲目不同" in pair["wameiji"]["version_evidence"]
    assert "渡边彻《约束》7寸EP" in pair["relation_note"]
    assert pair["price_comparable"] is False


def test_sample_58_uses_exact_complete_edition_not_initial_edition_a() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        record
        for record in payload["dual_observed_pairs"]
        if record["reference_product_id"] == 58
    )

    assert pair["same_product_verified"] is True
    assert pair["price_comparable"] is False
    assert pair["wameiji"]["state"] == "observed_current"
    assert pair["wameiji"]["price"] == 2000
    assert pair["wameiji"]["catalog_no"] == "VVCL-1700~1702"
    assert "CD+BD+フォトブック" in pair["wameiji"]["title"]
    assert pair["wameiji"]["source_url"].endswith(
        "6d37393832303531333436312f"
    )
    assert pair["wameiji"]["image_state"] == "page_reference_image"
    assert pair["wameiji"]["image_url"].endswith(
        "m79820513461_1.jpg?1790508487"
    )
    assert "VVCL-1703" in pair["relation_note"]
    assert "不比较利润" in pair["relation_note"]


def test_sample_114_restores_current_xianyu_listing_after_detail_reopens() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        row for row in payload["dual_observed_pairs"] if row["reference_product_id"] == 114
    )

    assert pair["same_product_verified"] is None
    assert pair["price_comparable"] is False
    assert pair["xianyu"]["state"] == "observed_current"
    assert pair["xianyu"]["price"] == 499
    assert pair["xianyu"]["last_observed_price"] == 499
    assert "O1CN01hYGbsd24f2hgoih1W" in pair["xianyu"]["image_url"]
    assert "不是黑胶" in pair["xianyu"]["version_evidence"]


def test_sample_125_has_current_related_vinyl_without_claiming_cd_is_a_match() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in payload[collection] if row["reference_product_id"] == 125)
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert "双彩胶LP" in pair["relation_note"]
        assert "不拿CD算双侧匹配" in pair["relation_note"]
        assert "棘ナシ" not in pair["wameiji"]["title"]
        assert pair["wameiji"]["catalog_no"] == "THCA-60298"
        assert pair["wameiji"]["price"] is None
        assert pair["wameiji"]["last_observed_price"] == 4000
        assert pair["wameiji"]["state"] == "blocked"
        assert pair["wameiji"]["image_url"] is None
        assert pair["xianyu"]["state"] == "observed_related"
        assert pair["xianyu"]["price"] == 699
        assert pair["xianyu"]["last_observed_price"] is None
        assert pair["xianyu"]["source_url"].startswith("https://www.goofish.com/item?id=1087537962429")
        assert pair["xianyu"]["image_url"].startswith("https://img.alicdn.com/bao/uploaded/")
    assert "仅是同方向当前商品" in pair["xianyu"]["version_evidence"]


def test_sample_1_rejects_wrong_listings_and_keeps_related_wameiji_item_one_sided() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    assert not any(row["reference_product_id"] == 1 for row in payload["dual_found_pairs"])
    assert not any(row["reference_product_id"] == 1 for row in payload["dual_observed_pairs"])
    sample = next(
        row for row in payload["single_observed_records"] if row["reference_product_id"] == 1
    )
    assert sample["available_market"] == "wameiji"
    assert sample["missing_market"] == "xianyu"
    assert sample["counterpart_state"] == "not_currently_listed"
    assert sample["observation"]["state"] == "observed_related"
    assert sample["observation"]["price"] == 6300
    assert sample["observation"]["source_url"].endswith("43435454774233584e45685738466a4e546e7755694b2f")
    assert sample["observation"]["image_state"] == "observed_first_gallery_image"
    assert sample["observation"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/hAKEAoC896BipW3MFHc767.jpg@jpg"
    assert "封面并不一致" in sample["observation"]["version_evidence"]
    assert sample["counterpart_candidate"]["state"] == "search_only"
    assert sample["counterpart_candidate"]["price"] is None
    assert sample["counterpart_candidate"]["image_url"] is None
    assert "1071313464471" in sample["counterpart_candidate"]["version_evidence"]
    assert "日落海面剪影封面" in sample["counterpart_candidate"]["version_evidence"]


def test_sample_45_recovers_current_wameiji_item_but_not_display_only_xianyu_price() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    sample = next(
        row for row in payload["dual_observed_pairs"] if row["reference_product_id"] == 45
    )
    assert sample["same_product_verified"] is False
    assert sample["price_comparable"] is False
    assert sample["wameiji"]["state"] == "observed_current"
    assert sample["wameiji"]["price"] == 11900
    assert sample["wameiji"]["source_url"].startswith("https://www.meruki.cn/")
    assert sample["xianyu"]["state"] == "blocked"
    assert sample["xianyu"]["price"] is None
    assert sample["xianyu"]["last_observed_price"] == 721
    assert "【展示】" in sample["xianyu"]["version_evidence"]


def test_sample_31_uses_matching_caucasus_book_not_different_hanasou_book() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    sample = next(
        row for row in payload["single_observed_records"] if row["reference_product_id"] == 31
    )
    assert sample["available_market"] == "xianyu"
    assert sample["missing_market"] == "wameiji"
    assert sample["observation"]["state"] == "observed_current"
    assert sample["observation"]["price"] == 513
    assert sample["observation"]["source_url"].endswith("id=990842888306&categoryId=126860296")
    assert "O1CN01G3wcM71D1Ut1vobZG" in sample["observation"]["image_url"]
    assert sample["counterpart_candidate"]["state"] == "search_only"
    assert sample["counterpart_candidate"]["price"] is None
    assert "《花葬》第二集画集" in sample["counterpart_candidate"]["version_evidence"]


def test_sample_102_distinguishes_current_wameiji_lp_from_historical_xianyu_deposit() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        row for row in payload["dual_observed_pairs"] if row["reference_product_id"] == 102
    )

    assert pair["same_product_verified"] is False
    assert pair["price_comparable"] is False
    assert "不比较利润" in pair["relation_note"]
    assert pair["wameiji"]["state"] == "observed_current"
    assert pair["wameiji"]["price"] == 16500
    assert pair["xianyu"]["state"] == "observed_current"
    assert pair["xianyu"]["price"] == 499
    assert pair["xianyu"]["last_observed_price"] == 499
    assert pair["xianyu"]["image_state"] == "observed_first_gallery_image"


def test_every_dual_observation_card_has_a_nonempty_middle_relation_note() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )

    missing = [
        row["reference_product_id"]
        for row in payload["dual_observed_pairs"]
        if not row.get("relation_note", "").strip()
    ]
    assert missing == []


def test_sample_105_uses_current_wameiji_price_and_marks_xianyu_detail_blocked() -> None:
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    pair = next(
        row for row in payload["dual_observed_pairs"] if row["reference_product_id"] == 105
    )

    assert pair["same_product_verified"] is False
    assert pair["price_comparable"] is False
    assert "不计算利润" in pair["relation_note"]
    assert pair["wameiji"]["title"].startswith("書簡型小説「二人称」")
    assert pair["wameiji"]["price"] == 8470
    assert pair["wameiji"]["barcode"] == "9784065416341"
    assert pair["wameiji"]["source_url"].endswith("shimamura-gakufu%2Fg0528352%2F")
    assert pair["wameiji"]["state"] == "observed_current"
    assert pair["xianyu"]["title"].startswith("国内现货 夜鹿n-buna")
    assert pair["xianyu"]["price"] == 400
    assert pair["xianyu"]["last_observed_price"] == 400
    assert pair["xianyu"]["state"] == "observed_current"
    assert "立即购买" in pair["xianyu"]["version_evidence"]


def test_single_and_unavailable_records_keep_manual_browser_evidence_labels() -> None:
    """Every non-dual record must identify its manual browser evidence source."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    records = list(payload["single_observed_records"])
    records.extend(payload["unavailable_records"])

    assert len(records) == 15
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
        # The JSON value is a site-root-relative URL, not a path relative to the JSON file.
        assert (Path("web") / relative_path).is_file()


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


def test_sample_25_live_detail_and_direct_first_images_are_refreshed_in_both_lists() -> None:
    """Refresh the current listing signals without conflating product image and seller condition."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in payload[collection] if row["reference_product_id"] == 25)
        assert sample["same_product_verified"] is False
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["price"] == 710
        assert "775浏览" in sample["xianyu"]["version_evidence"]
        assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample["wameiji"]["price"] == 9000
        assert "腕章曾单独取出展示" in sample["wameiji"]["version_evidence"]
        assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "首图直链" in sample["relation_note"]
        assert "成色及附件状态没有对齐" in sample["relation_note"]
        assert sample["xianyu"]["observed_at"].startswith("2026-09-29")
        assert sample["wameiji"]["observed_at"].startswith("2026-09-29")


def test_sample_112_active_records_keep_cover_variant_mismatch_explicit() -> None:
    """The two live listings are the same songs but visibly different LP cover variants."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in payload[collection] if row["reference_product_id"] == 112)
        assert sample["same_product_verified"] is False
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["price"] == 495
        assert "445浏览" in sample["xianyu"]["version_evidence"]
        assert sample["wameiji"]["price"] == 9500
        assert "未明示绿色胶" in sample["wameiji"]["version_evidence"]
        assert "蓝色人物封面" in sample["xianyu"]["version_evidence"]
        assert "不能确认完全同款" in sample["relation_note"]
        assert "O1CN01Hr1c2n1jXcNM69QP7" in sample["xianyu"]["image_url"]
        assert sample["xianyu"]["observed_at"].startswith("2026-10-02")
        assert sample["wameiji"]["observed_at"].startswith("2026-10-02")


def test_sample_29_active_records_keep_bundle_vs_single_disc_mismatch_explicit() -> None:
    """Keep the four-CD signed Xianyu bundle distinct from the single Mercari edition."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in payload[collection] if row["reference_product_id"] == 29)
        assert sample["same_product_verified"] is False
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["price"] == 5000
        assert "306浏览" in sample["xianyu"]["version_evidence"]
        assert "四碟实拍拼图" in sample["xianyu"]["version_evidence"]
        assert sample["wameiji"]["price"] == 33000
        assert "杯垫2枚及特装包装" in sample["wameiji"]["version_evidence"]
        assert sample["xianyu"]["observed_at"].startswith("2026-09-29")
        assert sample["wameiji"]["observed_at"].startswith("2026-09-29")


def test_sample_34_current_details_and_first_images_preserve_accessory_gap() -> None:
    """Both sides show the same edition cover, but only one side lists a missing shikishi."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in payload[collection] if row["reference_product_id"] == 34)
        assert sample["same_product_verified"] is True
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["price"] == 490
        assert "874浏览" in sample["xianyu"]["version_evidence"]
        assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample["wameiji"]["price"] == 15000
        assert "明确没有色纸" in sample["wameiji"]["version_evidence"]
        assert "首图直链" in sample["relation_note"]
        assert sample["xianyu"]["observed_at"].startswith("2026-09-27")
        assert sample["wameiji"]["observed_at"].startswith("2026-09-27")


def test_sample_46_xianyu_live_first_image_is_recorded_in_both_snapshot_lists() -> None:
    """Keep the manually opened Goofish main image while preserving edition uncertainty."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    expected = "https://img.alicdn.com/bao/uploaded/i2/O1CN016zJoMt21VTHnrOwh9_!!0-fleamarket.jpg_790x10000Q90.jpg_.webp"
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in payload[collection] if row["reference_product_id"] == 46)
        assert sample["xianyu"]["source_url"].endswith("id=687375217838&categoryId=126864811")
        assert sample["xianyu"]["image_url"] == expected
        assert sample["xianyu"]["image_state"] == "observed_main_image"
        assert sample["price_comparable"] is False
        assert sample["same_product_verified"] is True
        assert "私聊" in sample["xianyu"]["version_evidence"]


def test_sample_54_refreshes_live_details_and_keeps_first_image_difference_explicit() -> None:
    """The matching box set has different listing hero images and condition tiers."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in payload[collection] if row["reference_product_id"] == 54)
        assert sample["same_product_verified"] is True
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["price"] == 320
        assert "304浏览" in sample["xianyu"]["version_evidence"]
        assert sample["xianyu"]["image_url"].startswith("https://img.alicdn.com/")
        assert "红色外盒可读到TYPE-MOON Fes." in sample["xianyu"]["version_evidence"]
        assert sample["xianyu"]["observed_at"].startswith("2026-09-29T23:10")
        assert sample["wameiji"]["price"] == 6480
        assert "特典CD 1张" in sample["wameiji"]["version_evidence"]
        assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "人物插图包装面" in sample["wameiji"]["version_evidence"]
        assert sample["wameiji"]["observed_at"].startswith("2026-09-29T23:10")
        assert "不比较利润" in sample["relation_note"]


def test_sample_55_keeps_variant_price_ambiguous_and_marks_japan_listing_sold() -> None:
    """Do not turn a multi-variant range or a sold example-image listing into a match."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in payload[collection] if row["reference_product_id"] == 55)
        assert sample["same_product_verified"] is False
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["price"] is None
        assert "¥228–350包邮" in sample["xianyu"]["version_evidence"]
        assert "1017浏览" in sample["xianyu"]["version_evidence"]
        assert sample["xianyu"]["observed_at"].startswith("2026-09-29T23:13")
        assert sample["wameiji"]["price"] is None
        assert sample["wameiji"]["last_observed_price"] == 1610
        assert sample["wameiji"]["state"] == "current_sold_image"
        assert "售罄" in sample["wameiji"]["version_evidence"]
        assert sample["wameiji"]["image_state"] == "page_reference_image"
        assert "不比较利润" in sample["relation_note"]


def test_sample_71_replaces_deleted_dvd_with_live_bluray_candidate_without_profit_claim() -> None:
    """A live edition candidate must not silently erase the seller-title disc-count mismatch."""
    payload = json.loads(
        Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")
    )
    expected_xianyu_image = (
        "https://img.alicdn.com/bao/uploaded/i2/20297417/"
        "O1CN01sEDdXVtbZCI70gAX_!!4611686018427385545-0-xy_item.jpg_790x10000Q90.jpg_.webp"
    )
    expected_wameiji_image = (
        "https://imghk.doorzo.net/item/detail/orig/photos/"
        "m97098009553_1.jpg?1789274211"
    )
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in payload[collection] if row["reference_product_id"] == 71)
        assert sample["same_product_verified"] is False
        assert sample["price_comparable"] is False
        assert "CD+2Blu-ray" in sample["xianyu"]["title"]
        assert sample["xianyu"]["price"] == 699
        assert sample["xianyu"]["image_url"] == expected_xianyu_image
        assert sample["xianyu"]["observed_at"].startswith("2026-09-29T03:07")
        assert sample["wameiji"]["state"] == "observed_current"
        assert sample["wameiji"]["price"] == 13500
        assert sample["wameiji"]["catalog_no"] == "SECL-3332～3"
        assert sample["wameiji"]["image_url"] == expected_wameiji_image
        assert sample["wameiji"]["image_state"] == "page_reference_image"
        assert "图片可能与实物不同" in sample["wameiji"]["version_evidence"]
        assert "2Blu-ray" in sample["relation_note"]
        assert "不计利润" in sample["relation_note"]


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


def test_sample_30_replaces_wrong_yuzusoft_items_with_current_related_observations() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    historical = next(row for row in snapshot["dual_found_pairs"] if row["reference_product_id"] == 30)
    current = next(row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 30)

    assert historical["same_product_verified"] is False
    assert historical["price_comparable"] is False
    assert historical["wameiji"]["is_wameiji_platform"] is True
    assert historical["wameiji"]["price"] == 16000
    assert historical["wameiji"]["state"] == "observed_related"
    assert historical["wameiji"]["image_url"] == "https://static.mercdn.net/item/detail/orig/photos/m46029609421_1.jpg"
    assert historical["xianyu"]["price"] == 600
    assert historical["xianyu"]["state"] == "observed_related"
    first_gallery_url = (
        "https://img.alicdn.com/bao/uploaded/i4/2218457966011/"
        "O1CN01wZQ8cw1uH5tS9Axcg_!!4611686018427381179-53-xy_item.heic_790x10000Q90.jpg_.webp"
    )
    assert historical["xianyu"]["image_url"] == first_gallery_url
    assert historical["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert "不比较利润" in historical["relation_note"]

    assert current["observation"]["source_url"] == historical["wameiji"]["source_url"]
    assert current["xianyu"]["source_url"].endswith("id=1051600239512&categoryId=126860296")
    assert current["xianyu"]["image_url"] == first_gallery_url
    assert current["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert "午餐垫" not in current["observation"]["title"]
    assert "RIDDLE JOKER 设定集" not in current["xianyu"]["title"]
    assert "997446339847" not in json.dumps(current, ensure_ascii=False)
    assert "m84951448633" not in json.dumps(current, ensure_ascii=False)
