"""Utilities for extracting changed files and line ranges from git diff."""

import os
import re
import subprocess


def _run(cmd: list[str], cwd: str) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout


def get_changed_python_files(base_ref: str, workspace: str) -> list[str]:
    """Return absolute paths of Python files changed relative to base_ref."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACM", f"origin/{base_ref}...HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    # git diff exits 0 (no diffs) or 1 (diffs found) in some builds even without
    # --exit-code. Both are valid — use stdout either way. Codes ≥ 2 are fatal
    # errors (bad ref, not a git repo, etc.) and should propagate.
    if result.returncode >= 2:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    files = [line.strip() for line in result.stdout.splitlines() if line.strip() and line.strip().endswith(".py")]
    return [os.path.join(workspace, f) for f in files]


def get_changed_line_ranges(base_ref: str, filepath: str, workspace: str) -> set[int]:
    """Return the set of added/modified line numbers in filepath relative to base_ref."""
    rel = os.path.relpath(filepath, workspace)
    try:
        output = _run(
            ["git", "diff", "-U0", f"origin/{base_ref}...HEAD", "--", rel],
            cwd=workspace,
        )
    except subprocess.CalledProcessError:
        return set()

    changed_lines: set[int] = set()
    # Parse @@ -old_start,old_count +new_start,new_count @@ headers
    for match in re.finditer(r"^\+\+\+ ", output, re.MULTILINE):
        pass  # just confirm we have diff output

    for match in re.finditer(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@", output, re.MULTILINE):
        new_start = int(match.group(1))
        new_count = int(match.group(2)) if match.group(2) is not None else 1
        if new_count == 0:
            continue  # pure deletion, no new lines
        changed_lines.update(range(new_start, new_start + new_count))

    return changed_lines
