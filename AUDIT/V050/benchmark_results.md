## jsonl — 200 synthetic rows

| backend | concurrency | rows | published | wall_s | jobs_per_min | p50_ms | p95_ms | duplicate_or_errored | errors | cpu_s | maxrss_mb |
|---|---|---|---|---|---|---|---|---|---|---|---|
| jsonl | 1 | 200 | 200 | 0.976 | 12296.4 | 2.51 | 2.52 | 0 | 0 | 0.471 | 35392.0 |
| jsonl | 2 | 200 | 200 | 0.472 | 25448.2 | 2.51 | 2.52 | 0 | 0 | 0.387 | 35904.0 |
| jsonl | 4 | 200 | 200 | 0.394 | 30457.5 | 2.52 | 2.55 | 0 | 0 | 0.392 | 36048.0 |
| jsonl | 8 | 200 | 200 | 0.46 | 26106.7 | 2.52 | 2.66 | 0 | 0 | 0.44 | 36208.0 |

## postgres — 200 synthetic rows

| backend | concurrency | rows | published | wall_s | jobs_per_min | p50_ms | p95_ms | duplicate_or_errored | errors | cpu_s | maxrss_mb |
|---|---|---|---|---|---|---|---|---|---|---|---|
| postgres | 1 | 200 | 200 | 1.549 | 7746.4 | 2.51 | 2.53 | 0 | 0 | 0.193 | 49744.0 |
| postgres | 2 | 200 | 200 | 0.807 | 14876.3 | 2.51 | 2.62 | 0 | 0 | 0.166 | 53552.0 |
| postgres | 4 | 200 | 200 | 0.38 | 31545.1 | 2.5 | 2.52 | 0 | 0 | 0.15 | 53552.0 |
| postgres | 8 | 200 | 200 | 0.302 | 39784.9 | 2.51 | 2.63 | 0 | 0 | 0.257 | 53552.0 |

## redis — 200 synthetic rows

| backend | concurrency | rows | published | wall_s | jobs_per_min | p50_ms | p95_ms | duplicate_or_errored | errors | cpu_s | maxrss_mb |
|---|---|---|---|---|---|---|---|---|---|---|---|
| redis | 1 | 200 | 200 | 1.15 | 10435.4 | 2.51 | 2.54 | 0 | 0 | 0.186 | 45184.0 |
| redis | 2 | 200 | 200 | 0.621 | 19332.5 | 2.51 | 2.63 | 0 | 0 | 0.131 | 46064.0 |
| redis | 4 | 200 | 200 | 0.401 | 29930.6 | 2.32 | 2.55 | 0 | 0 | 0.105 | 46640.0 |
| redis | 8 | 200 | 200 | 0.366 | 32792.4 | 2.22 | 2.52 | 0 | 0 | 0.142 | 47776.0 |

