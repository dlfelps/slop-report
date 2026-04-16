"""Tests for src/metrics/performance.py"""

import pytest
from unittest.mock import MagicMock, patch

from src.metrics.performance import _parse_durations, _run_pytest, run


SAMPLE_PYTEST_OUTPUT = """\
0.42s call     tests/test_foo.py::test_bar
0.10s call     tests/test_foo.py::test_baz
1.20s call     tests/test_slow.py::test_heavy
"""

SAMPLE_TIMINGS = {
    "tests/test_foo.py::test_bar": 0.42,
    "tests/test_foo.py::test_baz": 0.10,
    "tests/test_slow.py::test_heavy": 1.20,
}


# ---------------------------------------------------------------------------
# _parse_durations
# ---------------------------------------------------------------------------

def test_parse_durations():
    timings = _parse_durations(SAMPLE_PYTEST_OUTPUT)
    assert timings["tests/test_foo.py::test_bar"] == pytest.approx(0.42)
    assert timings["tests/test_slow.py::test_heavy"] == pytest.approx(1.20)


# ---------------------------------------------------------------------------
# _run_pytest
# ---------------------------------------------------------------------------

def test_run_pytest_returns_timings():
    mock_proc = MagicMock()
    mock_proc.stdout = SAMPLE_PYTEST_OUTPUT
    with patch("subprocess.run", return_value=mock_proc):
        timings, timed_out = _run_pytest("/ws")
    assert not timed_out
    assert timings["tests/test_foo.py::test_bar"] == pytest.approx(0.42)


def test_run_pytest_timeout():
    with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("pytest", 300)):
        timings, timed_out = _run_pytest("/ws")
    assert timed_out
    assert timings == {}


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

def test_run_head_timeout():
    with patch("src.metrics.performance._run_pytest", return_value=({}, True)):
        with patch("src.metrics.performance._extract_base", return_value=(False, "git archive failed")):
            with patch("tempfile.mkdtemp", return_value="/tmp/fake"):
                with patch("shutil.rmtree"):
                    result = run("main", "/ws", threshold=20)
    assert result.status == "⚠️"
    assert "Timeout" in result.score


def test_run_extract_fails_returns_na():
    """When git archive fails, report N/A with the error detail."""
    with patch("src.metrics.performance._run_pytest", return_value=(SAMPLE_TIMINGS, False)):
        with patch("src.metrics.performance._extract_base", return_value=(False, "fatal: bad object")):
            with patch("tempfile.mkdtemp", return_value="/tmp/fake"):
                with patch("shutil.rmtree"):
                    result = run("main", "/ws", threshold=20)
    assert result.status == "⚠️"
    assert "N/A" in result.score
    assert "fatal: bad object" in result.detail


def test_run_no_regressions():
    """Same timings on HEAD and base → no regressions."""
    with patch("src.metrics.performance._run_pytest", return_value=(SAMPLE_TIMINGS, False)):
        with patch("src.metrics.performance._extract_base", return_value=(True, "")):
            with patch("tempfile.mkdtemp", return_value="/tmp/fake"):
                with patch("shutil.rmtree"):
                    result = run("main", "/ws", threshold=20)
    assert result.status == "✅"
    assert "No regressions" in result.score


def test_run_regression_detected():
    """HEAD is slower than base → regression flagged."""
    baseline = {"tests/test_foo.py::test_bar": 0.10}   # 100 ms on base
    current  = {"tests/test_foo.py::test_bar": 0.42}   # 420 ms on HEAD → +320%

    call_count = [0]

    def side_effect(cwd):
        call_count[0] += 1
        return (current, False) if call_count[0] == 1 else (baseline, False)

    with patch("src.metrics.performance._run_pytest", side_effect=side_effect):
        with patch("src.metrics.performance._extract_base", return_value=(True, "")):
            with patch("tempfile.mkdtemp", return_value="/tmp/fake"):
                with patch("shutil.rmtree"):
                    result = run("main", "/ws", threshold=20)

    assert result.status == "🛑"
    assert "regression" in result.detail
