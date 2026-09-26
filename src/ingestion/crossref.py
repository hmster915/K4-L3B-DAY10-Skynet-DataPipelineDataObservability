from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re
from core.config import Settings
import requests
import time 
import json
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


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """TODO(student): parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    items = payload.get("message",{}).get("items",[])
    for item in items : 
        doi= item.get("DOI","").strip()
        title = item.get("title",[])  
        abstract = item.get("abstract","").strip()
        if abstract : 
            bstract_clean  = re.sub(r"<[^>]+>")
        authors = item.get("author",[])
        author_list = []
        for author in authors : 
            name_part = [authors.get("given"),authors.get("family")]
            full_name = " ".join(part for part in name_part if part) 
            if full_name : 
                author_list.append(full_name)
    subject = item.get("subject",[])
    dates = item.get("published",{}).get("date-parts",[])
    update = item.get("created").get("date-time")
    url = item.get("URL","").strip()

    return PaperRecord(
        paper_id= doi,
        title= title,
        summary= abstract ,
        authors= author_list , 
        categories= subject , 
        published= dates , 
        updated= update ,
        abs_url= url
    )

def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """TODO(student): goi source API, luu raw response, parse thanh records.
    
    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    api_url = "https://api.crossref.org/works"
    params = {
        "query" : Settings.source_query ,
        "filter" : Settings.source_filter , 
        "rows": Settings.max_results ,
    }
    payload: dict | None = None 
    last_error : Exception | None = None 
    for attempt in range(3) : 
        try : 
            res = requests.get(api_url,params=params,timeout=30,)
            if res.status_code in {429,504} : 
                time.sleep(2*attempt) 
                continue
            res.raise_for_status()
            payload = res.json()
            break
        except (requests.RequestException,ValueError) as e : 
            last_error = e 
            if attempt < 2 : 
                time.sleep(2**attempt)
    raw_response_path = settings.paths.raw_api_response
    raw_records_path = settings.paths.raw_records_json
    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
    raw_records_path.parent.mkdir(parents=True, exist_ok=True)
    if payload is not None :
        raw_response_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    elif raw_response_path.exists():
        # Nếu API lỗi thì đọc snapshot có sẵn trong project
        payload = json.loads(
            raw_response_path.read_text(encoding="utf-8")
        )
    else:
        raise RuntimeError(
            "Không gọi được Crossref API và không có snapshot local."
        ) from last_error
    
def load_raw_records(path: Path) -> list[PaperRecord]:
    """TODO(student): doc JSON snapshot va map thanh `PaperRecord`."""
    raise NotImplementedError("Student task: implement raw record loading.")
