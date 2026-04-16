"""Maintainability index analysis using radon."""

import json
import subprocess

from src.git_utils import get_changed_python_files
from src.report import MetricResult


def run(base_ref: str, workspace: str, threshold: int) -> MetricResult:
    changed_files = get_changed_python_files(base_ref, workspace)
    if not changed_files:
        return MetricResult(
            name="Maintainability",
            score="N/A",
            status="✅",
            detail="No Python files changed",
        )

    try:
        result = subprocess.run(
            ["radon", "mi", "--json"] + changed_files,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        mi_data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return MetricResult(
            name="Maintainability",
            score="Error",
            status="⚠️",
            detail=f"radon mi failed: {e}",
        )

    if not mi_data:
        return MetricResult(
            name="Maintainability",
            score="N/A",
            status="✅",
            detail="No scoreable files in changeset",
        )

    scores = [entry["mi"] for entry in mi_data.values() if "mi" in entry]
    if not scores:
        return MetricResult(
            name="Maintainability",
            score="N/A",
            status="✅",
            detail="No scoreable files in changeset",
        )

    avg_score = sum(scores) / len(scores)

    if avg_score >= threshold:
        status = "✅"
        detail = f"Above threshold ({threshold})"
    elif avg_score >= threshold - 10:
        status = "⚠️"
        detail = f"Slightly below threshold ({threshold})"
    else:
        status = "🛑"
        detail = f"Well below threshold ({threshold})"

    return MetricResult(
        name="Maintainability",
        score=f"{avg_score:.0f} / 100",
        status=status,
        detail=detail,
    )
