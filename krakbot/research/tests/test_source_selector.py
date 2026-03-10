from pathlib import Path
import tempfile
import unittest

from src.ingestion import load_dataset_by_source


class TestSourceSelector(unittest.TestCase):
    def test_source_selector_routes_external_csv(self):
        with tempfile.TemporaryDirectory() as td:
            research_dir = Path(td)
            raw_dir = research_dir / "data" / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / "ohlcv.csv").write_text(
                "timestamp,open,high,low,close,volume\n"
                "2026-03-01T00:00:00Z,1,2,0.5,1.5,10\n",
                encoding="utf-8",
            )

            cfg = {
                "source": "external_csv",
                "timeframe": "1m",
                "external_csv": {
                    "path": "data/raw/ohlcv.csv",
                    "timezone": "UTC",
                    "column_mapping": {
                        "timestamp": "timestamp",
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close",
                        "volume": "volume",
                    },
                },
            }

            df = load_dataset_by_source(research_dir, cfg, database_url=None)
            self.assertEqual(len(df), 1)
            self.assertEqual(float(df.iloc[0]["close"]), 1.5)


if __name__ == "__main__":
    unittest.main()
