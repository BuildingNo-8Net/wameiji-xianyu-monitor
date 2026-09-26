from __future__ import annotations

import subprocess
import json
import re
from datetime import datetime
from pathlib import Path


def extract_dual_market_renderer(javascript: str) -> str:
    start = javascript.index("function eligibleComparisonCard")
    end = javascript.index("function setSelectionBoardQuery")
    return javascript[start:end]


def test_dual_market_ui_renders_only_eligible_pairs_with_both_source_images() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    loader = Path("web/dual-market-data.js").read_text(encoding="utf-8")
    renderer = extract_dual_market_renderer(javascript)

    assert "item.xianyu.image_url" in renderer
    assert "item.wameiji.image_url" in renderer
    assert "board.eligible" in renderer
    assert "waiting_wameiji" not in renderer
    assert "waiting_xianyu" not in renderer
    assert "nonReadyComparisonCard" not in renderer
    assert "/api/dual-market/board" in loader
    assert "xianyu_reference_price" not in renderer


def test_static_snapshot_product_images_resolve_from_the_pages_base_url() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    start = javascript.index("function safeHttpUrl")
    end = javascript.index("function liquidityChip")
    image_helpers = javascript[start:end]
    harness = f"""
const document = {{ baseURI: "https://example.github.io/project/" }};
{image_helpers}
const result = usableProductImage(
  "assets/dual-market/snapshot/4-xianyu.webp"
);
if (result !== "https://example.github.io/project/assets/dual-market/snapshot/4-xianyu.webp") {{
  throw new Error("unexpected image URL: " + result);
}}
const referenceImage = usableProductImage(
  "assets/reference-samples/52-verified.webp"
);
if (referenceImage !== "https://example.github.io/project/assets/reference-samples/52-verified.webp") {{
  throw new Error("reference image was not resolved: " + referenceImage);
}}
if (usableProductImage("../private.png") !== "") {{
  throw new Error("relative paths outside the published asset tree must be rejected");
}}
"""

    result = subprocess.run(
        ["node", "-e", harness],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_homepage_names_cd_and_galgame_physical_media() -> None:
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert "CD 与 GalGame 实体" in homepage
    assert "达标机会" in homepage


def test_homepage_distinguishes_xianyu_search_evidence_from_wameiji_detail() -> None:
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert "闲鱼以淡黄色显示搜索挂牌价样本" in homepage
    assert "挖煤姬以淡粉白显示详情已核验进货价" in homepage
    assert "只有详情已核验的来源才会进入机会流" not in homepage


def test_homepage_exposes_the_full_reference_audit_queue_separately_from_profit_cards() -> None:
    """Four eligible cards must never visually imply that every reference was finished."""
    homepage = Path("web/index.html").read_text(encoding="utf-8")
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")

    assert 'id="referenceAuditPanel"' in homepage
    assert "125 个参考样本" in homepage
    assert "双侧实物观察" in homepage
    assert "绝不伪装成达标机会" in homepage
    assert "挖煤姬页面已复核" in homepage
    assert 'id="referenceAuditPairList"' in homepage
    assert 'data/reference-audit-snapshot.json' in javascript
    assert "renderReferenceAudit" in javascript
    assert "双侧实物观察" in javascript
    assert "日本来源侧" in javascript
    assert "待挖煤姬复核" in javascript
    assert "已人工核验 · 观察记录" in javascript
    assert "源站未提供主图" in javascript
    assert "重定向至.*login" in javascript
    assert "待逐件核验</div>" not in javascript


def test_homepage_keeps_unprofitable_dual_listings_in_the_observation_queue() -> None:
    """The public audit must not hide real two-sided listings behind a profit gate."""
    homepage = Path("web/index.html").read_text(encoding="utf-8")
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")

    assert "双侧实物观察" in homepage
    assert "dual_observed_pairs" in javascript
    assert "双侧实物观察" in javascript


def test_homepage_keeps_concrete_one_sided_listings_in_the_primary_observation_queue() -> None:
    """A source listing must be visible even before the opposite market is found."""
    homepage = Path("web/index.html").read_text(encoding="utf-8")
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")

    assert 'id="referenceAuditSingleSummary"' in homepage
    assert 'id="referenceAuditSingleList"' in homepage
    assert 'id="referenceAuditUnavailableSummary"' in homepage
    assert 'id="referenceAuditUnavailableList"' in homepage
    assert "single_observed_records" in javascript
    assert "unavailable_records" in javascript
    assert "单侧检索观察" in javascript
    assert "参考样本图 · 非当前商品页" in javascript
    assert "参考样本图 · 两侧当前未见" in javascript


def test_reference_audit_cards_use_marketplace_main_images_and_platform_colours() -> None:
    """Observed sides use marketplace images; missing sides may show labelled references."""
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    stylesheet = Path("web/styles/kuro.css").read_text(encoding="utf-8")

    assert "source.image_url || source.main_image_url" in javascript
    assert "reference-audit-market-media" in javascript
    assert "主图链接待补" in javascript
    assert "首图直链待复核 · 不显示疑似错图" in javascript
    assert "源站未提供主图" in javascript
    assert "static.mercdn.net/item/detail/orig/photos/" in javascript
    assert "mokaki\\.cn\\/sigimage\\/icon" in javascript
    assert "ossimg\\/)" not in javascript
    assert "referenceAuditImageMarkup" not in javascript
    assert "const referenceImage = usableProductImage(item.reference_image_url);" in javascript
    assert "const relatedSource = item[missingMarket]" in javascript
    assert 'candidate?.state === "search_only"' in javascript
    assert "const displayCandidate = relatedCandidate || (searchOnlyCandidate ? null : candidate);" in javascript
    assert "当前未找到可核验同款商品页" in javascript
    assert "const observedImage = versionedAuditImageUrl(auditObservationImage(source));" in javascript
    assert "当前相关观察 · 非样本同款" in javascript
    assert "参考样本图 · 非当前商品页" in javascript
    assert '"xianyu-side"' in javascript
    assert '"wameiji-side"' in javascript
    assert ".reference-audit-side.xianyu-side" in stylesheet
    assert ".reference-audit-side.wameiji-side" in stylesheet
    assert ".reference-audit-market-media" in stylesheet
    assert ".reference-audit-center" in stylesheet


def test_reference_only_images_are_not_rendered_as_current_marketplace_photos() -> None:
    """Illustrative/reference art must not masquerade as a listing's first photo."""
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")

    reference_only_guard = 'if (source.image_state === "reference_only") return "";'
    assert reference_only_guard in javascript
    assert javascript.index(reference_only_guard) < javascript.index(
        'const directImage = usableProductImage(source.image_url || source.main_image_url);'
    )


def test_unverified_first_gallery_image_is_not_rendered() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    start = javascript.index("function auditObservationImage")
    end = javascript.index("function versionedAuditImageUrl")
    image_resolver = javascript[start:end]
    harness = f"""
const usableProductImage = (value) => value || "";
const inferredMercariMainImage = () => "";
{image_resolver}
const image = auditObservationImage({{
  image_url: "https://img.alicdn.com/possibly-wrong.webp",
  image_state: "first_gallery_image_link_unverified"
}});
if (image !== "") {{
  throw new Error("an unverified first-gallery link must not render as a product photo");
}}
"""

    result = subprocess.run(
        ["node", "-e", harness],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_reference_audit_image_urls_preserve_strict_source_query_parameters() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    start = javascript.index("function versionedAuditImageUrl")
    end = javascript.index("function inferredMercariMainImage")
    image_url_renderer = javascript[start:end]
    harness = f"""
const safeHttpUrl = (value) => /^https?:\\/\\//.test(value) ? value : "";
{image_url_renderer}
const original = "https://imghk.doorzo.net/tshopr10sjp/guruguru2/cabinet/205/vman-7.jpg?fitin=600:600";
const rendered = versionedAuditImageUrl(original);
if (rendered !== original) {{
  throw new Error("do not mutate signed/strict marketplace image URLs with cache-busting params");
}}
if (versionedAuditImageUrl("") !== "") {{
  throw new Error("missing images must stay missing rather than inventing a fallback");
}}
"""

    result = subprocess.run(
        ["node", "-e", harness],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_listing_reference_image_is_shown_with_explicit_non_item_badge() -> None:
    """A marketplace's own first gallery image remains visible but is not called a real item photo."""
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    stylesheet = Path("web/styles/kuro.css").read_text(encoding="utf-8")

    assert 'source.image_state === "page_reference_image"' in javascript
    assert "来源页示意图 · 非实物照" in javascript
    assert ".reference-audit-image-badge" in stylesheet


def test_multivariant_listing_image_is_not_mislabeled_as_selected_item_photo() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    sample_50 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 50)

    assert sample_50["same_product_verified"] is False
    assert sample_50["price_comparable"] is False
    assert sample_50["xianyu"]["image_state"] == "multi_option_listing_image"
    assert sample_50["xianyu"]["image_url"].startswith("https://img.alicdn.com/")
    assert "不比较价格或利润" in sample_50["relation_note"]
    assert "703浏览" in sample_50["xianyu"]["version_evidence"]
    assert sample_50["xianyu"]["state"] == "observed_related"
    assert sample_50["xianyu"]["observed_at"] == "2026-09-26T20:29:00+08:00"
    assert sample_50["xianyu"]["last_observed_price"] == 98
    assert "120 无册封 已出" in sample_50["xianyu"]["version_evidence"]
    assert sample_50["wameiji"]["state"] == "blocked"
    assert sample_50["wameiji"]["price"] is None
    assert 'source.image_state === "multi_option_listing_image"' in javascript
    assert "多规格合集首图 · 具体选项未锁定" in javascript


def test_sample_9_rechecks_current_xianyu_game_and_keeps_trial_disc_separate_without_profit() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    sample_9 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 9)
    wameiji = sample_9["wameiji"]

    assert sample_9["same_product_verified"] is False
    assert sample_9["xianyu"]["observed_at"] == "2026-09-26T19:49:45+08:00"
    assert "2人想要" in sample_9["xianyu"]["version_evidence"]
    assert "缺内箱、没卡牌" in sample_9["xianyu"]["version_evidence"]
    assert "页面显示立即购买" in sample_9["xianyu"]["version_evidence"]
    assert sample_9["xianyu"]["state"] == "observed_current"
    assert sample_9["xianyu"]["price"] == 450
    assert sample_9["xianyu"]["last_observed_price"] is None
    assert sample_9["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert sample_9["xianyu"]["image_url"].startswith("https://img.alicdn.com/")
    assert "1188浏览" in sample_9["xianyu"]["version_evidence"]
    assert "多出一张CD应为eden OST" in sample_9["xianyu"]["version_evidence"]
    assert wameiji["state"] == "observed_related"
    assert wameiji["price"] == 2500
    assert wameiji["observed_at"] == "2026-09-26T19:49:45+08:00"
    assert wameiji["currency"] == "JPY"
    assert wameiji["image_url"] == "https://imghk.doorzo.net/item/detail/orig/photos/m11488055179_1.jpg?1777576043"
    assert wameiji["image_state"] == "observed_first_gallery_image"
    assert "/mall/mercari/detail/" in wameiji["source_url"]
    assert "search_source_url" in wameiji
    assert "TRIAL DISC Sofmap エディション" in wameiji["version_evidence"]
    assert "该商品是试听盘，不是样本中的完整初回限定游戏" in wameiji["version_evidence"]
    assert "挖煤姬当前商品是《eden* TRIAL DISC》Sofmap试听盘" in sample_9["relation_note"]
    assert "两侧不是同一商品、价格不可比，不计算利润" in sample_9["relation_note"]
    assert "keywords=eden%2A+minori+Windows+CD" in wameiji["search_source_url"]
    assert "可加入购物车/立即购买" in wameiji["version_evidence"]
    assert "闲鱼商品为当前同款观察，但附件不完整" in sample_9["relation_note"]
    assert "未找到可核实的在售同款" in javascript
    assert "查看站内检索结果" in javascript


def test_sample_60_rechecks_current_images_prices_and_export_restriction() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        row = next(item for item in snapshot[collection] if item["reference_product_id"] == 60)
        assert row["same_product_verified"] is False
        assert row["price_comparable"] is False
        assert row["wameiji"]["catalog_no"] is None
        assert row["wameiji"]["price"] == 9009
        assert row["wameiji"]["state"] == "observed_current"
        assert "ESCL62689" in row["wameiji"]["version_evidence"]
        assert "未证明" in row["wameiji"]["version_evidence"]
        assert row["wameiji"]["image_state"] == "page_reference_image"
        assert row["xianyu"]["price"] == 777
        assert "通常版CD" in row["xianyu"]["version_evidence"]
        assert row["xianyu"]["source_url"].endswith("id=1083531548078&categoryId=126860296")
        assert row["xianyu"]["state"] == "observed_current"
        assert row["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert row["xianyu"]["image_url"].startswith("https://img.alicdn.com/bao/uploaded/")
        assert "不认定两侧同款" in row["relation_note"]
        assert "原挖煤姬6200 JPY链接另标輸出不可" in row["relation_note"]


def test_sample_61_rechecks_exact_catalog_match_and_distinguishes_condition() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        row = next(item for item in snapshot[collection] if item["reference_product_id"] == 61)
        assert row["same_product_verified"] is True
        assert row["price_comparable"] is False
        assert row["xianyu"]["catalog_no"] == "UPJY-9202/3"
        assert row["xianyu"]["barcode"] == "4988031460023"
        assert row["xianyu"]["price"] == 388
        assert row["xianyu"]["state"] == "observed_current"
        assert row["wameiji"]["catalog_no"] == "UPJY-9202/3"
        assert row["wameiji"]["barcode"] == "4988031460023"
        assert row["wameiji"]["price"] == 7900
        assert row["wameiji"]["state"] == "observed_current"
        assert "品相不可比" in row["relation_note"]


def test_sample_5_keeps_verified_xianyu_gallery_photo_but_blocks_stale_detail_and_marks_anniversary_related() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    image_url = "https://img.alicdn.com/bao/uploaded/i4/2209323678281/O1CN01OIdA0xJPgoL3KRr7_!!4611686018427386441-0-xy_item.jpg_790x10000Q90.jpg_.webp"
    copies = [
        (key, row)
        for key in ("dual_found_pairs", "dual_observed_pairs")
        for row in snapshot[key]
        if row["reference_product_id"] == 5
    ]

    assert len(copies) == 2
    for collection, pair in copies:
        xianyu = pair["xianyu"]
        wameiji = pair["wameiji"]
        assert pair["same_product_verified"] is False
        assert pair["price_comparable"] is False
        assert xianyu["state"] == "blocked"
        assert xianyu["price"] is None
        assert xianyu["last_observed_price"] == 9999
        assert xianyu["image_url"] == image_url
        assert xianyu["image_state"] == "historical_first_gallery_image"
        assert "14:24再次打开时只呈现通用页脚" in xianyu["version_evidence"]
        assert wameiji["state"] == "observed_related"
        assert wameiji["price"] == 19410
        assert wameiji["observed_at"] == (
            "2026-09-26T15:21:00+08:00"
            if collection == "dual_observed_pairs"
            else "2026-09-26T14:23:00+08:00"
        )
        assert wameiji["image_state"] == "page_reference_image"
        assert "10周年" in wameiji["version_evidence"]


def test_sample_2_blocks_stale_xianyu_replacement_and_keeps_live_wameiji_edition_unmatched() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_2 = next(row for row in rows if row["reference_product_id"] == 2)
        xianyu = sample_2["xianyu"]

        assert sample_2["same_product_verified"] is False
        assert "与样本《Under Mentality》双角色封面不同" in sample_2["relation_note"]
        assert "截图为已售" in sample_2["relation_note"]
        assert xianyu["source_url"].endswith("id=1007738775561&categoryId=126864811")
        assert xianyu["state"] == "observed_related"
        assert xianyu["price"] == 180
        assert xianyu["last_observed_price"] is None
        assert xianyu["observed_at"] == "2026-09-26T17:17:00+08:00"
        assert xianyu["search_source_url"].endswith("TUYU%20Under%20Mentality%20%E5%88%9D%E5%9B%9E%E9%99%90%E5%AE%9A%20CD")
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["image_url"] == "https://img.alicdn.com/bao/uploaded/i2/O1CN01R9NhyY26x1W18K6gk_!!4611686018427379775-53-fleamarket.heic_790x10000Q90.jpg_.webp"
        assert "¥180、3人想要/297浏览" in xianyu["version_evidence"]
        assert "主图/首图为白发角色的二专CD" in xianyu["version_evidence"]
        assert "与样本《Under Mentality》初回限定不同" in xianyu["version_evidence"]
        assert "点开图片后显示画廊1/1张" in xianyu["version_evidence"]
        assert "_790x10000Q90.jpg_.webp" in xianyu["version_evidence"]
        assert "原样本闲鱼截图为《Under Mentality》初回限定CD，¥280" in xianyu["version_evidence"]
        assert sample_2["wameiji"]["state"] == "observed_current"
        assert sample_2["wameiji"]["observed_at"] == "2026-09-26T18:02:00+08:00"
        assert "封面画面与样本一致" in sample_2["wameiji"]["version_evidence"]
        assert "未锁定Blu-ray/DVD及附件" in sample_2["wameiji"]["version_evidence"]
        assert "无杯垫" in sample_2["wameiji"]["version_evidence"]


def test_sample_3_xianyu_listing_is_sold_not_currently_available() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_3 = next(row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 3)
    observation = sample_3["observation"]

    assert observation["price"] == 90
    assert observation["state"] == "current_sold_image"
    assert observation["image_state"] == "current_sold_image"
    assert "购买区明确为“卖掉了”" in observation["version_evidence"]
    assert sample_3["counterpart_state"] == "search_only"
    assert sample_3["wameiji"]["state"] == "search_only"
    assert sample_3["wameiji"]["price"] is None
    assert sample_3["wameiji"]["image_url"] is None
    assert sample_3["wameiji"]["observed_at"] == "2026-09-26T15:12:00+08:00"
    assert "Altair/Rigel条目已确认是无关误配并撤下" in sample_3["wameiji"]["relation_note"]
    assert "Rigël Theatre" in sample_3["wameiji"]["version_evidence"]
    assert "此前记录的「劇団アルタイル」" in sample_3["wameiji"]["version_evidence"]


def test_sample_4_current_pair_keeps_version_match_separate_from_profit_comparability() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_4 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 4)

    assert sample_4["same_product_verified"] is True
    assert sample_4["price_comparable"] is False
    assert sample_4["xianyu"]["price"] == 500
    assert sample_4["xianyu"]["observed_at"] == "2026-09-26T15:18:00+08:00"
    assert "立即购买按钮可见" in sample_4["xianyu"]["version_evidence"]
    assert sample_4["wameiji"]["price"] == 10771
    assert sample_4["wameiji"]["observed_at"] == "2026-09-26T15:18:00+08:00"
    assert sample_4["wameiji"]["image_state"] == "page_reference_image"
    assert "无物流保障" in sample_4["wameiji"]["version_evidence"]
    assert "图片可能与实物不同" in sample_4["relation_note"]
    assert "不计算利润" in sample_4["relation_note"]


def test_sample_5_uses_reference_screenshot_price_and_keeps_anniversary_edition_related_only() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_5 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 5)

    assert sample_5["same_product_verified"] is False
    assert sample_5["price_comparable"] is False
    assert "原始闲鱼样本截图明确为¥450" in sample_5["relation_note"]
    assert "¥480" not in sample_5["relation_note"]
    assert "¥450、1人想要/453浏览" in sample_5["xianyu"]["version_evidence"]
    assert sample_5["xianyu"]["state"] == "blocked"
    assert sample_5["wameiji"]["state"] == "observed_related"
    assert sample_5["wameiji"]["price"] == 19410
    assert sample_5["wameiji"]["observed_at"] == "2026-09-26T15:21:00+08:00"
    assert "4张碟" in sample_5["wameiji"]["version_evidence"]
    assert "不是样本初回限定版" in sample_5["wameiji"]["version_evidence"]


def test_sample_41_keeps_unselected_xianyu_option_and_uses_verified_live_wameiji_candidate() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_41 = next(row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 41)
    observation = sample_41["observation"]

    assert observation["price"] is None
    assert observation["observed_at"] == "2026-09-25T19:42:00+08:00"
    assert "135–160 CNY区间" in observation["version_evidence"]
    assert "仍未选中具体专辑选项" in observation["version_evidence"]
    assert sample_41["counterpart_state"] == "observed_related"
    assert sample_41["same_product_verified"] is False
    assert sample_41["wameiji"]["state"] == "observed_current"
    assert sample_41["wameiji"]["price"] == 10000
    assert sample_41["wameiji"]["source_url"] == (
        "https://www.meruki.cn/mall/mercari/detail/"
        "68747470733a2f2f7777772e6d6572636172692e636f6d2f6a702f6974656d732f6d34363537313237383932312f"
    )
    assert sample_41["wameiji"]["image_url"] == (
        "https://imghk02.doorzo.net/item/detail/orig/photos/m46571278921_1.jpg?1790239139"
    )
    assert sample_41["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert "CURE一专" in sample_41["wameiji"]["version_evidence"]
    assert "全新未拆" in sample_41["wameiji"]["version_evidence"]
    assert "加入购物车/立即购买" in sample_41["wameiji"]["version_evidence"]
    assert "售罄" not in sample_41["wameiji"]["version_evidence"]


def test_samples_10_and_11_use_the_latest_matching_evidence_timestamps() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_10 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 10)
    sample_11 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 11)

    assert sample_10["same_product_verified"] is True
    assert sample_10["price_comparable"] is False
    assert sample_10["wameiji"]["observed_at"] == "2026-09-26T16:21:00+08:00"
    assert sample_10["wameiji"]["state"] == "observed_current"
    assert sample_10["wameiji"]["price"] == 8000
    assert sample_10["wameiji"]["image_url"] == "https://imghk.doorzo.net/item/detail/orig/photos/m44548019130_1.jpg?1789188843"
    assert sample_10["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert sample_10["xianyu"]["observed_at"] == "2026-09-26T16:21:00+08:00"
    assert sample_10["xianyu"]["state"] == "observed_current"
    assert sample_10["xianyu"]["price"] == 860
    assert sample_10["xianyu"]["last_observed_price"] is None
    assert sample_10["xianyu"]["source_url"] == "https://www.goofish.com/item?id=1068314324496&categoryId=126864811"
    assert sample_10["xianyu"]["image_url"] == (
        "https://img.alicdn.com/bao/uploaded/i3/1844172791/"
        "O1CN01nW9DXz1WUKZb2L3qi_!!4611686018427385847-0-xy_item.jpg_450x10000Q90.jpg_.webp"
    )
    assert sample_10["xianyu"]["image_state"] == "observed_main_image"
    assert "2012年发行、有侧标、全新未拆" in sample_10["xianyu"]["version_evidence"]
    assert "页面显示“立即购买”" in sample_10["xianyu"]["version_evidence"]
    assert "红发角色封面" in sample_10["relation_note"]
    assert sample_11["wameiji"]["observed_at"] == "2026-09-26T16:22:00+08:00"
    assert sample_11["wameiji"]["state"] == "observed_current"
    assert sample_11["xianyu"]["observed_at"] == "2026-09-26T16:22:00+08:00"
    assert sample_11["xianyu"]["state"] == "observed_current"
    assert sample_11["xianyu"]["price"] == 129
    assert sample_11["xianyu"]["last_observed_price"] is None
    assert sample_11["xianyu"]["image_state"] == "observed_main_image"
    assert "盒子烂" in sample_11["xianyu"]["version_evidence"]
    assert "立即购买" in sample_11["xianyu"]["version_evidence"]


def test_sample_59_sold_wameiji_item_has_no_invented_current_price() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    copies = [
        row
        for key in ("dual_found_pairs", "dual_observed_pairs")
        for row in snapshot[key]
        if row["reference_product_id"] == 59
    ]

    assert len(copies) == 2
    for pair in copies:
        assert pair["same_product_verified"] is False
        assert pair["wameiji"]["state"] == "not_currently_listed"
        assert pair["wameiji"]["price"] is None
        assert "已售出" in pair["wameiji"]["version_evidence"]
        assert "不是售价" in pair["wameiji"]["version_evidence"]
        assert pair["xianyu"]["price_range"] == {"min": 177, "max": 233, "currency": "CNY"}
        assert "537浏览" in pair["xianyu"]["version_evidence"]


def test_sample_8_confirms_same_kazusa_cd_direction_without_equating_condition_or_accessories() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_8 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 8)
    wameiji = sample_8["wameiji"]
    xianyu = sample_8["xianyu"]

    assert sample_8["same_product_verified"] is True
    assert "kazusa" in sample_8["relation_note"]
    assert "价差" in sample_8["relation_note"]
    assert "利润" in sample_8["relation_note"]
    assert wameiji["price"] == 19800
    assert wameiji["source_url"].endswith("324a5736784561697663594a537166344459465937792f")
    assert wameiji["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/2JW6xEZiNRUBMeERREzrzs.jpg@jpg"
    assert wameiji["state"] == "observed_current"
    assert xianyu["price"] == 360
    assert xianyu["image_state"] == "observed_first_gallery_image"
    assert "1,052浏览" in xianyu["version_evidence"]
    assert "状态不同" in xianyu["version_evidence"]


def test_sample_12_keeps_tuyu_album_unmatched_without_sku_crosscheck() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = [
        row
        for collection in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"])
        for row in collection
        if row["reference_product_id"] == 12
    ]

    assert len(rows) == 2
    for sample_12 in rows:
        assert sample_12["same_product_verified"] is False
        assert "TUYU-0002" in sample_12["relation_note"] or "TUYU-0002" in sample_12["wameiji"]["version_evidence"]
        assert "¥240–280包邮" in sample_12["relation_note"]
        assert sample_12["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample_12["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "32人想要/1,403浏览" in sample_12["xianyu"]["version_evidence"]
        assert "不比较价差或利润" in sample_12["relation_note"]


def test_sample_14_keeps_sold_xianyu_search_result_separate_from_current_buyable_wameiji_reference_image() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_14 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 14)
    xianyu = sample_14["xianyu"]
    wameiji = sample_14["wameiji"]

    assert sample_14["same_product_verified"] is False
    assert "单碟不可购买" in sample_14["relation_note"]
    assert "SW-045T详情当前1,370 JPY、可加入购物车/购买" in sample_14["relation_note"]
    assert "SW-045T" in wameiji["version_evidence"]
    assert wameiji["state"] == "observed_related"
    assert wameiji["observed_at"] == "2026-09-26T16:35:00+08:00"
    assert wameiji["catalog_no"] == "SW-045T"
    assert wameiji["image_state"] == "page_reference_image"
    assert "图片为示意图" in wameiji["version_evidence"]
    assert xianyu["state"] == "not_currently_listed"
    assert xianyu["price"] is None
    assert xianyu["image_state"] == "reference_only"
    assert xianyu["image_url"] is None
    assert xianyu["observed_at"] == "2026-09-26T16:35:00+08:00"
    assert "已出" in xianyu["version_evidence"] and "仅挂，展示" in xianyu["version_evidence"]
    assert "43人想要" in xianyu["version_evidence"]
    assert sample_14["reference_image_url"] == "assets/reference-samples/14-b9f4a41e4e062903.webp"
    assert "1077589995824" not in xianyu["source_url"]
    assert xianyu["source_url"] == "https://www.goofish.com/item?id=794620837421&categoryId=126864811"


def test_sample_17_does_not_conflate_narcissu_2_with_narcissu_side_2nd() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = [
        row
        for collection in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"])
        for row in collection
        if row["reference_product_id"] == 17
    ]

    assert len(rows) == 2
    for row in rows:
        assert row["same_product_verified"] is False
        assert "闲鱼当前ID 859421708400实际为泛称《Narcissu2》" in row["relation_note"]
        assert "直接图片链接尚未核实" in row["relation_note"]
        assert "SIDE 2nd" in row["relation_note"]
        assert "Narcissu2 音乐CD加本体一盒2盘" in row["xianyu"]["version_evidence"]
        assert row["xianyu"]["image_url"] is None
        assert row["wameiji"]["title"].find("SIDE 2nd") >= 0
        assert "图片可能与实物不同" in row["wameiji"]["version_evidence"]


def test_sample_15_marks_rewrite_items_as_related_when_condition_and_contents_are_not_proven_equal() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = [
        row
        for collection in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"])
        for row in collection
        if row["reference_product_id"] == 15
    ]

    assert len(rows) == 2
    for row in rows:
        assert row["same_product_verified"] is False
        assert "与闲鱼现候选成色不等价" in row["relation_note"]
        assert "不确认同SKU或利润机会" in row["relation_note"]
        wameiji = row["wameiji"]
        assert wameiji["state"] == "observed_current"
        assert wameiji["image_state"] == "observed_first_gallery_image"
        assert "配件逐项列" in wameiji["version_evidence"]
        assert "图片可能与实物不同" in wameiji["version_evidence"]
        xianyu = row["xianyu"]
        assert xianyu["state"] == "replacement_related"
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["image_url"] == "https://img.alicdn.com/bao/uploaded/i1/2213941510788/O1CN01IpWImVFsqhI1pITk_!!4611686018427380356-0-xy_item.jpg_Q90.jpg_.webp"
        assert "收纳盒" in xianyu["version_evidence"]
        assert "全新未拆、带原塑封”的状态不等价" in xianyu["version_evidence"]


def test_sample_16_confirms_same_album_but_not_comparable_condition_or_obi_completeness() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = [
        row
        for collection in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"])
        for row in collection
        if row["reference_product_id"] == 16
    ]

    assert len(rows) == 2
    for row in rows:
        assert row["same_product_verified"] is True
        assert "同一专辑方向" in row["relation_note"]
        assert "不作利润比较" in row["relation_note"]
        wameiji = row["wameiji"]
        assert wameiji["state"] == "observed_current"
        assert wameiji["price"] == 2000
        assert wameiji["image_state"] == "observed_first_gallery_image"
        assert "未测试播放" in wameiji["version_evidence"]
        assert "CD盒正面有划痕" in wameiji["version_evidence"]
        xianyu = row["xianyu"]
        assert xianyu["state"] == "replacement_related"
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["price"] == 120
        assert "未说明是否带obi" in xianyu["version_evidence"]


def test_sample_11_rechecks_current_xianyu_listing_and_current_wameiji() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_11 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 11)
    xianyu = sample_11["xianyu"]

    assert sample_11["same_product_verified"] is True
    assert "MGCG-1408" in sample_11["wameiji"]["version_evidence"]
    assert xianyu["source_url"] == "https://www.goofish.com/item?id=1022572554442&categoryId=126864811"
    assert xianyu["state"] == "observed_current"
    assert xianyu["price"] == 129
    assert xianyu["last_observed_price"] is None
    assert "盒子烂" in xianyu["version_evidence"]
    assert xianyu["image_state"] == "observed_main_image"
    assert xianyu["image_url"] == "https://img.alicdn.com/bao/uploaded/i4/3806490968/O1CN01akSR1b1J1OW0sRpFJ_!!4611686018427384152-0-xy_item.jpg_450x10000Q90.jpg_.webp"
    assert sample_11["wameiji"]["price"] == 1400
    assert sample_11["wameiji"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/ZDiem2N5o2hGr8jdxLj5VV.webp@jpg"


def test_sample_6_uses_matching_current_first_images_on_both_marketplaces() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        pair = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 6)
        assert pair["same_product_verified"] is True
        assert pair["wameiji"]["state"] == "observed_current"
        assert pair["wameiji"]["price"] == 4980
        assert pair["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "FRS001LE" in pair["wameiji"]["title"]
        assert pair["xianyu"]["state"] == "blocked"
        assert pair["xianyu"]["price"] is None
        assert pair["xianyu"]["last_observed_price"] == 264
        assert pair["xianyu"]["image_state"] == "observed_main_image"
        assert pair["xianyu"]["image_url"] == (
            "https://img.alicdn.com/bao/uploaded/i2/O1CN01GEquay1RHRLYVibNy_!!4611686018427383302-0-fleamarket.jpg_450x10000Q90.jpg_.webp"
        )
        if collection_name == "dual_found_pairs":
            assert "通用页脚" in pair["xianyu"]["version_evidence"]
        else:
            assert "跨境商品请前往闲鱼APP端查看" in pair["xianyu"]["version_evidence"]


def test_sample_53_refreshes_xianyu_after_previous_captcha_and_verifies_cover() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        sample_53 = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 53)
        xianyu = sample_53["xianyu"]
        wameiji = sample_53["wameiji"]

        assert sample_53["same_product_verified"] is True
        assert sample_53["price_comparable"] is False
        assert xianyu["source_url"] == "https://www.goofish.com/item?id=1080171737027&categoryId=126864811"
        assert xianyu["price"] == 168
        assert xianyu["last_observed_price"] is None
        assert xianyu["observed_at"] == "2026-09-26T21:08:00+08:00"
        assert xianyu["state"] == "observed_current"
        assert "当前168 CNY包邮" in xianyu["version_evidence"]
        assert "首图" in xianyu["version_evidence"]
        assert "204浏览" in xianyu["version_evidence"]
        assert "CD有细微毛痕" in xianyu["version_evidence"]
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["image_url"] == "https://img.alicdn.com/bao/uploaded/i2/1713419028/O1CN01E8jVKAJuh6I3thGS_!!4611686018427384596-0-xy_item.jpg_790x10000Q90.jpg_.webp"
        assert wameiji["state"] == "observed_current"
        assert wameiji["price"] == 7999
        assert wameiji["observed_at"] == "2026-09-26T21:08:00+08:00"
        assert "闲鱼当前168 CNY包邮" in sample_53["relation_note"]
        assert "Aimer" in sample_53["relation_note"]


