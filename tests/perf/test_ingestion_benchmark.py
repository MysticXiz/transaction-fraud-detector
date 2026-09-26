import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from src.fraud_detector.computational.ingestion.dataset_csv import DatasetCsvReader


def _synthetic_creditcard_csv(rows: int) -> bytes:
    features = ",".join(f"V{index}" for index in range(1, 29))
    header = f"Time,{features},Amount,Class\n"
    line = "1.5," + ",".join(["-0.123456"] * 28) + ",12.34,0\n"
    return (header + line * rows).encode("utf-8")


class IngestionBenchmarkTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("RUN_INGESTION_BENCH") == "1",
        "Benchmark de ingestão em massa; execute com RUN_INGESTION_BENCH=1",
    )
    def test_parser_throughput_on_bulk_csv(self):
        rows = int(os.environ.get("INGESTION_BENCH_ROWS", "50000"))
        payload = _synthetic_creditcard_csv(rows)
        with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as handle:
            handle.write(payload)
            path = Path(handle.name)
        try:
            started = time.perf_counter()
            parser = DatasetCsvReader(path)
            parsed = sum(1 for _ in parser.iter_copy_text(1))
            elapsed = time.perf_counter() - started
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(parsed, rows)
        megabytes = len(payload) / (1024 * 1024)
        print(
            f"\nBENCH parser rows={parsed} bytes={len(payload)} "
            f"seconds={elapsed:.3f} rows_per_s={parsed / elapsed:.0f} "
            f"mb_per_s={megabytes / elapsed:.2f}"
        )
        self.assertGreater(parsed / elapsed, 1000)
