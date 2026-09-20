"""Add observed marketplace first-image URLs to the public reference snapshot.

The regular Mercari mirror URL is deterministic for an item id and has been
verified manually in the logged-in 挖煤姬 pages.  The other entries below are
exact URL/image pairs read from visible marketplace pages with Chrome's page
asset inventory; no reference-sample screenshot is used.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "web" / "data" / "reference-audit-snapshot.json"

# Exact pairs observed from the corresponding visible detail pages.
OBSERVED = {
    # Goofish first-image assets captured before its anti-bot challenge.
    "https://www.goofish.com/item?id=1001729302397&categoryId=126864811": "https://img.alicdn.com/bao/uploaded/i2/O1CN01SyHn2U1njIwyKqseQ_!!4611686018427384677-0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1011291721486&categoryId=202061902": "https://img.alicdn.com/bao/uploaded/i3/O1CN01ynM6GabIUMG1wLSm_!!4611686018427380249-0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1015656902633&categoryId=126864811": "https://img.alicdn.com/bao/uploaded/i1/O1CN01siAdIJ1q6Ji07w2Aw_!!0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1029227800211&categoryId=126860296": "https://img.alicdn.com/bao/uploaded/i2/O1CN01HPcjD01bpSqeaWPZo_!!4611686018427384362-0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1030153019863&categoryId=126864811": "https://img.alicdn.com/bao/uploaded/i2/O1CN01N1SEmo2DNwV6LHXCC_!!4611686018427383894-0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1030546367795&categoryId=126862148": "https://img.alicdn.com/bao/uploaded/i3/O1CN01VKRUEK22GBwFrDoka_!!4611686018427386884-0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1037357615567&categoryId=126864811": "https://img.alicdn.com/bao/uploaded/i1/O1CN01SGB4Gx1baoDw284jA_!!4611686018427382138-0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1038997634344&categoryId=0": "https://img.alicdn.com/bao/uploaded/i4/O1CN01ZP7WBCxnKDI3th7A_!!4611686018427384413-0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1041306363872": "https://img.alicdn.com/bao/uploaded/i1/O1CN019Ohr3G1hWaANLvPCL_!!4611686018427383421-0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    "https://www.goofish.com/item?id=1041583191474&categoryId=126864811": "https://img.alicdn.com/bao/uploaded/i2/O1CN01mOSp5u1zFK3s7mIHZ_!!0-mtopupload.jpg_110x10000Q90.jpg_.webp",
    # Non-Mercari 挖煤姬 detail pages captured in the same Chrome pass.
    "https://meruki.cn/mall/market/detail/533363023135772672?shopid=454533197263278081": "https://img.hmv.co.jp/image/jacket/400/0000169/6/3/151.jpg",
    "https://meruki.cn/mall/market/detail/561762539112112129?shopid=150214744753020928": "https://content.bookoff.co.jp/goodsimages/LL/001868/0018687954LL.jpg",
    "https://meruki.cn/mall/market/detail/566254669502222336?shopid=278012958885810176": "https://store.jp.square-enix.com/img/goods/L/SQEX-11260-1_001.jpg",
    "https://meruki.cn/mall/market/detail/569747975801282560?shopid=149720279596601344": "https://imghk.doorzo.net/mandarake/webshopimg/03/00/948/0300341948/030034194815.jpg",
    "https://www.meruki.cn/mall/market/detail/551993953963372544?shopid=149720279596601344": "https://imghk.doorzo.net/mandarake/webshopimg/03/00/195/0300356195/s_030035619532.jpg",
    "https://meruki.cn/mall/paypay/detail/x1244399830": "https://imghk.doorzo.net/images.auctions.yahoo.co.jp/image/dr000/auc0209/user/03442474715459f08b27875781e9d35ef9c406fa83a8b3347ac1313203dc7bda/i-img1080x1080-1789290218729821jgx1bh24.jpg",
    "https://meruki.cn/mall/paypay/detail/z607937962": "https://imghk.doorzo.net/images.auctions.yahoo.co.jp/image/dr000/auc0209/users/f817d76d38605c53587adca90612bafb187426fe/i-img1200x1200-1789357261393237etu.jpg",
    "https://meruki.cn/mall/rakuma/detail/44ec81dec45afb371fb320cc290db31c": "https://imghk.doorzo.net/img/816497987/l/2800832029.jpg?updated_at=2026-02-17T00:18:45.000Z&1771287525=",
    "https://meruki.cn/mall/rakuma/detail/6f8d50003b0179a95e3986c600e41107": "https://imghk02.doorzo.net/img/823311623/l/2829147663.jpg?1789616310=&updated_at=2026-09-17T03:38:30.000Z",
    "https://meruki.cn/mall/rakuma/detail/7c4e2728f8da292a20da07d790441006": "https://imghk.doorzo.net/img/800693998/l/2731215840.jpg?1763512503=&updated_at=2025-11-19T00:35:04.000Z",
    "https://meruki.cn/mall/rakuten/detail/https%3A%2F%2Fitem.rakuten.co.jp%2Fakaikumasan%2F4988031862438%2F": "https://imghk02.doorzo.net/tshopr10sjp/akaikumasan/cabinet/picture20260309/4988031862438.jpg?fitin=600:600",
    "https://meruki.cn/mall/rakuten/detail/https%3A%2F%2Fitem.rakuten.co.jp%2Fcyberbay%2Fsecl-2765%2F": "https://imghk.doorzo.net/imgrakutencojp/cyberbay/cabinet/02413830/img60166590.jpg",
    "https://meruki.cn/mall/rakuten/detail/https%3A%2F%2Fitem.rakuten.co.jp%2Fhmvjapan%2F12565453%2F": "https://imghk.doorzo.net/tshopr10sjp/hmvjapan/cabinet/a25/66000/12565453.jpg?fitin=600:600",
    "https://meruki.cn/mall/rakuten/detail/https%3A%2F%2Fitem.rakuten.co.jp%2Fmifsoft%2Fmary-1004%2F": "https://image02.doorzo.net/tshopr10sjp/mifsoft/cabinet/025/mary-1004.jpg?fitin=600:600",
    "https://meruki.cn/mall/rakuten/detail/https%3A%2F%2Fitem.rakuten.co.jp%2Fmifsoft%2Fupjy-9202%2F": "https://imghk.doorzo.net/tshopr10sjp/mifsoft/cabinet/023/upjy-9202.jpg?fitin=600:600",
    "https://meruki.cn/mall/rakuten/detail/https%3A%2F%2Fitem.rakuten.co.jp%2Fneobest%2F4988002948420%2F": "https://imghk.doorzo.net/tshopr10sjp/neobest/cabinet/shohin/10952852/4988002948420.jpg?fitin=600:600",
    # Mercari Shops detail images captured from the same logged-in pages.
    "https://meruki.cn/mall/mercari/detail/68747470733a2f2f6a702e6d6572636172692e636f6d2f73686f70732f70726f647563742f324a475136746e4d784457754d435641514a6a6250342f": "https://assets.mercari-shops-static.com/-/large/plain/2JVvjSkCc39bAcTKm8yPYw.jpg@jpg",
    "https://meruki.cn/mall/mercari/detail/68747470733a2f2f6a702e6d6572636172692e636f6d2f73686f70732f70726f647563742f324a57344c646f6e3548394e665573644751776d47582f": "https://assets.mercari-shops-static.com/-/large/plain/2JW4JjWkgcz6YHctVVBUJt.jpg@jpg",
    "https://meruki.cn/mall/mercari/detail/68747470733a2f2f6a702e6d6572636172692e636f6d2f73686f70732f70726f647563742f324a576551696f33687654777643716145676b7332752f": "https://assets.mercari-shops-static.com/-/large/plain/2JWeQin6w2x8wiVC3S3Srz.webp@jpg",
    "https://meruki.cn/mall/mercari/detail/68747470733a2f2f6a702e6d6572636172692e636f6d2f73686f70732f70726f647563742f324a5758635a656f6a694a7a6f6568794378745268512f": "https://assets.mercari-shops-static.com/-/large/plain/2JWXcZdmayREpgKwbdGbzd.webp@jpg",
    "https://meruki.cn/mall/mercari/detail/68747470733a2f2f6a702e6d6572636172692e636f6d2f73686f70732f70726f647563742f324a576b71506877706e64415a71574b6a46674855732f": "https://assets.mercari-shops-static.com/-/large/plain/2JWkqPgsUA3ZWhpY7BVWq2.webp@jpg",
    "https://meruki.cn/mall/mercari/detail/68747470733a2f2f6a702e6d6572636172692e636f6d2f73686f70732f70726f647563742f324a576b77337033434c6a43615745726669596242382f": "https://assets.mercari-shops-static.com/-/large/plain/2JWkw3nwC2qSp7RCHmLg7z.webp@jpg",
}


def inferred_mercari_image(source_url: str) -> str | None:
    match = re.search(r"/mall/mercari/detail/([^/?#]+)", source_url)
    if not match or "/shops/product/" in match.group(1):
        return None
    try:
        decoded = bytes.fromhex(match.group(1)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    item = re.search(r"/items?/(m\d+)", decoded, flags=re.I)
    if not item:
        return None
    # The live Wameiji detail page exposes this public thumbnail CDN.  Keep
    # the URL deterministic but use the host/path that actually returns the
    # first product photo without a session-bound query string.
    return f"https://static.312588698.com/thumb/item/webp/{item.group(1)}_1.jpg"


def observations(data: dict):
    for pair in data.get("dual_observed_pairs", []):
        yield from (pair.get("wameiji", {}), pair.get("xianyu", {}))
    for record in data.get("single_observed_records", []):
        yield record.get("observation", {})


def main() -> None:
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    changed = 0
    for item in observations(data):
        source_url = str(item.get("source_url") or "")
        image = OBSERVED.get(source_url) or inferred_mercari_image(source_url)
        if image and item.get("image_url") != image:
            item["image_url"] = image
            changed += 1
    SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"updated={changed} observed={len(OBSERVED)}")


if __name__ == "__main__":
    main()