def test_sample_1_keeps_unverified_tuyu_bonus_cd_as_related_not_same_product() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        sample_1 = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 1)

        assert sample_1["same_product_verified"] is False
        assert sample_1["wameiji"]["state"] == "observed_current"
        assert sample_1["wameiji"]["observed_at"] == "2026-09-26T19:46:46+08:00"
        assert sample_1["wameiji"]["title"] == "【中古】同人音楽CDソフト 貴方を不幸に誘いますね 特典CD ナツノカゼ御来光(TUYU arrange ver.) / ツユ"
        assert sample_1["wameiji"]["price"] == 2200
        assert sample_1["wameiji"]["image_state"] == "page_reference_image"
        assert sample_1["wameiji"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/DbAqk35jA64sCttyyaDpUN.webp@jpg"
        assert sample_1["xianyu"]["state"] == "not_currently_listed"
        assert sample_1["xianyu"]["last_observed_price"] == 100
        assert sample_1["xianyu"]["image_url"] is None
        assert "TUYU ツユ 2专 特典CD" in sample_1["xianyu"]["title"]
        assert "没有共同品番、曲目或附件证据证明是同一张特典CD" in sample_1["relation_note"]
        assert "不比较价格或利润" in sample_1["relation_note"]


def test_sample_80_matches_the_base_egoist_edition_but_not_the_bonus_bundle() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    row = next(item for item in snapshot["dual_observed_pairs"] if item["reference_product_id"] == 80)

    assert row["same_product_verified"] is True
    assert row["price_comparable"] is False
    assert row["wameiji"]["catalog_no"] == "VVCL-1148"
    assert row["xianyu"]["catalog_no"] is None
    assert "目录列明CD和Blu-ray曲目" in row["wameiji"]["version_evidence"]
    assert "狗牌" in row["xianyu"]["title"]
    assert "当前商品未列狗牌/卡片" in row["relation_note"]
    assert "不按完整套装比价或计算利润" in row["relation_note"]


def test_sample_82_reopened_meruki_listing_is_current_and_matches_2lp_model() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 82)
        wameiji = sample["wameiji"]
        assert sample["same_product_verified"] is True
        assert sample["price_comparable"] is False
        assert wameiji["state"] == "observed_current"
        assert wameiji["price"] == 6999
        assert wameiji["last_observed_price"] is None
        assert wameiji["source_url"] == "https://www.meruki.cn/mall/mercari/detail/68747470733a2f2f7777772e6d6572636172692e636f6d2f6a702f6974656d732f6d31353533313431393138352f"
        assert wameiji["image_state"] == "observed_first_gallery_image"
        assert wameiji["image_url"].startswith("https://imghk.doorzo.net/item/detail/orig/photos/m15531419185_1.jpg")
        assert "接近未使用" in wameiji["version_evidence"]
        assert "2张LP" in wameiji["version_evidence"]


