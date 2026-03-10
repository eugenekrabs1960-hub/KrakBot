from pathlib import Path
import tempfile
import unittest

from src.ingestion import load_from_external_csv


class TestIngestionCSV(unittest.TestCase):
    def test_csv_ingestion_mapping_and_normalization(self):
        with tempfile.TemporaryDirectory() as td:
            research_dir = Path(td)
            raw_dir = research_dir / "data" / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            csv_path = raw_dir / "sample.csv"
            csv_path.write_text(
                "time,o,h,l,c,v\n"
                "2026-03-01 00:00:00,10,12,9,11,100\n"
                "2026-03-01 00:01:00,11,13,10,12,120\n",
                encoding="utf-8",
            )

            cfg = {
                "timeframe": "1m",
                "external_csv": {
                    "path": "data/raw/sample.csv",
                    "timezone": "UTC",
                    "column_mapping": {
                        "timestamp": "time",
                        "open": "o",
                        "high": "h",
                        "low": "l",
                        "close": "c",
                        "volume": "v",
                    },
                },
            }

            out = load_from_external_csv(research_dir, cfg)
            self.assertEqual(list(out.columns)[:6], ["ts", "open", "high", "low", "close", "volume"])
            self.assertEqual(len(out), 2)
            self.assertGreater(int(out.iloc[0]["open_ts"]), 0)
            self.assertGreater(out.iloc[0]["close_ts"], out.iloc[0]["open_ts"])


if __name__ == "__main__":
    unittest.main()
