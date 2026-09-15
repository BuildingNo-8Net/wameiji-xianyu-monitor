from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATH = ROOT / "web" / "data" / "manual-verified-candidates.json"


def test_manual_verified_candidates_are_renderable_and_conservative() -> None:
    payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["source"] == "manual_browser_review"
    assert payload["policy"]["minimum_net_margin"] == 0.25
    assert len(payload["candidates"]) >= 2

    for candidate in payload["candidates"]:
        image_path = ROOT / "web" / candidate["reference_sample_image"]
        assert image_path.is_file()
        assert candidate["status"] == "reserve_margin_qualified"
        assert urlparse(candidate["wameiji"]["url"]).netloc in {
            "meruki.cn",
            "www.meruki.cn",
        }
        assert urlparse(candidate["xianyu"]["url"]).netloc == "www.goofish.com"
        assert candidate["xianyu"]["evidence"].endswith("非代购")

        calculation = candidate["calculation"]
        sale_price = candidate["xianyu"]["price_cny"]
        assert calculation["net_margin"] >= payload["policy"]["minimum_net_margin"]
        assert calculation["expected_profit_cny"] > 0
        assert round(calculation["expected_profit_cny"] / sale_price, 4) == round(
            calculation["net_margin"], 4
        )
