from __future__ import annotations


def major_reason_for_classification(classification: str, baseline_equity: float, variant_equity: float) -> str:
    if classification == 'keep':
        return 'variant_equity_improved_after_fees'
    if classification == 'reject':
        return 'variant_equity_worse_after_fees'
    return 'delta_within_inconclusive_band_or_insufficient_signal'


def summarize_experiment(exp: dict) -> dict:
    b = (exp.get('baseline_metrics', {}) or {})
    v = (exp.get('variant_metrics', {}) or {})
    b_eq = float((b.get('paper_account', {}) or {}).get('total_equity_usd') or 0.0)
    v_eq = float((v.get('paper_account', {}) or {}).get('total_equity_usd') or 0.0)
    b_fees = float(b.get('fees_usd') or 0.0)
    v_fees = float(v.get('fees_usd') or 0.0)
    b_fills = int((b.get('summary', {}) or {}).get('fill_count') or b.get('fills') or 0)
    v_fills = int((v.get('summary', {}) or {}).get('fill_count') or v.get('fills') or 0)
    cls = str(exp.get('classification') or 'inconclusive')
    return {
        'classification': cls,
        'fills': {'baseline': b_fills, 'variant': v_fills},
        'fees_usd': {'baseline': b_fees, 'variant': v_fees},
        'equity': {'baseline': b_eq, 'variant': v_eq, 'delta': round(v_eq - b_eq, 6)},
        'major_reason': major_reason_for_classification(cls, b_eq, v_eq),
    }
