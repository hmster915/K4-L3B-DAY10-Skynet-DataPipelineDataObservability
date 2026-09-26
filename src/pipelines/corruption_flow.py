from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import ensure_parent, read_json, write_csv
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records, parse_crossref_payload
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import run_phase1_pipeline
from retrieval.index import LocalEmbeddingIndex


def _save_dataframe(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    ensure_parent(json_path)
    df.to_json(
        json_path,
        orient="records",
        date_format="iso",
        indent=2,
        force_ascii=False,
    )


def repair_from_raw_snapshot(settings: Settings) -> pd.DataFrame:
    """Rebuild clean data from the trusted raw snapshot."""
    if settings.paths.raw_records_json.exists():
        records = load_raw_records(settings.paths.raw_records_json)
    elif settings.paths.raw_api_response.exists():
        records = parse_crossref_payload(read_json(settings.paths.raw_api_response))
    else:
        raise FileNotFoundError("No raw Crossref snapshot is available for repair.")

    repaired_df = build_clean_dataframe(records, datetime.now(UTC))
    if repaired_df.empty:
        raise RuntimeError("Repair produced an empty dataframe.")

    for date_column in ("published", "updated"):
        repaired_df[date_column] = repaired_df[date_column].dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    _save_dataframe(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    return repaired_df


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Run corruption, impact evaluation, raw-snapshot repair, and comparison."""
    baseline_files = (
        settings.paths.clean_json,
        settings.paths.baseline_metrics,
        settings.paths.eval_testset,
    )
    if not all(path.exists() for path in baseline_files):
        run_phase1_pipeline(settings)

    clean_df = pd.DataFrame(read_json(settings.paths.clean_json))
    if clean_df.empty:
        raise RuntimeError("Baseline clean dataset is empty.")

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_metrics["source_rows"] = int(len(clean_df))

    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    _save_dataframe(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )

    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")

    repaired_df = repair_from_raw_snapshot(settings)
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")

    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_evaluation.summary,
        repaired_metrics=repaired_evaluation.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_quality["freshness"],
        repaired_freshness=repaired_quality["freshness"],
    )

    return {
        "baseline_metrics": baseline_metrics,
        "corrupted_metrics": corrupted_evaluation.summary,
        "repaired_metrics": repaired_evaluation.summary,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
        "artifacts": {
            "corruption_log": str(settings.paths.corruption_log),
            "corrupted_data": str(settings.paths.corrupted_clean_json),
            "repaired_data": str(settings.paths.repaired_clean_json),
            "report": str(settings.paths.comparison_report),
        },
    }


def main() -> None:
    result = run_corruption_flow_pipeline(load_settings())
    baseline = result["baseline_metrics"]
    corrupted = result["corrupted_metrics"]
    repaired = result["repaired_metrics"]

    print("\nBaseline vs Corrupted vs Repaired")
    print(f"{'Metric':<24} {'Baseline':>10} {'Corrupted':>12} {'Repaired':>10}")
    print("-" * 60)
    for key, label in (
        ("retrieval_hit_rate", "Retrieval hit rate"),
        ("mean_token_f1", "Mean token F1"),
        ("judge_accuracy", "Judge accuracy"),
        ("mean_judge_score", "Mean judge score"),
    ):
        print(
            f"{label:<24} "
            f"{float(baseline.get(key, 0)):>10.4f} "
            f"{float(corrupted.get(key, 0)):>12.4f} "
            f"{float(repaired.get(key, 0)):>10.4f}"
        )
    print(f"\nReport: {result['artifacts']['report']}")
