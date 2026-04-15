"""Tests for src/metrics/vibes.py"""

import pytest

from src.metrics.vibes import _VIBES, _vibe_index, run


def test_vibe_index_is_deterministic():
    idx1 = _vibe_index("main", "/workspace")
    idx2 = _vibe_index("main", "/workspace")
    assert idx1 == idx2


def test_vibe_index_in_range():
    idx = _vibe_index("main", "/workspace")
    assert 0 <= idx < len(_VIBES)


def test_vibe_index_differs_by_ref():
    idx_a = _vibe_index("main", "/workspace")
    idx_b = _vibe_index("develop", "/workspace")
    # Different refs should (almost certainly) produce different indices.
    # This could theoretically collide, but with 6 buckets and two very different
    # inputs it's astronomically unlikely — if it ever fails, change the refs.
    assert idx_a != idx_b


def test_run_returns_metric_result():
    result = run("main", "/workspace")
    assert result.name == "Vibes Check"
    assert result.score in [v[0] for v in _VIBES]
    assert result.status in [v[1] for v in _VIBES]
    assert result.detail in [v[2] for v in _VIBES]


def test_run_is_deterministic():
    r1 = run("main", "/workspace")
    r2 = run("main", "/workspace")
    assert r1.score == r2.score
    assert r1.status == r2.status
    assert r1.detail == r2.detail


@pytest.mark.parametrize("ref,workspace", [
    ("main", "/a"),
    ("main", "/b"),
    ("feat/cool", "/a"),
    ("v1.0.0", "/workspace"),
])
def test_run_all_inputs_produce_valid_vibes(ref, workspace):
    result = run(ref, workspace)
    assert result.name == "Vibes Check"
    assert result.score != ""
    assert result.status in ("✅", "⚠️", "📉")
    assert result.skipped is False
