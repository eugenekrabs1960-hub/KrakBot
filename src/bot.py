import os
from dotenv import load_dotenv

from kraken_client import from_env


def str_to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    load_dotenv()

    live_trading = str_to_bool(os.getenv("KRAKEN_LIVE_TRADING", "false"))
    pair = os.getenv("KRAKEN_PAIR", "XBTUSD")
    side = os.getenv("KRAKEN_ORDER_SIDE", "buy")
    order_type = os.getenv("KRAKEN_ORDER_TYPE", "market")
    volume = os.getenv("KRAKEN_ORDER_VOLUME", "0.0001")

    client = from_env()

    balance = client.private_post("Balance")
    if balance.get("error"):
        raise RuntimeError(f"Balance call failed: {balance['error']}")

    print("Authenticated successfully. Balance keys:", list(balance.get("result", {}).keys())[:10])

    order_payload = {
        "ordertype": order_type,
        "type": side,
        "volume": volume,
        "pair": pair,
    }

    if not live_trading:
        print("SAFE MODE: KRAKEN_LIVE_TRADING=false. No live order sent.")
        print("Would place order:", order_payload)
        return

    print("LIVE MODE ENABLED: sending AddOrder request...")
    result = client.private_post("AddOrder", order_payload)
    if result.get("error"):
        raise RuntimeError(f"AddOrder failed: {result['error']}")

    print("Order placed:", result.get("result"))


if __name__ == "__main__":
    main()
