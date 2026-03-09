from app.services.performance import PerformanceService


def test_win_rate_zero_safe():
    assert PerformanceService.compute_win_rate(0, 0) == 0.0


def test_win_rate_math():
    assert PerformanceService.compute_win_rate(5, 10) == 50.0
