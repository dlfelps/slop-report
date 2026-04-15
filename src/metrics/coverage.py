"""Change risk / coverage analysis for modified Python lines."""

import json
import os
import subprocess

from src.git_utils import get_changed_python_files, get_changed_line_ranges
from src.report import MetricResult


def _detect_runner(workspace: str) -> str:
    """Return 'pytest' or 'unittest' based on project config files."""
    for marker in ("pytest.ini", "conftest.py"):
        if os.path.exists(os.path.join(workspace, marker)):
            return "pytest"
    for cfg in ("setup.cfg", "pyproject.toml", "tox.ini"):
        path = os.path.join(workspace, cfg)
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            if "pytest" in content:
                return "pytest"
    return "unittest"


def run(base_ref: str, workspace: str, threshold: int) -> MetricResult:
    changed_files = get_changed_python_files(base_ref, workspace)
    if not changed_files:
        return MetricResult(
            name="Change Risk",
            score="N/A",
            status="✅",
            detail="No Python files changed",
        )

    # Build map of file -> changed line numbers
    changed_lines: dict[str, set[int]] = {}
    for f in changed_files:
        lines = get_changed_line_ranges(base_ref, f, workspace)
        if lines:
            changed_lines[f] = lines

    if not any(changed_lines.values()):
        return MetricResult(
            name="Change Risk",
            score="N/A",
            status="✅",
            detail="No added/modified lines detected",
        )

    runner = _detect_runner(workspace)
    cov_json = "/tmp/slop_coverage.json"

    try:
        if runner == "pytest":
            subprocess.run(
                ["coverage", "run", "-m", "pytest", "--tb=no", "-q"],
                cwd=workspace,
                capture_output=True,
                timeout=300,
            )
        else:
            subprocess.run(
                ["coverage", "run", "-m", "unittest", "discover"],
                cwd=workspace,
                capture_output=True,
                timeout=300,
            )

        subprocess.run(
            ["coverage", "json", "-o", cov_json],
            cwd=workspace,
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return MetricResult(
            name="Change Risk",
            score="Error",
            status="⚠️",
            detail=f"Coverage run failed: {e}",
        )

    with open(cov_json) as f:
        cov_data = json.load(f)

    total_changed = 0
    total_covered = 0

    for filepath, line_set in changed_lines.items():
        rel = os.path.relpath(filepath, workspace)
        # coverage.json keys can be absolute or relative depending on version
        file_data = cov_data.get("files", {}).get(filepath) or cov_data.get("files", {}).get(rel)
        if file_data is None:
            total_changed += len(line_set)
            continue
        executed = set(file_data.get("executed_lines", []))
        for line in line_set:
            total_changed += 1
            if line in executed:
                total_covered += 1

    if total_changed == 0:
        pct = 100.0
    else:
        pct = total_covered / total_changed * 100

    status = "✅" if pct >= threshold else "⚠️"
    return MetricResult(
        name="Change Risk",
        score=f"{pct:.0f}% covered",
        status=status,
        detail=(
            f"{total_covered}/{total_changed} changed lines have test coverage"
            if pct >= threshold
            else f"{total_changed - total_covered}/{total_changed} changed lines lack test coverage"
        ),
    )
