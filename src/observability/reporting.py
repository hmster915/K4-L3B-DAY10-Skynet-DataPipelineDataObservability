from __future__ import annotations

from typing import Any

from core.utils import write_text


def _format_metric(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write an evidence-based Markdown report for the baseline pipeline."""
    quality_rows = []
    for result in quality.get("expectations", []):
        config = result.get("expectation_config", {})
        expectation_type = config.get("type", "unknown")
        status = "PASS" if result.get("success") else "FAIL"
        observed = result.get("result", {}).get("observed_value", "-")
        quality_rows.append(f"| `{expectation_type}` | {status} | {observed} |")

    ragas = metrics.get("ragas", {})
    ragas_status = ragas.get("skipped") or ragas.get("error") or "Completed"
    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source and artifacts",
        "",
        f"- Source: {source_summary.get('source', 'unknown')}",
        f"- Query: {source_summary.get('query', '')}",
        f"- Raw records: {source_summary.get('raw_records', 0)}",
        f"- Clean records: {source_summary.get('clean_records', 0)}",
        f"- Test questions: {source_summary.get('test_questions', 0)}",
        f"- ChromaDB collection: `{source_summary.get('collection_name', '')}`",
        f"- Embedding model: `{source_summary.get('embedding_model', '')}`",
        f"- LLM provider/model: `{source_summary.get('llm_provider', '')}` / `{source_summary.get('llm_model', '')}`",
        "",
        "## Baseline evaluation",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Samples | {_format_metric(metrics.get('samples', 0))} |",
        f"| Retrieval hit rate | {_format_metric(metrics.get('retrieval_hit_rate', 0.0))} |",
        f"| Mean token F1 | {_format_metric(metrics.get('mean_token_f1', 0.0))} |",
        f"| Judge accuracy | {_format_metric(metrics.get('judge_accuracy', 0.0))} |",
        f"| Mean judge score | {_format_metric(metrics.get('mean_judge_score', 0.0))} |",
        "",
        f"Ragas: {ragas_status}",
        "",
        "## Great Expectations quality gate",
        "",
        f"Overall GX status: **{'PASS' if quality.get('quality_success') else 'FAIL'}**",
        "",
        "| Expectation | Status | Observed |",
        "| --- | --- | --- |",
        *quality_rows,
        "",
        "## Freshness SLA",
        "",
        f"- Status: **{'FRESH' if freshness.get('is_fresh') else 'STALE'}**",
        f"- Threshold: {freshness.get('threshold_days')} days",
        f"- Stale rows: {freshness.get('stale_rows', 0)}/{freshness.get('total_rows', 0)}",
        f"- Stale ratio: {_format_metric(freshness.get('stale_ratio', 0.0))}",
        f"- Maximum allowed stale ratio: {_format_metric(freshness.get('max_stale_ratio', 0.25))}",
        "",
        f"Final quality gate: **{'PASS' if quality.get('success') else 'FAIL'}**",
        "",
    ]
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """TODO(student): viet markdown report so sanh baseline/corrupted/repaired."""
    raise NotImplementedError("Student task: implement corruption comparison report.")
