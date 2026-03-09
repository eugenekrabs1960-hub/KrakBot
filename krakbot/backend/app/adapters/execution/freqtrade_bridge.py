import os
import requests


class FreqtradeBridge:
    """
    Thin bridge to Freqtrade REST API (if configured).
    If unavailable, caller can fallback to simulated paper fill.
    """

    def __init__(self):
        self.base_url = os.getenv('FREQTRADE_URL', '').rstrip('/')
        self.username = os.getenv('FREQTRADE_USERNAME', '')
        self.password = os.getenv('FREQTRADE_PASSWORD', '')
        self.enabled = bool(self.base_url)

    def place_order(self, pair: str, side: str, amount: float, order_type: str = 'market', price: float | None = None) -> dict | None:
        if not self.enabled:
            return None

        payload = {
            'pair': pair,
            'side': side,
            'ordertype': order_type,
            'amount': amount,
        }
        if price is not None:
            payload['price'] = price

        try:
            r = requests.post(
                f"{self.base_url}/api/v1/forceenter",
                json=payload,
                auth=(self.username, self.password) if self.username else None,
                timeout=8,
            )
            if r.ok:
                return r.json()
            return None
        except Exception:
            return None
