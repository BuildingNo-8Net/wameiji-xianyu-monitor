from __future__ import annotations

import subprocess
import json
import re
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
    assert "const displayCandidate = relatedCandidate || candidate;" in javascript
    assert "const observedImage = auditObservationImage(source);" in javascript
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


def test_listing_reference_image_is_shown_with_explicit_non_item_badge() -> None:
    """A marketplace's own first gallery image remains visible but is not called a real item photo."""
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    stylesheet = Path("web/styles/kuro.css").read_text(encoding="utf-8")

    assert 'source.image_state === "page_reference_image"' in javascript
    assert "来源页示意图 · 非实物照" in javascript
    assert ".reference-audit-image-badge" in stylesheet


def test_sample_9_keeps_unbuyable_catalog_cover_labeled_as_reference_only() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    sample_9 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 9)
    wameiji = sample_9["wameiji"]

    assert sample_9["same_product_verified"] is False
    assert wameiji["state"] == "blocked"
    assert wameiji["price"] is None
    assert wameiji["image_url"].endswith("/b007gttzzy.jpg?fitin=600:600")
    assert wameiji["image_state"] == "page_reference_image"
    assert "/mall/rakuten/detail/" in wameiji["source_url"]
    assert "search_source_url" in wameiji
    assert "不能证明现货实物或附件齐全" in wameiji["version_evidence"]
    assert "未找到可核实的在售同款" in javascript
    assert "查看站内检索结果" in javascript


def test_sample_2_replaces_sold_listing_with_live_related_cd_without_claiming_same_version() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_2 = next(row for row in rows if row["reference_product_id"] == 2)
        xianyu = sample_2["xianyu"]

        assert sample_2["same_product_verified"] is False
        assert "不是同SKU" in sample_2["relation_note"]
        assert xianyu["source_url"].endswith("id=1077380058162&categoryId=126864811")
        assert xianyu["state"] == "found"
        assert xianyu["price"] == 390
        assert xianyu["image_state"] == "observed_first_gallery_image"
        assert xianyu["image_url"].endswith("O1CN01CQs1o2FtxNG3thAe_!!4611686018427383567-0-xy_item.jpg_790x10000Q90.jpg_.webp")
        assert "商品介质栏只写CD" in xianyu["version_evidence"]
        assert "当前已售" in xianyu["version_evidence"]


