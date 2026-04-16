"""Tests for src/metrics/maintainability.py"""

from unittest.mock import patch

from src.metrics.maintainability import run_regression, run_new_files


# ---------------------------------------------------------------------------
# run_regression
# ---------------------------------------------------------------------------

def test_regression_no_modified_files():
    with patch("src.metrics.maintainability.get_modified_python_files", return_value=[]):
        result = run_regression("main", "/ws")
    assert result.score == "N/A"
    assert result.status == "✅"


def test_regression_improvement():
    """File improved 70 → 80 (+10 pts): no regression, ✅."""
    with patch("src.metrics.maintainability.get_modified_python_files", return_value=["/ws/foo.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={"/ws/foo.py": 80.0}):
            with patch("src.metrics.maintainability._base_mi", return_value=70.0):
                result = run_regression("main", "/ws")
    assert result.status == "✅"
    assert result.score == "+10 pts"


def test_regression_slight():
    """File regressed 65 → 60 (−5 pts): ⚠️."""
    with patch("src.metrics.maintainability.get_modified_python_files", return_value=["/ws/foo.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={"/ws/foo.py": 60.0}):
            with patch("src.metrics.maintainability._base_mi", return_value=65.0):
                result = run_regression("main", "/ws")
    assert result.status == "⚠️"
    assert result.score == "-5 pts"
    assert "65" in result.detail and "60" in result.detail


def test_regression_severe():
    """File regressed 65 → 40 (−25 pts): 🛑."""
    with patch("src.metrics.maintainability.get_modified_python_files", return_value=["/ws/foo.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={"/ws/foo.py": 40.0}):
            with patch("src.metrics.maintainability._base_mi", return_value=65.0):
                result = run_regression("main", "/ws")
    assert result.status == "🛑"
    assert result.score == "-25 pts"
    assert "65" in result.detail and "40" in result.detail


def test_regression_picks_worst():
    """Multiple files: worst absolute drop drives the result."""
    files = ["/ws/a.py", "/ws/b.py"]
    # a.py: 80 → 85 (+5 pts)
    # b.py: 70 → 55 (−15 pts)  ← worst
    call_count = [0]

    def mock_radon(file_list):
        call_count[0] += 1
        return {file_list[0]: 85.0 if call_count[0] == 1 else 55.0}

    def mock_base(base_ref, workspace, abs_path):
        return 80.0 if abs_path == "/ws/a.py" else 70.0

    with patch("src.metrics.maintainability.get_modified_python_files", return_value=files):
        with patch("src.metrics.maintainability._radon_scores", side_effect=mock_radon):
            with patch("src.metrics.maintainability._base_mi", side_effect=mock_base):
                result = run_regression("main", "/ws")

    assert result.status == "🛑"
    assert "b.py" in result.detail


def test_regression_detail_links_to_diff():
    """When repo and pr_number are supplied, detail contains a GitHub diff link."""
    with patch("src.metrics.maintainability.get_modified_python_files", return_value=["/ws/src/foo.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={"/ws/src/foo.py": 40.0}):
            with patch("src.metrics.maintainability._base_mi", return_value=65.0):
                result = run_regression("main", "/ws", repo="owner/repo", pr_number=42)
    assert "https://github.com/owner/repo/pull/42/files#diff-" in result.detail
    assert "[foo.py]" in result.detail


def test_regression_cannot_compute_mi():
    """If radon returns nothing for all files, report ⚠️."""
    with patch("src.metrics.maintainability.get_modified_python_files", return_value=["/ws/foo.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={}):
            with patch("src.metrics.maintainability._base_mi", return_value=None):
                result = run_regression("main", "/ws")
    assert result.score == "N/A"
    assert result.status == "⚠️"


# ---------------------------------------------------------------------------
# run_new_files
# ---------------------------------------------------------------------------

def test_new_files_none_added():
    with patch("src.metrics.maintainability.get_added_python_files", return_value=[]):
        result = run_new_files("main", "/ws")
    assert result.score == "N/A"
    assert result.status == "✅"


def test_new_files_better_than_main():
    """New files avg 85, main avg 75 → ratio 1.13 → ✅."""
    with patch("src.metrics.maintainability.get_added_python_files", return_value=["/ws/new.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={"/ws/new.py": 85.0}):
            with patch("src.metrics.maintainability._extract_base", return_value=(True, "")):
                with patch("src.metrics.maintainability._radon_scores_dir", return_value=[75.0, 75.0]):
                    with patch("tempfile.mkdtemp", return_value="/tmp/fake"):
                        with patch("shutil.rmtree"):
                            result = run_new_files("main", "/ws")
    assert result.status == "✅"
    assert float(result.score.rstrip("×")) >= 1.0


def test_new_files_slightly_worse():
    """New files avg 68, main avg 75 → ratio 0.91 → ⚠️."""
    with patch("src.metrics.maintainability.get_added_python_files", return_value=["/ws/new.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={"/ws/new.py": 68.0}):
            with patch("src.metrics.maintainability._extract_base", return_value=(True, "")):
                with patch("src.metrics.maintainability._radon_scores_dir", return_value=[75.0, 75.0]):
                    with patch("tempfile.mkdtemp", return_value="/tmp/fake"):
                        with patch("shutil.rmtree"):
                            result = run_new_files("main", "/ws")
    assert result.status == "⚠️"


def test_new_files_much_worse():
    """New files avg 55, main avg 75 → ratio 0.73 → 🛑."""
    with patch("src.metrics.maintainability.get_added_python_files", return_value=["/ws/new.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={"/ws/new.py": 55.0}):
            with patch("src.metrics.maintainability._extract_base", return_value=(True, "")):
                with patch("src.metrics.maintainability._radon_scores_dir", return_value=[75.0, 75.0]):
                    with patch("tempfile.mkdtemp", return_value="/tmp/fake"):
                        with patch("shutil.rmtree"):
                            result = run_new_files("main", "/ws")
    assert result.status == "🛑"


def test_new_files_extract_fails():
    """git archive failure → ⚠️ with error in detail."""
    with patch("src.metrics.maintainability.get_added_python_files", return_value=["/ws/new.py"]):
        with patch("src.metrics.maintainability._radon_scores", return_value={"/ws/new.py": 75.0}):
            with patch("src.metrics.maintainability._extract_base", return_value=(False, "fatal: bad object")):
                with patch("tempfile.mkdtemp", return_value="/tmp/fake"):
                    with patch("shutil.rmtree"):
                        result = run_new_files("main", "/ws")
    assert result.status == "⚠️"
    assert "fatal" in result.detail
