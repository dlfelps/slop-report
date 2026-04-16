"""Tests for src/git_utils.py"""

import subprocess
from unittest.mock import patch

import pytest

from src.git_utils import get_changed_line_ranges, get_changed_python_files


SAMPLE_DIFF_NAMES = "src/foo.py\nsrc/bar.py\n"

SAMPLE_DIFF_PATCH = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -10,3 +10,5 @@ def old():
+    new_line_one = 1
+    new_line_two = 2
@@ -20,0 +23,1 @@
+    another_line = 3
"""


def _make_result(stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_get_changed_python_files():
    with patch("subprocess.run", return_value=_make_result(SAMPLE_DIFF_NAMES)):
        files = get_changed_python_files("main", "/workspace")
    assert files == ["/workspace/src/foo.py", "/workspace/src/bar.py"]


def test_get_changed_python_files_empty():
    with patch("subprocess.run", return_value=_make_result("")):
        files = get_changed_python_files("main", "/workspace")
    assert files == []


def test_get_changed_python_files_filters_non_py():
    mixed = "src/foo.py\nREADME.md\nsrc/bar.py\nDockerfile\n"
    with patch("subprocess.run", return_value=_make_result(mixed)):
        files = get_changed_python_files("main", "/workspace")
    assert files == ["/workspace/src/foo.py", "/workspace/src/bar.py"]


def test_get_changed_python_files_exit_code_1_returns_files():
    """Exit code 1 from git diff is valid in some builds — stdout should still be used."""
    result = subprocess.CompletedProcess(
        args=["git", "diff"], returncode=1, stdout=SAMPLE_DIFF_NAMES, stderr=""
    )
    with patch("subprocess.run", return_value=result):
        files = get_changed_python_files("main", "/workspace")
    assert files == ["/workspace/src/foo.py", "/workspace/src/bar.py"]


def test_get_changed_python_files_fatal_error_raises():
    """Exit codes ≥ 2 (e.g. 128 for bad ref) should raise CalledProcessError."""
    result = subprocess.CompletedProcess(
        args=["git", "diff"], returncode=128, stdout="", stderr="fatal: bad object"
    )
    with patch("subprocess.run", return_value=result):
        with pytest.raises(subprocess.CalledProcessError):
            get_changed_python_files("main", "/workspace")


def test_get_changed_line_ranges():
    with patch("subprocess.run", return_value=_make_result(SAMPLE_DIFF_PATCH)):
        lines = get_changed_line_ranges("main", "/workspace/src/foo.py", "/workspace")
    # @@ -10,3 +10,5 @@ -> lines 10,11,12,13,14; @@ -20,0 +23,1 @@ -> line 23
    assert 10 in lines
    assert 11 in lines
    assert 23 in lines


def test_get_changed_line_ranges_pure_deletion():
    patch_text = "@@ -5,3 +5,0 @@\n-deleted\n"
    with patch("subprocess.run", return_value=_make_result(patch_text)):
        lines = get_changed_line_ranges("main", "/workspace/src/foo.py", "/workspace")
    assert lines == set()
