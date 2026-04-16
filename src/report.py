"""Render metric results as a markdown PR comment."""

from dataclasses import dataclass


MARKER = "<!-- slop-report-marker -->"


@dataclass
class MetricResult:
    name: str
    score: str
    status: str   # emoji: ✅ ⚠️ 🛑
    detail: str
    skipped: bool = False


def render(results: list[MetricResult], thresholds: dict) -> str:
    active = [r for r in results if not r.skipped]

    rows = "\n".join(
        f"| {r.name} | {r.score} | {r.status} | {r.detail} |"
        for r in active
    )

    threshold_line = " · ".join(
        f"{k}={v}" for k, v in thresholds.items()
    )

    return (
        f"{MARKER}\n"
        "## Slop Report\n\n"
        "| Metric | Score | Status | Details |\n"
        "|--------|-------|--------|----------|\n"
        f"{rows}\n\n"
        f"*Powered by [slop-report](https://github.com/dlfelps/slop-report) · Thresholds: {threshold_line}*"
    )
