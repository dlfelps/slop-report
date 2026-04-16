"""Tests for src/metrics/maintainability.py"""

import json
from unittest.mock import patch, MagicMock
import subprocess

from src.metrics.maintainability import run


def _mock_run(stdout: str):
    m = MagicMock()
    m.stdout = stdout
    m.returncode = 0
    return m


def test_run_no_changed_files():
    with patch("src.metrics.maintainability.get_changed_python_files", return_value=[]):
        result = run("main", "/ws", threshold=65)
    assert result.score == "N/A"
    assert result.status == "✅"


def test_run_above_threshold():
    mi_output = json.dumps({"/ws/foo.py": {"mi": 80.0, "rank": "A"}})
    with patch("src.metrics.maintainability.get_changed_python_files", return_value=["/ws/foo.py"]):
        with patch("subprocess.run", return_value=_mock_run(mi_output)):
            result = run("main", "/ws", threshold=65)
    assert result.status == "✅"
    assert "80" in result.score


def test_run_slightly_below_threshold():
    mi_output = json.dumps({"/ws/foo.py": {"mi": 58.0, "rank": "B"}})
    with patch("src.metrics.maintainability.get_changed_python_files", return_value=["/ws/foo.py"]):
        with patch("subprocess.run", return_value=_mock_run(mi_output)):
            result = run("main", "/ws", threshold=65)
    assert result.status == "⚠️"


def test_run_well_below_threshold():
    mi_output = json.dumps({"/ws/foo.py": {"mi": 30.0, "rank": "C"}})
    with patch("src.metrics.maintainability.get_changed_python_files", return_value=["/ws/foo.py"]):
        with patch("subprocess.run", return_value=_mock_run(mi_output)):
            result = run("main", "/ws", threshold=65)
    assert result.status == "🛑"


def test_run_radon_failure():
    with patch("src.metrics.maintainability.get_changed_python_files", return_value=["/ws/foo.py"]):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "radon")):
            result = run("main", "/ws", threshold=65)
    assert result.status == "⚠️"
    assert "Error" in result.score
