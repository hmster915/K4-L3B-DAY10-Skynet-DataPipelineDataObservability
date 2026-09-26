# Individual Report — Nguyễn Khánh Linh

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Khánh Linh |
| MSSV | 2A202602409 |
| Khóa/Lớp | K4-L3B |
| Tên nhóm | Skynet |
| Vai trò chính | Data Observability & Benchmark Evaluation |
| Repository | `K4-L3B-DAY10-Skynet-DataPipelineDataObservability` |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input | Output | Trạng thái |
|---|---|---|---|---|
| Quality Gate | `src/observability/quality.py`, `run_data_quality_checks()` | Clean dataframe, `age_days` | GX quality reports và freshness signals | Hoàn thành |
| Freshness report | `build_freshness_report()` | Clean dataframe, SLA settings | `data/quality/freshness_report.json` | Hoàn thành |
| Evaluation set | `src/evaluation/testset.py`, `build_test_set()` | Clean dataframe | `data/eval/test_set.json` | Hoàn thành |
| Comparison reporting | `src/observability/reporting.py`, `generate_corruption_report()` | Ba bộ metrics và quality results | `data/reports/corruption_report.md` | Hoàn thành |

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/artifact | Kết quả | Cách xác minh |
|---|---|---|---|
| Xây dựng GX 1.x quality gate | `src/observability/quality.py` | 5 expectations; baseline/repaired PASS, corrupted FAIL | `data/quality/*_quality_report.json` |
| Xây dựng Freshness SLA | `quality.py` | Baseline fresh: 1/24 stale; corrupted stale: 9/23 | `data/quality/freshness_report.json` và quality reports |
| Tạo evaluation set | `src/evaluation/testset.py` | 10 câu hỏi, 4 question types | `data/eval/test_set.json` |
| Tạo comparison report | `src/observability/reporting.py` | Bảng Baseline/Corrupted/Repaired | `data/reports/corruption_report.md` |

Output tiêu biểu là comparison report: retrieval hit rate giảm từ `1.0000` xuống `0.5000` sau corruption và phục hồi về `1.0000` sau repair.

## 4. Giải thích kỹ thuật

### Vấn đề cần giải quyết

RAG có thể tiếp tục chạy dù dữ liệu bị thiếu, trùng lặp, nhiễu hoặc stale. Quality Gate cần phát hiện lỗi trước serving layer, còn evaluation cần đo được tác động của lỗi lên retrieval và answer quality.

### Cách triển khai

`run_data_quality_checks()` tạo ephemeral Great Expectations context, pandas datasource, dataframe asset và batch. Suite kiểm tra row count, null `paper_id`, null `title`, uniqueness của `paper_id`, và summary length. Freshness được tính bằng `age_days`; dataset chỉ fresh khi stale ratio không vượt quá 25%.

`build_test_set()` tạo 10 câu hỏi deterministic từ clean dataframe, giữ document ID làm ground truth. `generate_corruption_report()` nhận metrics và quality results của ba trạng thái rồi tạo bảng so sánh cùng phần impact analysis.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | Clean dataframe có `paper_id`, `title`, `summary`, `published`, `age_days` và các cột helper |
| Output | Quality JSON, freshness JSON, test set JSON, comparison Markdown |
| Module phụ thuộc | `core.config`, `core.utils`, pandas, Great Expectations |
| Module sử dụng output | `phase1.py`, `corruption_flow.py`, evaluation/reporting |
| Điều kiện lỗi | Empty dataframe, thiếu cột bắt buộc, null/duplicate values, stale ratio vượt SLA |

