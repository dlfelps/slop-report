"""Tests for src/metrics/blast_radius.py"""

import os
import textwrap
from unittest.mock import patch

from src.metrics.blast_radius import _get_imports, _module_name, run
from src.report import MetricResult


def test_module_name_simple():
    assert _module_name("/ws/src/foo.py", "/ws") == "src.foo"


def test_module_name_nested():
    assert _module_name("/ws/src/utils/helpers.py", "/ws") == "src.utils.helpers"


def test_module_name_init():
    assert _module_name("/ws/src/__init__.py", "/ws") == "src"


def test_get_imports_regular(tmp_path):
    src = textwrap.dedent("""\
        import os
        import src.foo
        from src.bar import baz
        from collections import defaultdict
    """)
    f = tmp_path / "sample.py"
    f.write_text(src)
    imports = _get_imports(str(f))
    assert "os" in imports
    assert "src.foo" in imports
    assert "src.bar" in imports
    assert "src" in imports  # top-level package added


def test_get_imports_syntax_error(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def (broken syntax")
    imports = _get_imports(str(f))
    assert imports == set()


def test_run_no_changed_files():
    with patch("src.metrics.blast_radius.get_changed_python_files", return_value=[]):
        result = run("main", "/ws")
    assert result.score == "0 modules"
    assert result.status == "✅"


def test_run_risk_tiers(tmp_path):
    # Create 12 Python files that import "mymodule"
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    changed = tmp_path / "mymodule.py"
    changed.write_text("x = 1")

    for i in range(12):
        (pkg / f"consumer_{i}.py").write_text("import mymodule\n")

    with patch("src.metrics.blast_radius.get_changed_python_files", return_value=[str(changed)]):
        result = run("main", str(tmp_path))

    assert result.status == "🛑"
    assert int(result.score.split()[0]) >= 10
