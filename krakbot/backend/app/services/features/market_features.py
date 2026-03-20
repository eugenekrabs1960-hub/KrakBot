from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import math
import statistics

_HIST = defaultdict(lambda: deque(maxlen=500))


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _safe_logret(p_now: float, p_prev: float) -> float:
    if p_now > 0 and p_prev > 0:
        return math.log(p_now / p_prev)
    return 0.0


def _zscore(v: float, xs: list[float]) -> float:
    if len(xs) < 10:
        return 0.0
    mu = statistics.mean(xs)
    sd = statistics.pstdev(xs)
    if sd <= 1e-12:
        return 0.0
    return (v - mu) / sd


def _norm_ts(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _value_ago(hist: deque, key: str, seconds: int):
    if not hist:
        return None
    t_now = _norm_ts(hist[-1]['ts'])
    for row in reversed(hist):
        t_row = _norm_ts(row['ts'])
        if t_now is not None and t_row is not None and (t_now - t_row).total_seconds() >= seconds:
            return row.get(key)
    return None


def compute_market_features(market: dict, series: list[dict] | None = None) -> dict:
    coin = market.get('coin') or market.get('symbol', 'UNK').replace('-PERP', '')
    now = datetime.now(timezone.utc)
    px = float(market.get('mark_price') or market.get('last_price') or 0.0)
    spread_bps = float(market.get('spread_bps') or 0.0)
    vol5 = float(market.get('volume_5m_usd') or 0.0)
    vol1h = float(market.get('volume_1h_usd') or 0.0)
    oi = float(market.get('open_interest_usd') or 0.0)
    funding = float(market.get('funding_rate') or 0.0)
    source = str(market.get('source') or 'unknown')

    hist = _HIST[coin]
    if series is not None and len(series) > 0:
        hist.clear()
        for row in series[-500:]:
            hist.append({'ts': row['ts'], 'px': float(row['px']), 'vol5': float(row.get('vol5') or 0.0), 'oi': float(row.get('oi') or 0.0), 'funding': float(row.get('funding') or 0.0)})
    else:
        hist.append({'ts': now, 'px': px, 'vol5': vol5, 'oi': oi, 'funding': funding})
    prices = [x['px'] for x in hist]
    vols = [x['vol5'] for x in hist]
    ois = [x['oi'] for x in hist]

    def lag_ret_sec(sec: int) -> float:
        prev = _value_ago(hist, 'px', sec)
        if prev is None:
            return 0.0
        return _safe_logret(prices[-1], float(prev))

    # returns (time-based horizons)
    ret_1m = lag_ret_sec(60)
    ret_5m = lag_ret_sec(300)
    ret_15m = lag_ret_sec(900)
    ret_1h = lag_ret_sec(3600)
    ret_4h = lag_ret_sec(14400)

    momentum = _clamp(0.5 + (ret_1m * 8 + ret_5m * 5 + ret_15m * 3 + ret_1h * 1.5), 0.0, 1.0)
    acceleration = _clamp(0.5 + ((ret_1m - ret_5m) * 8), 0.0, 1.0)

    # volatility
    def rv_sec(sec: int) -> float:
        if len(hist) < 3:
            return 0.0
        t_now = _norm_ts(hist[-1]['ts'])
        pts = [row for row in hist if t_now is not None and _norm_ts(row['ts']) is not None and (t_now - _norm_ts(row['ts'])).total_seconds() <= sec]
        if len(pts) < 3:
            return 0.0
        p = [float(x['px']) for x in pts]
        rets = [_safe_logret(p[i], p[i-1]) for i in range(1, len(p))]
        return float(statistics.pstdev(rets)) if len(rets) > 1 else 0.0

    rv_5m = rv_sec(300)
    rv_15m = rv_sec(900)
    rv_1h = rv_sec(3600)
    vol_state = 'high' if rv_1h > 0.01 else ('normal' if rv_1h > 0.003 else 'low')

    # trend
    def ma_sec(sec: int) -> float:
        if not hist:
            return 0.0
        t_now = _norm_ts(hist[-1]['ts'])
        pts = [float(row['px']) for row in hist if t_now is not None and _norm_ts(row['ts']) is not None and (t_now - _norm_ts(row['ts'])).total_seconds() <= sec]
        if not pts:
            pts = [prices[-1]]
        return float(statistics.mean(pts))

    ma5, ma15, ma60, ma240 = ma_sec(300), ma_sec(900), ma_sec(3600), ma_sec(14400)

    def trend_from(ma_s: float, ma_l: float) -> str:
        if ma_s > ma_l * 1.0005:
            return 'up'
        if ma_s < ma_l * 0.9995:
            return 'down'
        return 'flat'

    t5 = trend_from(ma5, ma15 if ma15 > 0 else ma5)
    t15 = trend_from(ma15, ma60 if ma60 > 0 else ma15)
    t1h = trend_from(ma60, ma240 if ma240 > 0 else ma60)
    t4h = t1h
    aligned = len({t5, t15, t1h, t4h}) == 1
    trend_alignment = 1.0 if aligned else (0.66 if len({t5, t15, t1h, t4h}) == 2 else 0.33)
    trend_quality = _clamp(abs((ma5 - ma60) / ma60) * 50 if ma60 > 0 else 0.0)

    # volume
    vz5 = _zscore(vol5, vols)
    recent_1h = vols[-12:] if len(vols) >= 12 else vols
    vol1h_now = float(sum(recent_1h))
    vol1h_hist = [sum(vols[max(0, i - 12):i]) for i in range(12, len(vols) + 1)]
    vz1h = _zscore(vol1h_now, vol1h_hist)
    vol_acc = 0.0
    if len(vols) >= 2 and vols[-2] > 0:
        vol_acc = (vols[-1] - vols[-2]) / vols[-2]

    # orderbook proxies from spread/volume (deterministic approximation until L2 integration)
    depth_score = _clamp((vol1h / 5_000_000.0) * 0.7 + (1.0 - _clamp(spread_bps / 25.0)) * 0.3)
    micro_pressure = _clamp(0.5 + (ret_1m * 20), 0.0, 1.0)
    imbalance_10 = _clamp((ret_1m * 25), -1.0, 1.0)
    imbalance_25 = _clamp((ret_5m * 15), -1.0, 1.0)
    slip_bps = max(0.5, spread_bps * (1.2 - depth_score * 0.7))

    # derivatives
    def oi_chg_sec(sec: int) -> float:
        prev = _value_ago(hist, 'oi', sec)
        cur = ois[-1] if ois else 0.0
        if prev is None or cur <= 0 or float(prev) <= 0:
            return 0.0
        return (cur - float(prev)) / float(prev)

    oi5 = oi_chg_sec(300)
    oi15 = oi_chg_sec(900)
    oi1h = oi_chg_sec(3600)
    funding_state = 'positive' if funding > 0.00001 else ('negative' if funding < -0.00001 else 'neutral')

    # structure
    t_now = _norm_ts(hist[-1]['ts'])
    p1h = [float(row['px']) for row in hist if t_now is not None and _norm_ts(row['ts']) is not None and (t_now - _norm_ts(row['ts'])).total_seconds() <= 3600] or prices[-1:]
    p4h = [float(row['px']) for row in hist if t_now is not None and _norm_ts(row['ts']) is not None and (t_now - _norm_ts(row['ts'])).total_seconds() <= 14400] or prices[-1:]
    high1h = max(p1h) if p1h else px
    low1h = min(p1h) if p1h else px
    high4h = max(p4h) if p4h else px
    low4h = min(p4h) if p4h else px

    d1h_hi = _clamp((high1h - px) / high1h if high1h > 0 else 0.0, 0.0, 1.0)
    d1h_lo = _clamp((px - low1h) / low1h if low1h > 0 else 0.0, 0.0, 1.0)
    d4h_hi = _clamp((high4h - px) / high4h if high4h > 0 else 0.0, 0.0, 1.0)
    d4h_lo = _clamp((px - low4h) / low4h if low4h > 0 else 0.0, 0.0, 1.0)
    breakout_state = 'confirmed' if abs(ret_15m) > 0.01 and max(vz5, vz1h) > 1.0 else ('attempt' if abs(ret_5m) > 0.004 else 'none')

    # quality
    history_ready = _value_ago(hist, 'px', 3600) is not None
    source_ok = 1.0 if source == 'hyperliquid_public' else 0.0
    freshness = 1.0
    if len(hist) >= 2:
        t1 = _norm_ts(hist[-1]['ts'])
        t0 = _norm_ts(hist[-2]['ts'])
        if t1 is not None and t0 is not None:
            dt = (t1 - t0).total_seconds()
            freshness = _clamp(1.0 - max(0.0, dt - 60.0) / 240.0)

    liquidity = _clamp(0.6 * depth_score + 0.4 * (1.0 - _clamp(spread_bps / 30.0)))
    completeness = _clamp(
        0.20 * (1.0 if px > 0 else 0.0) +
        0.20 * (1.0 if vol1h > 0 else 0.0) +
        0.20 * (1.0 if oi >= 0 else 0.0) +
        0.40 * (1.0 if history_ready else 0.0)
    )
    source_health = _clamp(0.7 * source_ok + 0.3 * freshness)

    return {
        'returns': {
            'ret_1m': ret_1m,
            'ret_5m': ret_5m,
            'ret_15m': ret_15m,
            'ret_1h': ret_1h,
            'ret_4h': ret_4h,
            'momentum_score': momentum,
            'acceleration_score': acceleration,
        },
        'volatility': {
            'rv_5m': rv_5m,
            'rv_15m': rv_15m,
            'rv_1h': rv_1h,
            'volatility_state': vol_state,
        },
        'trend': {
            'trend_5m': t5,
            'trend_15m': t15,
            'trend_1h': t1h,
            'trend_4h': t4h,
            'trend_alignment_score': trend_alignment,
            'trend_quality_score': trend_quality,
        },
        'volume': {
            'volume_zscore_5m': vz5,
            'volume_zscore_1h': vz1h,
            'volume_acceleration': vol_acc,
        },
        'orderbook': {
            'imbalance_10bp': imbalance_10,
            'imbalance_25bp': imbalance_25,
            'micro_pressure_score': micro_pressure,
            'book_depth_score': depth_score,
            'slippage_estimate_bps': slip_bps,
        },
        'derivatives': {
            'oi_change_5m': oi5,
            'oi_change_15m': oi15,
            'oi_change_1h': oi1h,
            'funding_state': funding_state,
        },
        'structure': {
            'distance_from_1h_high': d1h_hi,
            'distance_from_1h_low': d1h_lo,
            'distance_from_4h_high': d4h_hi,
            'distance_from_4h_low': d4h_lo,
            'breakout_state': breakout_state,
        },
        'quality': {
            'liquidity_score': liquidity,
            'freshness_score': freshness,
            'data_completeness_score': completeness,
            'source_health_score': source_health,
        },
    }
