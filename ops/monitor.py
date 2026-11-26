#!/usr/bin/env python3
"""Poll the public health endpoints and write a secret-free JSONL report."""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ENDPOINTS = ("/healthz", "/api/health")


def probe(base_url: str, path: str, timeout: float) -> dict[str, object]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    started = time.perf_counter()
    status: int | None = None
    error: str | None = None
    body = b""

    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            body = response.read(16_384)
    except HTTPError as exc:
        status = exc.code
        error = f"http_{exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        error = type(reason).__name__

    payload: dict[str, object] = {}
    if path == "/api/health" and body:
        try:
            decoded = json.loads(body)
            if isinstance(decoded, dict):
                payload = decoded
        except (json.JSONDecodeError, UnicodeDecodeError):
            error = "invalid_json"

    ok = status == 200
    if path == "/api/health":
        ok = ok and payload.get("status") == "ok" and payload.get("db") == "ok"
        if status == 200 and not ok and error is None:
            error = "unhealthy_payload"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "path": path,
        "http_status": status,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "ok": ok,
        "error": error,
        "version": payload.get("version"),
    }


def percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="Base URL served by Nginx")
    parser.add_argument("--count", type=int, default=5, help="Number of probe rounds")
    parser.add_argument("--interval", type=float, default=10, help="Seconds between rounds")
    parser.add_argument("--timeout", type=float, default=3, help="Timeout per endpoint in seconds")
    parser.add_argument("--output", type=Path, help="Optional JSONL report path")
    args = parser.parse_args()
    if args.count < 1 or args.interval < 0 or args.timeout <= 0:
        parser.error("count must be >= 1, interval >= 0, and timeout > 0")

    records: list[dict[str, object]] = []
    for round_number in range(args.count):
        for path in ENDPOINTS:
            record = probe(args.url, path, args.timeout)
            records.append(record)
            print(json.dumps(record, ensure_ascii=False))
        if round_number + 1 < args.count:
            time.sleep(args.interval)

    latencies = [float(row["latency_ms"]) for row in records]
    passed = sum(bool(row["ok"]) for row in records)
    summary = {
        "type": "summary",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": len(records),
        "errors": len(records) - passed,
        "availability_pct": round(passed * 100 / len(records), 2),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
        "p95_latency_ms": percentile95(latencies),
    }
    print(json.dumps(summary, ensure_ascii=False))
    records.append(summary)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
            encoding="utf-8",
        )
        print(f"Report saved: {args.output}")

    return 0 if passed == args.count * len(ENDPOINTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
