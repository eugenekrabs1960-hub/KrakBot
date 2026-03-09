# KrakBot

Starter Kraken trading bot scaffold with safety-first defaults.

## What this includes

- Branch setup target: `feature/kraken-live-trading`
- Secure env scaffolding (`.env.example`, `.gitignore`)
- Authenticated Kraken private API test (`src/test_auth.py`)
- Trading runner with **safe mode** toggle (`src/bot.py`)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```env
KRAKEN_API_KEY=...
KRAKEN_API_SECRET=...
KRAKEN_LIVE_TRADING=false
KRAKEN_PAIR=XBTUSD
KRAKEN_ORDER_TYPE=market
KRAKEN_ORDER_SIDE=buy
KRAKEN_ORDER_VOLUME=0.0001
```

## Verify API auth (no trade)

```bash
python src/test_auth.py
```

## Run bot

Safe mode (default, no real trade):

```bash
python src/bot.py
```

Live trading (real funds risk):

1. Set `KRAKEN_LIVE_TRADING=true`
2. Ensure API key has trading permissions
3. Start with minimum size

```bash
python src/bot.py
```

## Notes

- Do **not** commit `.env`
- Use dedicated Kraken API keys with least privileges
- Restrict API key by IP where possible