def test_sample_104_refreshes_current_meruki_price_and_keeps_blocked_xianyu_historical() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 104)
        assert sample["same_product_verified"] is True
        assert sample["price_comparable"] is False
        assert sample["wameiji"]["state"] == "observed_current"
        assert sample["wameiji"]["price"] == 1580
        assert sample["wameiji"]["catalog_no"] == "SECL-1983〜1984"
        assert sample["wameiji"]["barcode"] == "4547557046267"
        assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample["wameiji"]["image_url"].startswith("https://imghk.doorzo.net/item/detail/orig/photos/m83659633620_1.jpg")
        assert sample["xianyu"]["state"] == "blocked"
        assert sample["xianyu"]["price"] is None
        assert sample["xianyu"]["last_observed_price"] == 261


def test_exact_catalog_and_barcode_matches_are_not_mislabeled_as_different_products() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    expected = {
        61: ("UPJY-9202/3", "4988031460023"),
        85: ("DFCL-2046", None),
        94: ("NAS-2164", "4988003660604"),
    }
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        rows = {row["reference_product_id"]: row for row in snapshot[collection]}
        for reference_id, (catalog_no, barcode) in expected.items():
            row = rows[reference_id]
            assert row["same_product_verified"] is True
            assert row["price_comparable"] is False
            assert row["wameiji"]["catalog_no"] == catalog_no
            assert row["xianyu"]["catalog_no"] == catalog_no
            if barcode is not None:
                assert row["wameiji"]["barcode"] == barcode
                assert row["xianyu"]["barcode"] == barcode


def test_round8_sample_relations_are_evidence_backed_and_never_auto_compare_profit() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    expected = {
        43: True,
        44: False,
        45: False,
        42: True,
        47: True,
        49: True,
        60: False,
        62: False,
        64: False,
        69: True,
        70: True,
        72: False,
        75: True,
        81: True,
        83: True,
        89: True,
        91: True,
        93: True,
        95: True,
        96: True,
        97: False,
        98: True,
        99: True,
        100: False,
        101: True,
        104: True,
        106: True,
        107: True,
        108: True,
        109: True,
        110: True,
        111: True,
        113: True,
        116: True,
        117: True,
        118: True,
        119: True,
        120: True,
        121: True,
        122: True,
        123: False,
        124: True,
    }
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        rows = {row["reference_product_id"]: row for row in snapshot[collection]}
        for reference_id, same_product in expected.items():
            if reference_id not in rows and collection == "dual_found_pairs":
                continue
            row = rows[reference_id]
            assert row["same_product_verified"] is same_product
            assert row["price_comparable"] is False
            assert row["relation_note"]

    sample_62 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 62)
    assert "12" in sample_62["xianyu"]["title"]
    assert "LP" in sample_62["xianyu"]["title"]
    assert "未证明欧洲版、黑胶或12英寸" in sample_62["relation_note"]
    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        sample_64 = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 64)
        assert sample_64["same_product_verified"] is False
        assert sample_64["price_comparable"] is False
        assert sample_64["wameiji"]["price"] == 1800
        assert sample_64["wameiji"]["state"] == "observed_current"
        assert sample_64["xianyu"]["price"] == 105
        assert sample_64["xianyu"]["state"] == "observed_current"
        assert sample_64["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample_64["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample_64["wameiji"]["observed_at"] == "2026-09-26T21:17:00+08:00"
        assert sample_64["xianyu"]["observed_at"] == "2026-09-26T21:17:00+08:00"
        sample_65 = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 65)
        assert sample_65["same_product_verified"] is False
        assert sample_65["price_comparable"] is False
        assert "带侧（腰封）" in sample_65["relation_note"]
        assert "不作为样本同款" in sample_65["xianyu"]["version_evidence"]
        assert sample_65["wameiji"]["state"] == "observed_current"
        assert sample_65["xianyu"]["state"] == "replacement_related"
        assert sample_65["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample_65["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample_65["wameiji"]["image_url"].startswith("https://image02.doorzo.net/item/detail/orig/photos/m70515766054_1.jpg")
        assert "O1CN01PDkdtw1joZ4H6xAkU" in sample_65["xianyu"]["image_url"]
        assert sample_65["wameiji"]["observed_at"] == "2026-09-26T21:25:00+08:00"
        assert sample_65["xianyu"]["observed_at"] == "2026-09-26T21:25:00+08:00"
    sample_44 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 44)
    assert "单张" in sample_44["relation_note"]
    assert "四张不同专辑CD合照" in sample_44["relation_note"]
    assert sample_44["xianyu"]["state"] == "blocked"
    assert sample_44["xianyu"]["price"] is None
    assert sample_44["xianyu"]["last_observed_price"] == 2000
    assert sample_44["wameiji"]["price"] == 17800
    assert "不比较价格或利润" in sample_44["relation_note"]
    sample_114 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 114)
    assert sample_114["same_product_verified"] is not True
    sample_115 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 115)
    assert sample_115["same_product_verified"] is None
    sample_124 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 124)
    assert sample_124["same_product_verified"] is True
    assert "构成数2" in sample_124["wameiji"]["version_evidence"]
    assert "构成数2" in sample_124["xianyu"]["version_evidence"]
    assert "SKU与盘数已对齐" in sample_124["relation_note"]


def test_explicit_catalog_identifiers_are_not_left_only_inside_free_text_evidence() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    expected_wameiji = {
        23: (None, "4988102218560"),
        42: ("PCCG1128", "4988013016569"),
        114: ("SRCL9567", "4547366329674"),
        119: ("DUED1223", "4589686422857"),
        120: (None, "4560429729075"),
        122: ("VVCL-1961", None),
    }
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        rows = {row["reference_product_id"]: row for row in snapshot[collection]}
        for reference_id, (catalog_no, barcode) in expected_wameiji.items():
            if reference_id not in rows and collection == "dual_found_pairs":
                continue
            assert rows[reference_id]["wameiji"]["catalog_no"] == catalog_no
            assert rows[reference_id]["wameiji"]["barcode"] == barcode


def test_sample_120_has_current_linked_images_and_keeps_unverified_accessories_out_of_profit() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 120)
        assert sample["same_product_verified"] is True
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["state"] == "observed_current"
        assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample["xianyu"]["image_url"].startswith("https://img.alicdn.com/bao/uploaded/")
        assert "18浏览" in sample["xianyu"]["version_evidence"]
        assert sample["wameiji"]["state"] == "observed_current"
        assert sample["wameiji"]["image_state"] == "page_reference_image"
        assert sample["wameiji"]["image_url"].startswith("https://imghk.doorzo.net/")
        assert sample["wameiji"]["barcode"] == "4560429729075"
        assert "商品图为样图" in sample["wameiji"]["version_evidence"]


def test_sample_121_has_current_same_cover_booklet_images_without_profit_claim() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 121)
        assert sample["same_product_verified"] is True
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["state"] == "observed_current"
        assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample["xianyu"]["image_url"].startswith("https://img.alicdn.com/bao/uploaded/")
        assert "560浏览" in sample["xianyu"]["version_evidence"]
        assert sample["wameiji"]["state"] == "observed_current"
        assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample["wameiji"]["image_url"].startswith("https://static.mercdn.net/item/detail/orig/photos/")
        assert "同为楪祈花田封面" in sample["wameiji"]["version_evidence"]


