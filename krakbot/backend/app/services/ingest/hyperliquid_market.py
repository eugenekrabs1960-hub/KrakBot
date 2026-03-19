import random


def fetch_market_snapshot(coin: str) -> dict:
    px = random.uniform(100, 70000)
    return {
        "coin": coin,
        "symbol": f"{coin}-PERP",
        "last_price": px,
        "mark_price": px * random.uniform(0.9995, 1.0005),
        "index_price": px * random.uniform(0.999, 1.001),
        "spread_bps": random.uniform(1, 15),
        "volume_5m_usd": random.uniform(500_000, 8_000_000),
        "volume_1h_usd": random.uniform(8_000_000, 120_000_000),
        "open_interest_usd": random.uniform(50_000_000, 800_000_000),
        "funding_rate": random.uniform(-0.0008, 0.0008),
    }
