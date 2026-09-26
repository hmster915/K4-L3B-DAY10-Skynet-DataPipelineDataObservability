from __future__ import annotations

import json
from typing import Any

import great_expectations as gx
import pandas as pd
from great_expectations.expectations import (
    ExpectColumnValueLengthsToBeBetween,
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToNotBeNull,
    ExpectTableRowCountToBeBetween,
)

from core.config import Settings


def evaluate_freshness_sla(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Evaluate the freshness SLA for the cleaned dataset.

    A row is stale when its ``age_days`` is greater than the configured
    threshold.  The dataset is fresh when at most 25% of its rows are stale.
    Missing or invalid ages are treated as stale because their freshness
    cannot be established safely.
    """
    threshold_days = int(settings.freshness_threshold_days)
    total_rows = int(len(df))

    if "age_days" not in df.columns:
        stale_rows = total_rows
    else:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
        stale_rows = int((ages.isna() | (ages > threshold_days)).sum())

    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    max_stale_ratio = 0.25
    return {
        "is_fresh": bool(total_rows > 0 and stale_ratio <= max_stale_ratio),
        "threshold_days": threshold_days,
        "max_stale_ratio": max_stale_ratio,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, stage: str) -> dict[str, Any]:
    """Run the GX quality gate and the freshness SLA for ``df``.

    The context and batch are intentionally ephemeral: every invocation
    validates the dataframe supplied by the caller without creating a GX
    project or relying on persisted datasource state.
    """
    freshness = evaluate_freshness_sla(df, settings)
    report: dict[str, Any] = {
        "success": False,
        "stage": stage,
        "row_count": int(len(df)),
        "freshness": freshness,
    }

    try:
        context = gx.get_context(mode="ephemeral")
        data_source = context.data_sources.add_pandas(name="papers_source")
        data_asset = data_source.add_dataframe_asset(name="papers_asset")
        batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
        batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

        expectations = [
            ExpectTableRowCountToBeBetween(min_value=1),
            ExpectColumnValuesToNotBeNull(column="paper_id"),
            ExpectColumnValuesToNotBeNull(column="title"),
            ExpectColumnValuesToBeUnique(column="paper_id"),
            ExpectColumnValueLengthsToBeBetween(column="summary", min_value=1),
        ]
        suite = gx.ExpectationSuite(name=f"{stage}_quality_suite", expectations=expectations)
        validation = batch.validate(suite)
        validation_dict = validation.to_json_dict()
        report["gx"] = validation_dict
        report["expectations"] = validation_dict.get("results", [])
        report["quality_success"] = bool(validation.success)
        report["success"] = bool(validation.success and freshness["is_fresh"])
    except Exception as exc:  # Return an observable failed gate for malformed input/configuration.
        report["quality_success"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"

    quality_dir = settings.paths.quality_dir
    quality_dir.mkdir(parents=True, exist_ok=True)
    report_path = quality_dir / f"{stage}_quality_report.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """TODO(student): tong hop freshness report.

    Pseudo-code:
    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    raise NotImplementedError("Student task: implement freshness reporting.")
