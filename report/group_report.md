# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
|---|---|
| Khóa/Lớp | K4-L3B |
| Tên nhóm | Skynet |
| Repository | `K4-L3B-DAY10-Skynet-DataPipelineDataObservability` |
| Ngày hoàn thành | 2026-09-26 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
|---:|---|---|---|---|
| 1 | Nguyễn Hồng Khoa | 2A202602534 | Pipeline Integrator | `core/`, `phase1.py`, `corruption_flow.py` |
| 2 | Ngô Lê Thủy Tiên | 2A202602614 | Data Foundation & Recovery | `crossref.py`, `cleaning.py`, raw data |
| 3 | Phùng Trọng Chiến | 2A202602430 | RAG & Vector Index | `retrieval/`, ChromaDB |
| 4 | Nguyễn Khánh Linh | 2A202602409 | Observability & Evaluation | `quality.py`, `testset.py`, reporting |

## 2. Tóm tắt kết quả

Nhóm đã xây dựng pipeline từ raw Crossref snapshot đến cleaned dataset, MiniLM embeddings, ChromaDB index, evaluation và quality gate. Snapshot có 24 records; cleaned dataset giữ lại 24 records và tạo `text_for_embedding`, `age_days`, authors và categories đã chuẩn hóa. Evaluation set có 10 câu hỏi thuộc bốn nhóm nghiệp vụ: summary, authors, date và categories.

Baseline đạt retrieval hit rate 1.0, mean token F1 1.0, judge accuracy 1.0 và mean judge score 5. Sau khi tiêm sáu loại corruption, retrieval hit rate giảm còn 0.5, mean token F1 còn 0.5529, judge accuracy còn 0.6 và mean judge score còn 3. Quality gate chuyển sang FAIL, freshness chuyển sang STALE với 9/23 rows stale. Repair từ raw snapshot khôi phục dataset 24 rows, quality/freshness PASS và các metrics trở lại baseline. Giới hạn còn lại là việc rerun embedding cần truy cập Hugging Face; lần rerun trong môi trường offline bị lỗi DNS dù các artifacts đã tạo vẫn tồn tại.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref API/local snapshot
    -> raw response/raw records
    -> cleaning và data modeling
    -> MiniLM embeddings + ChromaDB
    -> baseline evaluation và quality gate
    -> six corruption scenarios
    -> corrupted re-index/evaluation
    -> repair từ raw snapshot
    -> repaired re-index/evaluation
    -> three-state comparison report