def test_sample_56_login_redirect_was_resolved_and_historical_labels_remain_available() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    sample_56 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 56)

    assert sample_56["same_product_verified"] is True
    assert sample_56["wameiji"]["state"] == "observed_current"
    assert sample_56["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert "登录/验证受阻 · 历史证据" in javascript
    assert "历史页面首图 · 当前链接受阻" in javascript
    assert "已售历史商品图 · 非当前在售图" in javascript
    assert "已售 · 历史挂牌价，仅作参考" in javascript


def test_blocked_and_sold_source_images_are_never_labeled_as_current() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    pairs = {row["reference_product_id"]: row for row in snapshot["dual_observed_pairs"]}

    # These notes document login redirects or pages that never loaded the product;
    # their retained images are historical evidence, not current listing photos.
    for sample_id in (74, 79, 84, 92, 94, 99, 103, 107, 111):
        source = pairs[sample_id]["wameiji"]
        assert source["state"] == "login_required", sample_id
        assert source["image_state"] == "historical_first_gallery_image", sample_id

    sold = pairs[77]["wameiji"]
    assert sold["state"] == "current_sold_image"
    assert sold["image_state"] == "current_sold_image"

    related = pairs[63]["wameiji"]
    assert related["state"] == "observed_related"
    assert related["image_state"] == "page_reference_image"
    assert related["price"] == 8038
    assert related["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/2JPiTHew9Ja2SEqC4HruTM.jpg@jpg"
    assert "航空禁运" in related["version_evidence"]
    assert "无物流保障" in related["version_evidence"]
    assert "特典/带/附件不保证" in related["version_evidence"]
    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        sample_63 = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 63)
        assert sample_63["same_product_verified"] is False
        assert sample_63["price_comparable"] is False
        assert sample_63["xianyu"]["state"] == "observed_current"
        assert sample_63["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample_63["xianyu"]["image_url"] == "https://img.alicdn.com/bao/uploaded/i4/4033685196/O1CN01Q8pOvf1oFp76BqsVT_!!4611686018427381452-0-xy_item.jpg_790x10000Q90.jpg_.webp"
        assert sample_63["wameiji"]["image_url"] == related["image_url"]
        assert sample_63["wameiji"]["observed_at"] == "2026-09-26T21:17:00+08:00"

    current_search_only = pairs[82]["wameiji"]
    assert current_search_only["state"] == "observed_current"
    assert current_search_only["image_state"] == "observed_first_gallery_image"

    for sample_id in (94, 100, 104):
        source = pairs[sample_id]["xianyu"]
        assert source["state"] == "blocked", sample_id
        assert source["image_state"] == "historical_first_gallery_image", sample_id

    current_sample_100 = pairs[100]["wameiji"]
    assert current_sample_100["state"] == "observed_current"
    assert current_sample_100["image_state"] == "page_reference_image"

    current_sample_98 = pairs[98]["wameiji"]
    assert current_sample_98["state"] == "observed_current"
    assert current_sample_98["price"] == 5600
    assert current_sample_98["image_state"] == "page_reference_image"

    sold_sample_101 = pairs[101]["wameiji"]
    assert sold_sample_101["state"] == "current_sold_image"
    assert sold_sample_101["image_state"] == "current_sold_image"

    current_sample_102 = pairs[102]["wameiji"]
    assert current_sample_102["state"] == "observed_current"
    assert current_sample_102["image_state"] == "page_reference_image"

    for sample_id, side in ((5, "xianyu"),):
        source = pairs[sample_id][side]
        assert source["state"] == "blocked", sample_id
        assert source["source_url"] == "https://www.goofish.com/item?id=1084719238003&categoryId=126860296"
        assert source["price"] is None
        assert source["last_observed_price"] == 9999
        assert source["image_url"].startswith("https://img.alicdn.com/bao/uploaded/i4/2209323678281/")
        assert source["image_state"] == "historical_first_gallery_image", sample_id
        assert "第一张主图直链" in source["version_evidence"]
        assert "附件和同版未核" in source["version_evidence"]
        assert "14:24再次打开时只呈现通用页脚" in source["version_evidence"]
        assert source["search_source_url"].startswith("https://www.goofish.com/search?")
        old_snapshot = next(row for row in snapshot["dual_found_pairs"] if row["reference_product_id"] == sample_id)
        assert old_snapshot[side] == source

    sample_106 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 106)
    assert sample_106["wameiji"]["state"] == "current_sold_image"
    assert sample_106["wameiji"]["image_state"] == "current_sold_image"
    assert sample_106["xianyu"]["state"] == "blocked"
    assert sample_106["xianyu"]["price"] is None
    assert sample_106["xianyu"]["last_observed_price"] == 85
    assert sample_106["xianyu"]["image_state"] == "historical_first_gallery_image"
    assert "滑块验证码" in sample_106["xianyu"]["version_evidence"]

    sample_28 = next(row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 28)
    assert sample_28["observation"]["state"] == "current_sold_image"
    assert sample_28["observation"]["image_state"] == "current_sold_image"

    sample_106 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 106)
    assert sample_106["wameiji"]["state"] == "current_sold_image"
    assert sample_106["wameiji"]["image_state"] == "current_sold_image"

    sample_28 = next(row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 28)
    assert sample_28["observation"]["state"] == "current_sold_image"
    assert sample_28["observation"]["image_state"] == "current_sold_image"

    source = pairs[13]["xianyu"]
    assert source["state"] == "observed_current"
    assert source["image_state"] == "observed_first_gallery_image"
    assert "配件清单" in source["version_evidence"]
    assert "不认定完整同款" in source["version_evidence"]


def test_sample_50_reopened_multi_option_listing_keeps_option_and_gallery_limits_explicit() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 50)

    assert sample["same_product_verified"] is False
    assert sample["price_comparable"] is False
    assert sample["xianyu"]["state"] == "observed_related"
    assert sample["xianyu"]["price"] is None
    assert sample["xianyu"]["last_observed_price"] == 98
    assert sample["xianyu"]["price_range"] is None
    assert sample["xianyu"]["observed_at"] == "2026-09-26T20:29:00+08:00"
    assert sample["xianyu"]["image_state"] == "multi_option_listing_image"
    assert sample["xianyu"]["source_url"] == "https://www.goofish.com/item?id=966395255268&categoryId=126864811"
    assert "100–120 CNY" in sample["xianyu"]["version_evidence"]
    assert "120 无册封 已出" in sample["xianyu"]["version_evidence"]
    assert "100–120 CNY" in sample["xianyu"]["version_evidence"]
    assert "703浏览" in sample["xianyu"]["version_evidence"]
    assert "20:29 内置浏览器重开闲鱼详情" in sample["xianyu"]["version_evidence"]
    assert "直接打开首图可见坐姿人物CD封面与参考样本相同" in sample["xianyu"]["version_evidence"]
    assert "当前闲鱼同款已售" in sample["relation_note"]
    assert sample["wameiji"]["state"] == "blocked"
    assert sample["wameiji"]["price"] is None
    assert sample["wameiji"]["last_observed_price"] is None
    assert sample["wameiji"]["source_url"] == sample["wameiji"]["search_source_url"]
    assert sample["wameiji"]["barcode"] is None
    assert sample["wameiji"]["image_url"] is None
    assert sample["wameiji"]["image_state"] == "no_verified_item_photo"
    assert sample["wameiji"]["observed_at"] == "2026-09-26T20:29:00+08:00"
    assert "商品链接实为TUYU特典CD" in sample["wameiji"]["version_evidence"]
    assert "未见样本歌曲“Flashback、春之雪、约束、闪现、花瓣”或相符封面" in sample["wameiji"]["version_evidence"]


def test_sample_87_replacement_xianyu_box_set_is_live_but_not_comparable_to_disc_only_meruki() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 87)

    assert sample.get("same_product_verified") is not True
    assert sample["xianyu"]["state"] == "observed_current"
    assert sample["xianyu"]["price"] == 550
    assert sample["xianyu"]["last_observed_price"] is None
    assert sample["xianyu"]["source_url"].endswith("id=990083056936&categoryId=126864806")
    assert sample["xianyu"]["observed_at"] == "2026-09-26T22:50:00+08:00"
    assert sample["xianyu"]["image_url"].endswith("O1CN01RfDqaN1bJP9Mjslff_!!4611686018427384756-0-fleamarket.jpg_790x10000Q90.jpg_.webp")
    assert "不声称为原始卖家的同一件实物" in sample["xianyu"]["version_evidence"]
    assert sample["wameiji"]["price"] == 2610
    assert sample["wameiji"]["state"] == "observed_related"
    assert sample["wameiji"]["observed_at"] == "2026-09-26T22:50:00+08:00"
    assert sample["wameiji"]["image_state"] == "page_reference_image"
    assert "无外盒/歌词卡" in sample["wameiji"]["version_evidence"]


def test_sample_114_reopened_pair_drops_dead_xianyu_image_and_unseen_catalog_fields() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 114)

    assert sample.get("same_product_verified") is not True
    assert sample["xianyu"]["state"] == "blocked"
    assert sample["xianyu"]["price"] is None
    assert sample["xianyu"]["last_observed_price"] == 499
    assert sample["xianyu"]["observed_at"] == "2026-09-26T04:18:00+08:00"
    assert sample["xianyu"]["catalog_no"] is None
    assert sample["xianyu"]["barcode"] is None
    assert sample["xianyu"]["image_url"] is None
    assert sample["xianyu"]["image_state"] == "no_verified_item_photo"
    assert "滑块验证码" in sample["xianyu"]["version_evidence"]
    assert "1×1空白图" in sample["xianyu"]["version_evidence"]
    assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert sample["wameiji"]["price"] == 5197
    assert sample["wameiji"]["observed_at"] == "2026-09-26T02:00:00+08:00"


def test_multi_option_xianyu_ranges_are_structured_and_use_the_listed_lower_bound() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    expected_ranges = {
        48: (180, 550),
        59: (177, 233),
        75: (427, 549),
        77: (199, 333),
        84: (218, 228),
        89: (248, 2800),
        98: (255, 309),
        109: (351, 480),
        110: (175, 375),
        111: (550, 580),
        117: (119, 169),
    }

    for sample_id, (minimum, maximum) in expected_ranges.items():
        copies = [
            row
            for collection in ("dual_found_pairs", "dual_observed_pairs")
            for row in snapshot[collection]
            if row["reference_product_id"] == sample_id
        ]
        assert copies, sample_id
        for sample in copies:
            if sample["xianyu"].get("state") == "blocked":
                assert sample["xianyu"]["price"] is None, sample_id
                assert sample["xianyu"]["last_observed_price"] == minimum, sample_id
            elif sample_id in (89, 109, 117):
                assert sample["xianyu"]["price"] is None, sample_id
            else:
                assert sample["xianyu"]["price"] == minimum, sample_id
            assert sample["xianyu"]["price_range"] == {
                "min": minimum,
                "max": maximum,
                "currency": "CNY",
            }, sample_id


def test_reference_audit_snapshot_timestamp_is_not_older_than_its_observations() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    generated_at = datetime.fromisoformat(snapshot["generated_at"])
    observed_at = [
        datetime.fromisoformat(source["observed_at"])
        for collection in ("dual_found_pairs", "dual_observed_pairs", "single_observed_records", "unavailable_records")
        for row in snapshot[collection]
        for source in (row.get("xianyu"), row.get("wameiji"))
        if source and source.get("observed_at")
    ]

    assert observed_at
    assert generated_at >= max(observed_at)


def test_sample_5_wameiji_evidence_matches_the_linked_sakura_no_uta_listing() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = [
        row
        for collection in ("dual_found_pairs", "dual_observed_pairs")
        for row in snapshot[collection]
        if row["reference_product_id"] == 5
    ]

    assert len(rows) == 2
    for row in rows:
        assert row["same_product_verified"] is False
        item = row["wameiji"]
        assert "サクラノ詩" in item["title"]
        assert "サクラノ詩" in item["version_evidence"]
        assert "ハミダシクリエイティブ" not in item["version_evidence"]
        assert item["price"] == 19410
        assert "加入购物车" in item["version_evidence"]


def test_sample_66_replaces_sold_wameiji_item_with_the_live_matching_catalog_number() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 66)
        assert sample["same_product_verified"] is False
        assert sample["wameiji"]["title"] == "【中古】アニメ系CD 初音ミク / Winterland’s Anthology"
        assert sample["wameiji"]["catalog_no"] == "KRCD-0011"
        assert sample["wameiji"]["price"] == 15700
        assert sample["wameiji"]["state"] == "observed_current"
        assert sample["wameiji"]["image_state"] == "page_reference_image"
        assert sample["wameiji"]["observed_at"] == "2026-09-26T21:29:00+08:00"
        assert sample["wameiji"]["image_url"] == (
            "https://assets.mercari-shops-static.com/-/large/plain/eYJdde7pUJUvjnyPn8ouxd.webp@jpg"
        )
        assert "加入购物车/立即购买" in sample["wameiji"]["version_evidence"]
        assert "五选一合集" in sample["xianyu"]["version_evidence"]
        assert "7人想要/605浏览" in sample["xianyu"]["version_evidence"]
        assert sample["xianyu"]["price"] is None
        assert sample["xianyu"]["state"] == "observed_current"
        assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample["xianyu"]["observed_at"] == "2026-09-26T21:29:00+08:00"
        assert sample["xianyu"]["image_url"].endswith("O1CN01W4vsVQnJNBI3thGS_!!4611686018427387341-0-xy_item.jpg_790x10000Q90.jpg_.webp")
        assert "不把239 CNY当作本选项价格" in sample["relation_note"]


def test_sample_67_refreshes_live_pages_and_keeps_disc_count_unverified() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 67)
        assert sample["same_product_verified"] is False
        assert sample["price_comparable"] is False
        assert sample["wameiji"]["catalog_no"] == "YKS-001"
        assert sample["wameiji"]["state"] == "observed_current"
        assert sample["wameiji"]["image_state"] == "page_reference_image"
        assert sample["wameiji"]["image_url"].endswith("QyHirHFi87A5gPpevSzAhZ.webp@jpg")
        assert "压制CD+附属压制DVD共2枚" in sample["wameiji"]["version_evidence"]
        assert sample["xianyu"]["state"] == "observed_current"
        assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample["xianyu"]["image_url"].endswith("O1CN01AFJdhl1dU3cLxy9CX_!!4611686018427383946-53-xy_item.heic_790x10000Q90.jpg_.webp")
        assert "未列型番、盘数或附件清单" in sample["xianyu"]["version_evidence"]
        assert sample["wameiji"]["observed_at"] == "2026-09-26T21:32:00+08:00"
        assert sample["xianyu"]["observed_at"] == "2026-09-26T21:32:00+08:00"


def test_sample_68_keeps_unavailable_exact_listing_separate_from_related_items() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["unavailable_records"] if row["reference_product_id"] == 68)
    assert sample["wameiji_state"] == "not_currently_listed"
    assert sample["xianyu_state"] == "not_currently_listed"
    assert sample["wameiji"]["state"] == "observed_related"
    assert sample["wameiji"]["price"] == 800
    assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert sample["wameiji"]["image_url"].endswith("m94075439530_1.jpg?1769258162")
    assert sample["xianyu"]["state"] == "observed_related"
    assert sample["xianyu"]["price"] == 60
    assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert sample["xianyu"]["image_url"].endswith(
        "O1CN01kSgGjY2CRm9YAmq3y_!!4611686018427385159-53-fleamarket.heic_790x10000Q90.jpg_.webp"
    )
    assert sample["wameiji"]["observed_at"] == "2026-09-26T21:38:00+08:00"
    assert sample["xianyu"]["observed_at"] == "2026-09-26T21:38:00+08:00"
    assert "不是样本中的签名海报+卡片套组" in sample["wameiji"]["version_evidence"]
    assert "不是样本中的签名海报+卡片套组" in sample["xianyu"]["version_evidence"]


def test_sample_69_refreshes_live_counts_and_full_resolution_first_image() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 69)
    assert sample["same_product_verified"] is True
    assert sample["price_comparable"] is False
    assert sample["xianyu"]["price"] is None
    assert sample["xianyu"]["price_range"] == {"min": 329, "max": 389, "currency": "CNY"}
    assert "34人想要/859浏览" in sample["xianyu"]["version_evidence"]
    assert sample["xianyu"]["state"] == "observed_current"
    assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert sample["xianyu"]["image_url"].endswith(
        "O1CN0105T6enGPGzD37MJM_!!4611686018427385545-2-xy_item.png_790x10000.jpg_.webp"
    )
    assert sample["wameiji"]["price"] == 6600
    assert sample["wameiji"]["image_state"] == "page_reference_image"
    assert "不代表卖家实拍" in sample["wameiji"]["version_evidence"]
    assert sample["xianyu"]["observed_at"] == "2026-09-26T21:38:26+08:00"
    assert sample["wameiji"]["observed_at"] == "2026-09-26T21:38:26+08:00"


def test_sample_70_refreshes_both_sources_and_does_not_assume_sample_attachments() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 70)
    assert sample["same_product_verified"] is True
    assert sample["price_comparable"] is False
    assert sample["wameiji"]["catalog_no"] == "VVCL-1225"
    assert sample["wameiji"]["price"] == 1087
    assert sample["wameiji"]["image_state"] == "page_reference_image"
    assert sample["wameiji"]["image_url"].endswith("2JWm7dwSqQa2MTSts4vsQj.webp@jpg")
    assert sample["xianyu"]["price"] == 81
    assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert sample["xianyu"]["image_url"].endswith(
        "O1CN01qONTEa21Ch9UWSwcP_!!53-fleamarket.heic_790x10000Q90.jpg_.webp"
    )
    for side in ("wameiji", "xianyu"):
        assert sample[side]["state"] == "observed_current"
        assert sample[side]["observed_at"] == "2026-09-26T21:41:00+08:00"
    assert "写真册、特装盒和随机特典明信片" in sample["xianyu"]["version_evidence"]
    assert "中古商品不保证" in sample["wameiji"]["version_evidence"]


