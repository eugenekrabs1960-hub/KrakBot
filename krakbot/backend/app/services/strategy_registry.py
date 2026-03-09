import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session


STRATEGY_NAME_TO_ID = {
    'trend_following': 'strat_trend_following',
    'mean_reversion': 'strat_mean_reversion',
    'breakout': 'strat_breakout',
}


def create_instance(db: Session, strategy_name: str, market: str, instrument_type: str, starting_equity_usd: float, params: dict) -> dict:
    instance_id = f"inst_{uuid.uuid4().hex[:12]}"
    portfolio_id = f"port_{uuid.uuid4().hex[:12]}"
    strategy_id = STRATEGY_NAME_TO_ID[strategy_name]

    db.execute(
        text(
            """
            INSERT INTO strategy_instances(id, strategy_id, market, instrument_type, enabled, status, params)
            VALUES (:id, :strategy_id, :market, :instrument_type, true, 'idle', :params::jsonb)
            """
        ),
        {
            'id': instance_id,
            'strategy_id': strategy_id,
            'market': market,
            'instrument_type': instrument_type,
            'params': __import__('json').dumps(params),
        },
    )

    db.execute(
        text(
            """
            INSERT INTO paper_portfolios(id, strategy_instance_id, base_currency, starting_equity_usd, equity_usd)
            VALUES (:id, :strategy_instance_id, 'USD', :starting_equity_usd, :starting_equity_usd)
            """
        ),
        {
            'id': portfolio_id,
            'strategy_instance_id': instance_id,
            'starting_equity_usd': starting_equity_usd,
        },
    )

    db.commit()
    return {'strategy_instance_id': instance_id, 'paper_portfolio_id': portfolio_id}


def set_enabled(db: Session, strategy_instance_id: str, enabled: bool):
    db.execute(
        text(
            """
            UPDATE strategy_instances
            SET enabled = :enabled, updated_at = NOW()
            WHERE id = :id
            """
        ),
        {'enabled': enabled, 'id': strategy_instance_id},
    )
    db.commit()
