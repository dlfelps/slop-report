"""Blast radius: identify which modules import the changed files."""

import ast
import os

from src.git_utils import get_changed_python_files
from src.report import MetricResult


def _module_name(filepath: str, workspace: str) -> str | None:
    """Convert an absolute file path to a dotted module name relative to workspace."""
    rel = os.path.relpath(filepath, workspace)
    if rel.startswith(".."):
        return None
    parts = rel.replace(os.sep, "/").removesuffix(".py").split("/")
    # Drop leading path segments until we find a package boundary or hit the root
    # Simple heuristic: use the full dotted path from workspace root
    return ".".join(p for p in parts if p != "__init__")


def _get_imports(filepath: str) -> set[str]:
    """Return all module names imported by a Python file."""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, OSError):
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
                # Also add the top-level package
                imports.add(node.module.split(".")[0])
    return imports


def run(base_ref: str, workspace: str) -> MetricResult:
    changed_files = get_changed_python_files(base_ref, workspace)
    if not changed_files:
        return MetricResult(
            name="Blast Radius",
            score="0 modules",
            status="✅",
            detail="No Python files changed",
        )

    changed_modules: set[str] = set()
    for f in changed_files:
        mod = _module_name(f, workspace)
        if mod:
            changed_modules.add(mod)
            # Also add intermediate package names
            parts = mod.split(".")
            for i in range(1, len(parts)):
                changed_modules.add(".".join(parts[:i]))

    # Walk all Python files in workspace and check which import changed modules
    affected: set[str] = set()
    for dirpath, _, filenames in os.walk(workspace):
        # Skip hidden dirs and common non-source dirs
        dirpath_rel = os.path.relpath(dirpath, workspace)
        if any(part.startswith(".") or part in ("__pycache__", ".git", "node_modules", ".venv", "venv")
               for part in dirpath_rel.split(os.sep)):
            continue
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, filename)
            if filepath in changed_files:
                continue
            imports = _get_imports(filepath)
            for changed_mod in changed_modules:
                if changed_mod in imports:
                    rel = os.path.relpath(filepath, workspace)
                    affected.add(rel)
                    break

    count = len(affected)
    if count <= 3:
        status = "✅"
        risk = "Low"
    elif count <= 10:
        status = "⚠️"
        risk = "Medium"
    else:
        status = "🛑"
        risk = "High"

    sample = sorted(affected)[:5]
    sample_str = ", ".join(sample)
    if len(affected) > 5:
        sample_str += f" (+{len(affected) - 5} more)"

    detail = f"{risk} impact" + (f": {sample_str}" if sample_str else "")

    return MetricResult(
        name="Blast Radius",
        score=f"{count} module{'s' if count != 1 else ''}",
        status=status,
        detail=detail,
    )
