import unittest

import pandas as pd

from src.data_quality import run_quality_checks


class TestDataQuality(unittest.TestCase):
    def test_data_quality_dedupe_missing_and_ohlc_sanity(self):
        df = pd.DataFrame(
            {
                "ts": [
                    "2026-03-01T00:00:00Z",
                    "2026-03-01T00:01:00Z",
                    "2026-03-01T00:01:00Z",
                    "2026-03-01T00:03:00Z",
                ],
                "open": [10, 11, 11, 12],
                "high": [11, 12, 12, 11],
                "low": [9, 10, 10, 13],
                "close": [10.5, 11.5, 11.5, 12.5],
                "volume": [100, 100, 100, 100],
            }
        )

        cleaned, report = run_quality_checks(df, timeframe="1m")

        self.assertEqual(len(cleaned), 3)
        self.assertEqual(report["duplicates_removed"], 1)
        self.assertEqual(report["missing_interval_count"], 1)
        self.assertEqual(report["ohlc_sanity_violations"], 1)
        self.assertTrue(report["monotonic_timestamps"])


if __name__ == "__main__":
    unittest.main()