def test_sample_71_rechecks_and_keeps_dvd_and_bluray_as_different_versions() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 71)
    assert sample["same_product_verified"] is False
    assert sample["price_comparable"] is False
    assert sample["wameiji"]["price"] == 11000
    assert sample["wameiji"]["state"] == "replacement_current"
    assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert sample["wameiji"]["image_url"].endswith("m79559114267_1.jpg?1790083987")
    assert sample["xianyu"]["price"] == 699
    assert sample["xianyu"]["state"] == "observed_current"
    assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert sample["xianyu"]["image_url"].endswith(
        "O1CN01sEDdXVtbZCI70gAX_!!4611686018427385545-0-xy_item.jpg_790x10000Q90.jpg_.webp"
    )
    assert "11,000 JPY" in sample["wameiji"]["version_evidence"]
    assert "CD+2DVD" in sample["wameiji"]["version_evidence"]
    assert "CD+2Blu-ray" in sample["xianyu"]["version_evidence"]


def test_sample_72_refreshes_standard_edition_and_multi_option_listing_photo() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 72)
    assert sample["same_product_verified"] is False
    assert sample["price_comparable"] is False
    assert sample["wameiji"]["price"] == 3200
    assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert sample["wameiji"]["image_url"].endswith("m67553121806_1.jpg?1789991547")
    assert sample["xianyu"]["price"] == 185
    assert sample["xianyu"]["price_range"] == {"min": 185, "max": 670, "currency": "CNY"}
    assert sample["xianyu"]["image_url"].endswith(
        "O1CN01HxX2RwiNNSJ3thGS_!!4611686018427385863-0-xy_item.jpg_790x10000Q90.jpg_.webp"
    )
    assert "15人想要/603浏览" in sample["xianyu"]["version_evidence"]
    assert "通常盘和初回蓝光盘并列实拍" in sample["xianyu"]["version_evidence"]


def test_sample_53_keeps_both_live_sources_after_recheck() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 53)
        assert sample["same_product_verified"] is True
        assert sample["xianyu"]["price"] == 168
        assert sample["xianyu"]["last_observed_price"] is None
        assert sample["xianyu"]["observed_at"] == "2026-09-26T21:08:00+08:00"
        assert sample["xianyu"]["state"] == "observed_current"
        assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample["wameiji"]["price"] == 7999
        assert sample["wameiji"]["observed_at"] == "2026-09-26T21:08:00+08:00"
        assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample["xianyu"]["image_url"] == (
            "https://img.alicdn.com/bao/uploaded/i2/1713419028/"
            "O1CN01E8jVKAJuh6I3thGS_!!4611686018427384596-0-xy_item.jpg_790x10000Q90.jpg_.webp"
        )
        assert "2026-09-26 21:08 内置浏览器重开闲鱼原详情" in sample["xianyu"]["version_evidence"]


def test_samples_23_to_25_refresh_current_status_and_preserve_match_limits() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        rows = {row["reference_product_id"]: row for row in snapshot[collection]}

        candidate = rows[23]
        assert candidate["same_product_verified"] is True
        assert candidate["xianyu"]["price"] is None
        assert candidate["xianyu"]["last_observed_price"] == 60
        assert candidate["xianyu"]["observed_at"] == "2026-09-26T05:30:00+08:00"
        assert candidate["xianyu"]["state"] == "blocked"
        assert candidate["xianyu"]["image_url"] is None
        assert candidate["xianyu"]["image_state"] == "first_gallery_image_link_unverified"
        assert "候选¥60" in candidate["xianyu"]["version_evidence"]
        assert "05:30重开原详情" in candidate["xianyu"]["version_evidence"]
        assert "滑块验证" in candidate["xianyu"]["version_evidence"]
        assert "JAN" in candidate["wameiji"]["version_evidence"]
        assert candidate["wameiji"]["state"] == "observed_current"
        assert candidate["wameiji"]["image_state"] == "page_reference_image"
        assert "JAN 4988102218560" in candidate["wameiji"]["version_evidence"]

        uncertain = rows[24]
        assert uncertain["same_product_verified"] is False
        assert uncertain["xianyu"]["price"] == 283
        assert uncertain["xianyu"]["state"] == "observed_current"
        assert uncertain["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert uncertain["wameiji"]["price"] == 4800
        assert "3CD" in uncertain["relation_note"]
        assert "不比较价差或利润" in uncertain["relation_note"]

        limited_box = rows[25]
        assert limited_box["same_product_verified"] is False
        assert limited_box["xianyu"]["price"] == 710
        assert limited_box["wameiji"]["price"] == 9000
        assert limited_box["xianyu"]["state"] == "observed_current"
        assert limited_box["wameiji"]["state"] == "observed_current"
        assert "不把未拆和腕章已展示当成等价状态" in limited_box["relation_note"]


def test_sample_51_current_links_and_first_images_match_fate_vita_limited_set() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 51)
        assert sample["same_product_verified"] is True
        assert sample["wameiji"]["price"] == 2980
        assert sample["xianyu"]["price"] == 240
        assert sample["wameiji"]["image_url"] == (
            "https://assets.mercari-shops-static.com/-/large/plain/"
            "2JNgeB5ghSc3jU2wJ7NMvh.jpg@jpg"
        )
        assert "268浏览" in sample["xianyu"]["version_evidence"]


def test_sample_52_current_yorushika_links_keep_condition_mismatch_explicit() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 52)
        assert sample["same_product_verified"] is True
        assert sample["wameiji"]["price"] == 30000
        assert sample["xianyu"]["price"] == 480
        assert "935浏览" in sample["xianyu"]["version_evidence"]
        assert "闲鱼有损、挖煤姬标未使用" in sample["xianyu"]["version_evidence"]
        assert sample["xianyu"]["image_url"].endswith(".webp")


def test_sample_57_removes_wrong_pokemon_match_and_keeps_only_verified_related_listing() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample = next(row for row in rows if row["reference_product_id"] == 57)
        assert sample["same_product_verified"] is False
        assert "\u7f57\u5c0f\u9ed1\u6218\u8bb02" in sample["relation_note"]

        wameiji = sample["wameiji"]
        assert "\u7f85\u5c0f\u9ed2\u6226\u8a18\uff12" in wameiji["title"]
        assert wameiji["price"] == 15895
        assert "当前15,895 JPY" in wameiji["version_evidence"]
        assert wameiji["state"] == "observed_related"
        assert "rakuten/detail" in wameiji["source_url"]
        assert "image03.doorzo.net/tshopr10sjp/sproutsllc" in wameiji["image_url"]
        assert "\u5b9d\u53ef\u68a6" not in wameiji["title"]

        xianyu = sample["xianyu"]
        assert xianyu["price"] is None
        assert xianyu["image_url"] is None
        assert xianyu["image_state"] == "no_verified_item_photo"
        assert xianyu["state"] == "not_currently_listed"
        assert "goofish.com/search" in xianyu["source_url"]
        assert "\u5b9d\u53ef\u68a6" not in xianyu["title"]


def test_sample_58_lisa_listing_does_not_claim_unverified_edition_a_match() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample = next(row for row in rows if row["reference_product_id"] == 58)
        assert sample["same_product_verified"] is False
        assert sample["wameiji"]["catalog_no"] == "VVCL-1703"
        assert sample["wameiji"]["price"] == 1111
        assert sample["xianyu"]["price"] == 145
        assert "53浏览" in sample["xianyu"]["version_evidence"]
        assert "未显示A版字样或VVCL-1703" in sample["xianyu"]["version_evidence"]
        assert "不确认同SKU" in sample["relation_note"]


def test_sample_22_uses_current_moon_box_related_xianyu_listing_without_claiming_full_match() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_13 = next(row for row in rows if row["reference_product_id"] == 13)
        sample_22 = next(row for row in rows if row["reference_product_id"] == 22)
        assert sample_22["same_product_verified"] is False
        assert sample_22["reference_image_url"].endswith("22-f1e63661cafe1b24.webp")
        wameiji = sample_22["wameiji"]
        assert wameiji["price"] is None
        assert wameiji["image_url"] is None
        assert wameiji["image_state"] == "reference_only"
        assert wameiji["state"] == "blocked"
        assert "/search" in wameiji["source_url"]
        assert "TYPE-MOON%20%E6%9C%88%E7%AE%B1" in wameiji["search_source_url"]
        assert "月姫PLUS+DISC/歌月十夜" in wameiji["version_evidence"]
        assert "不能证明是样本所需完整月箱" in wameiji["version_evidence"]
        assert wameiji["source_url"] != sample_13["wameiji"]["source_url"]

        xianyu = sample_22["xianyu"]
        assert xianyu["price"] == 2188
        assert xianyu["currency"] == "CNY"
        assert xianyu["image_url"].startswith("https://img.alicdn.com/bao/uploaded/")
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["state"] == "observed_current"
        assert "/item?" in xianyu["source_url"]
        assert "完整附件待核" in xianyu["title"]
        assert "立即购买" in xianyu["version_evidence"]
        assert "265浏览" in xianyu["version_evidence"]


def test_sample_13_removes_wrong_unavailable_wameiji_candidate() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))

    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_13 = next(row for row in rows if row["reference_product_id"] == 13)
        wameiji = sample_13["wameiji"]
        xianyu = sample_13["xianyu"]
        assert wameiji["title"] == "挖煤姬未找到《月箱》三件套同款现货"
        assert wameiji["state"] == "not_currently_listed"
        assert wameiji["price"] is None
        assert wameiji["last_observed_price"] is None
        assert wameiji["observed_at"] == "2026-09-26T18:49:00+08:00"
        assert wameiji["image_state"] == "no_verified_item_photo"
        assert wameiji["image_url"] is None
        assert "%E6%9C%88%E7%AE%B1%20TYPE-MOON" in wameiji["search_source_url"]
        assert "%E6%9C%88%E7%AE%B1%20CD" in wameiji["source_url"]
        assert "website=rakuten" in wameiji["rakuten_search_source_url"]
        assert sample_13["same_product_verified"] is False
        assert xianyu["title"] == "月姬 月箱 TYPE-MOON同人合集"
        assert xianyu["price"] == 2300
        assert xianyu["state"] == "observed_current"
        assert xianyu["observed_at"] == "2026-09-26T18:49:00+08:00"
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["image_url"].startswith("https://img.alicdn.com/bao/uploaded/")
        assert "配件清单" in xianyu["version_evidence"]
        assert "192浏览" in xianyu["version_evidence"]


def test_sample_28_does_not_match_a_pc_game_cdrom_to_two_printed_novels() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_28 = next(
        row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 28
    )

    assert sample_28["observation"]["image_state"] == "current_sold_image"
    assert "C83场贩小说" in sample_28["observation"]["title"]
    wameiji = sample_28["wameiji"]
    assert "未找到匹配商品" in wameiji["title"]
    assert "/search?" in wameiji["source_url"]
    assert wameiji["price"] is None
    assert wameiji["image_url"] is None
    assert wameiji["image_state"] == "reference_only"
    assert wameiji["state"] == "blocked"
    assert "PC游戏/附原声CD-ROM" in wameiji["version_evidence"]
    assert sample_28["reference_image_url"].endswith("28-efd530b47e5f58a4.webp")


def test_sample_26_removes_unrelated_artbook_and_labels_search_only_evidence() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    sample = next(row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 26)

    assert sample["counterpart_state"] == "not_currently_listed"
    assert "wameiji" not in sample
    assert sample["observation"]["state"] == "observed_current"
    assert sample["observation"]["image_state"] == "observed_first_gallery_image"
    assert sample["observation"]["price"] == 36.4
    assert sample["observation"]["source_url"].endswith("id=1027107076352&categoryId=202029302")
    assert "不确认同一版次" in sample["observation"]["version_evidence"]

    candidate = sample["counterpart_candidate"]
    assert candidate["state"] == "search_only"
    assert candidate["source_url"] == (
        "https://www.meruki.cn/search?keywords="
        "%E3%83%A8%E3%82%B9%E3%82%AC%E3%83%8E%E3%82%BD%E3%83%A9+%E7%94%BB%E9%9B%86"
    )
    assert candidate["price"] is None
    assert candidate["image_url"] is None
    assert "《ゴッドイーター》" in candidate["version_evidence"]
    assert "空之境界" in candidate["version_evidence"]
    assert "当前未找到可核验同款商品页" in javascript
    assert "searchOnlyCandidate" in javascript


def test_sample_27_removes_unverified_xianyu_pair_and_keeps_both_evidence_links() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    sample = next(row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 27)

    assert sample["counterpart_state"] == "not_currently_listed"
    assert "xianyu" not in sample
    assert sample["observation"]["state"] == "observed_current"
    assert sample["observation"]["price"] == 4980
    assert sample["observation"]["image_state"] == "observed_first_gallery_image"
    assert "活动中" in sample["observation"]["version_evidence"]
    candidate = sample["counterpart_candidate"]
    assert candidate["state"] == "search_only"
    assert "没有找到" in candidate["version_evidence"]
    assert candidate["price"] is None
    assert candidate["image_url"] is None
    assert candidate["image_state"] == "reference_only"
    assert candidate["source_url"] == (
        "https://www.goofish.com/search?q="
        "%E5%B0%91%E5%A5%B3%E9%A2%86%E5%9F%9F%20%E5%B9%BF%E6%92%AD%E5%89%A7%20CD%20vol.10"
    )
    assert candidate["detail_source_url"].endswith("id=1022550203177&categoryId=126862148")
    assert "打开原样本详情页（当前网页端不可核验）" in javascript


