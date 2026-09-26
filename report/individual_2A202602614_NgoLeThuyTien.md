# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Ngô Lê Thùy Tiên             |
| MSSV               | 2A202602614                     |
| Khóa/Lớp         | K4              |
| Tên nhóm         | Skynet     |
| Vai trò chính    | Data ingestion & cleaning owner                 |
| Repository         | https://github.com/hmster915/K4-L3B-DAY10-Skynet-DataPipelineDataObservability (nhánh `tien`, PR #1) |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Raw ingestion (Crossref) | `src/ingestion/crossref.py`: `parse_crossref_payload()`, `fetch_source_records()`, `load_raw_records()` | Crossref REST API response / snapshot cục bộ đã lưu trước đó | `PaperRecord` list, raw records JSON snapshot (24 bản ghi) | Hoàn thành |
| Cleaning & data modeling | `src/ingestion/cleaning.py`: `build_clean_dataframe()` | `list[PaperRecord]` từ bước ingestion | `data/clean/papers_clean.csv`, `papers_clean.json` (schema chuẩn + cột `text_for_embedding`) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Tự triển khai một bản giải pháp end-to-end đầy đủ (evaluation set, quality/freshness gate, baseline pipeline, corruption & repair flow) để tự xác minh mình hiểu toàn bộ luồng trước khi nhóm chốt phân công cuối cùng | Nguyễn Hồng Khoa (evaluation/observability/baseline owner), Phùng Trọng Chiến (corruption/repair owner) | Phát hiện và tự sửa lỗi ChromaDB metadata reject `pandas.Timestamp` ngay ở bước cleaning trước khi lỗi này lan sang bước index của nhóm; dùng bản giải pháp solo để đối chiếu kết quả với artifact mà Khoa/Chiến tạo ra trên `main` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Fetch + parse Crossref payload, retry/backoff khi gặp 429/503, tái sử dụng snapshot cục bộ khi không cần refresh | `src/ingestion/crossref.py` | `data/raw/` raw records JSON, 24 `PaperRecord` | `python script/run_phase1.py` → log xác nhận 24 bài báo được fetch (checkpoint CP0) |
| Chuẩn hoá text, parse ngày tháng, tính `age_days`, loại bỏ trùng `paper_id`, build `text_for_embedding` | `src/ingestion/cleaning.py: build_clean_dataframe()` | `data/clean/papers_clean.csv`, `papers_clean.json` (24 dòng) | Checkpoint CP1: `data/quality/baseline_quality_report.json` có `success: true`, `row_count: 24` |

Output cụ thể: `data/clean/papers_clean.csv` (24 dòng, schema ổn định với cột `text_for_embedding`) là input trực tiếp cho bước index/embedding (`phase1.py`), bước sinh evaluation set (`testset.py`) và bước quality gate (`quality.py`) của các thành viên khác trong nhóm.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi nhận response thô từ Crossref REST API (field lồng nhau, `abstract` chứa JATS/HTML tag, ngày tháng ở dạng `date-parts`, `author`/`category` là list) và biến nó thành một bảng dữ liệu sạch, có schema ổn định để các bước embedding, evaluation và quality checks phía sau có thể dùng chung mà không phải tự parse lại từng field.

### Cách triển khai

- `parse_crossref_payload()`: duyệt qua các item trả về từ API, loại bỏ item thiếu DOI hoặc title, strip JATS/HTML tag khỏi abstract trong `_clean_abstract()`, format lại `date-parts` (year/month/day) thành chuỗi ngày trong `_format_date_parts()`.
- `fetch_source_records()`: gọi Crossref API kèm retry/backoff khi gặp lỗi 429/503; nếu `settings.refresh_source=False` thì tái sử dụng snapshot cục bộ sẵn có (idempotent, tránh bị rate-limit khi chạy lại nhiều lần); nếu API lỗi thì fallback về snapshot cũ thay vì để pipeline crash.
- `build_clean_dataframe()`: chuẩn hoá whitespace cho `title`/`summary`, parse `published`/`updated` thành `datetime` rồi format lại thành chuỗi `YYYY-MM-DD` (ban đầu để nguyên `pandas.Timestamp` tz-aware, nhưng ChromaDB metadata chỉ chấp nhận `str/int/float/bool/list/None` nên phải sửa), tính `age_days` so với `run_date`, build các cột phụ trợ `authors_joined`/`categories_joined`/`summary_chars`/`text_for_embedding`, loại bỏ dòng trùng `paper_id`, sắp xếp kết quả.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `list[PaperRecord]` từ `crossref.fetch_source_records()`/`load_raw_records()`, cùng `run_date` |
| Output                         | `pandas.DataFrame` với cột `paper_id, title, summary, authors_joined, categories_joined, published, updated, age_days, summary_chars, text_for_embedding`, ghi ra `data/clean/papers_clean.csv`/`.json` |
| Module phụ thuộc             | `src/ingestion/crossref.py` (`PaperRecord`) |
| Module sử dụng output        | `src/observability/quality.py` (quality gate), `src/evaluation/testset.py` (build test set), `src/pipelines/phase1.py` (index + evaluate) |
| Điều kiện lỗi cần xử lý | Response thiếu DOI/title → loại bỏ; ngày tháng không parse được → `_parse_date()` trả `None`; API rate limit 429/503 → retry/backoff rồi fallback snapshot cũ |

