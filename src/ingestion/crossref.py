from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_API_URL = "https://api.crossref.org/works"
_RETRY_STATUS_CODES = {429, 503}
_MAX_ATTEMPTS = 3
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_abstract(raw_abstract: str | None) -> str:
    if not raw_abstract:
        return ""
    return normalize_whitespace(_TAG_RE.sub(" ", raw_abstract))


def _format_date_parts(date_parts: list[list[int]] | None) -> str:
    if not date_parts or not date_parts[0]:
        return ""
    parts = date_parts[0]
    return "-".join(f"{part:02d}" if idx > 0 else str(part) for idx, part in enumerate(parts))


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    items = (payload or {}).get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        doi = item.get("DOI")
        titles = item.get("title") or []
        if not doi or not titles:
            continue

        title = normalize_whitespace(titles[0])
        summary = _clean_abstract(item.get("abstract"))
        authors = [
            normalize_whitespace(f"{author.get('given', '')} {author.get('family', '')}")
            for author in item.get("author", []) or []
        ]
        categories = list(item.get("subject") or [])
        primary_category = categories[0] if categories else ""
        published = _format_date_parts(item.get("published", {}).get("date-parts"))
        updated = (item.get("created", {}).get("date-time") or "")[:10] or published
        url = item.get("URL", "")

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=url,
                pdf_url=url,
                comment=f"Crossref record {doi}",
            )
        )

    return records


def _request_crossref_payload(settings: Settings) -> dict | None:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }

    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = requests.get(CROSSREF_API_URL, params=params, timeout=30)
        except requests.RequestException:
            if attempt == _MAX_ATTEMPTS - 1:
                return None
            time.sleep(2**attempt)
            continue

        if response.status_code in _RETRY_STATUS_CODES:
            if attempt == _MAX_ATTEMPTS - 1:
                return None
            time.sleep(2**attempt)
            continue

        if response.ok:
            return response.json()

        return None

    return None


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.

    Neu da co snapshot local va `settings.refresh_source` la False, tai su dung
    snapshot do thay vi goi lai API (idempotent, tranh Rate Limit khong can thiet).
    """
    reuse_existing_snapshot = not settings.refresh_source and settings.paths.raw_api_response.exists()
    payload = read_json(settings.paths.raw_api_response) if reuse_existing_snapshot else None

    if payload is None:
        payload = _request_crossref_payload(settings)

        if payload is None:
            if settings.paths.raw_api_response.exists():
                payload = read_json(settings.paths.raw_api_response)
            else:
                raise RuntimeError(
                    "Crossref API unavailable and no local snapshot found at "
                    f"{settings.paths.raw_api_response}."
                )
        else:
            write_json(settings.paths.raw_api_response, payload)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    raw_records = read_json(path)
    return [PaperRecord(**record) for record in raw_records]
