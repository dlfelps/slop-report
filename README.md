# Slop Report

**Automatic PR quality reports for Python projects.**

Slop Report posts a code quality summary as a comment on every pull request — coverage, blast radius, performance regressions, and maintainability — so reviewers have the data they need without leaving GitHub.

| Metric | Score | Status | Details |
|--------|-------|--------|---------|
| Change Risk | 72% covered | ⚠️ | 28% of changed lines lack test coverage |
| Blast Radius | 12 modules | 🛑 | High impact: auth, api, models affected |
| Performance | No regressions | ✅ | No tests exceeded 20% slowdown threshold |
| MI Regression | -12% | 🛑 | Worst: auth.py (-12%) |
| New File Quality | 0.94× | ⚠️ | New files avg MI 68 vs main avg 72 |

Runs alongside your existing CI — it never blocks a merge, just surfaces the signal.

---

## Quick Start

```yaml
# .github/workflows/slop-report.yml
name: Slop Report

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  pull-requests: write
  contents: read

jobs:
  slop-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # required — Slop Report diffs against the base branch

      - name: Run Slop Report
        uses: dlfelps/slop-report@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## Metrics

| Metric | What it measures |
|--------|-----------------|
| **Change Risk** | % of added/modified lines covered by your existing test suite |
| **Blast Radius** | How many other modules import the files you changed |
| **Performance** | Per-test timing compared to the base branch — regressions are flagged |
| **MI Regression** | Worst relative drop in Maintainability Index across modified files |
| **New File Quality** | Avg MI of added files relative to the base branch average |

---

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `github-token` | `${{ github.token }}` | Token for posting the PR comment |
| `enable-coverage` | `true` | Run change risk / coverage analysis |
| `enable-blast-radius` | `true` | Run blast radius / dependency analysis |
| `enable-performance` | `true` | Run performance regression analysis |
| `enable-maintainability` | `true` | Run MI regression and new file quality analysis |
| `coverage-threshold` | `80` | Minimum % of changed lines covered (0–100) |
| `performance-threshold` | `20` | Max % slowdown before flagging a regression |

---

## Configuration Examples

### Disable a metric

```yaml
- uses: dlfelps/slop-report@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    enable-performance: 'false'
```

### Stricter thresholds

```yaml
- uses: dlfelps/slop-report@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    coverage-threshold: '90'
    performance-threshold: '10'
```

---

## How It Works

### Change Risk
Runs your test suite via `coverage run -m pytest` (auto-detected; falls back to `unittest`), then cross-references coverage data against the exact lines added or modified in the PR. Reports the percentage of those lines actually exercised by tests.

### Blast Radius
Parses every Python file in the repository with Python's `ast` module to build an import graph. Identifies all files that import the modules you changed, and classifies impact as Low (≤3), Medium (4–10), or High (>10 affected modules).

### Performance
Runs `pytest --durations=0` on both the base branch and the PR branch using `git archive`, then compares per-test timings. Tests that slowed by more than the configured threshold are flagged, with the worst offender highlighted in the report.

### MI Regression
Runs `radon mi` on each modified Python file and compares its score against the same file on the base branch via `git show`. Computes the relative change for each file and reports the worst (most negative) value. Only files present in both branches are included; newly added files are excluded.

### New File Quality
Runs `radon mi` on all Python files added in the PR and computes their average Maintainability Index. Extracts the base branch via `git archive` and computes the average MI of all existing Python files. Reports the ratio: new files avg ÷ base avg. A ratio ≥ 1.0 means new code is at least as maintainable as the existing codebase.

---

## Assumptions & Limitations

- **Python only** — all analysis (coverage, blast radius, maintainability) targets `.py` files. Other languages are ignored.
- **pytest or unittest** — the test runner must be one of these two. Coverage is collected via `coverage run -m pytest`; `unittest` is the fallback if pytest is not installed.
- **Performance baseline requires a shared history** — the base branch must be reachable via `git archive origin/<base>`. Shallow clones (`fetch-depth: 1`) will cause the performance metric to report N/A; use `fetch-depth: 0`.
- **Performance compares only tests present in both branches** — tests added or removed in the PR are excluded from the regression comparison.
- **Blast radius uses static import analysis** — dynamic imports (`importlib`, `__import__`) and conditional imports are not detected.
- **MI Regression only covers files present on both branches** — newly added files are measured separately by New File Quality; deleted files are ignored.
- **Radon scores very short files leniently** — files with fewer than ~10 lines tend to score near 100 regardless of quality.
- **No blocking** — Slop Report never fails the workflow. It only posts an informational comment.

---

## Requirements

- Python project with pytest or unittest
- `fetch-depth: 0` on the `actions/checkout` step
- `pull-requests: write` permission for posting the comment

---

## Status Indicators

| Icon | Meaning |
|------|---------|
| ✅ | Metric is within acceptable range |
| ⚠️ | Metric is below threshold or needs attention |
| 🛑 | Significant issue detected |
