"""Tests for src/report.py"""

from src.report import MARKER, MetricResult, render


def test_render_contains_marker():
    results = [MetricResult("Change Risk", "80% covered", "✅", "Good coverage")]
    body = render(results, {"coverage": "80%"})
    assert MARKER in body


def test_render_skips_disabled_metrics():
    results = [
        MetricResult("Change Risk", "80% covered", "✅", "Good coverage"),
        MetricResult("Blast Radius", "Disabled", "—", "Metric disabled", skipped=True),
    ]
    body = render(results, {"coverage": "80%"})
    assert "Change Risk" in body
    assert "Blast Radius" not in body


def test_render_includes_thresholds():
    results = [MetricResult("Maintainability", "75 / 100", "✅", "Above threshold")]
    body = render(results, {"MI": "65", "coverage": "80%"})
    assert "MI=65" in body
    assert "coverage=80%" in body


def test_render_table_structure():
    results = [
        MetricResult("Change Risk", "72% covered", "⚠️", "28% uncovered"),
        MetricResult("Blast Radius", "5 modules", "⚠️", "Medium impact"),
    ]
    body = render(results, {})
    assert "| Metric |" in body
    assert "| Change Risk |" in body
    assert "| Blast Radius |" in body