def test_sample_8_confirms_same_kazusa_cd_direction_without_equating_condition_or_accessories() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_8 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 8)
    wameiji = sample_8["wameiji"]
    xianyu = sample_8["xianyu"]

    assert sample_8["same_product_verified"] is True
    assert "同一张kazusa单CD专辑" in sample_8["relation_note"]
    assert "不将标价差当作利润" in sample_8["relation_note"]
    assert wameiji["price"] == 19800
    assert wameiji["source_url"].endswith("324a5736784561697663594a537166344459465937792f")
    assert wameiji["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/2JW6xEZiNRUBMeERREzrzs.jpg@jpg"
    assert wameiji["state"] == "found"
    assert xianyu["price"] == 360
    assert xianyu["image_state"] == "observed_first_gallery_image"
    assert "当前具体闲鱼详情页可打开" in xianyu["version_evidence"]
    assert "1,035浏览" in xianyu["version_evidence"]
    assert "未证明歌词册/腰封" in xianyu["version_evidence"]


def test_sample_12_confirms_tuyu_album_and_tracks_live_price_range_and_first_gallery_images() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = [
        row
        for collection in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"])
        for row in collection
        if row["reference_product_id"] == 12
    ]

    assert len(rows) == 2
    for sample_12 in rows:
        assert sample_12["same_product_verified"] is True
        assert "TUYU-0002" in sample_12["relation_note"] or "TUYU-0002" in sample_12["wameiji"]["version_evidence"]
        assert "240–280元区间" in sample_12["relation_note"]
        assert sample_12["wameiji"]["image_state"] == "observed_first_gallery_image"
        assert sample_12["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "32人想要/1,373浏览" in sample_12["xianyu"]["version_evidence"]


def test_sample_14_removes_unrelated_comic_listing_and_keeps_reference_image_for_missing_exact_match() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_14 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 14)
    xianyu = sample_14["xianyu"]
    wameiji = sample_14["wameiji"]

    assert sample_14["same_product_verified"] is False
    assert "漫画单本" in sample_14["relation_note"]
    assert "SW-045T" in wameiji["version_evidence"]
    assert wameiji["catalog_no"] == "SW-045T"
    assert wameiji["image_state"] == "page_reference_image"
    assert xianyu["state"] == "not_currently_listed"
    assert xianyu["price"] is None
    assert xianyu["image_state"] == "reference_only"
    assert xianyu["image_url"] is None
    assert sample_14["reference_image_url"] == "assets/reference-samples/14-b9f4a41e4e062903.webp"
    assert "1077589995824" not in xianyu["source_url"]
    assert "minori%20eden%20TRIAL%20DISC" in xianyu["source_url"]


def test_sample_11_replaces_sold_xianyu_link_with_verified_live_detail() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_11 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 11)
    xianyu = sample_11["xianyu"]

    assert sample_11["same_product_verified"] is True
    assert "MGCG-1408" in sample_11["wameiji"]["version_evidence"]
    assert xianyu["source_url"] == "https://www.goofish.com/item?id=1022572554442&categoryId=126864811"
    assert xianyu["state"] == "found"
    assert xianyu["price"] == 129
    assert "已卖出" not in xianyu["version_evidence"]
    assert "盒子破损" in xianyu["version_evidence"]
    assert xianyu["image_state"] == "observed_first_gallery_image"
    assert xianyu["image_url"] == "https://img.alicdn.com/bao/uploaded/i4/3806490968/O1CN01akSR1b1J1OW0sRpFJ_!!4611686018427384152-0-xy_item.jpg_790x10000Q90.jpg_.webp"
    assert "当前首图直链单独打开确认与详情图相符" in xianyu["version_evidence"]


def test_sample_53_uses_single_version_aimer_listing_and_its_first_image() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample_53 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 53)
    xianyu = sample_53["xianyu"]

    assert sample_53["same_product_verified"] is True
    assert xianyu["source_url"] == "https://www.goofish.com/item?id=1080171737027&categoryId=126864811"
    assert xianyu["price"] == 168
    assert "CD有细微毛痕" in xianyu["version_evidence"]
    assert xianyu["image_state"] == "observed_first_gallery_image"
    assert xianyu["image_url"] == "https://img.alicdn.com/bao/uploaded/i2/1713419028/O1CN01E8jVKAJuh6I3thGS_!!4611686018427384596-0-xy_item.jpg_790x10000Q90.jpg_.webp"


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
    for sample_id in (63, 74, 77, 78, 79, 82, 84, 85, 86, 88, 90, 91, 92, 94, 99, 103, 107, 111):
        source = pairs[sample_id]["wameiji"]
        assert source["state"] == "login_required", sample_id
        assert source["image_state"] == "historical_first_gallery_image", sample_id

    for sample_id in (87, 94, 100, 104):
        source = pairs[sample_id]["xianyu"]
        assert source["state"] == "blocked", sample_id
        assert source["image_state"] == "historical_first_gallery_image", sample_id

    for sample_id in (97, 98, 100, 101, 102):
        source = pairs[sample_id]["wameiji"]
        assert source["state"] == "blocked", sample_id
        assert source["image_state"] == "historical_first_gallery_image", sample_id

    for sample_id, side in ((5, "xianyu"),):
        source = pairs[sample_id][side]
        assert source["state"] == "current_sold_image", sample_id
        assert source["image_state"] == "current_sold_image", sample_id
        assert "1084719238003" in source["version_evidence"]
        assert "滑块验证" in source["version_evidence"]
        assert source["search_source_url"].startswith("https://www.goofish.com/search?")

    source = pairs[13]["xianyu"]
    assert source["state"] == "not_currently_listed"
    assert source["image_state"] == "historical_first_gallery_image"


