"""Tests for src/metrics/performance.py"""

import pytest
from unittest.mock import MagicMock, patch

from src.metrics.performance import _parse_durations, run


SAMPLE_PYTEST_OUTPUT = """\
0.42s call     tests/test_foo.py::test_bar
0.10s call     tests/test_foo.py::test_baz
1.20s call     tests/test_slow.py::test_heavy
"""


def test_parse_durations():
    timings = _parse_durations(SAMPLE_PYTEST_OUTPUT)
    assert timings["tests/test_foo.py::test_bar"] == pytest.approx(0.42)  # noqa
    assert timings["tests/test_slow.py::test_heavy"] == pytest.approx(1.20)


def test_run_no_baseline_sets_baseline():
    mock_proc = MagicMock()
    mock_proc.stdout = SAMPLE_PYTEST_OUTPUT

    with patch("src.metrics.performance.cache_client.get_baseline", return_value=None):
        with patch("src.metrics.performance.cache_client.save_baseline") as mock_save:
            with patch("subprocess.run", return_value=mock_proc):
                result = run("main", "/ws", threshold=20)

    assert result.status == "✅"
    assert "Baseline set" in result.score
    mock_save.assert_called_once()


def test_run_no_regressions():
    baseline = {
        "tests/test_foo.py::test_bar": 0.40,
        "tests/test_foo.py::test_baz": 0.10,
        "tests/test_slow.py::test_heavy": 1.20,
    }
    mock_proc = MagicMock()
    mock_proc.stdout = SAMPLE_PYTEST_OUTPUT

    with patch("src.metrics.performance.cache_client.get_baseline", return_value=baseline):
        with patch("src.metrics.performance.cache_client.save_baseline"):
            with patch("subprocess.run", return_value=mock_proc):
                result = run("main", "/ws", threshold=20)

    assert result.status == "✅"
    assert "No regressions" in result.score


def test_run_regression_detected():
    baseline = {
        "tests/test_foo.py::test_bar": 0.10,  # was 100ms, now 420ms → +320%
    }
    mock_proc = MagicMock()
    mock_proc.stdout = SAMPLE_PYTEST_OUTPUT

    with patch("src.metrics.performance.cache_client.get_baseline", return_value=baseline):
        with patch("src.metrics.performance.cache_client.save_baseline"):
            with patch("subprocess.run", return_value=mock_proc):
                result = run("main", "/ws", threshold=20)

    assert result.status == "📉"
    assert "regression" in result.detail


