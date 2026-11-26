#!/usr/bin/env python3
"""Compare same-run catalog benchmark JSON and create a report plus SVG chart."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path, phase: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("phase") != phase:
        raise ValueError(f"{path} must contain phase={phase!r}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("qa-results"))
    args = parser.parse_args()

    before = load(args.before, "before")
    after = load(args.after, "after")
    if before.get("fixture") != after.get("fixture"):
        raise SystemExit("Benchmark fixtures differ; comparison is invalid")
    if before.get("method") != after.get("method"):
        raise SystemExit("Benchmark methods differ; comparison is invalid")

    cases = []
    for limit in sorted(before["cases"], key=int):
        old = before["cases"][limit]
        new = after["cases"].get(limit)
        if new is None:
            raise SystemExit(f"After result is missing limit={limit}")
        if old["payload_sha256"] != new["payload_sha256"]:
            raise SystemExit(f"Response payload differs for limit={limit}; behavior changed")
        cases.append((limit, old, new))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Catalog benchmark: before / after",
        "",
        f"Fixture: {json.dumps(before['fixture'], ensure_ascii=False)}. Method: {before['method']}.",
        "The response payload SHA-256 matched for each page size. Timings are measurements from one CI runner and are not an SLA.",
        "",
        "| Page size | Median before (ms) | Median after (ms) | Change | p95 before / after (ms) | SQL queries before / after |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for limit, old, new in cases:
        delta = (new["median_ms"] / old["median_ms"] - 1) * 100 if old["median_ms"] else 0
        lines.append(
            f"| {limit} | {old['median_ms']:.3f} | {new['median_ms']:.3f} | {delta:+.1f}% | "
            f"{old['p95_ms']:.3f} / {new['p95_ms']:.3f} | {old['sql_queries']} / {new['sql_queries']} |"
        )
    (args.output_dir / "catalog-benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    width, height = 820, 110 + 90 * len(cases)
    max_value = max(
        max(old["median_ms"], new["median_ms"]) for _, old, new in cases
    ) or 1
    scale = 500 / max_value
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="34" font-family="Arial,sans-serif" font-size="20" font-weight="bold" fill="#172033">Catalog median latency (lower is better)</text>',
    ]
    for i, (limit, old, new) in enumerate(cases):
        y = 72 + i * 90
        svg.append(f'<text x="24" y="{y + 18}" font-family="Arial,sans-serif" font-size="15" fill="#172033">Page size {limit}</text>')
        for offset, value, color, label in (
            (28, old["median_ms"], "#8793a8", "before"),
            (53, new["median_ms"], "#2474d2", "after"),
        ):
            bar_width = max(1, value * scale)
            svg.append(f'<rect x="150" y="{y + offset}" width="{bar_width:.1f}" height="18" rx="4" fill="{color}"/>')
            svg.append(f'<text x="{min(660, 158 + bar_width):.1f}" y="{y + offset + 14}" font-family="Arial,sans-serif" font-size="13" fill="#172033">{label}: {value:.3f} ms</text>')
    svg.append('</svg>')
    (args.output_dir / "catalog-benchmark.svg").write_text("\n".join(svg) + "\n", encoding="utf-8")
    print("Wrote catalog-benchmark.md and catalog-benchmark.svg; response hashes match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