def test_sample_50_reopened_multi_option_listing_keeps_option_and_gallery_limits_explicit() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    sample = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 50)

    assert sample["same_product_verified"] is False
    assert sample["xianyu"]["state"] == "found"
    assert sample["xianyu"]["price"] == 120
    assert sample["xianyu"]["image_state"] == "observed_first_gallery_image"
    assert sample["xianyu"]["source_url"] == "https://www.goofish.com/item?id=966395255268&categoryId=126864811"
    assert "价格区间100–120 CNY" in sample["xianyu"]["version_evidence"]
    assert "多选项合集" in sample["xianyu"]["version_evidence"]
    assert "第一张图库图" in sample["xianyu"]["version_evidence"]
    assert sample["wameiji"]["state"] == "found"
    assert sample["wameiji"]["image_state"] == "page_reference_image"


def test_sample_53_uses_live_aimer_daydream_packaging_main_image() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for collection in ("dual_found_pairs", "dual_observed_pairs"):
        sample = next(row for row in snapshot[collection] if row["reference_product_id"] == 53)
        assert sample["same_product_verified"] is True
        assert sample["xianyu"]["price"] == 168
        assert sample["xianyu"]["image_url"] == (
            "https://img.alicdn.com/bao/uploaded/i2/1713419028/"
            "O1CN01E8jVKAJuh6I3thGS_!!4611686018427384596-0-xy_item.jpg_790x10000Q90.jpg_.webp"
        )
        assert "包装主图" in sample["xianyu"]["version_evidence"]


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
        assert "923浏览" in sample["xianyu"]["version_evidence"]
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
        assert wameiji["price"] == 14552
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


def test_sample_22_does_not_reuse_sample_13_three_disc_listings_for_moon_box() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_13 = next(row for row in rows if row["reference_product_id"] == 13)
        sample_22 = next(row for row in rows if row["reference_product_id"] == 22)
        assert sample_22["same_product_verified"] is False
        assert sample_22["reference_image_url"].endswith("22-f1e63661cafe1b24.webp")
        for market in ("wameiji", "xianyu"):
            side = sample_22[market]
            assert side["price"] is None
            assert side["image_url"] is None
            assert side["image_state"] == "reference_only"
            assert side["state"] == "blocked"
            assert "/search" in side["source_url"]
            assert side["source_url"] != sample_13[market]["source_url"]


def test_sample_13_seller_rating_block_is_not_counted_as_a_buyable_price() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))

    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_13 = next(row for row in rows if row["reference_product_id"] == 13)
        wameiji = sample_13["wameiji"]
        assert wameiji["state"] == "blocked"
        assert wameiji["price"] is None
        assert wameiji["last_observed_price"] == 104459
        assert wameiji["image_state"] == "page_reference_image"
        assert "卖家好评过低" in wameiji["version_evidence"]
        assert "不保证" in wameiji["version_evidence"]


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


def test_sample_35_does_not_reuse_music_cd_links_for_an_unidentified_game_box() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    rows = {row["reference_product_id"]: row for row in snapshot["dual_observed_pairs"]}
    sample_29 = rows[29]
    sample_35 = rows[35]

    assert sample_35["same_product_verified"] is False
    assert "/search?" in sample_35["wameiji"]["source_url"]
    assert "/search?" in sample_35["xianyu"]["source_url"]
    assert sample_35["wameiji"]["price"] is None
    assert sample_35["xianyu"]["price"] is None
    assert sample_35["wameiji"]["image_url"] is None
    assert sample_35["xianyu"]["image_url"] is None
    assert sample_35["wameiji"]["image_state"] == "reference_only"
    assert sample_35["xianyu"]["image_state"] == "reference_only"
    assert sample_35["wameiji"]["state"] == "blocked"
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

    for sample_id in (22, 35):
        row = rows[sample_id]
        assert row["wameiji"]["state"] == "blocked"
        assert row["xianyu"]["state"] == "blocked"
        assert unavailable_pattern.search(row["wameiji"]["version_evidence"])
        assert unavailable_pattern.search(row["xianyu"]["version_evidence"])


