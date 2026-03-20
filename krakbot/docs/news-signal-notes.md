# News Signal Notes

- Source: CoinDesk RSS only (`https://feeds.feedburner.com/CoinDesk`).
- `sentiment_score`, `novelty_score`, and `latest_published_at` are derived from RSS content/metadata.
- `priced_in_risk_score` is **hybrid**: combines news context with market microstructure inputs (e.g., spread/funding), so it is not pure RSS-derived.