def test_sample_35_keeps_distinct_innocent_grey_candidates_as_non_comparable_observations() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = {row["reference_product_id"]: row for row in snapshot["dual_observed_pairs"]}
    sample_29 = rows[29]
    sample_35 = rows[35]

    assert sample_35["same_product_verified"] is False
    assert sample_35["price_comparable"] is False
    assert "FLOWERS" in sample_35["wameiji"]["title"]
    assert sample_35["wameiji"]["source_url"].startswith("https://www.meruki.cn/mall/mercari/detail/")
    assert "/search?" in sample_35["wameiji"]["search_source_url"]
    assert sample_35["wameiji"]["price"] == 4252
    assert sample_35["wameiji"]["image_url"].startswith("https://assets.mercari-shops-static.com/")
    assert sample_35["wameiji"]["image_state"] == "page_reference_image"
    assert sample_35["wameiji"]["state"] == "observed_related"
    assert "白雪" in sample_35["xianyu"]["title"]
    assert sample_35["xianyu"]["source_url"].endswith("id=1079328133819&categoryId=126860296")
    assert "/search?" in sample_35["xianyu"]["search_source_url"]
    assert sample_35["xianyu"]["price"] is None
    assert sample_35["xianyu"]["last_observed_price"] == 430
    assert sample_35["xianyu"]["image_url"].startswith("https://img.alicdn.com/")
    assert sample_35["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert sample_35["xianyu"]["state"] == "blocked"
    assert sample_35["reference_image_url"].endswith("35-e614e34d2690d0fa.webp")
    assert sample_35["wameiji"]["source_url"] != sample_29["wameiji"]["source_url"]


def test_unmatched_samples_are_counted_as_currently_unavailable_in_pair_summary() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    match = re.search(r"const unavailablePattern = /([^/\n]+)/;", javascript)
    assert match is not None
    unavailable_pattern = re.compile(match.group(1))
    rows = {row["reference_product_id"]: row for row in snapshot["dual_observed_pairs"]}

    row_22 = rows[22]
    assert row_22["wameiji"]["state"] == "blocked"
    assert row_22["xianyu"]["state"] == "observed_current"
    assert unavailable_pattern.search(row_22["wameiji"]["version_evidence"])

    row_35 = rows[35]
    assert row_35["wameiji"]["state"] == "observed_related"
    assert row_35["xianyu"]["state"] == "blocked"
    assert "不比较利润" in row_35["wameiji"]["version_evidence"]
    assert unavailable_pattern.search(row_35["xianyu"]["version_evidence"])


def test_sample_54_current_listings_and_mismatched_first_image_are_disclosed() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        row = next(row for row in rows if row["reference_product_id"] == 54)
        assert row["same_product_verified"] is True
        assert row["wameiji"]["price"] == 6480
        assert row["xianyu"]["price"] == 320
        assert row["wameiji"]["image_url"] == "https://static.mercdn.net/item/detail/orig/photos/m45167830585_1.jpg"
        assert row["xianyu"]["image_url"] == "https://img.alicdn.com/bao/uploaded/i2/2211904345937/O1CN01Ny4P0cPJ1pI37rd6_!!4611686018427385681-0-xy_item.jpg_Q90.jpg_.webp"
        assert row["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert row["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "仍可加入购物车/立即购买" in row["wameiji"]["version_evidence"]
        assert "291浏览" in row["xianyu"]["version_evidence"]
        assert "人物插图" in row["wameiji"]["version_evidence"]
        assert "图片不作为同款实物证明" in row["relation_note"]


def test_sample_55_does_not_assign_one_price_or_real_item_photo_to_uncertain_variants() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection, rows in (("dual_found_pairs", snapshot["dual_found_pairs"]), ("dual_observed_pairs", snapshot["dual_observed_pairs"])):
        row = next(row for row in rows if row["reference_product_id"] == 55)
        assert row["xianyu"]["price"] is None
        assert "¥228–350" in row["xianyu"]["version_evidence"]
        assert row["xianyu"]["image_state"] == (
            "historical_first_gallery_image"
            if collection == "dual_found_pairs"
            else "observed_first_gallery_image"
        )
        assert row["wameiji"]["image_state"] == "page_reference_image"
        assert "首图仅为示例" in row["wameiji"]["version_evidence"]
        assert "不能确认具体版本" in row["relation_note"]
        assert "不能用挖煤姬示例图证明实物" in row["relation_note"]


def test_sample_56_current_krrc6_pair_preserves_accessory_difference() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    row = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 56)
    assert row["same_product_verified"] is True
    assert row["wameiji"]["price"] == 17000
    assert row["wameiji"]["state"] == "observed_current"
    assert row["wameiji"]["image_state"] == "observed_first_gallery_image"
    assert row["xianyu"]["price"] == 1800
    assert row["xianyu"]["state"] == "observed_current"
    assert row["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert "附件/品相不等价" in row["relation_note"]


def test_sample_6_does_not_publish_a_secondary_gallery_photo_as_the_main_image() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_6 = next(row for row in rows if row["reference_product_id"] == 6)
        assert sample_6["same_product_verified"] is True
        assert sample_6["price_comparable"] is False
        assert sample_6["wameiji"]["state"] == "observed_current"
        assert sample_6["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample_6["wameiji"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/2JTfUARaCv7LsoHBBXwMxD.jpg@jpg"
        assert sample_6["xianyu"]["state"] == "blocked"
        assert sample_6["xianyu"]["price"] is None
        assert sample_6["xianyu"]["last_observed_price"] == 264
        assert sample_6["xianyu"]["image_url"].startswith("https://img.alicdn.com/bao/uploaded/i2/")
        assert sample_6["xianyu"]["image_state"] == "observed_main_image"
    current_sample_6 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 6)
    assert current_sample_6["xianyu"]["observed_at"] == "2026-09-26T17:47:00+08:00"
    assert "跨境商品请前往闲鱼APP端查看" in current_sample_6["xianyu"]["version_evidence"]
    assert "直接打开闲鱼候选首图直链" in current_sample_6["xianyu"]["version_evidence"]
    assert "四角色外盒，与参考样本封面相符" in current_sample_6["xianyu"]["version_evidence"]
    assert "¥264仅为上次搜索卡末次观察价" in current_sample_6["xianyu"]["version_evidence"]


def test_sample_7_refreshes_live_xianyu_and_removes_wrong_seller_info_image() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_7 = next(row for row in snapshot["single_observed_records"] if row["reference_product_id"] == 7)
    assert sample_7["observation"]["state"] == "observed_current"
    assert sample_7["observation"]["price"] == 126.8
    assert sample_7["observation"]["observed_at"] == "2026-09-26T15:33:00+08:00"
    assert sample_7["observation"]["image_url"] is None
    assert sample_7["observation"]["image_state"] == "no_verified_item_photo"
    assert "卖家介绍/¥1说明图，并非此商品首图" in sample_7["observation"]["version_evidence"]
    assert sample_7["wameiji"]["state"] == "current_sold_image"
    assert sample_7["wameiji"]["image_state"] == "current_sold_image"
    assert sample_7["wameiji"]["image_url"] == "https://image03.doorzo.net/item/detail/orig/photos/m91159547197_1.jpg"


def test_sample_33_uses_each_listing_first_gallery_image_not_another_gallery_photo() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_33 = next(row for row in rows if row["reference_product_id"] == 33)
        assert sample_33["same_product_verified"] is False
        assert sample_33["price_comparable"] is False
        assert sample_33["xianyu"]["state"] == "observed_current"
        assert sample_33["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample_33["wameiji"]["state"] == "observed_related"
        assert sample_33["wameiji"]["image_state"] == "page_reference_image"
        assert "不能证明是同一游戏/版本" in sample_33["relation_note"]
        assert sample_33["xianyu"]["image_url"].endswith("O1CN012tbsvy1d0HoMvNcdc_!!4611686018427383289-53-fleamarket.heic_790x10000Q90.jpg_.webp")
        assert sample_33["wameiji"]["image_url"] == "https://imghk.doorzo.net/item/detail/orig/photos/m32301324782_1.jpg?1643898636"
        assert "thumb/item/webp" not in sample_33["wameiji"]["image_url"]


def test_sample_17_separates_related_xianyu_listing_and_verifies_wameiji_first_image() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_17 = next(row for row in rows if row["reference_product_id"] == 17)
        assert sample_17["same_product_verified"] is False
        assert sample_17["xianyu"]["source_url"].endswith("id=859421708400&categoryId=126860296")
        assert sample_17["xianyu"]["price"] == 600
        assert sample_17["xianyu"]["state"] == "observed_related"
        assert sample_17["xianyu"]["observed_at"] == "2026-09-26T16:09:00+08:00"
        assert "2,255浏览" in sample_17["xianyu"]["version_evidence"]
        assert "闲鱼当前ID 859421708400实际为泛称《Narcissu2》" in sample_17["relation_note"]
        assert sample_17["xianyu"]["image_url"] is None
        assert sample_17["xianyu"]["image_state"] == "first_gallery_image_link_unverified"
        assert "995592593200" not in sample_17["xianyu"]["source_url"]
        assert "展示/非卖品/拍下不发" in sample_17["relation_note"]
        assert sample_17["wameiji"]["price"] == 13800
        assert sample_17["wameiji"]["state"] == "observed_current"
        assert sample_17["wameiji"]["observed_at"] == "2026-09-26T16:09:00+08:00"
        assert "图片可能与实物不同" in sample_17["wameiji"]["version_evidence"]
        assert sample_17["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample_17["wameiji"]["image_url"].startswith("https://imghk.doorzo.net/-/large/plain/")
        assert "不比较价差或利润" in sample_17["relation_note"]
        assert "SIDE 2nd" in sample_17["relation_note"]


def test_sample_23_keeps_search_price_historical_when_detail_is_captcha_blocked() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_23 = next(row for row in rows if row["reference_product_id"] == 23)
        xianyu = sample_23["xianyu"]
        assert xianyu["source_url"].endswith("id=1057452820190&categoryId=126860296")
        assert xianyu["price"] is None
        assert xianyu["last_observed_price"] == 60
        assert xianyu["observed_at"] == "2026-09-26T05:30:00+08:00"
        assert xianyu["state"] == "blocked"
        assert "候选¥60" in xianyu["version_evidence"]
        assert "05:30重开原详情" in xianyu["version_evidence"]
        assert "滑块验证" in xianyu["version_evidence"]
        assert xianyu["image_url"] is None
        assert xianyu["image_state"] == "first_gallery_image_link_unverified"
        assert "首图直链仍未核实" in sample_23["relation_note"]
        assert "详情观察同商品ID 1057452820190" in sample_23["relation_note"]
        assert "不能据此认定成色/附件一致或计算利润" in sample_23["relation_note"]


def test_sample_85_keeps_wameiji_catalog_image_caveat_and_refreshes_live_xianyu_item() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_85 = next(row for row in rows if row["reference_product_id"] == 85)
        wameiji = sample_85["wameiji"]
        xianyu = sample_85["xianyu"]
        assert sample_85["same_product_verified"] is True
        assert sample_85["price_comparable"] is False
        assert wameiji["price"] == 2535
        assert wameiji["state"] == "observed_current"
        assert wameiji["source_url"].endswith("324a54617a334656725561663375636b345450446d662f")
        assert wameiji["image_state"] == "page_reference_image"
        assert wameiji["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/2JTaz3EVc4ztwV8FXHQQn2.jpg@jpg"
        assert "不是实际发货商品照片" in wameiji["version_evidence"]
        assert xianyu["price"] == 158
        assert xianyu["state"] == "observed_current"
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["source_url"].endswith("id=909027010379&categoryId=126864811")
        assert "2人想要/114浏览" in xianyu["version_evidence"]
        assert xianyu["image_url"] == "https://img.alicdn.com/bao/uploaded/i1/O1CN01ZWNFpU1Evf1BRk5jw_!!4611686018427381214-0-fleamarket.jpg_Q90.jpg_.webp"
        assert "不再沿用此前验证码拦截状态" in xianyu["version_evidence"]
        assert "不比较利润" in sample_85["relation_note"]


def test_sample_86_replaces_stale_rakuten_pair_with_two_live_exact_catalog_matches() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_86 = next(row for row in rows if row["reference_product_id"] == 86)
        wameiji = sample_86["wameiji"]
        xianyu = sample_86["xianyu"]
        assert sample_86["same_product_verified"] is True
        assert sample_86["price_comparable"] is False
        assert wameiji["price"] == 8800
        assert wameiji["state"] == "observed_current"
        assert wameiji["catalog_no"] == "FLJG-9012"
        assert wameiji["image_state"] == "page_reference_image"
        assert wameiji["image_url"] == "https://imghk02.doorzo.net/item/detail/orig/photos/m73862589913_1.jpg?1789574390"
        assert xianyu["price"] == 385
        assert xianyu["last_observed_price"] == 425
        assert xianyu["state"] == "observed_current"
        assert xianyu["catalog_no"] == "FLJG-9012"
        assert xianyu["source_url"].endswith("id=1042821001002&categoryId=126864811")
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert "标价不含税费及后续运费" in xianyu["version_evidence"]
        assert "不作利润判断" in sample_86["relation_note"]


def test_sample_88_rechecks_live_prema_listing_without_conflating_variant_prices() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_88 = next(row for row in rows if row["reference_product_id"] == 88)
        wameiji = sample_88["wameiji"]
        xianyu = sample_88["xianyu"]
        assert sample_88["same_product_verified"] is False
        assert sample_88["price_comparable"] is False
        assert wameiji["price"] == 7777
        assert wameiji["state"] == "observed_related"
        assert wameiji["barcode"] is None
        assert wameiji["image_state"] == "observed_first_gallery_image"
        assert wameiji["image_url"] == "https://imghk.doorzo.net/item/detail/orig/photos/m17630574571_1.jpg?1787892114"
        assert "不足以确认样本所写的“非欧版非日版”限定版" in wameiji["version_evidence"]
        assert xianyu["price"] is None
        assert xianyu["last_observed_price"] is None
        assert xianyu["state"] == "observed_current"
        assert xianyu["price_range"] == {"min": 145, "max": 280, "currency": "CNY"}
        assert xianyu["observed_at"] == "2026-09-26T22:50:00+08:00"
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["image_url"].endswith("O1CN01ntVwMy1H0oktdKR30_!!4611686018427384392-0-fleamarket.jpg_790x10000Q90.jpg_.webp")
        assert "页面封面主图直链已打开核对" in xianyu["version_evidence"]
        assert "日版发行" in xianyu["version_evidence"]
        assert "版本文字与样本“非欧版非日版”不一致" in xianyu["version_evidence"]
        assert "不把区间最低价当该样本报价" in sample_88["relation_note"]


def test_sample_22_keeps_current_month_box_listing_separate_from_sample_13() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_13 = next(row for row in rows if row["reference_product_id"] == 13)
        sample_22 = next(row for row in rows if row["reference_product_id"] == 22)
        xianyu = sample_22["xianyu"]
        assert xianyu["source_url"].endswith("id=1081169121696&categoryId=126860296")
        assert xianyu["price"] == 2188
        assert xianyu["observed_at"] == "2026-09-26T01:29:00+08:00"
        assert "265浏览" in xianyu["version_evidence"]
        assert "¥2,188" in sample_22["relation_note"]
        assert "1084287467098" not in xianyu["source_url"]
        assert sample_13["xianyu"]["source_url"].endswith("id=1084287467098&categoryId=126864811")
        assert sample_13["xianyu"]["price"] == 2300
        assert "2,300 CNY" in sample_13["relation_note"]


def test_sample_1_keeps_historical_xianyu_sample_separate_from_related_wameiji_item() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample_1 = next(row for row in snapshot[collection] if row["reference_product_id"] == 1)
        assert sample_1["same_product_verified"] is False
        assert sample_1["xianyu"]["state"] == "not_currently_listed"
        assert sample_1["xianyu"]["price"] is None
        assert sample_1["xianyu"]["last_observed_price"] == 100
        assert sample_1["xianyu"]["observed_at"] == "2026-09-26T19:46:46+08:00"
        assert sample_1["xianyu"]["catalog_no"] is None
        assert "不能作为二专可售商品" in sample_1["xianyu"]["version_evidence"]
        assert sample_1["xianyu"]["image_state"] == "no_verified_item_photo"
        assert sample_1["xianyu"]["image_url"] is None
        assert "不比较价格或利润" in sample_1["relation_note"]
        assert sample_1["wameiji"]["title"] == "【中古】同人音楽CDソフト 貴方を不幸に誘いますね 特典CD ナツノカゼ御来光(TUYU arrange ver.) / ツユ"
        assert sample_1["wameiji"]["price"] == 2200
        assert sample_1["wameiji"]["observed_at"] == "2026-09-26T19:46:46+08:00"
        assert sample_1["wameiji"]["state"] == "observed_current"
        assert sample_1["wameiji"]["image_state"] == "page_reference_image"
        assert sample_1["wameiji"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/DbAqk35jA64sCttyyaDpUN.webp@jpg"
        assert sample_1["wameiji"]["source_url"].endswith("325a7237514a3470465971584876766f3553597237332f")
        assert "やっぱり雨は降るんだね" not in sample_1["wameiji"]["title"]


def test_sample_73_separates_same_bd_edition_from_unconfirmed_bonus_ticket_and_multivariant_quote() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection_name in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection_name] if row["reference_product_id"] == 73)

        assert sample["same_product_verified"] is True
        assert sample["price_comparable"] is False
        assert sample["xianyu"]["image_state"] == "multi_option_listing_image"
        assert sample["xianyu"]["price_range"] == {"min": 687, "max": 799, "currency": "CNY"}
        assert sample["wameiji"]["observed_at"] == "2026-09-26T21:48:30+08:00"
        assert sample["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "18张明信片" in sample["wameiji"]["version_evidence"]
        assert "烫印入场券" in sample["relation_note"]
        assert "未列样本要求的外付烫印入场券" in sample["relation_note"]
        assert "当前本体有现货" in sample["xianyu"]["version_evidence"]
        assert sample["xianyu"]["observed_at"] == "2026-09-26T21:48:30+08:00"
        assert sample["xianyu"]["image_url"].endswith(
            "O1CN01GrC34D24f2lzpxrXx_!!4611686018427385545-0-xy_item.jpg_790x10000Q90.jpg_.webp"
        )


def test_reference_audit_snapshot_has_no_duplicate_json_keys() -> None:
    content = Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8")

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    json.loads(content, object_pairs_hook=reject_duplicate_keys)


def test_sample_18_does_not_compare_four_disc_bundle_with_one_volume() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample_18 = next(row for row in snapshot[collection] if row["reference_product_id"] == 18)
        assert sample_18["same_product_verified"] is False
        assert sample_18["xianyu"]["price"] == 900
        assert "VOL.2 与 VOL.3 各含DISC1/2的4张CD合售" in sample_18["xianyu"]["version_evidence"]
        assert "不含原盒/封面/歌词本" in sample_18["xianyu"]["version_evidence"]
        assert sample_18["wameiji"]["price"] == 19299
        assert "单独第三卷" in sample_18["wameiji"]["version_evidence"]
        assert "不能替代闲鱼VOL.2+VOL.3四盘合售" in sample_18["wameiji"]["version_evidence"]
        assert "不能按同SKU或利润机会比较" in sample_18["relation_note"]


def test_sample_20_confirms_live_xianyu_detail_and_keeps_condition_difference() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample_20 = next(row for row in snapshot[collection] if row["reference_product_id"] == 20)
        assert sample_20["same_product_verified"] is True
        assert sample_20["xianyu"]["price"] == 400
        assert sample_20["xianyu"]["search_source_url"].startswith("https://www.goofish.com/search?q=")
        assert "¥400包邮、181浏览，有立即购买" in sample_20["xianyu"]["version_evidence"]
        assert "实物拍摄所见所得" in sample_20["xianyu"]["version_evidence"]
        assert sample_20["wameiji"]["price"] == 3200
        assert "仍显示加入购物车/立即购买" in sample_20["wameiji"]["version_evidence"]
        assert "不同实物，成色不同" in sample_20["relation_note"]


def test_sample_21_uses_current_prices_and_keeps_xianyu_variant_ambiguity() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample_21 = next(row for row in snapshot[collection] if row["reference_product_id"] == 21)
        assert sample_21["same_product_verified"] is True
        assert sample_21["price_comparable"] is False
        assert sample_21["xianyu"]["price"] == 193
        assert "首价对应哪个选项和腰封状态未明确" in sample_21["xianyu"]["version_evidence"]
        assert sample_21["wameiji"]["price"] == 2899
        assert "当前2,899 JPY" in sample_21["wameiji"]["version_evidence"]
        assert "价格不可比，不计算利润" in sample_21["relation_note"]


def test_reference_audit_snapshot_persists_direct_marketplace_images() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = []
    for pair in snapshot["dual_observed_pairs"]:
        rows.extend([pair["wameiji"], pair["xianyu"]])
    rows.extend(record["observation"] for record in snapshot["single_observed_records"])

    mercari_item_rows = [
        row for row in rows
        if "/mall/mercari/detail/" in str(row.get("source_url", ""))
        and "/shops/product/" not in str(row.get("source_url", ""))
    ]
    assert mercari_item_rows
    # Mercari detail images may be served through Wameiji's direct proxy host
    # (imghk.doorzo.net) rather than the original static.mercdn.net hostname.
    # Both are direct listing-image URLs; screenshot/thumbnail hosts remain
    # excluded by this allowlist.
    direct_marketplace_images = (
        "https://static.mercdn.net/item/detail/orig/photos/",
        "https://imghk.doorzo.net/",
        "https://imghk02.doorzo.net/item/detail/orig/photos/",
        "https://image03.doorzo.net/item/detail/orig/photos/",
    )
    assert sum(str(row.get("image_url", "")).startswith(direct_marketplace_images) for row in mercari_item_rows) >= 40
    assert not any("static.312588698.com/thumb/item/webp/" in str(row.get("image_url", "")) for row in mercari_item_rows)
    sample_50 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 50)
    assert sample_50["same_product_verified"] is False
    assert sample_50["price_comparable"] is False
    assert sample_50["wameiji"]["source_url"] == sample_50["wameiji"]["search_source_url"]
    assert sample_50["wameiji"]["state"] == "blocked"
    assert sample_50["wameiji"]["price"] is None
    assert sample_50["wameiji"]["last_observed_price"] is None
    assert sample_50["wameiji"]["barcode"] is None
    assert sample_50["wameiji"]["image_url"] is None
    assert sample_50["wameiji"]["image_state"] == "no_verified_item_photo"
    assert "商品链接实为TUYU特典CD" in sample_50["wameiji"]["version_evidence"]
    assert "100–120 CNY" in sample_50["xianyu"]["version_evidence"]
    assert "120 无册封 已出" in sample_50["xianyu"]["version_evidence"]
    assert sample_50["xianyu"]["state"] == "observed_related"
    assert sample_50["xianyu"]["price"] is None
    assert sample_50["xianyu"]["price_range"] is None
    assert sample_50["xianyu"]["last_observed_price"] == 98
    assert sample_50["xianyu"]["image_state"] == "multi_option_listing_image"
    assert sum(bool(row.get("image_url")) for row in rows) >= 70


def test_reference_audit_covers_all_125_samples_without_blank_source_records() -> None:
    """Every requested sample has a source link and an explicit observation note."""
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    records = (
        snapshot["dual_observed_pairs"]
        + snapshot["single_observed_records"]
        + snapshot["unavailable_records"]
    )
    target = [record for record in records if 1 <= record["reference_product_id"] <= 125]
    assert len(target) == 125
    assert {record["reference_product_id"] for record in target} == set(range(1, 126))
    sides = [
        side
        for record in target
        for side in (record.get("xianyu"), record.get("wameiji"))
        if side is not None
    ]
    assert sides
    assert all(side.get("source_url") for side in sides)
    assert all(side.get("version_evidence") for side in sides)
    assert all(
        (
            side.get("image_url")
            or side.get("main_image_url")
            or side.get("image_state") in {"source_no_image", "first_gallery_image_link_unverified", "reference_only", "no_verified_item_photo"}
        )
        for side in sides
    )


def test_historical_profit_kpi_is_not_labeled_as_current_full_audit_result() -> None:
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert "历史利润卡（9/9 快照）" in homepage
    assert '<small>达标机会</small><strong id="kpiToday">' not in homepage


def test_dual_market_ui_fails_closed_when_its_board_is_unavailable() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    loader = Path("web/dual-market-data.js").read_text(encoding="utf-8")

    assert 'apiGet("/api/dual-market/board").catch(() => null)' not in javascript
    assert 'mode: "unavailable"' in loader
    assert "unavailable: true" in loader
    assert "eligible: []" in loader
    assert "双边证据流暂不可用" in javascript
    assert "不展示旧机会卡" in javascript


def test_dual_market_ui_does_not_submit_scan_or_resume_while_collection_is_paused() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")

    assert "采集已暂停，未提交扫描命令" in javascript
    assert "采集已暂停，未提交恢复命令" in javascript


def test_dual_market_ui_does_not_coerce_missing_landed_cost_to_zero() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    start = javascript.index("function cny")
    end = javascript.index("function jpy")
    currency_formatter = javascript[start:end]

    assert 'value === null || value === undefined || value === ""' in currency_formatter


def test_market_prices_use_explicit_cny_and_jpy_units_with_conversion() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    start = javascript.index("function cny")
    end = javascript.index("function percent")
    currency_formatter = javascript[start:end]
    harness = f"""
{currency_formatter}
if (cny(30) !== "30 CNY") throw new Error("unexpected CNY: " + cny(30));
if (jpy(110, 0.046) !== "110 JPY（约 5.06 CNY）") {{
  throw new Error("unexpected JPY conversion: " + jpy(110, 0.046));
}}
if (cny(null) !== "--" || jpy(null, 0.046) !== "--") {{
  throw new Error("missing prices must remain unknown");
}}
"""

    result = subprocess.run(
        ["node", "-e", harness],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_reference_audit_does_not_calculate_spread_for_unverified_product_pairs() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    assert '"历史挂牌价 · " + price' in javascript
    assert "相关商品观察 · 非样本同款" in javascript
    assert 'cny(rangeMin) + " – " + cny(rangeMax)' in javascript
    start = javascript.index("function referenceAuditCenterMarkup")
    end = javascript.index("function referenceAuditPairMarkup")
    center_renderer = javascript[start:end]
    harness = f"""
const displayJpyCnyRate = () => 0.0442;
const cny = (value) => Number.isFinite(value) ? value.toFixed(2) + " CNY" : "--";
const esc = (value) => String(value);
{center_renderer}
const mismatched = referenceAuditCenterMarkup(
  {{ price: 120 }}, {{ price: 99 }}, "历史错配", "未证实为同一商品", false
);
if (!mismatched.includes("不比较价差或利润")) {{
  throw new Error("unverified pairs must explicitly suppress profit comparison");
}}
if (!mismatched.includes("120.00 CNY") || !mismatched.includes("4.38 CNY")) {{
  throw new Error("keep each source-side price visible as a reference");
}}
if (mismatched.includes("115.62 CNY") || mismatched.includes("91.62 CNY")) {{
  throw new Error("unverified pairs must not display a synthetic spread or net value");
}}
const noSellableXianyu = referenceAuditCenterMarkup(
  {{ price: null }}, {{ price: 13800 }}, "非卖品展示", "闲鱼不在售", false
);
if (!noSellableXianyu.includes("闲鱼侧无可售价格")
  || !noSellableXianyu.includes("挖煤姬报价仅作观察参考")
  || noSellableXianyu.includes("两侧挂牌价分别保留")) {{
  throw new Error("a non-sale listing must not claim that both sides have usable prices");
}}
const comparable = referenceAuditCenterMarkup(
  {{ price: 120, state: "observed_current" }}, {{ price: 99, state: "observed_current" }}, "同版本样本", "同一商品已核验", true
);
if (!comparable.includes("115.62 CNY") || !comparable.includes("91.70 CNY")) {{
  throw new Error("verified same-product references may show the illustrative calculation");
}}
const unavailable = referenceAuditCenterMarkup(
  {{ price: 120, state: "found" }}, {{ price: 99, state: "current_sold_image" }},
  "历史记录", "一侧已售", true
);
if (!unavailable.includes("来源当前受阻 · 历史价不计利润")
  || !unavailable.includes("历史挂牌价作样本线索")
  || unavailable.includes("115.62 CNY") || unavailable.includes("91.70 CNY")) {{
  throw new Error("sold, blocked, login-gated and unlisted records must never calculate as current profit");
}}
const blockedUnknown = referenceAuditCenterMarkup(
  {{ price: null, state: "blocked" }}, {{ price: null, state: "login_required" }},
  "受阻来源", "当前页面未读到报价", true
);
if (!blockedUnknown.includes("闲鱼挂牌价</small><strong>当前未核实")
  || !blockedUnknown.includes("挖煤姬折合</small><strong>当前未核实")) {{
  throw new Error("a blocked source with no known price must not be rendered as no currently listed item");
}}
const historicalSoldQuote = referenceAuditCenterMarkup(
  {{ price: 120, state: "found" }},
  {{ price: 99, price_range: {{ min: 90, max: 99 }}, state: "current_sold_image" }},
  "已售商品", "保留历史挂牌价", true
);
if (!historicalSoldQuote.includes("挖煤姬折合</small><strong>当前未核实")
  || historicalSoldQuote.includes("4.38 CNY")
  || historicalSoldQuote.includes("3.98 CNY")) {{
  throw new Error("sold historical prices and ranges must not appear as current quotes in the comparison panel");
}}
const unlistedHistoricalQuote = referenceAuditCenterMarkup(
  {{ price: 177, price_range: {{ min: 177, max: 233 }}, state: "not_currently_listed" }},
  {{ price: 300, state: "observed_current" }}, "已下架商品", "旧价格仅保留作历史", false
);
if (!unlistedHistoricalQuote.includes("闲鱼挂牌价</small><strong>当前未核实")
  || unlistedHistoricalQuote.includes("177.00 CNY – 233.00 CNY")) {{
  throw new Error("unlisted historical ranges must not appear as current quotes in the comparison panel");
}}
const sameVersionUnpriced = referenceAuditCenterMarkup(
  {{ price: 687, price_range: {{ min: 687, max: 799 }}, state: "observed_current" }},
  {{ price: 13999, state: "observed_current" }}, "同款观察", "多选项报价未锁定", true, false
);
const spreadCell = sameVersionUnpriced.match(/<small>参考价差<\\/small><strong>(.*?)<\\/strong>/);
const netCell = sameVersionUnpriced.match(/<small>默认成本后参考值<\\/small><strong>(.*?)<\\/strong>/);
if (!sameVersionUnpriced.includes("同款已核 · 选项/价格未锁定，不比较")
  || !sameVersionUnpriced.includes("687.00 CNY – 799.00 CNY")
  || !spreadCell || spreadCell[1] !== "不比较"
  || !netCell || netCell[1] !== "不适用") {{
  throw new Error("a verified edition with an unresolved multi-option price must retain observations but suppress the spread and net value");
}}
"""

    result = subprocess.run(
        ["node", "-e", harness],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_blocked_reference_card_keeps_last_price_as_explicit_history() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    start = javascript.index("function referenceAuditObservationMarkup")
    end = javascript.index("function referenceAuditCenterMarkup")
    observation_renderer = javascript[start:end]
    harness = f"""
const safeHttpUrl = (value) => value || "";
const auditObservationImage = () => "";
const versionedAuditImageUrl = (value) => value || "";
const esc = (value) => String(value);
const displayJpyCnyRate = () => 0.0442;
const cny = (value) => Number.isFinite(Number(value)) ? Number(value).toFixed(2) + " CNY" : "--";
const jpy = (value) => Number.isFinite(Number(value)) ? Number(value).toFixed(0) + " JPY" : "--";
{observation_renderer}
const card = referenceAuditObservationMarkup(
  "闲鱼销售侧",
  {{ title: "礼衣 tuyu特典", state: "blocked", price: null, last_observed_price: 150 }},
  "CNY",
  "xianyu"
);
if (!card.includes("历史挂牌价 · 150.00 CNY")
  || !card.includes("当前详情未能核实 · 不作在售报价")) {{
  throw new Error("blocked cards should preserve the last price but label it as historical, never as an active quote");
}}
"""
    result = subprocess.run(
        ["node", "-e", harness],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_unknown_market_state_is_historical_and_cannot_be_compared_as_current() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    start = javascript.index("function referenceAuditObservationMarkup")
    end = javascript.index("function referenceAuditPairMarkup")
    renderers = javascript[start:end]
    harness = f"""
const safeHttpUrl = (value) => value || "";
const auditObservationImage = () => "";
const versionedAuditImageUrl = (value) => value || "";
const esc = (value) => String(value);
const displayJpyCnyRate = () => 0.0442;
const cny = (value) => Number.isFinite(Number(value)) ? Number(value).toFixed(2) + " CNY" : "--";
const jpy = (value) => Number.isFinite(Number(value)) ? Number(value).toFixed(0) + " JPY" : "--";
{renderers}
const card = referenceAuditObservationMarkup(
  "闲鱼销售侧", {{ title: "旧观察记录", price: 168, image_url: null }}, "CNY", "xianyu"
);
const center = referenceAuditCenterMarkup(
  {{ price: 168 }}, {{ price: 2200 }}, "观察参考", "状态未标注", true
);
if (!card.includes("当前状态未标注 · 历史参考")
  || !card.includes("历史挂牌价 · 168.00 CNY")) {{
  throw new Error("an unclassified market state must not present a stored price as current");
}}
if (!center.includes("来源状态未标注 · 历史价不计利润")
  || center.includes("参考价差</small><strong>70.88 CNY")
  || center.includes("默认成本后参考值</small><strong>47.19 CNY")) {{
  throw new Error("pairs missing either market state must never render an implied current spread");
}}
"""
    result = subprocess.run(
        ["node", "-e", harness], text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_reference_samples_separate_version_identity_from_price_comparability() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        rows = {row["reference_product_id"]: row for row in snapshot[collection]}
        for row in rows.values():
            if row.get("same_product_verified") is not True:
                assert row.get("price_comparable") is False, row["reference_product_id"]

        voltage = rows[73]
        assert voltage["same_product_verified"] is True
        assert voltage["price_comparable"] is False
        assert voltage["xianyu"]["image_state"] == "multi_option_listing_image"
        assert voltage["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "只作核心版本关联观察" in voltage["relation_note"]
        assert "未列样本要求的外付烫印入场券" in voltage["relation_note"]

        bad_mode = rows[82]
        assert bad_mode["same_product_verified"] is True
        assert bad_mode["price_comparable"] is False
        assert bad_mode["xianyu"]["catalog_no"] == bad_mode["wameiji"]["catalog_no"] == "ESJL-3123-4"
        assert bad_mode["wameiji"]["state"] == "observed_current"
        assert bad_mode["wameiji"]["price"] == 6999
        assert bad_mode["wameiji"]["last_observed_price"] is None
        assert bad_mode["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert "/mall/mercari/detail/" in bad_mode["wameiji"]["source_url"]

        fantome = rows[97]
        assert fantome["same_product_verified"] is False
        assert fantome["price_comparable"] is False
        assert fantome["wameiji"]["state"] == "observed_current"
        assert fantome["wameiji"]["price"] == 6200
        assert fantome["xianyu"]["state"] == "blocked"


def test_duplicate_sample_layers_keep_current_replacements_separate_and_remove_unsupported_quotes() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    layers = {
        name: {row["reference_product_id"]: row for row in snapshot[name]}
        for name in ("dual_found_pairs", "dual_observed_pairs")
    }

    for layer in layers.values():
        assert layer[93]["xianyu"]["price"] == 290
        assert layer[100]["xianyu"]["price"] is None
        assert layer[100]["xianyu"]["image_state"] == "historical_first_gallery_image"
    assert layers["dual_found_pairs"][87]["xianyu"]["source_url"] == layers["dual_observed_pairs"][87]["xianyu"]["source_url"]
    assert layers["dual_found_pairs"][87]["xianyu"]["state"] == "observed_current"
    assert layers["dual_found_pairs"][114]["xianyu"]["source_url"] != layers["dual_observed_pairs"][114]["xianyu"]["source_url"]


def test_dual_market_ui_states_the_china_resale_profit_direction() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    renderer = extract_dual_market_renderer(javascript)
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert "挖煤姬进货（JPY） → 闲鱼国内销售（CNY）" in renderer
    assert "闲鱼预计净利（CNY）" in renderer
    assert "闲鱼销售利润率" in renderer
    assert "利润 = 闲鱼销售价（CNY）" in renderer
    assert "闲鱼预计净利" in homepage
    assert "闲鱼最高净利" in homepage


def test_dual_market_kpis_use_only_eligible_profit_and_show_the_full_funnel() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    start = javascript.index("function renderKpis")
    end = javascript.index("function safeHttpUrl")
    renderer = javascript[start:end]

    assert "eligibleCount" in renderer
    assert "evaluatedCount" in renderer
    assert "costPendingCount" in renderer
    assert '"待算"' not in renderer
    assert 'setText("funnelEvaluated"' in renderer
    assert 'setText("funnelEligible"' in renderer


def test_homepage_loads_snapshot_loader_before_the_board_renderer() -> None:
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert "dual-market-data.js" in homepage
    assert homepage.index("dual-market-data.js") < homepage.index("discovery-ui.js")


def test_homepage_busts_cached_renderer_after_dual_observation_queue_fix() -> None:
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert "app.js?v=20260915-reference-audit-v1" in homepage
    assert "dual-market-data.js?v=20260915-reference-audit-v1" in homepage
    assert "discovery-ui.js?v=20260926-reference-audit-v9" in homepage
    assert "styles/kuro.css?v=20260923-reference-analysis-v1" in homepage


def test_board_refresh_decouples_legacy_api_failures_from_dual_market_data() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")

    assert 'apiGet("/api/discovery/board").catch(() => emptyBoard)' in javascript
    assert 'apiGet("/api/discovery/commands").catch(() => ({ items: [] }))' in javascript
    assert "window.DualMarketData.load({ apiGet, live: view.liveMode })" in javascript


def test_eligible_card_exposes_costs_match_evidence_and_recheck_warning() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    renderer = extract_dual_market_renderer(javascript)
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert "cost-breakdown" in javascript
    assert "cost_breakdown.wameiji_exchange_rate_cny_per_jpy" in renderer
    assert "15 CNY" in javascript
    assert "5 CNY" in javascript
    assert "闲鱼手续费" in javascript
    assert "匹配证据" in renderer
    assert "下单前重新核验" in renderer
    assert 'id="profitFunnel"' in homepage
    assert 'id="funnelEvaluated"' in homepage
    assert 'id="funnelCostPending"' in homepage
    assert 'id="funnelBelowMargin"' in homepage
    assert 'id="funnelEligible"' in homepage
    assert "净利润为正" in homepage


def test_static_snapshot_status_is_explicit_about_freshness() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")

    assert "Pages 已核验快照" in javascript
    assert "Pages 历史快照" in javascript
    assert "下单前重新核验" in javascript
    assert "采集仅在本机运行" in javascript


def test_static_snapshot_keeps_verified_cards_regardless_of_snapshot_age() -> None:
    """GitHub Pages is a historical evidence board, not a three-hour TTL cache."""
    loader = Path("web/dual-market-data.js").read_text(encoding="utf-8")
    harness = f"""
const window = {{}};
const document = {{ baseURI: "https://example.github.io/board/" }};
const payload = {{
  schema_version: 2,
  generated_at: "2000-01-01T00:00:00+08:00",
  strategy: {{
    policy_version: "wameiji-xianyu-net-v2",
    trade_direction: "wameiji_jpy_to_xianyu_cny",
    minimum_net_margin: 0,
  }},
  summary: {{
    evaluated_count: 1,
    eligible_count: 1,
    below_margin_count: 0,
    cost_pending_count: 0,
    waiting_wameiji_count: 0,
    waiting_xianyu_count: 0,
  }},
  eligible: [{{ comparison_id: 77 }}],
}};
async function fetch() {{
  return {{ ok: true, json: async () => payload }};
}}
{loader}
window.DualMarketData.load({{ live: false }}).then((board) => {{
  if (board.stale !== false) throw new Error("dated snapshot should remain displayable");
  if (board.eligible.length !== 1) throw new Error("verified card was removed");
}}).catch((error) => {{ console.error(error); process.exit(1); }});
"""

    result = subprocess.run(
        ["node", "-e", harness],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_dual_market_cards_can_be_hidden_locally_and_recovered() -> None:
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    renderer = extract_dual_market_renderer(javascript)

    assert 'data-dismiss-dual-market-card' in renderer
    assert 'aria-label="隐藏此机会卡"' in renderer
    assert "dismissDualMarketComparison" in javascript
    assert "restoreDismissedDualMarketComparisons" in javascript
    assert "localStorage" in javascript
    assert "isDualMarketComparisonDismissed" in javascript
    assert "eligible = eligible.filter" in renderer


def test_public_pages_bootstrap_has_no_external_runtime_config_dependency() -> None:
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert 'window.CD_MONITOR_CONFIG = { apiBase: "", accessToken: "" };' in homepage
    assert '<script async src="runtime-config.js"></script>' in homepage


def test_home_feed_is_two_columns_with_compact_three_part_cards() -> None:
    css = Path("web/styles/kuro.css").read_text(encoding="utf-8")
    homepage = Path("web/index.html").read_text(encoding="utf-8")

    assert "body.kuro #homeFeed" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert (
        "grid-template-columns: minmax(0, 1fr) minmax(130px, .7fr) "
        "minmax(0, 1fr)" in css
    )
    assert "max-height: 245px" in css
    assert "@media (max-width: 1180px)" in css
    assert "@media (max-width: 760px)" in css
    assert "一行两条机会" in homepage
    assert "左侧闲鱼" in homepage
    assert "右侧挖煤姬" in homepage


def test_sample_109_does_not_show_overwatch_option_as_yoasobi_cover() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))

    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_109 = next(row for row in rows if row["reference_product_id"] == 109)
        xianyu = sample_109["xianyu"]

        assert xianyu["price"] is None
        assert "Overwatch美版封面而非目标Art Edition封面" in xianyu["version_evidence"]
        assert xianyu["image_url"] is None
        assert xianyu["image_state"] == "no_verified_item_photo"


def test_samples_74_and_75_current_page_evidence_is_synchronized() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))

    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_74 = next(row for row in rows if row["reference_product_id"] == 74)
        assert sample_74["wameiji"]["price"] is None
        assert sample_74["wameiji"]["last_observed_price"] == 4070
        assert sample_74["wameiji"]["image_state"] == "historical_first_gallery_image"
        assert sample_74["xianyu"]["observed_at"] == "2026-09-26T21:51:40+08:00"
        assert sample_74["xianyu"]["image_url"].endswith("jpg_790x10000Q90.jpg_.webp")

        sample_75 = next(row for row in rows if row["reference_product_id"] == 75)
        assert sample_75["same_product_verified"] is True
        assert sample_75["price_comparable"] is False
        assert sample_75["wameiji"]["price"] == 7111
        assert sample_75["wameiji"]["image_url"].endswith("m36622866113_1.jpg?1789510404")
        assert sample_75["xianyu"]["price_range"] == {"min": 427, "max": 549, "currency": "CNY"}
        assert sample_75["xianyu"]["image_url"].endswith("jpg_790x10000Q90.jpg_.webp")
        assert "不能证明当前可选项实际含卡" in sample_75["xianyu"]["version_evidence"]
        assert "未确认额外照片卡" in sample_75["relation_note"]

        sample_76 = next(row for row in rows if row["reference_product_id"] == 76)
        assert sample_76["same_product_verified"] is False
        assert sample_76["price_comparable"] is False
        assert sample_76["xianyu"]["price"] == 699
        assert sample_76["xianyu"]["price_range"] == {"min": 229, "max": 699, "currency": "CNY"}
        assert sample_76["wameiji"]["price"] == 11500
        assert "未写初回限定或目录号" in sample_76["wameiji"]["version_evidence"]
        assert "CD+BD初回盘699 CNY" in sample_76["relation_note"]
        assert sample_76["xianyu"]["image_url"].endswith("jpg_790x10000Q90.jpg_.webp")

        sample_77 = next(row for row in rows if row["reference_product_id"] == 77)
        assert sample_77["same_product_verified"] is True
        assert sample_77["price_comparable"] is False
        assert sample_77["wameiji"]["price"] is None
        assert sample_77["wameiji"]["last_observed_price"] == 9400
        assert sample_77["wameiji"]["state"] == "current_sold_image"
        assert sample_77["wameiji"]["image_state"] == "current_sold_image"
        assert sample_77["xianyu"]["price_range"] == {"min": 199, "max": 333, "currency": "CNY"}
        assert sample_77["xianyu"]["image_url"].endswith("jpg_790x10000Q90.jpg_.webp")
        assert "可先付订金预留" in sample_77["xianyu"]["version_evidence"]

        sample_78 = next(row for row in rows if row["reference_product_id"] == 78)
        assert sample_78["same_product_verified"] is False
        assert sample_78["price_comparable"] is False
        assert sample_78["wameiji"]["state"] == "current_listed"
        assert sample_78["wameiji"]["price"] == 129999
        assert "2026年重制" in sample_78["wameiji"]["version_evidence"]
        assert sample_78["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample_78["wameiji"]["image_url"].endswith("m59481550077_1.jpg?1788334422")
        assert sample_78["xianyu"]["price"] == 620
        assert sample_78["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert sample_78["xianyu"]["image_url"].endswith("jpg_790x10000Q90.jpg_.webp")
        assert "不能证明同版" in sample_78["relation_note"]

        sample_79 = next(row for row in rows if row["reference_product_id"] == 79)
        assert sample_79["wameiji"]["price"] is None
        assert sample_79["wameiji"]["last_observed_price"] == 9680
        assert sample_79["wameiji"]["image_state"] == "historical_first_gallery_image"
        assert sample_79["xianyu"]["price"] is None
        assert sample_79["xianyu"]["last_observed_price"] == 470
        assert sample_79["xianyu"]["image_state"] == "current_sold_image"
        assert sample_79["xianyu"]["image_url"].endswith("jpg_790x10000Q90.jpg_.webp")
        assert "卖掉了" in sample_79["xianyu"]["version_evidence"]

        sample_80 = next(row for row in rows if row["reference_product_id"] == 80)
        assert sample_80["same_product_verified"] is True
        assert sample_80["price_comparable"] is False
        assert sample_80["wameiji"]["price"] == 9795
        assert sample_80["wameiji"]["catalog_no"] == "VVCL-1148"
        assert sample_80["wameiji"]["image_state"] == "page_reference_image"
        assert sample_80["wameiji"]["image_url"].endswith("2JWmnkmzfuCjZUXUEYk8eE.webp@jpg")
        assert sample_80["xianyu"]["price"] == 650
        assert sample_80["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert ".heic_790x10000Q90.jpg_.webp" in sample_80["xianyu"]["image_url"]
        assert "859浏览" in sample_80["relation_note"]
