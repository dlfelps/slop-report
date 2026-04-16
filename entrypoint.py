"""Main entrypoint for the Slop Report GitHub Action."""

import json
import os
import sys

from src import github_client, report
from src.metrics import blast_radius, coverage, maintainability, performance
from src.report import MetricResult


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _bool_env(key: str) -> bool:
    return _env(key, "true").lower() not in ("false", "0", "no")


def _int_env(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _get_pr_number(event_path: str) -> int:
    with open(event_path) as f:
        event = json.load(f)
    pr = event.get("pull_request") or event.get("issue", {})
    number = pr.get("number")
    if number is None:
        raise RuntimeError(f"Could not find PR number in event payload at {event_path}")
    return int(number)


def main() -> None:
    token = _env("GITHUB_TOKEN")
    repo = _env("GITHUB_REPOSITORY")
    base_ref = _env("GITHUB_BASE_REF", "main")
    workspace = _env("GITHUB_WORKSPACE", "/github/workspace")
    event_path = _env("GITHUB_EVENT_PATH")

    if not token:
        print("::error::GITHUB_TOKEN is not set", file=sys.stderr)
        sys.exit(1)
    if not repo:
        print("::error::GITHUB_REPOSITORY is not set", file=sys.stderr)
        sys.exit(1)
    if not event_path:
        print("::error::GITHUB_EVENT_PATH is not set", file=sys.stderr)
        sys.exit(1)

    try:
        pr_number = _get_pr_number(event_path)
    except Exception as e:
        print(f"::error::Failed to read PR number: {e}", file=sys.stderr)
        sys.exit(1)

    enable_coverage = _bool_env("INPUT_ENABLE_COVERAGE")
    enable_blast = _bool_env("INPUT_ENABLE_BLAST_RADIUS")
    enable_perf = _bool_env("INPUT_ENABLE_PERFORMANCE")
    enable_mi = _bool_env("INPUT_ENABLE_MAINTAINABILITY")

    cov_threshold = _int_env("INPUT_COVERAGE_THRESHOLD", 80)
    perf_threshold = _int_env("INPUT_PERFORMANCE_THRESHOLD", 20)

    results: list[MetricResult] = []

    if enable_coverage:
        print("Running coverage analysis...")
        results.append(coverage.run(base_ref, workspace, cov_threshold))
    else:
        results.append(MetricResult("Change Risk", "Disabled", "—", "Metric disabled", skipped=True))

    if enable_blast:
        print("Running blast radius analysis...")
        results.append(blast_radius.run(base_ref, workspace))
    else:
        results.append(MetricResult("Blast Radius", "Disabled", "—", "Metric disabled", skipped=True))

    if enable_perf:
        print("Running performance regression analysis...")
        results.append(performance.run(base_ref, workspace, perf_threshold))
    else:
        results.append(MetricResult("Performance", "Disabled", "—", "Metric disabled", skipped=True))

    if enable_mi:
        print("Running maintainability regression analysis...")
        results.append(maintainability.run_regression(base_ref, workspace, repo, pr_number))
        print("Running new file quality analysis...")
        results.append(maintainability.run_new_files(base_ref, workspace))
    else:
        results.append(MetricResult("MI Regression", "Disabled", "—", "Metric disabled", skipped=True))
        results.append(MetricResult("New File Quality", "Disabled", "—", "Metric disabled", skipped=True))

    thresholds = {}
    if enable_coverage:
        thresholds["coverage"] = f"{cov_threshold}%"
    if enable_perf:
        thresholds["perf"] = f"{perf_threshold}%"

    body = report.render(results, thresholds)

    print("Posting report to PR...")
    try:
        github_client.upsert_comment(token, repo, pr_number, body)
        print("Report posted successfully.")
    except Exception as e:
        print(f"::error::Failed to post comment: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