### Cách xác minh

```bash
python script/run_phase1.py
```

- **Kết quả mong đợi:** 24 bản ghi Crossref được fetch (CP0), 24 dòng sau cleaning không trùng `paper_id` (CP1).
- **Kết quả thực tế:** đúng như mong đợi — `data/clean/papers_clean.csv` có 24 dòng; `data/quality/baseline_quality_report.json` có `success: true`, `row_count: 24`.
- **Artifact/log:** `data/clean/papers_clean.csv`, `data/clean/papers_clean.json`, `data/quality/baseline_quality_report.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Sau khi parse, `published`/`updated` là `pandas.Timestamp` có timezone. Khi bước `phase1.py` index dữ liệu vào ChromaDB, việc ghi metadata bị lỗi vì `Timestamp` không thuộc kiểu ChromaDB chấp nhận (chỉ `str/int/float/bool/list/None`).
- **Các phương án đã cân nhắc:** (1) Giữ nguyên `Timestamp` trong dataframe và convert sang string ngay tại bước index (trong `phase1.py`) mỗi lần cần ghi Chroma; (2) Chuẩn hoá `published`/`updated` thành chuỗi ISO ngay tại `build_clean_dataframe()` để mọi consumer downstream đều nhận cùng một kiểu dữ liệu ổn định.
- **Phương án đã chọn:** Phương án (2) — format lại `published`/`updated` thành chuỗi `YYYY-MM-DD` ngay trong `cleaning.py`.
- **Lý do:** `cleaning.py` là nguồn tạo artifact dùng chung (`papers_clean.csv`/`.json`) cho nhiều module khác (evaluation, quality, indexing). Sửa tại nguồn tránh việc mỗi module phải tự convert lại kiểu dữ liệu, giảm rủi ro lệch schema giữa các thành viên trong nhóm.
- **Bằng chứng quyết định phù hợp:** Sau khi sửa, checkpoint CP1 (quality gate) vẫn `success: true`, và bước index Chroma trong `phase1.py` không còn lỗi validation metadata.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** ChromaDB raise lỗi validation khi ghi metadata cho document, vì giá trị `published`/`updated` là `pandas.Timestamp` (tz-aware), không nằm trong tập kiểu cho phép (`str/int/float/bool/list/None`).
- **Lệnh hoặc bước tái hiện:** Chạy `python script/run_phase1.py` khi `build_clean_dataframe()` còn để nguyên `Timestamp` thô — pipeline fail ngay ở bước index vào Chroma.
- **Nguyên nhân gốc:** `build_clean_dataframe()` parse `published`/`updated` bằng `pandas`/`datetime` nhưng không convert lại về string trước khi cột này được dùng làm metadata cho Chroma.
- **Cách xử lý:** Sửa `build_clean_dataframe()` để `published`/`updated` được format thành chuỗi `YYYY-MM-DD` (dùng `strftime`) thay vì để nguyên object `Timestamp`.
- **Cách xác minh sau khi sửa:** Chạy lại `python script/run_phase1.py` — bước index Chroma chạy hết không lỗi, `data/chroma/` được tạo, và checkpoint CP1 (quality gate) vẫn `success: true`, `row_count: 24`.
- **Điều học được:** Artifact dùng chung giữa nhiều module — đặc biệt khi ghi vào một storage có schema ràng buộc như metadata của ChromaDB — nên được chuẩn hoá kiểu dữ liệu ngay tại nguồn (bước cleaning), thay vì để mỗi module tiêu thụ tự xử lý type conversion khác nhau.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?** `fetch_source_records()` gọi Crossref API (hoặc tái dùng snapshot cục bộ) → `parse_crossref_payload()` convert response thành list `PaperRecord` (lưu ở `data/raw/`) → `build_clean_dataframe()` chuẩn hoá thành bảng sạch (`data/clean/papers_clean.csv`/`.json`) có cột `text_for_embedding` → `phase1.py` encode `text_for_embedding` và ghi vào collection ChromaDB `papers` (embeddings cũng được lưu song song ở `data/embeddings/papers_embeddings.json`).
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?** `testset.py: build_test_set()` sinh 10 câu hỏi round-robin theo 4 loại (summary/authors/date/categories), mỗi câu lấy từ một paper đại diện; `ground_truth` là câu trả lời tham chiếu (câu đầu của summary, danh sách authors nối chuỗi, ngày published ISO, categories nối chuỗi) và `ground_truth_doc_ids` là `paper_id` của paper đó. Khi evaluate, agent truy vấn Chroma với `question`, so `paper_id` trả về với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và so câu trả lời sinh ra với `ground_truth` để tính `mean_token_f1`/`judge_accuracy`/`mean_judge_score`.
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?** `quality.py` chạy hai lớp kiểm tra độc lập: (a) GX `ExpectationSuite` kiểm tra cấu trúc/nội dung tại một thời điểm (row count, not-null, unique `paper_id`, độ dài `summary`) — kiểm tra "tĩnh" trên dữ liệu hiện có; (b) freshness SLA (`evaluate_freshness_sla()`) kiểm tra tính "mới" của dữ liệu theo thời gian, dựa trên `age_days` so với `freshness_threshold_days`, và đánh dấu `is_fresh=False` khi tỉ lệ dòng stale vượt 25%. Freshness không kiểm tra giá trị đúng/sai mà kiểm tra dữ liệu có bị lỗi thời so với ngưỡng SLA hay không — bổ sung góc nhìn thời gian mà GX suite không có.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?** Để phép so sánh `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy` có ý nghĩa (apples-to-apples). Nếu mỗi trạng thái dùng câu hỏi/ground-truth khác nhau thì chênh lệch metric có thể do câu hỏi khác nhau chứ không phải do corruption/repair tác động lên dữ liệu.
5. **Repair được xem là thành công dựa trên artifact và metric nào?** `repair_from_raw_snapshot()` (trong `cleaning.py`) rebuild lại clean dataframe trực tiếp từ raw snapshot, độc lập với corruption đã tiêm vào, sau đó re-index vào collection `papers-repaired` và re-evaluate. Repair được xem là thành công vì: (a) `data/quality/repaired_quality_report.json` có `success: true`, `row_count` quay lại 24, `is_fresh: true` (stale_ratio ≈ 0.0417, giống baseline); (b) `data/results/repaired_metrics.json` có `retrieval_hit_rate=1.0`, `mean_token_f1=1.0`, `judge_accuracy=1.0`, `mean_judge_score=5` — khớp hoàn toàn với `baseline_metrics.json`, tức retrieval gap so với baseline bằng 0 (được nêu rõ trong `data/reports/corruption_report.md`).

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.0000 |       0.5000 |      1.0000 | Giảm đúng 50% vì `drop_latest_records` xoá hẳn 5/24 document khỏi index — đối chiếu `data/results/corrupted_answers.json` với `data/eval/test_set.json` thì chính xác 5 câu hỏi có `ground_truth_doc_ids` trỏ vào 5 document bị xoá đó bị miss, phục hồi hoàn toàn sau repair |
| `mean_token_f1`      |      1.0000 |       0.5529 |      1.0000 | Giảm do hai nguyên nhân cộng dồn: (1) 5 câu hỏi có document bị `drop_latest_records` xoá hẳn nên không có gì để trả lời đúng; (2) trong số document còn sống, 4 document vừa bị `duplicate_rows` vừa bị `blank_summary`/`truncate_title`/`stale_date` — vẫn được retrieve đúng nhưng nội dung để sinh câu trả lời bị mất, khiến 2/4 câu hỏi liên quan có `token_f1 = 0`. Phục hồi hoàn toàn sau repair |
| `judge_accuracy`     |      1.0000 |       0.6000 |      1.0000 | Cùng xu hướng giảm/phục hồi như hai metric trên |
| `mean_judge_score`   |      5 |       3 |      5 | LLM-judge chấm điểm thấp hơn rõ rệt trên dữ liệu corrupted |
| Quality checks         |      PASS (24 rows) |       FAIL (23 rows) |      PASS (24 rows) | Corrupted fail vì vi phạm `unique paper_id` và độ dài `summary` tối thiểu |
| Freshness status       |      FRESH (stale_ratio 0.0417) |       STALE (stale_ratio 0.3913) |      FRESH (stale_ratio 0.0417) | `stale_date` corruption đẩy 9/23 dòng vượt ngưỡng 180 ngày, vượt max_stale_ratio 25% |

### Kết luận từ số liệu

1. `drop_latest_records` xoá hẳn 5/24 document, `duplicate_rows` nhân đôi 4 document khác, `stale_date` đẩy lùi ngày published của 4 document đó 365 ngày → row_count còn 23, quality gate FAIL (vi phạm `unique paper_id` do duplicate), freshness chuyển STALE (9/23 dòng stale: 1 dòng vốn đã stale từ baseline + 4 dòng bị `stale_date` + 4 bản duplicate của chính chúng, vượt ngưỡng 25%) → `retrieval_hit_rate` giảm còn 0.5 (mất hẳn 5 ground-truth document) và `mean_token_f1` giảm còn 0.5529 (vừa do mất document, vừa do `blank_summary` làm nội dung của 4 document còn sống bị rỗng).
2. `repair_from_raw_snapshot()` rebuild lại từ raw snapshot gốc → quality gate quay lại PASS, freshness quay lại FRESH (stale_ratio 0.0417) → agent metrics phục hồi hoàn toàn về mức baseline (`retrieval_hit_rate=1.0`, `mean_token_f1=1.0`, `judge_accuracy=1.0`).

Corruption nào ảnh hưởng rõ nhất và vì sao?

`drop_latest_records` ảnh hưởng rõ nhất tới `retrieval_hit_rate`: đây là corruption duy nhất xoá hẳn document khỏi dataset trước khi index, nên 5 document bị xoá không thể được retrieve dưới bất kỳ hình thức nào. Đối chiếu `data/eval/test_set.json` với `data/results/corrupted_answers.json` cho thấy đúng 5 câu hỏi (q01–q05) có `ground_truth_doc_ids` trỏ vào 5 document đó đều miss, khớp chính xác với mức giảm 50% của `retrieval_hit_rate`. Ngược lại, `duplicate_rows` không hề gây miss retrieval (document trùng vẫn được tìm thấy) — tác động của nó nằm ở `mean_token_f1`/`judge_score`, vì `blank_summary` áp trên cùng 4 document đó xoá mất nội dung cần thiết để sinh câu trả lời đúng dù đã retrieve đúng document (q06, q07 có `token_f1 = 0`).

Kết quả nào khác với kỳ vọng ban đầu?

Ban đầu tôi dự đoán repair chỉ phục hồi được một phần, vì corruption tạo ra 25 sự kiện thuộc 6 loại khác nhau nên có vẻ khó rebuild sạch 100%. Tuy nhiên vì `repair_from_raw_snapshot()` đọc thẳng từ raw snapshot (không cố sửa từng dòng đã bị corrupt) nên metrics phục hồi đúng 100% so với baseline. Tôi đã kiểm tra bằng cách so trực tiếp `data/results/repaired_metrics.json` với `data/results/baseline_metrics.json` — hai file có giá trị giống hệt nhau.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Chuẩn hoá kiểu dữ liệu ngay tại bước cleaning (nguồn artifact dùng chung) quan trọng hơn việc sửa lỗi tại từng nơi tiêu thụ, đặc biệt khi nhiều thành viên trong nhóm cùng phụ thuộc vào một schema.
2. Data quality checks tĩnh (GX) và freshness monitoring bổ sung cho nhau chứ không thay thế nhau — chúng bắt các loại lỗi khác nhau (cấu trúc/nội dung vs. thời gian).
3. Repair "từ nguồn" (rebuild từ raw snapshot) an toàn và dễ verify hơn nhiều so với việc cố sửa từng dòng dữ liệu đã bị corrupt, vì nó độc lập hoàn toàn với loại corruption đã xảy ra.

### Nếu có thêm thời gian

Tôi muốn thêm một expectation kiểm tra `text_for_embedding` không rỗng ngay tại bước cleaning (`build_clean_dataframe()`), trước khi dữ liệu tới quality gate ở `phase1.py`, để bắt lỗi kiểu `blank_summary` sớm hơn một bước trong pipeline. Cách đo cải thiện: so sánh số corruption case bị bắt ngay tại cleaning stage so với hiện tại (chỉ bị bắt ở quality gate stage, tức là sau khi đã index/evaluate một lần).

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Ngô Lê Thùy Tiên
**Ngày xác nhận:** 2026-09-26
