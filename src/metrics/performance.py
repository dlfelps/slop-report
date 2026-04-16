"""Performance regression analysis: run tests on base branch and HEAD, then compare."""

import io
import re
import shutil
import subprocess
import tarfile
import tempfile

from src.report import MetricResult


def _parse_durations(output: str) -> dict[str, float]:
    """Parse pytest --durations=0 output into {test_id: seconds}."""
    timings: dict[str, float] = {}
    # Lines look like: "0.42s call     tests/test_foo.py::test_bar"
    pattern = re.compile(r"^\s*([\d.]+)s\s+\w+\s+(.+)$", re.MULTILINE)
    for match in pattern.finditer(output):
        duration = float(match.group(1))
        test_id = match.group(2).strip()
        timings[test_id] = duration
    return timings


def _run_pytest(cwd: str) -> tuple[dict[str, float], bool]:
    """Run pytest --durations=0 in cwd. Returns (timings, timed_out)."""
    try:
        result = subprocess.run(
            # --durations-min=0 forces all durations to be shown regardless of how
            # fast they are (pytest 6+ defaults to hiding anything under 0.005s).
            ["pytest", "--tb=no", "-q", "--durations=0", "--durations-min=0"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return _parse_durations(result.stdout), False
    except subprocess.TimeoutExpired:
        return {}, True


def _extract_base(base_ref: str, workspace: str, dest: str) -> tuple[bool, str]:
    """Extract base ref source tree into dest via git archive.
    Returns (success, error_detail)."""
    result = subprocess.run(
        ["git", "-c", "safe.directory=*", "archive", "--format=tar", f"origin/{base_ref}"],
        cwd=workspace,
        capture_output=True,
    )
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace").strip()[:200] or f"exit {result.returncode}"
        return False, err
    try:
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
            tar.extractall(dest)
        return True, ""
    except Exception as e:
        return False, str(e)[:200]


def run(base_ref: str, workspace: str, threshold: int) -> MetricResult:
    # Run tests on HEAD first
    current, timed_out = _run_pytest(workspace)
    if timed_out:
        return MetricResult(
            name="Performance",
            score="Timeout",
            status="⚠️",
            detail="Test suite timed out after 5 minutes",
        )

    # Extract base branch into a temp directory and run its tests
    baseline: dict[str, float] | None = None
    extract_err = ""
    tmpdir = tempfile.mkdtemp()
    try:
        ok, extract_err = _extract_base(base_ref, workspace, tmpdir)
        if ok:
            base_timings, _ = _run_pytest(tmpdir)
            if base_timings:
                baseline = base_timings
    except Exception as e:
        extract_err = str(e)[:200]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if not baseline:
        reason = extract_err or "no test timings produced"
        return MetricResult(
            name="Performance",
            score="N/A",
            status="⚠️",
            detail=f"Could not establish baseline from {base_ref}: {reason}",
        )

    regressions: list[tuple[str, float, float]] = []
    for test_id, new_time in current.items():
        old_time = baseline.get(test_id)
        if old_time and old_time > 0:
            pct_change = (new_time - old_time) / old_time * 100
            if pct_change > threshold:
                regressions.append((test_id, old_time, new_time))

    if not regressions:
        return MetricResult(
            name="Performance",
            score="No regressions",
            status="✅",
            detail=f"No tests exceeded {threshold}% slowdown threshold",
        )

    regressions.sort(key=lambda x: (x[2] - x[1]) / x[1], reverse=True)
    worst = regressions[0]
    worst_pct = (worst[2] - worst[1]) / worst[1] * 100
    short_id = worst[0].split("::")[-1]

    detail = (
        f"{len(regressions)} regression{'s' if len(regressions) != 1 else ''} found; "
        f"worst: {short_id} {worst[1]:.0f}ms → {worst[2]:.0f}ms (+{worst_pct:.0f}%)"
    )

    return MetricResult(
        name="Performance",
        score=f"+{worst_pct:.0f}% slowdown",
        status="🛑",
        detail=detail,
    )
