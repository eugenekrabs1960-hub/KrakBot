export type BotCommand = 'start' | 'stop' | 'pause' | 'resume' | 'reload';

export interface StrategyCard {
  strategy_instance_id: string;
  name: 'trend_following' | 'mean_reversion' | 'breakout';
  enabled: boolean;
  market: string;
  pnl_usd: number;
  drawdown_pct: number;
  win_rate_pct: number;
  trade_count: number;
}

export interface TradeRow {
  strategy_instance_id: string;
  side: 'buy' | 'sell';
  qty: number;
  entry_price: number;
  exit_price?: number;
  realized_pnl_usd?: number;
  ts: string;
}

export interface EifSummaryResponse {
  analytics_api_enabled: boolean;
  capture_enabled?: boolean;
  shadow_mode?: boolean;
  enforce_mode?: boolean;
  summary: {
    context_events?: number;
    filter_decisions?: number;
    allowed_decisions?: number;
    blocked_decisions?: number;
    regime_snapshots?: number;
    scorecard_snapshots?: number;
  };
}

export interface EifRegimeRow {
  id: number;
  strategy_instance_id: string;
  market: string;
  trend: string;
  volatility: string;
  liquidity: string;
  session_structure: string;
  sample_size: number;
  captured_ts: string;
}

export interface EifFilterDecisionRow {
  id: number;
  strategy_instance_id: string;
  market: string;
  decision: string;
  reason_code: string;
  allowed: boolean;
  precedence_stage?: string;
  regime_snapshot_id?: number;
  trace?: unknown;
  ts: string;
}
