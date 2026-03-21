from sqlalchemy import String, Float, DateTime, Text, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class FeaturePacketDB(Base):
    __tablename__ = "feature_packets"
    packet_id: Mapped[str] = mapped_column(String, primary_key=True)
    coin: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    payload: Mapped[dict] = mapped_column(JSON)


class DecisionOutputDB(Base):
    __tablename__ = "decision_outputs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    packet_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    payload: Mapped[dict] = mapped_column(JSON)


class PolicyDecisionDB(Base):
    __tablename__ = "policy_decisions"
    policy_decision_id: Mapped[str] = mapped_column(String, primary_key=True)
    packet_id: Mapped[str] = mapped_column(String, index=True)
    final_action: Mapped[str] = mapped_column(String)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime)
    payload: Mapped[dict] = mapped_column(JSON)


class ExecutionRecordDB(Base):
    __tablename__ = "execution_records"
    execution_id: Mapped[str] = mapped_column(String, primary_key=True)
    packet_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    filled_notional_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    payload: Mapped[dict] = mapped_column(JSON)


class PositionDB(Base):
    __tablename__ = "lab_positions"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    qty: Mapped[float] = mapped_column(Float, default=0)
    avg_entry: Mapped[float] = mapped_column(Float, default=0)
    mode: Mapped[str] = mapped_column(String, default="paper")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OutcomeLabelDB(Base):
    __tablename__ = "outcome_labels"
    outcome_id: Mapped[str] = mapped_column(String, primary_key=True)
    packet_id: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime)


class ConfigProfileDB(Base):
    __tablename__ = "config_profiles"
    profile_id: Mapped[str] = mapped_column(String, primary_key=True)
    profile_type: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON)


class TrackedUniverseDB(Base):
    __tablename__ = "tracked_universe"
    coin: Mapped[str] = mapped_column(String, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ReviewReportDB(Base):
    __tablename__ = "review_reports"
    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    packet_id: Mapped[str] = mapped_column(String, index=True)
    recommendation: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime)


class LoopRunDB(Base):
    __tablename__ = "loop_runs"
    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    loop_type: Mapped[str] = mapped_column(String, index=True)  # feature|decision
    status: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class LiveRelayRequestDB(Base):
    __tablename__ = "live_relay_requests"
    idempotency_key: Mapped[str] = mapped_column(String, primary_key=True)
    action: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ReconciliationRunDB(Base):
    __tablename__ = "reconciliation_runs"
    recon_id: Mapped[str] = mapped_column(String, primary_key=True)
    mode: Mapped[str] = mapped_column(String)
    broker_position_count: Mapped[int] = mapped_column(Integer)
    local_position_count: Mapped[int] = mapped_column(Integer)
    drift_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class WalletEventDB(Base):
    __tablename__ = "wallet_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    coin: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    wallet_address: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String)
    notional_usd: Mapped[float] = mapped_column(Float)
    event_ts: Mapped[datetime] = mapped_column(DateTime)
    bucket_ts: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)


class WalletSummaryDB(Base):
    __tablename__ = "wallet_summaries"
    summary_id: Mapped[str] = mapped_column(String, primary_key=True)
    coin: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class ExperimentRunDB(Base):
    __tablename__ = "experiment_runs"
    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class MarketSnapshot1mDB(Base):
    __tablename__ = "market_snapshots_1m"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    coin: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    mid_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    mark_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    index_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_interest_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_5m_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_1h_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String, default='unknown')


class AutonomyRecommendationDB(Base):
    __tablename__ = "autonomy_recommendations"
    recommendation_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
