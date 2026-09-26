from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.config import Settings, load_settings
from core.utils import ensure_parent, read_json, write_csv
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Run the complete baseline data and RAG evaluation pipeline."""
    records = fetch_source_records(settings)

    df = build_clean_dataframe(records, datetime.now(UTC))
    if df.empty:
        raise RuntimeError("Cleaning produced an empty dataframe; phase 1 cannot continue.")
    for date_column in ("published", "updated"):
        df[date_column] = df[date_column].dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    write_csv(df, settings.paths.clean_csv)
    ensure_parent(settings.paths.clean_json)
    df.to_json(
        settings.paths.clean_json,
        orient="records",
        date_format="iso",
        indent=2,
        force_ascii=False,
    )

    index = LocalEmbeddingIndex.build(
        df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )

    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)

    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    quality = run_data_quality_checks(df, settings, "baseline")
    freshness = quality["freshness"]
    source_summary = {
        "source": settings.source_api,
        "query": settings.source_query,
        "raw_records": len(records),
        "clean_records": len(df),
        "test_questions": len(test_set),
        "collection_name": index.collection_name,
        "embedding_model": settings.embedding_model,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.model_name,
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    return {
        "success": bool(quality["success"]),
        "source_summary": source_summary,
        "metrics": evaluation.summary,
        "quality": quality,
        "freshness": freshness,
        "artifacts": {
            "clean_csv": str(settings.paths.clean_csv),
            "clean_json": str(settings.paths.clean_json),
            "embeddings": str(settings.paths.embeddings_json),
            "test_set": str(settings.paths.eval_testset),
            "metrics": str(settings.paths.baseline_metrics),
            "answers": str(settings.paths.baseline_answers),
            "quality": str(settings.paths.baseline_quality_report),
            "report": str(settings.paths.baseline_report),
        },
    }


def main() -> None:
    result = run_phase1_pipeline(load_settings())
    metrics = result["metrics"]
    print(f"Phase 1 success: {result['success']}")
    print(f"Retrieval hit rate: {metrics['retrieval_hit_rate']:.3f}")
    print(f"Mean token F1: {metrics['mean_token_f1']:.3f}")
    print(f"Report: {result['artifacts']['report']}")
