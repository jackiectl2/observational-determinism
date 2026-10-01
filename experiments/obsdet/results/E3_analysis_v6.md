# E3 cost analysis (cost_analyze.py): preview + count model, DuckDB v6, PostgreSQL v6pg; pilot tool on v3

Scales x10 / x100 / x30 replicate SF1 data (offset copies): a stress test, not a representative workload.

## A. Preview + count model: observation = first 20 rows under the policy's order + exact row count

Records: {'cert_probes_v6.jsonl': 3018}

### DuckDB, total = preview + count

Probes replayed: 1006; succeeding at sf1: 1006; failing with an error at a larger scale (excluded, cannot be timed): 18 [536, 550, 589, 602, 733, 734, 745, 746, 747, 748, 805, 807]...; missing: 0; with a timeout at some scale: 2 [193, 222]. **Main set: 986 probes, identical at every scale.** Scales beyond sf1 are replicated-data stress tests.

| scale | set | n | raw s | smartlex s | certified s | certified vs smartlex (95% CI) | median per-probe S/C (95% CI) | largest single-probe share of S / C total | share of S-C from one probe | count s |
|---|---|---|---|---|---|---|---|---|---|---|
| sf1 | main | 986 | 3.62 | 3.88 | 3.82 | +1.7% [-0.6, +4.6] | 1.001x [0.999, 1.002] | 2% / 2% | #403 67% **(one probe)** | 1.69 |
| sf1 | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 29.20 | 29.46 | 29.46 | -0.0% [-0.3, +2.8] | 1.001x [0.999, 1.002] | 44% / 44% | n/a (difference < 0.5%) | 14.45 |
| x10 | main | 986 | 11.25 | 11.50 | 11.06 | +3.8% [+1.1, +7.3] | 1.001x [1.000, 1.003] | 4% / 4% | #403 26% | 4.89 |
| x10 | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 251.25 | 251.50 | 251.06 | +0.2% [+0.0, +5.0] | 1.001x [1.000, 1.003] | 48% / 48% | n/a (difference < 0.5%) | 124.89 |
| xmax | main | 986 | 48.08 | 44.63 | 42.76 | +4.2% [-0.9, +10.2] | 1.002x [1.000, 1.003] | 4% / 5% | #403 40% | 18.16 |
| xmax | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 288.08 | 284.63 | 282.76 | +0.7% [-0.2, +6.3] | 1.002x [1.000, 1.003] | 42% / 42% | #403 40% | 138.16 |

Per-probe smartlex/certified at xmax (main set, n=986): p10 0.96x, p25 0.99x, median 1.00x, p75 1.02x, p90 1.13x; certified >10% faster on 12% of probes, >10% slower on 5%.

LIMIT classes at xmax (main set):

| class | n | raw s | smartlex s | certified s | smartlex/certified (ratio of totals) | 95% CI | median per-probe S/C |
|---|---|---|---|---|---|---|---|
| L1: LIMIT/OFFSET, verdict != DET (predeclared class) | 176 | 9.50 | 11.24 | 11.69 | 0.96x | [0.87, 1.09] | 1.00x |
| L2: LIMIT without ORDER BY (syntactic) | 58 | 1.74 | 2.46 | 1.94 | 1.27x | [1.08, 1.69] | 1.00x |
| L3: LIMIT/OFFSET, verdict NARROW/ALL (repaired) | 147 | 5.84 | 7.57 | 8.02 | 0.94x | [0.84, 1.15] | 1.00x |

