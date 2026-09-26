from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from pathlib import Path

import pandas as pd

from core.utils import write_json


def _display_value(value):
    if isinstance(value, dict):
        return {key: _display_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_display_value(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    if pd.isna(value):
        return None
    return value


def _rebuild_embedding_text(df: pd.DataFrame) -> None:
    df["summary_chars"] = df["summary"].fillna("").astype(str).str.len()

    def build_text(row: pd.Series) -> str:
        published = pd.to_datetime(row["published"], errors="coerce")
        published_text = published.date().isoformat() if not pd.isna(published) else ""
        return (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {published_text}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        )

    df["text_for_embedding"] = df.apply(build_text, axis=1)


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path) -> pd.DataFrame:
    """Simulate six deterministic data corruption scenarios.

    Pseudo-code:
    1. Drop mot so latest records.
    2. Blank summary o mot so dong.
    3. Inject noise vao text.
    4. Lam title bi truncate.
    5. Lam published date cu di.
    6. Add duplicate rows.
    7. Rebuild `text_for_embedding`.
    8. Ghi corruption log vao output_log_path.
    """
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    events: list[dict] = []

    def log_change(corruption_type: str, row: pd.Series, column: str, before, after) -> None:
        events.append(
            {
                "corruption_type": corruption_type,
                "paper_id": str(row["paper_id"]),
                "column": column,
                "before": _display_value(before),
                "after": _display_value(after),
            }
        )

    # 1. Drop 20% newest records.
    drop_count = max(1, ceil(len(corrupted) * 0.20))
    published_dates = pd.to_datetime(corrupted["published"], errors="coerce")
    latest_indices = published_dates.sort_values(ascending=False).head(drop_count).index.tolist()
    for index in latest_indices:
        row = corrupted.loc[index]
        log_change("drop_latest_records", row, "row", row.to_dict(), None)
    corrupted = corrupted.drop(index=latest_indices).reset_index(drop=True)

    change_count = max(1, ceil(len(corrupted) * 0.20))
    first_indices = corrupted.index[:change_count].tolist()
    next_indices = corrupted.index[change_count : change_count * 2].tolist()
    if not next_indices:
        next_indices = first_indices

    # 2. Blank summaries on some records.
    for index in first_indices:
        before = corrupted.at[index, "summary"]
        corrupted.at[index, "summary"] = ""
        log_change("blank_summary", corrupted.loc[index], "summary", before, "")

    # 3. Inject visible noise into another group of summaries.
    noise = "@@@ ### CORRUPTED_DATA ### %%%"
    for index in next_indices:
        before = str(corrupted.at[index, "summary"])
        after = f"{noise} {before} {noise}"
        corrupted.at[index, "summary"] = after
        log_change("inject_noise", corrupted.loc[index], "summary", before, after)

    # 4. Truncate titles to fewer than eight characters. This overlaps with
    # blank summaries to reproduce a realistic compound failure.
    for index in first_indices:
        before = str(corrupted.at[index, "title"])
        after = before[:7]
        corrupted.at[index, "title"] = after
        log_change("truncate_title", corrupted.loc[index], "title", before, after)

    # 5. Move publication dates back one year and update age_days.
    for index in first_indices:
        before = corrupted.at[index, "published"]
        stale_date = pd.to_datetime(before, errors="coerce") - pd.Timedelta(days=365)
        stale_value = stale_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        corrupted.at[index, "published"] = stale_value
        if "age_days" in corrupted.columns:
            corrupted.at[index, "age_days"] = int(corrupted.at[index, "age_days"]) + 365
        log_change("stale_date", corrupted.loc[index], "published", before, stale_value)

    # 6. Duplicate already-corrupted rows so the uniqueness quality gate fails.
    duplicates = corrupted.loc[first_indices].copy(deep=True)
    for _, row in duplicates.iterrows():
        log_change("duplicate_rows", row, "paper_id", row["paper_id"], row["paper_id"])
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)

    _rebuild_embedding_text(corrupted)

    write_json(
        output_log_path,
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "input_rows": int(len(df)),
            "output_rows": int(len(corrupted)),
            "event_count": len(events),
            "corruption_types": sorted({event["corruption_type"] for event in events}),
            "events": events,
        },
    )
    return corrupted.reset_index(drop=True)
