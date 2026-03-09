from sqlalchemy import String, Float, DateTime, Boolean, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime


class Base(DeclarativeBase):
    pass


class StrategyInstance(Base):
    __tablename__ = "strategy_instances"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    market: Mapped[str] = mapped_column(String, nullable=False)
    instrument_type: Mapped[str] = mapped_column(String, default="spot")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy_instance_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    base_currency: Mapped[str] = mapped_column(String, default="USD")
    equity_usd: Mapped[float] = mapped_column(Float, default=0.0)


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_instance_id: Mapped[str] = mapped_column(String, index=True)
    pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_pct: Mapped[float] = mapped_column(Float, default=0.0)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