def test_sample_54_current_listings_and_direct_first_images_match_manual_evidence() -> None:
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
        assert "278浏览" in row["xianyu"]["version_evidence"]
        assert "成色不等价" in row["relation_note"]


def test_sample_55_does_not_assign_one_price_or_real_item_photo_to_uncertain_variants() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        row = next(row for row in rows if row["reference_product_id"] == 55)
        assert row["xianyu"]["price"] is None
        assert "¥228–350" in row["xianyu"]["version_evidence"]
        assert row["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert row["wameiji"]["image_state"] == "page_reference_image"
        assert "首图仅为示例" in row["wameiji"]["version_evidence"]
        assert "不能用于价差或利润判断" in row["relation_note"]


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
        assert sample_6["xianyu"]["image_url"].endswith("O1CN01Ybgkgx1HmuNm8zYgA_!!4611686018427383905-0-xy_item.jpg_790x10000Q90.jpg_.webp")
        assert sample_6["xianyu"]["image_state"] == "observed_first_gallery_image"
        assert "首张画廊图直链已单独打开" in sample_6["xianyu"]["version_evidence"]


def test_sample_33_uses_each_listing_first_gallery_image_not_another_gallery_photo() -> None:
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    for rows in (snapshot["dual_found_pairs"], snapshot["dual_observed_pairs"]):
        sample_33 = next(row for row in rows if row["reference_product_id"] == 33)
        assert sample_33["xianyu"]["image_url"].endswith("O1CN012tbsvy1d0HoMvNcdc_!!4611686018427383289-53-fleamarket.heic_790x10000Q90.jpg_.webp")
        assert sample_33["wameiji"]["image_url"] == "https://imghk.doorzo.net/item/detail/orig/photos/m32301324782_1.jpg?1643898636"
        assert "thumb/item/webp" not in sample_33["wameiji"]["image_url"]


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
    )
    assert sum(str(row.get("image_url", "")).startswith(direct_marketplace_images) for row in mercari_item_rows) >= 40
    assert not any("static.312588698.com/thumb/item/webp/" in str(row.get("image_url", "")) for row in mercari_item_rows)
    sample_50 = next(row for row in snapshot["dual_observed_pairs"] if row["reference_product_id"] == 50)
    assert sample_50["wameiji"]["image_url"] == "https://assets.mercari-shops-static.com/-/large/plain/2JV8Y52xxbisFRB4eaHmr8.jpg@jpg"
    assert sample_50["wameiji"]["image_state"] == "page_reference_image"
    assert "商品图片为样图" in sample_50["wameiji"]["version_evidence"]
    assert sum(bool(row.get("image_url")) for row in rows) >= 70


def test_reference_audit_covers_samples_one_to_120_without_blank_source_records() -> None:
    """Every requested sample has a source link and an explicit observation note."""
    snapshot = json.loads(Path("web/data/reference-audit-snapshot.json").read_text(encoding="utf-8"))
    records = (
        snapshot["dual_observed_pairs"]
        + snapshot["single_observed_records"]
        + snapshot["unavailable_records"]
    )
    target = [record for record in records if 1 <= record["reference_product_id"] <= 120]
    assert len(target) == 120
    assert {record["reference_product_id"] for record in target} == set(range(1, 121))
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
const comparable = referenceAuditCenterMarkup(
  {{ price: 120 }}, {{ price: 99 }}, "同版本样本", "同一商品已核验", true
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
"""

    result = subprocess.run(
        ["node", "-e", harness],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


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
    assert "discovery-ui.js?v=20260924-reference-analysis-v6" in homepage
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
