# PR Quality Gate

A GitHub Action that posts an automated, data-driven code quality report as a comment on every pull request. Designed to run **alongside** your existing CI/CD pipeline — not replace it.

When a PR is opened or updated, this action analyzes the changed Python files and posts a summary table directly in the PR:

| Metric | Score | Status | Details |
|--------|-------|--------|---------|
| Change Risk | 72% covered | ⚠️ | 28% of changed lines lack test coverage |
| Blast Radius | 12 modules | 📉 | High impact: auth, api, models affected |
| Performance | No regressions | ✅ | No tests exceeded 20% slowdown threshold |
| Maintainability | 74 / 100 | ✅ | Above threshold (65) |

---

## Metrics

| Metric | What it measures |
|--------|-----------------|
| **Change Risk** | % of added/modified lines covered by your existing test suite |
| **Blast Radius** | How many other modules import the files you changed |
| **Performance** | Whether any tests slowed down compared to the base branch baseline |
| **Maintainability** | Radon Maintainability Index score for the changed files (0–100) |

---

## Quick Start

```yaml
# .github/workflows/pr-quality-gate.yml
name: PR Quality Gate

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  pull-requests: write   # post the comment
  contents: read         # checkout code
  actions: write         # read/write performance baseline cache

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # required — action uses git diff against base branch

      - name: Run PR Quality Gate
        uses: dlfelps/slop-report@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `github-token` | `${{ github.token }}` | Token for posting the PR comment |
| `enable-coverage` | `true` | Run change risk / coverage analysis |
| `enable-blast-radius` | `true` | Run blast radius / dependency analysis |
| `enable-performance` | `true` | Run performance regression analysis |
| `enable-maintainability` | `true` | Run maintainability index analysis |
| `coverage-threshold` | `80` | Minimum % of changed lines covered (0–100) |
| `maintainability-threshold` | `65` | Minimum Radon MI score (0–100) |
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
    maintainability-threshold: '75'
    performance-threshold: '10'
```

---

## How It Works

### Change Risk
Runs your test suite via `coverage run -m pytest` (auto-detected; falls back to `unittest`), then cross-references the coverage data against the exact lines added or modified in the PR. Reports the percentage of those lines that are actually exercised by tests.

### Blast Radius
Parses every Python file in your repository with Python's `ast` module to build an import graph. Identifies all files that import the modules you changed, and classifies the impact as Low (≤3), Medium (4–10), or High (>10 affected modules).

### Performance
Runs `pytest --durations=0` and compares per-test timings against a baseline stored in the GitHub Actions cache (keyed to the base branch). On the first run, the baseline is recorded. On subsequent runs, tests that slowed by more than the configured threshold are flagged. The baseline is updated after each run.

### Maintainability
Runs `radon mi` on the changed files and reports the average Maintainability Index score (0–100). Scores ≥ threshold are green (✅), within 10 points below are yellow (⚠️), and further below are red (📉).

---

## Requirements

- Python project (pytest or unittest)
- `fetch-depth: 0` on the `actions/checkout` step (required for git diff)
- `pull-requests: write` permission for posting the comment
- `actions: write` permission if using the performance metric (cache access)

---

## Status Indicators

| Icon | Meaning |
|------|---------|
| ✅ | Metric is within acceptable range |
| ⚠️ | Metric is below threshold or needs attention |
| 📉 | Significant issue detected |