### Cách xác minh

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -v
PYTHONPATH=src .venv/bin/python -m compileall -q src script tests
```

- **Kết quả:** 6 tests pass; compilation pass.
- **Artifacts:** `data/quality/`, `data/eval/test_set.json`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quality check lặp lại trên từng dataframe mà không phụ thuộc datasource state persisted.
- **Phương án cân nhắc:** dùng GX context persisted hoặc ephemeral context.
- **Phương án chọn:** ephemeral context với pandas dataframe asset.
- **Lý do:** phù hợp lab offline, mỗi stage được kiểm tra độc lập, tránh state cũ làm sai kết quả.
- **Bằng chứng:** baseline và repaired reports có 5/5 expectations pass; corrupted report fail đúng do corruption.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Quality gate chỉ trả freshness nested trong quality report và chưa có freshness artifact riêng.
- **Nguyên nhân:** `build_freshness_report()` ban đầu còn là stub `NotImplementedError`.
- **Cách xử lý:** triển khai report với latest/oldest published, stale rows, ratio, threshold và `is_fresh`; nối vào baseline pipeline.
- **Cách xác minh:** freshness report hiện ghi latest `2026-07-22`, oldest `2026-03-28`, 1/24 stale và `is_fresh=true`.

Một blocker tích hợp còn lại là rerun embedding cần truy cập Hugging Face; môi trường offline hiện báo lỗi DNS khi tải `all-MiniLM-L6-v2`.

## 7. Hiểu biết về luồng end-to-end

1. Crossref response được parse thành `PaperRecord`, cleaning tạo dataframe và `text_for_embedding`, sau đó MiniLM sinh vectors và ChromaDB lưu index.
2. Evaluation set lưu câu hỏi, ground truth và document ID. Retrieval hit rate kiểm tra document đúng có nằm trong top-k; token F1 và judge đo answer quality.
3. Quality checks kiểm tra tính hợp lệ/schema của dataframe; freshness monitoring đo tuổi dữ liệu qua `age_days` và tỷ lệ stale.
4. Cùng test set giúp so sánh chỉ tác động của data state, không trộn thêm thay đổi từ câu hỏi hoặc ground truth.
5. Repair thành công khi clean/repaired quality và freshness pass, metrics phục hồi, và repaired artifacts được rebuild từ raw snapshot.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 | Corruption làm giảm một nửa hit rate; repair phục hồi hoàn toàn |
| `mean_token_f1` | 1.0000 | 0.5529 | 1.0000 | Nhiễu/blank summary làm answer overlap giảm |
| `judge_accuracy` | 1.0000 | 0.6000 | 1.0000 | Answer correctness giảm theo retrieval/context |
| `mean_judge_score` | 5 | 3 | 5 | Chất lượng phục hồi sau repair |
| Quality checks | PASS | FAIL | PASS | Duplicate/blank data bị phát hiện |
| Freshness status | FRESH | STALE | FRESH | Stale ratio 4.17% → 39.13% → 4.17% |

Chuỗi nhân quả:

1. Blank/noisy summary, stale date và duplicate ID → quality/freshness signals fail → retrieval hit rate giảm 1.0 xuống 0.5.
2. Repair từ raw snapshot → dataset 24 rows và quality/freshness pass → tất cả metrics chính trở lại baseline.

Corruption ảnh hưởng rõ nhất là nhóm summary/title/date vì trực tiếp thay đổi nội dung embedding và freshness. Kết quả khác kỳ vọng là corrupted dataset còn 23 rows thay vì giữ nguyên kích thước do kịch bản drop latest records được áp dụng trước duplicate injection.

## 9. Điều học được và hướng cải thiện

1. Data contract cần được kiểm tra trước khi dữ liệu đi vào embedding/index.
2. Freshness là tín hiệu khác với schema quality nhưng cần kết hợp trong quality gate.
3. Evaluation trên cùng test set giúp lượng hóa silent failure của RAG.

Nếu có thêm thời gian, nhóm nên thêm test cho mọi corruption scenario và CI coverage, đồng thời cache embedding model để pipeline tái hiện được khi offline.

## 10. Cam kết của thành viên

- [x] Nội dung phản ánh phạm vi Observability & Evaluation.
- [x] Các kết luận có artifact hoặc metric đối chiếu.
- [x] Không ghi kết quả Ragas vì Ragas đang được skip.
- [x] Không có API key hoặc secret trong báo cáo.

**Họ và tên:** Nguyễn Khánh Linh
**Ngày xác nhận:** 2026-09-26
