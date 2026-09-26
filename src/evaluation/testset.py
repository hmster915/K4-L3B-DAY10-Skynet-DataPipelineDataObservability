from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


_QUESTION_TYPES = (
    "summary",
    "authors",
    "date",
    "categories",
    "summary",
    "authors",
    "date",
    "categories",
    "summary",
    "authors",
)


def _as_text(value: Any) -> str:
    """Convert a dataframe scalar to normalized text without leaking NaN."""
    if value is None or (not isinstance(value, (list, tuple)) and pd.isna(value)):
        return ""
    return normalize_whitespace(str(value))


def _question_and_answer(row: pd.Series, question_type: str) -> tuple[str, str]:
    title = _as_text(row["title"])

    if question_type == "summary":
        return f"Summarize the paper '{title}'.", first_sentence(_as_text(row["summary"]))
    if question_type == "authors":
        return f"Who authored the paper '{title}'?", _as_text(row["authors_joined"])
    if question_type == "date":
        return f"When was the paper '{title}' published?", _as_text(row["published"])
    if question_type == "categories":
        return f"What categories does the paper '{title}' belong to?", _as_text(row["categories_joined"])
    raise ValueError(f"Unsupported question type: {question_type}")


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build and persist a deterministic, balanced 10-question test set."""
    required_columns = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "published",
        "categories_joined",
    }
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing required columns: {', '.join(missing_columns)}")
    if len(df) < len(_QUESTION_TYPES):
        raise ValueError(f"At least {len(_QUESTION_TYPES)} documents are required to build the test set.")

    test_set: list[dict[str, Any]] = []
    selected_doc_ids: set[str] = set()

    for question_type in _QUESTION_TYPES:
        selected_row: pd.Series | None = None
        selected_question = ""
        selected_answer = ""

        for _, row in df.iterrows():
            paper_id = _as_text(row["paper_id"])
            title = _as_text(row["title"])
            if not paper_id or not title or paper_id in selected_doc_ids:
                continue

            question, answer = _question_and_answer(row, question_type)
            if answer:
                selected_row = row
                selected_question = question
                selected_answer = answer
                break

        if selected_row is None:
            raise ValueError(f"Not enough eligible documents for question type '{question_type}'.")

        paper_id = _as_text(selected_row["paper_id"])
        selected_doc_ids.add(paper_id)
        test_set.append(
            {
                "id": f"q{len(test_set) + 1:02d}",
                "question_type": question_type,
                "question": selected_question,
                "ground_truth": selected_answer,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    write_json(Path(output_path), test_set)
    return test_set