```

| Khối | Input | Xử lý chính | Output | Owner |
|---|---|---|---|---|
| Ingestion | Crossref API/snapshot | Fetch, retry, parse, fallback | `data/raw/*.json` | Ngô Lê Thủy Tiên |
| Cleaning | Raw `PaperRecord` | Normalize, deduplicate, dates, embedding text | `data/clean/*` | Ngô Lê Thủy Tiên |
| Embedding/index | Clean dataframe | MiniLM encoding và ChromaDB indexing | `data/embeddings/`, `data/chroma/` | Phùng Trọng Chiến |
| Evaluation | Clean dataframe/index | 10-question test set và metrics | `data/eval/`, `data/results/*metrics.json` | Nguyễn Khánh Linh |
| Observability | Dataframes | GX 1.x expectations và freshness SLA | `data/quality/` | Nguyễn Khánh Linh |
| Corruption/repair | Clean data/raw snapshot | Six corruptions, rebuild từ raw | corrupted/repaired artifacts | Nguyễn Hồng Khoa |
| Orchestration | Settings và module contracts | Baseline/corruption flow | `data/reports/` | Nguyễn Hồng Khoa |

## 4. Cấu hình và tái hiện

| Biến/cấu hình | Giá trị |
|---|---|
| `LLM_PROVIDER` | `gemini` |
| `LLM_MODEL` | `gemini-2.5-flash` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; tối đa 25% stale |
| Random seed | Không sử dụng |

```bash
python -m pip install -e .
python script/run_phase1.py
python script/run_corruption_flow.py
```

Các artifacts hiện có chứng minh baseline và corruption flow đã được chạy. Rerun mới nhất của baseline bị chặn khi SentenceTransformers cố tải model từ Hugging Face trong môi trường không có DNS/network.

## 5. Ingestion, cleaning và data contract

- Source: Crossref REST API; local fallback tại `data/raw/crossref_response.json`.
- Query: `agentic retrieval augmented generation large language model`.
- Raw records: 24.
- Retry: tối đa 3 lần, exponential backoff cho network error, HTTP 429 và 503.
- Clean dataset: 24 rows, deduplicate theo `paper_id`.
- `text_for_embedding` gồm Title, Authors, Published, Categories và Summary.
- `age_days = run_date - published`.

Các trường clean chính gồm `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `updated`, `text_for_embedding` và `age_days`. Record thiếu DOI/title/ngày xuất bản hợp lệ bị loại khỏi clean dataset.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
|---|---|
| Số câu hỏi | 10 |
| Question types | `summary`, `authors`, `date`, `categories` |
| Ground truth | Câu trả lời lấy trực tiếp từ clean row và `paper_id` tương ứng |
| Vector store | ChromaDB, collection baseline/corrupted/repaired |
| Retrieval `top_k` | 4 |
| Test set dùng chung | `data/eval/test_set.json` |

Giữ nguyên cùng test set giúp tách tác động của corruption/repair khỏi tác động do thay đổi câu hỏi hoặc ground truth.

## 7. Baseline results

| Artifact | Trạng thái | Bằng chứng |
|---|---|---|
| Raw response/records | Có | `data/raw/` |
| Cleaned dataset | Có | `data/clean/papers_clean.*` |
| Embedding/index | Có | `data/embeddings/`, `data/chroma/` |
| Evaluation set | Có | `data/eval/test_set.json` |
| Baseline metrics | Có | `data/results/baseline_metrics.json` |
| Quality/freshness | Có | `data/quality/` |
| Baseline report | Có | `data/reports/phase1_report.md` |

| Metric | Baseline |
|---|---:|
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 1.0000 |
| `judge_accuracy` | 1.0000 |
| `mean_judge_score` | 5 |
| Ragas | Skipped; chỉ chạy khi `RUN_RAGAS=1` |

## 8. Data quality và freshness

| Check | Kỳ vọng | Baseline |
|---|---|---|
| Row count | >= 1 | PASS, 24 |
| `paper_id` non-null | Không null | PASS |
| `title` non-null | Không null | PASS |
| `paper_id` unique | Unique | PASS |
| Summary length | >= 1 | PASS |
| Freshness | Stale ratio <= 25% | PASS, 1/24 = 4.17% |

Freshness report tại `data/quality/freshness_report.json` ghi latest published `2026-07-22`, oldest published `2026-03-28`, threshold 180 ngày và trạng thái `is_fresh=true`.

## 9. Corruption và repair

| Corruption | Record/event bị tác động | Tác động quan sát được | Repair |
|---|---:|---|---|
| Drop latest records | 5 events | Dataset giảm từ 24 xuống 23 rows | Rebuild từ raw |
| Blank summary | 4 events | Summary quality fail | Rebuild từ raw |
| Inject noise | 4 events | Token F1 và answer quality giảm | Rebuild từ raw |
| Truncate title | 4 events | Metadata/title bị suy giảm | Rebuild từ raw |
| Stale date | 4 events | Stale rows tăng lên 9/23 | Rebuild từ raw |
| Duplicate rows | 4 events | Uniqueness check fail | Rebuild từ raw |

`data/results/corruption_log.json` ghi nhận 25 events và đủ 6 corruption types. Repair đọc lại `data/raw/crossref_records.json`, chạy lại cleaning, indexing và evaluation; không chỉnh sửa trực tiếp corrupted dataframe.

## 10. So sánh ba trạng thái

| Metric/signal | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| `retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 |
| `mean_token_f1` | 1.0000 | 0.5529 | 1.0000 |
| `judge_accuracy` | 1.0000 | 0.6000 | 1.0000 |
| `mean_judge_score` | 5 | 3 | 5 |
| Quality gate | PASS | FAIL | PASS |
| Freshness | FRESH | STALE | FRESH |

Kết luận nhân quả:

1. Blank/noisy summaries, stale dates và duplicate IDs → quality gate fail, stale ratio tăng từ 4.17% lên 39.13% → retrieval hit rate giảm từ 1.0 xuống 0.5 và token F1 giảm xuống 0.5529.
2. Rebuild từ raw snapshot → clean dataset 24 rows, quality/freshness pass → retrieval hit rate, token F1 và judge metrics trở lại baseline.

## 11. Vấn đề tích hợp

- **Triệu chứng:** Rerun baseline trong môi trường hiện tại không tải được embedding model.
- **Nguyên nhân:** DNS/network không truy cập được `huggingface.co`.
- **Cách xử lý:** Giữ lại artifacts đã tạo; cần bật network hoặc preload model cache trước khi rerun.
- **Cách xác minh:** Baseline metrics, ChromaDB manifest và report hiện có; các test unit vẫn pass.

## 12. Giới hạn và hướng cải thiện

| Giới hạn | Ảnh hưởng | Hướng cải thiện |
|---|---|---|
| Fresh rerun phụ thuộc Hugging Face network | Không thể tái tạo index offline nếu model chưa cache | Pre-download/cache model hoặc dùng local model path |
| Ragas mặc định bị skip | Chưa có Ragas metrics | Chạy với `RUN_RAGAS=1` khi provider/credentials sẵn sàng |
| Chưa có CI coverage >80% | Regression coverage còn giới hạn | Thêm pytest suite và GitHub Actions |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository đã điền.
- [x] Phân công khớp với module/artifact.
- [ ] Rerun hai pipeline thành công trong môi trường có model cache/network.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness kết luận khớp với `data/quality/`.
- [x] Các report và artifact hiện có.
- [ ] Tạo báo cáo cá nhân riêng cho từng thành viên.
- [x] Không commit `.env`, API key hoặc secret.
