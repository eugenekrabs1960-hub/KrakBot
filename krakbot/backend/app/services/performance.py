class PerformanceService:
    """Single canonical location for PnL/metrics calculations."""

    @staticmethod
    def compute_win_rate(wins: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round((wins / total) * 100.0, 4)
