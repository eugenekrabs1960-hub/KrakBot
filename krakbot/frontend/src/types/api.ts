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
