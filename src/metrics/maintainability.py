"""Maintainability metrics: regression on modified files and quality of new files."""

import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile

from src.git_utils import get_modified_python_files, get_added_python_files
from src.report import MetricResult


def _radon_scores(files: list[str]) -> dict[str, float]:
    """Run radon mi --json on a list of files. Returns {path: mi_score}."""
    if not files:
        return {}
    result = subprocess.run(
        ["radon", "mi", "--json"] + files,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if not result.stdout.strip():
        return {}
    try:
        data = json.loads(result.stdout)
        return {path: entry["mi"] for path, entry in data.items() if "mi" in entry}
    except (json.JSONDecodeError, KeyError):
        return {}


def _radon_scores_dir(directory: str) -> list[float]:
    """Run radon mi --json on all Python files in a directory. Returns list of scores."""
    result = subprocess.run(
        ["radon", "mi", "--json", directory],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
        return [entry["mi"] for entry in data.values() if "mi" in entry]
    except (json.JSONDecodeError, KeyError):
        return []


def _base_mi(base_ref: str, workspace: str, abs_path: str) -> float | None:
    """Get radon MI for a single file at the base branch via git show."""
    rel = os.path.relpath(abs_path, workspace)
    result = subprocess.run(
        ["git", "-c", f"safe.directory={workspace}", "show", f"origin/{base_ref}:{rel}"],
        cwd=workspace,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    try:
        tmp.write(result.stdout)
        tmp.close()
        scores = _radon_scores([tmp.name])
        return next(iter(scores.values()), None)
    finally:
        os.unlink(tmp.name)


def _extract_base(base_ref: str, workspace: str, dest: str) -> tuple[bool, str]:
    """Extract base ref into dest using git archive. Returns (success, error_detail)."""
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


def run_regression(base_ref: str, workspace: str, repo: str = "", pr_number: int = 0) -> MetricResult:
    """Worst-case absolute MI point change across modified files only."""
    modified = get_modified_python_files(base_ref, workspace)
    if not modified:
        return MetricResult(
            name="MI Regression",
            score="N/A",
            status="✅",
            detail="No modified Python files",
        )

    changes: list[tuple[str, str, float, float, float]] = []  # (filename, rel_path, base_mi, head_mi, diff)
    for abs_path in modified:
        head_scores = _radon_scores([abs_path])
        head_mi = next(iter(head_scores.values()), None)
        base = _base_mi(base_ref, workspace, abs_path)
        if head_mi is not None and base is not None:
            rel = os.path.relpath(abs_path, workspace)
            changes.append((os.path.basename(abs_path), rel, base, head_mi, head_mi - base))

    if not changes:
        return MetricResult(
            name="MI Regression",
            score="N/A",
            status="⚠️",
            detail="Could not compute MI for any modified file",
        )

    worst = min(changes, key=lambda x: x[4])
    worst_name, worst_rel, worst_base, worst_head, worst_diff = worst

    if repo and pr_number:
        anchor = hashlib.md5(worst_rel.encode()).hexdigest()
        file_ref = f"[{worst_name}](https://github.com/{repo}/pull/{pr_number}/files#diff-{anchor})"
    else:
        file_ref = worst_name

    if worst_diff >= 0:
        status = "✅"
        detail = f"No regression detected ({len(changes)} file(s) checked)"
    elif worst_diff >= -10:
        status = "⚠️"
        detail = f"Worst: {file_ref} ({worst_base:.0f} → {worst_head:.0f})"
    else:
        status = "🛑"
        detail = f"Worst: {file_ref} ({worst_base:.0f} → {worst_head:.0f})"

    return MetricResult(
        name="MI Regression",
        score=f"{worst_diff:+.0f} pts",
        status=status,
        detail=detail,
    )


def run_new_files(base_ref: str, workspace: str) -> MetricResult:
    """Avg MI of added files relative to the avg MI of the base branch."""
    added = get_added_python_files(base_ref, workspace)
    if not added:
        return MetricResult(
            name="New File Quality",
            score="N/A",
            status="✅",
            detail="No new Python files added",
        )

    new_scores = list(_radon_scores(added).values())
    if not new_scores:
        return MetricResult(
            name="New File Quality",
            score="N/A",
            status="⚠️",
            detail="Could not compute MI for new files",
        )
    avg_new = sum(new_scores) / len(new_scores)

    tmpdir = tempfile.mkdtemp()
    try:
        ok, err = _extract_base(base_ref, workspace, tmpdir)
        if not ok:
            return MetricResult(
                name="New File Quality",
                score=f"{avg_new:.0f} / 100",
                status="⚠️",
                detail=f"Could not extract {base_ref} for comparison: {err}",
            )
        base_scores = _radon_scores_dir(tmpdir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if not base_scores:
        return MetricResult(
            name="New File Quality",
            score=f"{avg_new:.0f} / 100",
            status="⚠️",
            detail=f"No Python files found on {base_ref} to compare against",
        )

    avg_base = sum(base_scores) / len(base_scores)
    ratio = avg_new / avg_base if avg_base > 0 else 1.0

    if ratio >= 1.0:
        status = "✅"
    elif ratio >= 0.9:
        status = "⚠️"
    else:
        status = "🛑"

    return MetricResult(
        name="New File Quality",
        score=f"{ratio:.2f}×",
        status=status,
        detail=f"New files avg MI {avg_new:.0f} vs {base_ref} avg {avg_base:.0f}",
    )
