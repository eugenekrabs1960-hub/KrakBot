from __future__ import annotations

from collections import defaultdict

from app.core.config import settings
from app.services.ingest.hyperliquid_market import fetch_market_snapshot


def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def compute_paper_account_from_exec(exec_rows: list[dict]) -> dict:
    starting = float(settings.paper_starting_equity_usd)
    realized = 0.0
    fees = 0.0

    # position lots by symbol (single avg basis, good enough for paper ops)
    qty = defaultdict(float)
    avg = defaultdict(float)

    rows = sorted([e for e in exec_rows if (e.get('mode') == 'paper' and e.get('status') == 'filled')], key=lambda x: x.get('created_at') or '')

    for e in rows:
        px = _f(e.get('fill_price'))
        notional = _f(e.get('filled_notional_usd') or e.get('notional_usd'))
        if px <= 0 or notional <= 0:
            continue
        q = notional / px
        if e.get('action') == 'short':
            q = -q

        fees += _f(e.get('fee_usd'))

        s = e.get('symbol')
        prev_q = qty[s]
        new_q = prev_q + q

        if abs(prev_q) < 1e-12:
            qty[s] = new_q
            avg[s] = px if abs(new_q) > 1e-12 else 0.0
            continue

        if prev_q * q > 0:
            # add same side
            avg[s] = ((abs(prev_q) * avg[s]) + (abs(q) * px)) / (abs(prev_q) + abs(q))
            qty[s] = new_q
            continue

        # reducing/closing/flipping
        close_qty = min(abs(prev_q), abs(q))
        pnl_per_unit = (px - avg[s]) * (1 if prev_q > 0 else -1)
        realized += close_qty * pnl_per_unit

        if abs(new_q) < 1e-12:
            qty[s] = 0.0
            avg[s] = 0.0
        elif prev_q * new_q > 0:
            qty[s] = new_q  # partial close keeps avg
        else:
            qty[s] = new_q
            avg[s] = px  # flipped remainder opens at new px

    unrealized = 0.0
    open_positions = []
    for s, q in qty.items():
        if abs(q) <= 1e-9:
            continue
        coin = s.replace('-PERP', '')
        m = fetch_market_snapshot(coin)
        mark = _f(m.get('mark_price') or m.get('last_price'))
        upnl = ((mark - avg[s]) * q) if mark > 0 else 0.0
        unrealized += upnl
        open_positions.append({'symbol': s, 'qty': q, 'entry_px': avg[s], 'mark_px': mark, 'unrealized_pnl': upnl})

    cash = starting + realized - fees
    equity = cash + unrealized
    return {
        'starting_equity_usd': starting,
        'cash_usd': cash,
        'realized_pnl_usd': realized,
        'unrealized_pnl_usd': unrealized,
        'total_equity_usd': equity,
        'cumulative_fees_usd': fees,
        'open_positions_count': len(open_positions),
    }