Leave-out at xmax (main set): certified vs smartlex +4.2%; without the largest contributor in that direction (#403) +2.6%; without the top 5 ([403, 428, 349, 235, 149]) -0.0%.

Per class at xmax (main set; probe class x verdict), total seconds:

| class | verdict | n | raw | smartlex | certified | smartlex/certified | certified/raw |
|---|---|---|---|---|---|---|---|
| order_limit | DET | 7 | 0.067 | 0.067 | 0.066 | 1.01x | 1.00x |
| order_limit | NARROW | 83 | 3.62 | 4.24 | 4.71 | 0.90x | 1.30x |
| order_limit | ALL | 8 | 0.729 | 1.12 | 1.61 | 0.69x | 2.20x |
| order_limit | UNSUPPORTED | 27 | 3.42 | 3.43 | 3.43 | 1.00x | 1.00x |
| **order_limit** | all | 125 | 7.83 | 8.85 | 9.82 | **0.90x** | 1.25x |
| order_only | NARROW | 24 | 0.672 | 0.676 | 0.690 | 0.98x | 1.03x |
| order_only | UNSUPPORTED | 14 | 3.21 | 3.22 | 3.20 | 1.01x | 1.00x |
| **order_only** | all | 38 | 3.88 | 3.89 | 3.89 | **1.00x** | 1.00x |
| limit_no_order | NARROW | 45 | 1.36 | 2.05 | 1.53 | 1.34x | 1.12x |
| limit_no_order | ALL | 11 | 0.134 | 0.170 | 0.171 | 0.99x | 1.28x |
| limit_no_order | UNSUPPORTED | 2 | 0.240 | 0.241 | 0.241 | 1.00x | 1.00x |
| **limit_no_order** | all | 58 | 1.74 | 2.46 | 1.94 | **1.27x** | 1.12x |
| distinct | DET | 7 | 0.084 | 0.086 | 0.085 | 1.01x | 1.00x |
| distinct | NARROW | 24 | 1.21 | 1.24 | 1.23 | 1.00x | 1.02x |
| distinct | ALL | 93 | 3.77 | 3.80 | 3.81 | 1.00x | 1.01x |
| distinct | UNSUPPORTED | 4 | 0.113 | 0.113 | 0.113 | 0.99x | 1.00x |
| **distinct** | all | 128 | 5.19 | 5.24 | 5.24 | **1.00x** | 1.01x |
| group_by | DET | 1 | 0.006 | 0.006 | 0.006 | 1.02x | 0.96x |
| group_by | NARROW | 45 | 0.589 | 0.598 | 0.603 | 0.99x | 1.03x |
| group_by | UNSUPPORTED | 14 | 0.627 | 0.632 | 0.633 | 1.00x | 1.01x |
| **group_by** | all | 60 | 1.22 | 1.24 | 1.24 | **0.99x** | 1.02x |
| other | DET | 151 | 2.46 | 2.51 | 2.47 | 1.02x | 1.00x |
| other | NARROW | 282 | 12.13 | 13.30 | 10.97 | 1.21x | 0.90x |
| other | ALL | 60 | 9.32 | 2.82 | 2.86 | 0.99x | 0.31x |
| other | UNSUPPORTED | 84 | 4.31 | 4.34 | 4.33 | 1.00x | 1.01x |
| **other** | all | 577 | 28.22 | 22.96 | 20.63 | **1.11x** | 0.73x |

A/A check at xmax (identical preview SQL timed as two policies): DET certified/raw = 1.006 (n=166); UNSUPPORTED certified/smartlex = 0.998 (n=145).

Largest per-probe smartlex - certified at xmax (s): #403 card_games other/NARROW +0.744, #428 card_games other/NARROW +0.577, #349 card_games other/NARROW +0.243, #235 california limit_no_order/NARROW +0.168, #149 california limit_no_order/NARROW +0.153; most negative: #604 codebase_c other/NARROW -0.011, #72 california order_limit/NARROW -0.012, #582 codebase_c other/ALL -0.033, #71 california order_limit/NARROW -0.476, #113 california order_limit/ALL -0.491.

NARROW probes at DuckDB xmax, total by certified tie-break column (output column or not (name match); type):

| tie-break | type | n | raw s | smartlex s | certified s | smartlex/certified |
|---|---|---|---|---|---|---|
| non-output | numeric | 200 | 7.85 | 8.83 | 7.95 | 1.11x |
| non-output | string | 85 | 2.67 | 3.22 | 3.70 | 0.87x |
| non-output | unknown | 45 | 2.39 | 2.40 | 2.39 | 1.00x |
| output | numeric | 102 | 4.24 | 4.46 | 3.01 | 1.48x |
| output | string | 70 | 2.42 | 3.18 | 2.68 | 1.19x |
| output | unknown | 1 | 0.002 | 0.002 | 0.006 | 0.33x |

DuckDB plan attribution, preview queries at xmax (one EXPLAIN ANALYZE per policy and probe, n=986):

| quantity | raw | smartlex | certified |
|---|---|---|---|
| main sort operator = TOP_N | 165 | 925 | 751 |
| main sort operator = ORDER_BY | 6 | 61 | 76 |
| main sort operator = no sort | 815 | 0 | 159 |
| late materialization | 46 | 146 | 257 |
| profile failed | 0 | 0 | 0 |
| mean sort keys in main sort | 1.04 | 2.76 | 1.55 |
| engine latency s | 31.08 | 27.23 | 25.53 |
| sort operators s (sum over threads) | 4.52 | 12.47 | 18.08 |
| table scans s (sum over threads) | 93.65 | 105.74 | 85.40 |
| rows scanned (M) | 6239.18 | 7441.17 | 7687.91 |
| peak buffer memory (GB, sum over probes) | 2163.39 | 2207.47 | 2187.77 |

### DuckDB, preview only (secondary view)

Probes replayed: 1006; succeeding at sf1: 1006; failing with an error at a larger scale (excluded, cannot be timed): 18 [536, 550, 589, 602, 733, 734, 745, 746, 747, 748, 805, 807]...; missing: 0; with a timeout at some scale: 2 [193, 222]. **Main set: 986 probes, identical at every scale.** Scales beyond sf1 are replicated-data stress tests.

| scale | set | n | raw s | smartlex s | certified s | certified vs smartlex (95% CI) | median per-probe S/C (95% CI) | largest single-probe share of S / C total | share of S-C from one probe |
|---|---|---|---|---|---|---|---|---|---|
| sf1 | main | 986 | 1.93 | 2.19 | 2.12 | +2.9% [-1.2, +8.0] | 1.001x [0.999, 1.004] | 3% / 2% | #403 67% **(one probe)** |
| sf1 | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 14.75 | 15.01 | 15.01 | -0.0% [-0.6, +4.9] | 1.001x [0.999, 1.004] | 43% / 43% | n/a (difference < 0.5%) |
| x10 | main | 986 | 6.36 | 6.61 | 6.17 | +6.7% [+1.9, +12.3] | 1.002x [0.999, 1.005] | 4% / 4% | #403 26% |
| x10 | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 126.36 | 126.61 | 126.17 | +0.3% [+0.1, +8.6] | 1.002x [0.999, 1.005] | 47% / 48% | n/a (difference < 0.5%) |
| xmax | main | 986 | 29.92 | 26.48 | 24.61 | +7.1% [-1.5, +16.9] | 1.003x [1.001, 1.005] | 4% / 6% | #403 40% |
| xmax | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 149.92 | 146.48 | 144.61 | +1.3% [-0.3, +10.7] | 1.003x [1.001, 1.005] | 41% / 41% | #403 40% |

Per-probe smartlex/certified at xmax (main set, n=986): p10 0.93x, p25 0.98x, median 1.00x, p75 1.03x, p90 1.22x; certified >10% faster on 15% of probes, >10% slower on 8%.

LIMIT classes at xmax (main set):

| class | n | raw s | smartlex s | certified s | smartlex/certified (ratio of totals) | 95% CI | median per-probe S/C |
|---|---|---|---|---|---|---|---|
| L1: LIMIT/OFFSET, verdict != DET (predeclared class) | 176 | 6.05 | 7.79 | 8.24 | 0.95x | [0.84, 1.14] | 1.00x |
| L2: LIMIT without ORDER BY (syntactic) | 58 | 0.879 | 1.60 | 1.09 | 1.48x | [1.14, 2.16] | 1.00x |
| L3: LIMIT/OFFSET, verdict NARROW/ALL (repaired) | 147 | 4.05 | 5.78 | 6.22 | 0.93x | [0.81, 1.23] | 1.01x |

Leave-out at xmax (main set): certified vs smartlex +7.1%; without the largest contributor in that direction (#403) +4.4%; without the top 5 ([403, 428, 349, 235, 149]) -0.1%.
Records: {'cert_probes_v6.jsonl': 1994}
PostgreSQL-dialect vs DuckDB (v6) verdicts at sf1: {('ALL', 'ALL'): 175, ('ALL', 'NARROW'): 1, ('ALL', 'UNSUPPORTED'): 1, ('DET', 'DET'): 166, ('NARROW', 'NARROW'): 512, ('UNSUPPORTED', 'UNSUPPORTED'): 151}

### PostgreSQL, total = preview + count

Probes replayed: 1006; succeeding at sf1: 988; failing with an error at a larger scale (excluded, cannot be timed): 18 [536, 550, 589, 602, 733, 734, 745, 746, 747, 748, 805, 807]...; missing: 0; with a timeout at some scale: 8 [115, 139, 193, 222, 429, 433, 529, 582]. **Main set: 962 probes, identical at every scale.** Scales beyond sf1 are replicated-data stress tests.

| scale | set | n | raw s | smartlex s | certified s | certified vs smartlex (95% CI) | median per-probe S/C (95% CI) | largest single-probe share of S / C total | share of S-C from one probe | count s |
|---|---|---|---|---|---|---|---|---|---|---|
| sf1 | main | 962 | 16.50 | 16.13 | 19.65 | -21.8% [-38.1, -8.6] | 1.001x [1.000, 1.001] | 3% / 3% | #385 16% | 7.62 |
| sf1 | sensitivity: + timeouts at 60 s (lower bounds) | 970 | 136.01 | 141.43 | 148.21 | -4.8% [-44.8, +8.5] | 1.001x [1.000, 1.001] | 36% / 35% | #139 103% **(one probe)** | 69.56 |
| x10 | main | 962 | 111.74 | 132.66 | 246.90 | -86.1% [-212.4, -8.5] | 1.000x [1.000, 1.000] | 15% / 20% | #320 43% | 53.80 |
| x10 | sensitivity: + timeouts at 60 s (lower bounds) | 970 | 413.39 | 493.80 | 667.40 | -35.2% [-123.7, +9.3] | 1.000x [1.000, 1.000] | 12% / 9% | #529 -34% | 354.59 |

Per-probe smartlex/certified at x10 (main set, n=962): p10 0.97x, p25 1.00x, median 1.00x, p75 1.00x, p90 1.05x; certified >10% faster on 8% of probes, >10% slower on 6%.

LIMIT classes at x10 (main set):

| class | n | raw s | smartlex s | certified s | smartlex/certified (ratio of totals) | 95% CI | median per-probe S/C |
|---|---|---|---|---|---|---|---|
| L1: LIMIT/OFFSET, verdict != DET (predeclared class) | 171 | 34.80 | 33.09 | 38.63 | 0.86x | [0.75, 1.02] | 1.00x |
| L2: LIMIT without ORDER BY (syntactic) | 54 | 16.62 | 14.74 | 15.08 | 0.98x | [0.87, 1.23] | 1.04x |
| L3: LIMIT/OFFSET, verdict NARROW/ALL (repaired) | 142 | 22.74 | 20.94 | 26.48 | 0.79x | [0.69, 1.03] | 1.00x |

Leave-out at x10 (main set): certified vs smartlex -86.1%; without the largest contributor in that direction (#320) -49.2%; without the top 5 ([320, 323, 356, 450, 355]) -6.6%.

Per class at x10 (main set; probe class x verdict), total seconds:

| class | verdict | n | raw | smartlex | certified | smartlex/certified | certified/raw |
|---|---|---|---|---|---|---|---|
| order_limit | DET | 7 | 0.186 | 0.186 | 0.186 | 1.00x | 1.00x |
| order_limit | NARROW | 82 | 11.57 | 11.64 | 16.82 | 0.69x | 1.45x |
| order_limit | ALL | 8 | 0.342 | 0.457 | 0.479 | 0.95x | 1.40x |
| order_limit | UNSUPPORTED | 27 | 6.26 | 6.26 | 6.26 | 1.00x | 1.00x |
| **order_limit** | all | 124 | 18.36 | 18.54 | 23.74 | **0.78x** | 1.29x |
| order_only | NARROW | 24 | 1.24 | 1.24 | 1.22 | 1.01x | 0.99x |
| order_only | UNSUPPORTED | 14 | 6.63 | 6.62 | 6.62 | 1.00x | 1.00x |
| **order_only** | all | 38 | 7.86 | 7.86 | 7.85 | **1.00x** | 1.00x |
| limit_no_order | NARROW | 41 | 10.73 | 8.72 | 9.09 | 0.96x | 0.85x |
| limit_no_order | ALL | 11 | 0.088 | 0.124 | 0.096 | 1.30x | 1.09x |
| limit_no_order | UNSUPPORTED | 2 | 5.80 | 5.89 | 5.90 | 1.00x | 1.02x |
| **limit_no_order** | all | 54 | 16.62 | 14.74 | 15.08 | **0.98x** | 0.91x |
| distinct | DET | 7 | 0.691 | 0.689 | 0.691 | 1.00x | 1.00x |
| distinct | NARROW | 24 | 1.23 | 1.24 | 1.24 | 1.00x | 1.00x |
| distinct | ALL | 92 | 12.49 | 12.49 | 12.46 | 1.00x | 1.00x |
| distinct | UNSUPPORTED | 4 | 0.101 | 0.101 | 0.101 | 1.00x | 1.00x |
| **distinct** | all | 127 | 14.51 | 14.52 | 14.49 | **1.00x** | 1.00x |
| group_by | DET | 1 | 0.025 | 0.025 | 0.025 | 1.00x | 1.00x |
| group_by | NARROW | 45 | 1.21 | 1.21 | 1.20 | 1.00x | 1.00x |
| group_by | UNSUPPORTED | 14 | 0.942 | 0.940 | 0.940 | 1.00x | 1.00x |
| **group_by** | all | 60 | 2.17 | 2.17 | 2.17 | **1.00x** | 1.00x |
| other | DET | 140 | 6.31 | 6.31 | 6.33 | 1.00x | 1.00x |
| other | NARROW | 279 | 34.74 | 37.28 | 146.06 | 0.26x | 4.20x |
| other | ALL | 58 | 3.10 | 23.14 | 23.08 | 1.00x | 7.44x |
| other | UNSUPPORTED | 82 | 8.06 | 8.11 | 8.10 | 1.00x | 1.01x |
| **other** | all | 559 | 52.21 | 74.84 | 183.57 | **0.41x** | 3.52x |

A/A check at x10 (identical preview SQL timed as two policies): DET certified/raw = 1.001 (n=155); UNSUPPORTED certified/smartlex = 1.000 (n=143).

Largest per-probe smartlex - certified at x10 (s): #449 card_games limit_no_order/NARROW +0.117, #448 card_games other/NARROW +0.099, #286 card_games other/NARROW +0.098, #287 card_games other/NARROW +0.097, #283 card_games other/NARROW +0.097; most negative: #355 card_games other/NARROW -2.618, #450 card_games order_limit/NARROW -3.038, #356 card_games other/NARROW -3.353, #323 card_games other/NARROW -47.915, #320 card_games other/NARROW -49.177.

NARROW probes at PostgreSQL x10, total by certified tie-break column (output column or not (name match); type):

| tie-break | type | n | raw s | smartlex s | certified s | smartlex/certified |
|---|---|---|---|---|---|---|
| non-output | numeric | 198 | 38.93 | 40.77 | 152.84 | 0.27x |
| non-output | string | 84 | 10.15 | 8.60 | 10.80 | 0.80x |
| non-output | unknown | 43 | 2.40 | 2.40 | 2.39 | 1.00x |
| output | numeric | 99 | 5.39 | 5.55 | 5.55 | 1.00x |
| output | string | 70 | 3.86 | 4.00 | 4.04 | 0.99x |
| output | unknown | 1 | 0.000 | 0.000 | 0.000 | 1.02x |

PostgreSQL plans, preview queries at x10, all probes:

| quantity | raw | smartlex | certified |
|---|---|---|---|
| plan: failed | 0 | 0 | 2 |
| plan: incremental sort | 28 | 166 | 48 |
| plan: index-ordered, no sort | 175 | 23 | 232 |
| plan: no sort | 428 | 12 | 90 |
| plan: sort (full) | 237 | 581 | 455 |
| plan: top-N heapsort | 94 | 180 | 135 |
| execution time s (EXPLAIN ANALYZE) | 70.39 | 111.18 | 143.11 |
| rows scanned (M) | 611.87 | 700.20 | 672.03 |
| shared buffers hit+read (k) | 24188.62 | 28244.68 | 27505.53 |
| temp blocks written (k) | 19.54 | 19.28 | 44.94 |

PostgreSQL plans, preview queries at x10, NARROW:

| quantity | raw | smartlex | certified |
|---|---|---|---|
| plan: failed | 0 | 0 | 2 |
| plan: incremental sort | 17 | 136 | 21 |
| plan: index-ordered, no sort | 96 | 10 | 171 |
| plan: no sort | 238 | 0 | 0 |
| plan: sort (full) | 88 | 236 | 227 |
| plan: top-N heapsort | 56 | 113 | 74 |
| execution time s (EXPLAIN ANALYZE) | 36.87 | 34.59 | 66.11 |
| rows scanned (M) | 240.89 | 280.40 | 254.20 |
| shared buffers hit+read (k) | 13696.04 | 17061.18 | 16261.39 |
| temp blocks written (k) | 19.54 | 19.28 | 44.94 |

PostgreSQL plans, preview queries at x10, NARROW with LIMIT:

| quantity | raw | smartlex | certified |
|---|---|---|---|
| plan: incremental sort | 2 | 30 | 4 |
| plan: index-ordered, no sort | 8 | 0 | 35 |
| plan: no sort | 31 | 0 | 0 |
| plan: sort (full) | 37 | 34 | 36 |
| plan: top-N heapsort | 45 | 59 | 48 |
| execution time s (EXPLAIN ANALYZE) | 18.78 | 13.82 | 21.97 |
| rows scanned (M) | 56.89 | 66.41 | 60.15 |
| shared buffers hit+read (k) | 1409.42 | 2486.34 | 2421.57 |
| temp blocks written (k) | 6.73 | 19.28 | 44.94 |

### PostgreSQL, preview only (secondary view)

Probes replayed: 1006; succeeding at sf1: 988; failing with an error at a larger scale (excluded, cannot be timed): 18 [536, 550, 589, 602, 733, 734, 745, 746, 747, 748, 805, 807]...; missing: 0; with a timeout at some scale: 8 [115, 139, 193, 222, 429, 433, 529, 582]. **Main set: 962 probes, identical at every scale.** Scales beyond sf1 are replicated-data stress tests.

| scale | set | n | raw s | smartlex s | certified s | certified vs smartlex (95% CI) | median per-probe S/C (95% CI) | largest single-probe share of S / C total | share of S-C from one probe |
|---|---|---|---|---|---|---|---|---|---|
| sf1 | main | 962 | 8.75 | 8.49 | 11.96 | -40.8% [-70.7, -15.9] | 1.001x [1.001, 1.002] | 3% / 5% | #385 16% |
| sf1 | sensitivity: + timeouts at 60 s (lower bounds) | 970 | 66.30 | 71.85 | 78.58 | -9.4% [-87.8, +16.9] | 1.001x [1.001, 1.002] | 36% / 34% | #139 103% **(one probe)** |
| x10 | main | 962 | 57.82 | 78.74 | 192.98 | -145.1% [-383.7, -14.0] | 1.001x [1.000, 1.001] | 25% / 26% | #320 43% |
| x10 | sensitivity: + timeouts at 60 s (lower bounds) | 970 | 298.67 | 439.31 | 553.27 | -25.9% [-142.2, +29.0] | 1.001x [1.000, 1.001] | 14% / 11% | #582 -53% |

Per-probe smartlex/certified at x10 (main set, n=962): p10 0.99x, p25 1.00x, median 1.00x, p75 1.01x, p90 1.12x; certified >10% faster on 12% of probes, >10% slower on 5%.

LIMIT classes at x10 (main set):

| class | n | raw s | smartlex s | certified s | smartlex/certified (ratio of totals) | 95% CI | median per-probe S/C |
|---|---|---|---|---|---|---|---|
| L1: LIMIT/OFFSET, verdict != DET (predeclared class) | 171 | 19.75 | 18.05 | 23.60 | 0.76x | [0.60, 1.03] | 1.00x |
| L2: LIMIT without ORDER BY (syntactic) | 54 | 8.45 | 6.56 | 6.90 | 0.95x | [0.63, 1.37] | 1.08x |
| L3: LIMIT/OFFSET, verdict NARROW/ALL (repaired) | 142 | 12.00 | 10.21 | 15.75 | 0.65x | [0.47, 1.05] | 1.00x |

Leave-out at x10 (main set): certified vs smartlex -145.1%; without the largest contributor in that direction (#320) -82.9%; without the top 5 ([320, 323, 356, 450, 355]) -10.9%.

### Controlled LIMIT study, DuckDB (DuckDB xmax = x30 codebase_community, x100 card_games) (median ms over 5 repetitions; S/C = smartlex/certified preview; in brackets the count query / the pctxn transaction of certified)

| table | form | verdict, tie-break | sf1 raw / smartlex / certified | sf1 S/C | x10 raw / smartlex / certified | x10 S/C | xmax raw / smartlex / certified | xmax S/C |
|---|---|---|---|---|---|---|---|---|
| cards | cols3 | NARROW ['"cards"."id"'] | 0.62 / 4.26 / 1.67 [0.55] | 2.5x | 0.64 / 7.97 / 1.89 [0.51] | 4.2x | 0.75 / 56.93 / 2.06 [0.60] | 27.6x |
| cards | cols3_where | NARROW ['"cards"."id"'] | 0.75 / 4.29 / 2.11 [0.66] | 2.0x | 0.93 / 6.79 / 2.75 [0.72] | 2.5x | 1.02 / 31.93 / 3.18 [0.81] | 10.0x |
| cards | star | NARROW ['"cards"."id"'] | 6.42 / 63.78 / 8.07 [1.28] | 7.9x | 6.55 / 122.15 / 9.05 [1.09] | 13.5x | 6.30 / 130.49 / 9.56 [1.21] | 13.6x |
| comments | cols3 | NARROW ['"comments"."id"'] | 0.43 / 1.29 / 1.68 [0.49] | 0.8x | 0.42 / 1.36 / 1.64 [0.48] | 0.8x | 0.43 / 1.36 / 1.66 [0.48] | 0.8x |
| comments | cols3_where | NARROW ['"comments"."id"'] | 0.64 / 0.99 / 1.67 [0.67] | 0.6x | 0.76 / 1.03 / 1.76 [0.77] | 0.6x | 0.78 / 1.04 / 1.91 [0.76] | 0.5x |
| comments | star | NARROW ['"comments"."id"'] | 0.90 / 21.61 / 2.01 [0.58] | 10.7x | 0.91 / 20.73 / 1.92 [0.56] | 10.8x | 0.84 / 21.75 / 1.86 [0.52] | 11.7x |
| posts | cols3 | NARROW ['"posts"."id"'] | 0.49 / 4.90 / 1.74 [0.47] | 2.8x | 0.52 / 9.55 / 1.84 [0.50] | 5.2x | 0.57 / 17.41 / 1.94 [0.53] | 9.0x |
| posts | cols3_where | NARROW ['"posts"."id"'] | 0.58 / 2.96 / 1.75 [0.57] | 1.7x | 1.47 / 4.21 / 1.98 [0.76] | 2.1x | 1.46 / 10.70 / 2.14 [0.78] | 5.0x |
| posts | star | NARROW ['"posts"."id"'] | 1.51 / 18.03 / 3.14 [0.69] | 5.7x | 1.39 / 23.67 / 3.46 [0.68] | 6.8x | 1.45 / 22.47 / 3.28 [0.82] | 6.9x |
| users | cols3 | NARROW ['"users"."id"'] | 0.45 / 1.28 / 1.35 [0.47] | 0.9x | 0.54 / 5.51 / 1.80 [0.51] | 3.1x | 0.53 / 9.95 / 1.73 [0.51] | 5.7x |
| users | cols3_where | NARROW ['"users"."id"'] | 0.54 / 0.75 / 1.40 [0.56] | 0.5x | 0.70 / 1.62 / 1.95 [0.67] | 0.8x | 0.73 / 2.12 / 1.80 [0.71] | 1.2x |
| users | star | NARROW ['"users"."id"'] | 1.12 / 6.01 / 2.33 [0.56] | 2.6x | 1.15 / 18.85 / 2.78 [0.59] | 6.8x | 1.13 / 18.76 / 2.86 [0.57] | 6.6x |
| votes | cols3 | NARROW ['"votes"."id"'] | 0.41 / 0.88 / 1.34 [0.47] | 0.7x | 0.42 / 1.36 / 1.60 [0.45] | 0.9x | 0.41 / 1.39 / 1.57 [0.47] | 0.9x |
| votes | cols3_where | NARROW ['"votes"."id"'] | 0.56 / 0.82 / 1.69 [0.60] | 0.5x | 0.59 / 1.27 / 2.06 [0.61] | 0.6x | 0.64 / 1.34 / 2.01 [0.65] | 0.7x |
| votes | star | NARROW ['"votes"."id"'] | 0.47 / 1.14 / 1.49 [0.50] | 0.8x | 0.47 / 1.68 / 1.70 [0.50] | 1.0x | 0.49 / 1.69 / 1.66 [0.50] | 1.0x |

### Controlled LIMIT study, PostgreSQL (DuckDB xmax = x30 codebase_community, x100 card_games) (median ms over 5 repetitions; S/C = smartlex/certified preview; in brackets the count query / the pctxn transaction of certified)

| table | form | verdict, tie-break | sf1 raw / smartlex / certified | sf1 S/C | x10 raw / smartlex / certified | x10 S/C |
|---|---|---|---|---|---|---|
| cards | cols3 | NARROW ['"cards"."id"'] | 0.07 / 17.36 / 0.11 [0.24] | 165.3x | 0.10 / 123.23 / 0.11 [0.20] | 1173.6x |
| cards | cols3_where | NARROW ['"cards"."id"'] | 0.35 / 10.97 / 0.46 [0.81] | 23.8x | 0.34 / 65.60 / 0.66 [1.05] | 99.7x |
| cards | star | NARROW ['"cards"."id"'] | 0.22 / 0.40 / 0.24 [0.38] | 1.7x | 0.22 / 0.40 / 0.24 [0.38] | 1.7x |
| comments | cols3 | NARROW ['"comments"."id"'] | 0.08 / 18.96 / 0.09 [0.25] | 201.7x | 0.10 / 154.37 / 0.11 [0.24] | 1456.3x |
| comments | cols3_where | NARROW ['"comments"."id"'] | 0.40 / 13.33 / 0.62 [1.11] | 21.6x | 0.38 / 100.41 / 0.80 [1.23] | 126.3x |
| comments | star | NARROW ['"comments"."id"'] | 0.08 / 0.11 / 0.10 [0.21] | 1.1x | 0.08 / 0.11 / 0.10 [0.25] | 1.1x |
| posts | cols3 | NARROW ['"posts"."id"'] | 0.08 / 17.55 / 0.11 [0.25] | 161.1x | 0.11 / 161.74 / 0.11 [0.22] | 1525.9x |
| posts | cols3_where | NARROW ['"posts"."id"'] | 0.11 / 15.90 / 0.12 [0.27] | 128.2x | 0.12 / 107.10 / 0.14 [0.27] | 754.2x |
| posts | star | NARROW ['"posts"."id"'] | 0.12 / 0.17 / 0.13 [0.27] | 1.3x | 0.12 / 0.17 / 0.13 [0.27] | 1.3x |
| users | cols3 | NARROW ['"users"."id"'] | 0.07 / 7.71 / 0.09 [0.21] | 82.1x | 0.08 / 36.54 / 0.11 [0.25] | 341.5x |
| users | cols3_where | NARROW ['"users"."id"'] | 0.12 / 2.31 / 0.16 [0.31] | 14.1x | 0.13 / 19.75 / 0.18 [0.37] | 106.8x |
| users | star | NARROW ['"users"."id"'] | 0.10 / 0.14 / 0.12 [0.23] | 1.2x | 0.11 / 0.14 / 0.12 [0.23] | 1.2x |
| votes | cols3 | NARROW ['"votes"."id"'] | 0.07 / 4.94 / 0.08 [0.19] | 60.2x | 0.08 / 29.29 / 0.09 [0.22] | 332.8x |
| votes | cols3_where | NARROW ['"votes"."id"'] | 0.76 / 1.95 / 1.39 [2.18] | 1.4x | 0.77 / 13.76 / 1.43 [2.24] | 9.7x |
| votes | star | NARROW ['"votes"."id"'] | 0.07 / 0.09 / 0.08 [0.19] | 1.1x | 0.08 / 0.10 / 0.09 [0.19] | 1.2x |

## B. Tool as implemented in the pilot (each policy's SQL fetched up to 100,000 rows; cert file v3)


### DuckDB, pilot tool (capped fetch)

Probes replayed: 1006; succeeding at sf1: 1006; failing with an error at a larger scale (excluded, cannot be timed): 18 [536, 550, 589, 602, 733, 734, 745, 746, 747, 748, 805, 807]...; missing: 0; with a timeout at some scale: 3 [193, 222, 604]. **Main set: 985 probes, identical at every scale.** Scales beyond sf1 are replicated-data stress tests.

| scale | set | n | raw s | smartlex s | certified s | certified vs smartlex (95% CI) | median per-probe S/C (95% CI) | largest single-probe share of S / C total | share of S-C from one probe |
|---|---|---|---|---|---|---|---|---|---|
| sf1 | main | 985 | 2.02 | 2.25 | 2.21 | +1.7% [+0.3, +3.5] | 1.002x [0.998, 1.004] | 2% / 3% | #149 32% |
| sf1 | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 14.87 | 15.09 | 15.12 | -0.2% [-0.4, +2.4] | 1.002x [0.998, 1.004] | 43% / 43% | n/a (difference < 0.5%) |
| x10 | main | 985 | 7.22 | 7.21 | 7.04 | +2.4% [-0.1, +5.3] | 1.003x [1.000, 1.006] | 3% / 3% | #235 36% |
| x10 | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 127.29 | 127.29 | 127.12 | +0.1% [-0.0, +3.5] | 1.003x [1.000, 1.006] | 47% / 47% | n/a (difference < 0.5%) |
| xmax | main | 985 | 37.42 | 32.46 | 32.95 | -1.5% [-6.1, +2.7] | 1.004x [1.001, 1.007] | 4% / 5% | #71 109% **(one probe)** |
| xmax | sensitivity: + timeouts at 60 s (lower bounds) | 988 | 157.64 | 212.46 | 212.95 | -0.2% [-1.9, +0.5] | 1.004x [1.001, 1.007] | 28% / 28% | n/a (difference < 0.5%) |

Per-probe smartlex/certified at xmax (main set, n=985): p10 0.94x, p25 0.98x, median 1.00x, p75 1.04x, p90 1.15x; certified >10% faster on 15% of probes, >10% slower on 5%.

LIMIT classes at xmax (main set):

| class | n | raw s | smartlex s | certified s | smartlex/certified (ratio of totals) | 95% CI | median per-probe S/C |
|---|---|---|---|---|---|---|---|
| L1: LIMIT/OFFSET, verdict != DET (predeclared class) | 176 | 6.94 | 8.65 | 9.12 | 0.95x | [0.84, 1.14] | 1.00x |
| L2: LIMIT without ORDER BY (syntactic) | 58 | 0.976 | 1.74 | 1.21 | 1.44x | [1.11, 2.13] | 1.01x |
| L3: LIMIT/OFFSET, verdict NARROW/ALL (repaired) | 148 | 4.70 | 6.39 | 6.86 | 0.93x | [0.82, 1.22] | 1.01x |

Leave-out at xmax (main set): certified vs smartlex -1.5%; without the largest contributor in that direction (#71) +0.1%; without the top 5 ([71, 113, 349, 428, 582]) +2.3%.

### PostgreSQL, pilot tool (capped fetch)

Probes replayed: 1006; succeeding at sf1: 989; failing with an error at a larger scale (excluded, cannot be timed): 18 [536, 550, 589, 602, 733, 734, 745, 746, 747, 748, 805, 807]...; missing: 0; with a timeout at some scale: 5 [115, 139, 193, 222, 582]. **Main set: 966 probes, identical at every scale.** Scales beyond sf1 are replicated-data stress tests.

| scale | set | n | raw s | smartlex s | certified s | certified vs smartlex (95% CI) | median per-probe S/C (95% CI) | largest single-probe share of S / C total | share of S-C from one probe |
|---|---|---|---|---|---|---|---|---|---|
| sf1 | main | 966 | 11.00 | 10.81 | 10.84 | -0.2% [-2.4, +1.3] | 1.001x [1.000, 1.002] | 3% / 3% | n/a (difference < 0.5%) |
| sf1 | sensitivity: + timeouts at 60 s (lower bounds) | 971 | 74.29 | 74.09 | 81.82 | -10.4% [-65.1, +0.1] | 1.001x [1.000, 1.002] | 35% / 33% | #139 90% **(one probe)** |
| x10 | main | 966 | 84.79 | 83.64 | 88.42 | -5.7% [-14.5, +1.1] | 1.000x [1.000, 1.001] | 4% / 7% | #450 59% **(one probe)** |
| x10 | sensitivity: + timeouts at 60 s (lower bounds) | 971 | 384.79 | 383.64 | 388.42 | -1.2% [-4.8, +0.3] | 1.000x [1.000, 1.001] | 16% / 15% | #450 59% **(one probe)** |

Per-probe smartlex/certified at x10 (main set, n=966): p10 0.98x, p25 1.00x, median 1.00x, p75 1.01x, p90 1.04x; certified >10% faster on 6% of probes, >10% slower on 2%.

LIMIT classes at x10 (main set):

| class | n | raw s | smartlex s | certified s | smartlex/certified (ratio of totals) | 95% CI | median per-probe S/C |
|---|---|---|---|---|---|---|---|
| L1: LIMIT/OFFSET, verdict != DET (predeclared class) | 171 | 21.53 | 20.73 | 25.62 | 0.81x | [0.65, 1.05] | 1.00x |
| L2: LIMIT without ORDER BY (syntactic) | 54 | 9.31 | 7.90 | 7.79 | 1.01x | [0.74, 1.57] | 1.03x |
| L3: LIMIT/OFFSET, verdict NARROW/ALL (repaired) | 143 | 12.96 | 12.01 | 16.92 | 0.71x | [0.54, 1.12] | 1.00x |

Leave-out at x10 (main set): certified vs smartlex -5.7%; without the largest contributor in that direction (#450) -2.4%; without the top 5 ([450, 49, 413, 330, 71]) +1.4%.

## Predeclared materiality bar (primary: A total, main set; secondary: A preview; B for reference)

- **DuckDB, total = preview + count**, xmax, main set (n=986): certified vs smartlex +4.2% (95% CI [-0.9, +10.2]) -> criterion 1 (>= 20% lower): **NOT MET**; sensitivity with timeouts at 60 s (n=988): +0.7% (largest single-probe share of the smartlex-certified difference 40%, #403). L1 (n=176): smartlex/certified 0.96x -> criterion 2 (>= 5x): **NOT MET**.
- **DuckDB, preview only**, xmax, main set (n=986): certified vs smartlex +7.1% (95% CI [-1.5, +16.9]) -> criterion 1 (>= 20% lower): **NOT MET**; sensitivity with timeouts at 60 s (n=988): +1.3% (largest single-probe share of the smartlex-certified difference 40%, #403). L1 (n=176): smartlex/certified 0.95x -> criterion 2 (>= 5x): **NOT MET**.
- **PostgreSQL, total = preview + count**, x10, main set (n=962): certified vs smartlex -86.1% (95% CI [-212.4, -8.5]) -> criterion 1 (>= 20% lower): **NOT MET**; sensitivity with timeouts at 60 s (n=970): -35.2% (largest single-probe share of the smartlex-certified difference -34%, #529). L1 (n=171): smartlex/certified 0.86x -> criterion 2 (>= 5x): **NOT MET**.
- **PostgreSQL, preview only**, x10, main set (n=962): certified vs smartlex -145.1% (95% CI [-383.7, -14.0]) -> criterion 1 (>= 20% lower): **NOT MET**; sensitivity with timeouts at 60 s (n=970): -25.9% (largest single-probe share of the smartlex-certified difference -53%, #582). L1 (n=171): smartlex/certified 0.76x -> criterion 2 (>= 5x): **NOT MET**.
- **DuckDB, pilot tool (capped fetch, v3)**, xmax, main set (n=985): certified vs smartlex -1.5% (95% CI [-6.1, +2.7]) -> criterion 1 (>= 20% lower): **NOT MET**; sensitivity with timeouts at 60 s (n=988): -0.2% (largest single-probe share of the smartlex-certified difference 109%, #71). L1 (n=176): smartlex/certified 0.95x -> criterion 2 (>= 5x): **NOT MET**.
- **PostgreSQL, pilot tool (capped fetch, v3)**, x10, main set (n=966): certified vs smartlex -5.7% (95% CI [-14.5, +1.1]) -> criterion 1 (>= 20% lower): **NOT MET**; sensitivity with timeouts at 60 s (n=971): -1.2% (largest single-probe share of the smartlex-certified difference 59%, #450). L1 (n=171): smartlex/certified 0.81x -> criterion 2 (>= 5x): **NOT MET**.
