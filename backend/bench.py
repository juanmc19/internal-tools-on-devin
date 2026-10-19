"""`make bench`: p50/p95 latency of each registered app's benchmark requests against a running, seeded API.

Each app may ship `backend/apps/<app>/bench.py` with `BENCHMARKS = [(label, dev_user, path), ...]`.
SCL-3 threshold: p95 under 300 ms.
"""

from __future__ import annotations

import importlib
import os
import statistics
import sys
import time

import httpx

from backend.apps import MANIFESTS

BASE_URL = os.environ.get("BENCH_URL", "http://127.0.0.1:8000")
ROUNDS = int(os.environ.get("BENCH_ROUNDS", "40"))
P95_LIMIT_MS = 300.0


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def main() -> int:
    failed = False
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        health = client.get("/health").json()
        print(
            f"{BASE_URL} env={health['env']} "
            + ", ".join(f"{a['key']}={a['record_count']:,}" for a in health["apps"])
        )
        for manifest in MANIFESTS:
            try:
                module = importlib.import_module(f"backend.apps.{manifest.key}.bench")
            except ModuleNotFoundError:
                continue
            print(f"\n{manifest.name} ({ROUNDS} rounds each)")
            print(f"  {'scenario':<36} {'p50 ms':>8} {'p95 ms':>8} {'total':>8}")
            for label, dev_user, path in module.BENCHMARKS:
                samples: list[float] = []
                total = None
                for _ in range(ROUNDS):
                    started = time.perf_counter()
                    response = client.get(path, headers={"X-Dev-User": dev_user})
                    samples.append((time.perf_counter() - started) * 1000)
                    response.raise_for_status()
                    payload = response.json()
                    total = payload.get("total", payload.get("count"))
                p95 = percentile(samples, 95)
                flag = "" if p95 < P95_LIMIT_MS else "  FAIL"
                failed = failed or bool(flag)
                shown = total if total is not None else ""
                print(f"  {label:<36} {statistics.median(samples):>8.1f} {p95:>8.1f} {shown:>8}{flag}")
    print(f"\np95 limit {P95_LIMIT_MS:.0f} ms: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
