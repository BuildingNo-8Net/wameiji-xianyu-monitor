from __future__ import annotations

import subprocess
import json
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
    assert "单边待补观察" in javascript
    assert "参考样本图 · 非当前商品页" in javascript
    assert "参考样本图 · 两侧当前未见" in javascript


def test_reference_audit_cards_use_marketplace_main_images_and_platform_colours() -> None:
    """Observed sides use marketplace images; missing sides may show labelled references."""
    javascript = Path("web/discovery-ui.js").read_text(encoding="utf-8")
    stylesheet = Path("web/styles/kuro.css").read_text(encoding="utf-8")

    assert "source.image_url || source.main_image_url" in javascript
    assert "reference-audit-market-media" in javascript
    assert "主图链接待补" in javascript
    assert "源站未提供主图" in javascript
    assert "static.mercdn.net/item/detail/orig/photos/" in javascript
    assert "mokaki\\.cn\\/sigimage\\/icon" in javascript
    assert "ossimg\\/)" not in javascript
    assert "referenceAuditImageMarkup" not in javascript
    assert "const referenceImage = usableProductImage(item.reference_image_url);" in javascript
    assert "参考样本图 · 非当前商品页" in javascript
    assert '"xianyu-side"' in javascript
    assert '"wameiji-side"' in javascript
    assert ".reference-audit-side.xianyu-side" in stylesheet
    assert ".reference-audit-side.wameiji-side" in stylesheet
    assert ".reference-audit-market-media" in stylesheet
    assert ".reference-audit-center" in stylesheet


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
    assert sample_50["wameiji"]["image_url"].startswith("https://imgoss.mokaki.cn/ossimg/")
    assert sum(bool(row.get("image_url")) for row in rows) >= 70


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
    assert "discovery-ui.js?v=e6c3158" in homepage
    assert "styles/kuro.css?v=20260920-market-main-images-v2" in homepage


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
