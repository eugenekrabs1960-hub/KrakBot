import base64
import hashlib
import hmac
import os
import time
import urllib.parse

import requests


class KrakenClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.kraken.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")

    def _sign(self, urlpath: str, data: dict) -> str:
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        secret = base64.b64decode(self.api_secret)
        sigdigest = hmac.new(secret, message, hashlib.sha512)
        return base64.b64encode(sigdigest.digest()).decode()

    def private_post(self, endpoint: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        payload["nonce"] = int(time.time() * 1000)
        path = f"/0/private/{endpoint}"
        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign(path, payload),
        }
        resp = requests.post(self.base_url + path, data=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()


def from_env() -> KrakenClient:
    key = os.getenv("KRAKEN_API_KEY", "")
    secret = os.getenv("KRAKEN_API_SECRET", "")
    if not key or not secret:
        raise ValueError("Missing KRAKEN_API_KEY or KRAKEN_API_SECRET")
    return KrakenClient(key, secret)
