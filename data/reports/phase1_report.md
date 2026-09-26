# Phase 1 Baseline Report

## Source and artifacts

- Source: Crossref REST API
- Query: agentic retrieval augmented generation large language model
- Raw records: 24
- Clean records: 24
- Test questions: 10
- ChromaDB collection: `papers-baseline`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- LLM provider/model: `gemini` / `gemini-2.5-flash`

## Baseline evaluation

| Metric | Value |
| --- | ---: |
| Samples | 10 |
| Retrieval hit rate | 1.0000 |
| Mean token F1 | 1.0000 |
| Judge accuracy | 1.0000 |
| Mean judge score | 5 |

Ragas: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## Great Expectations quality gate

Overall GX status: **PASS**

| Expectation | Status | Observed |
| --- | --- | --- |
| `expect_table_row_count_to_be_between` | PASS | 24 |
| `expect_column_values_to_not_be_null` | PASS | - |
| `expect_column_values_to_be_unique` | PASS | - |
| `expect_column_values_to_not_be_null` | PASS | - |
| `expect_column_value_lengths_to_be_between` | PASS | - |

## Freshness SLA

- Status: **FRESH**
- Threshold: 180 days
- Stale rows: 1/24
- Stale ratio: 0.0417
- Maximum allowed stale ratio: 0.2500

Final quality gate: **PASS**
