# Data Corruption and Recovery Report

## Evaluation comparison

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Samples | 10 | 10 | 10 |
| Retrieval hit rate | 1.0000 | 0.5000 | 1.0000 |
| Mean token F1 | 1.0000 | 0.5529 | 1.0000 |
| Judge accuracy | 1.0000 | 0.6000 | 1.0000 |
| Mean judge score | 5 | 3 | 5 |

## Data quality comparison

| Check | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Rows | 24 | 23 | 24 |
| Quality gate | - | FAIL | PASS |
| Freshness SLA | - | STALE | FRESH |
| Stale rows | - | 9 | 1 |
| Stale ratio | - | 0.3913 | 0.0417 |

## Impact analysis

- Retrieval degradation after corruption: **0.5000**.
- Retrieval recovery after rebuilding from raw snapshot: **0.5000**.
- Remaining retrieval gap versus baseline: **0.0000**.
- The corrupted quality gate is expected to fail because blank summaries and duplicated paper IDs violate the contract.
- Repair is idempotent because it rebuilds clean artifacts from the unchanged raw snapshot instead of editing corrupted rows in place.

## Conclusion

The comparison demonstrates the silent-failure pattern: the pipeline can still execute while retrieval quality and data-quality signals degrade. Rebuilding from the trusted raw snapshot restores the clean dataset and its index.
