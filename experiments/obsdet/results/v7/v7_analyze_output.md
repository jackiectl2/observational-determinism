### E4 v7 on tasks_v2 (E4 original tasks) (runs e4_v7_qwen3_8b, e4_v7_phi4)

| Group | Qwen3-8B traj / final SQL / result / correctness | phi-4 traj / final SQL / result / correctness |
|---|---|---|
| raw, 3 physical orders | 61 / 57 / 43 / 16 | 31 / 27 / 17 (cens. 1) / 4 |
| smart-lex, 3 physical orders | 5 / 5 / 5 / 0 | 1 / 1 / 1 / 0 |
| hybrid (certified), 3 physical orders | 6 / 6 / 5 / 1 | 1 / 1 / 1 / 0 |
| strict (fail-closed), 3 physical orders | 2 / 2 / 1 / 0 | 0 / 0 / 0 / 0 |
| raw, 1 vs 8 threads | 23 / 21 / 11 / 1 | 8 / 7 / 6 / 0 |
| hybrid, 1 vs 8 threads | 2 / 2 / 2 / 0 | 1 / 1 / 1 / 0 |
| strict, 1 vs 8 threads | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

| Group | Qwen3-8B unattributed; same-SQL observation-change sources | phi-4 unattributed; same-SQL observation-change sources |
|---|---|---|
| raw, 3 physical orders | 0/150; {"raw": 70, "runtime-error": 2} | 0/150; {"raw": 55} |
| smart-lex, 3 physical orders | 0/150; {"smartlex": 8, "runtime-error": 2} | 0/150; {"smartlex": 8} |
| hybrid (certified), 3 physical orders | 0/150; {"UNSUPPORTED": 7, "runtime-error": 2} | 0/150; {"UNSUPPORTED": 8} |
| strict (fail-closed), 3 physical orders | 0/150; {"runtime-error": 2} | 0/150; {} |
| raw, 1 vs 8 threads | 0/150; {"raw": 35} | 0/150; {"raw": 22} |
| hybrid, 1 vs 8 threads | 0/150; {"runtime-error": 1, "UNSUPPORTED": 3} | 0/150; {"UNSUPPORTED": 4} |
| strict, 1 vs 8 threads | 0/150; {} | 0/150; {} |

| Accuracy, set (bag) | Qwen3-8B | phi-4 |
|---|---|---|
| raw (4 conditions) | 0.507–0.533 (0.480–0.513) | 0.433–0.453 (0.433–0.447) |
| smart-lex (3) | 0.533 (0.507) | 0.440 (0.433) |
| hybrid (4) | 0.513–0.520 (0.487–0.493) | 0.453 (0.447) |
| strict (4) | 0.547 (0.513) | 0.413 (0.400) |

| Paired difference (3 physical orders), 95% task-clustered bootstrap CI | Qwen3-8B | phi-4 |
|---|---|---|
| cer-raw | -0.9 pp [-4.2, +2.2] | +0.9 pp [-0.2, +2.4] |
| slx-raw | +0.9 pp [-2.9, +4.9] | -0.4 pp [-2.2, +1.1] |
| cer-slx | -1.8 pp [-4.7, +0.7] | +1.3 pp [+0.0, +3.3] |
| str-raw | +2.2 pp [-1.8, +6.2] | -3.1 pp [-6.9, -0.0] |
| str-cer | +3.1 pp [+0.0, +6.4] | -4.0 pp [-7.3, -1.3] |

- Qwen3-8B: statements under hybrid/strict by verdict {"cer": {"UNSUPPORTED": 625, "NARROW": 768, "ALL": 380, "DET": 613}, "str": {"UNSUPPORTED": 181, "NARROW": 864, "ALL": 400, "DET": 769, "UNSUPPORTED/refused": 596}}
- Qwen3-8B: strict burden (strict_burden.py): 66/150 tasks with >=1 withheld preview; median 1.5 (max 6) among them; hybrid-correct -> strict-wrong 1, hybrid-wrong -> strict-correct 5
- Qwen3-8B: same-SQL observation changes from CERTIFIED statements: 0
- phi-4: statements under hybrid/strict by verdict {"cer": {"UNSUPPORTED": 507, "NARROW": 556, "ALL": 256, "DET": 388}, "str": {"UNSUPPORTED": 152, "NARROW": 652, "ALL": 316, "UNSUPPORTED/refused": 624, "DET": 512}}
- phi-4: strict burden (strict_burden.py): 57/150 tasks with >=1 withheld preview; median 2 (max 8) among them; hybrid-correct -> strict-wrong 6, hybrid-wrong -> strict-correct 0
- phi-4: same-SQL observation changes from CERTIFIED statements: 0

### E4 v7 on tasks_v3 (first task-disjoint set) (runs e4_v7td_qwen3_8b, e4_v7td_phi4)

| Group | Qwen3-8B traj / final SQL / result / correctness | phi-4 traj / final SQL / result / correctness |
|---|---|---|
| raw, 3 physical orders | 53 / 49 / 29 / 13 | 38 / 30 / 17 (cens. 1) / 8 |
| smart-lex, 3 physical orders | 4 / 4 / 4 / 1 | 1 / 1 / 0 (cens. 1) / 0 |
| hybrid (certified), 3 physical orders | 3 / 3 / 4 / 1 | 2 / 1 / 0 (cens. 1) / 0 |
| strict (fail-closed), 3 physical orders | 2 / 2 / 2 / 0 | 0 / 0 / 0 (cens. 1) / 0 |
| raw, 1 vs 8 threads | 32 / 28 / 13 / 6 | 10 / 6 / 5 (cens. 1) / 2 |
| hybrid, 1 vs 8 threads | 1 / 1 / 1 / 1 | 0 / 0 / 0 (cens. 1) / 0 |
| strict, 1 vs 8 threads | 0 / 0 / 0 / 0 | 0 / 0 / 0 (cens. 1) / 0 |

| Group | Qwen3-8B unattributed; same-SQL observation-change sources | phi-4 unattributed; same-SQL observation-change sources |
|---|---|---|
| raw, 3 physical orders | 0/150; {"raw": 69, "runtime-error": 2} | 0/150; {"raw": 57} |
| smart-lex, 3 physical orders | 0/150; {"smartlex": 7, "runtime-error": 3} | 0/150; {"smartlex": 3} |
| hybrid (certified), 3 physical orders | 0/150; {"UNSUPPORTED": 5, "runtime-error": 2} | 0/150; {"UNSUPPORTED": 3} |
| strict (fail-closed), 3 physical orders | 0/150; {"runtime-error": 2} | 0/150; {} |
| raw, 1 vs 8 threads | 0/150; {"raw": 38, "runtime-error": 1} | 0/150; {"raw": 20} |
| hybrid, 1 vs 8 threads | 0/150; {"runtime-error": 1} | 0/150; {} |
| strict, 1 vs 8 threads | 0/150; {} | 0/150; {} |

| Accuracy, set (bag) | Qwen3-8B | phi-4 |
|---|---|---|
| raw (4 conditions) | 0.613–0.660 (0.587–0.627) | 0.447–0.467 (0.407–0.433) |
| smart-lex (3) | 0.647–0.653 (0.607–0.613) | 0.453 (0.413) |
| hybrid (4) | 0.660–0.667 (0.627–0.633) | 0.467 (0.427) |
| strict (4) | 0.653 (0.620) | 0.400 (0.360) |

| Paired difference (3 physical orders), 95% task-clustered bootstrap CI | Qwen3-8B | phi-4 |
|---|---|---|
| cer-raw | +3.1 pp [+0.7, +6.2] | +1.3 pp [-0.9, +3.8] |
| slx-raw | +1.8 pp [-0.9, +4.7] | -0.0 pp [-2.9, +2.7] |
| cer-slx | +1.3 pp [+0.0, +3.3] | +1.3 pp [+0.0, +3.3] |
| str-raw | +2.2 pp [-1.1, +6.0] | -5.3 pp [-9.6, -1.1] |
| str-cer | -0.9 pp [-3.3, +1.3] | -6.7 pp [-10.7, -2.7] |

- Qwen3-8B: statements under hybrid/strict by verdict {"cer": {"NARROW": 784, "DET": 549, "UNSUPPORTED": 509, "ALL": 424}, "str": {"NARROW": 849, "DET": 723, "UNSUPPORTED": 180, "ALL": 440, "UNSUPPORTED/refused": 420}}
- Qwen3-8B: strict burden (strict_burden.py): 57/150 tasks with >=1 withheld preview; median 1 (max 5) among them; hybrid-correct -> strict-wrong 2, hybrid-wrong -> strict-correct 1
- Qwen3-8B: same-SQL observation changes from CERTIFIED statements: 0
- phi-4: statements under hybrid/strict by verdict {"cer": {"NARROW": 536, "UNSUPPORTED": 322, "ALL": 320, "DET": 400}, "str": {"NARROW": 604, "UNSUPPORTED": 84, "ALL": 356, "DET": 456, "UNSUPPORTED/refused": 432}}
- phi-4: strict burden (strict_burden.py): 42/150 tasks with >=1 withheld preview; median 1.0 (max 8) among them; hybrid-correct -> strict-wrong 10, hybrid-wrong -> strict-correct 0
- phi-4: same-SQL observation changes from CERTIFIED statements: 0

### E4 v7 on tasks_v4 (second task-disjoint set) (runs e4_v7td2_qwen3_8b, e4_v7td2_phi4)

| Group | Qwen3-8B traj / final SQL / result / correctness | phi-4 traj / final SQL / result / correctness |
|---|---|---|
| raw, 3 physical orders | 52 / 42 / 28 (cens. 2) / 8 | 23 / 23 / 15 (cens. 1) / 4 |
| smart-lex, 3 physical orders | 2 / 2 / 2 (cens. 2) / 0 | 0 / 0 / 0 (cens. 1) / 0 |
| hybrid (certified), 3 physical orders | 3 / 3 / 4 (cens. 2) / 1 | 0 / 0 / 0 (cens. 1) / 0 |
| strict (fail-closed), 3 physical orders | 1 / 1 / 1 (cens. 2) / 0 | 1 / 1 / 0 (cens. 1) / 0 |
| raw, 1 vs 8 threads | 21 / 16 / 9 (cens. 1) / 0 | 6 / 5 / 2 (cens. 1) / 1 |
| hybrid, 1 vs 8 threads | 0 / 0 / 0 (cens. 2) / 0 | 0 / 0 / 0 (cens. 1) / 0 |
| strict, 1 vs 8 threads | 0 / 0 / 0 (cens. 2) / 0 | 0 / 0 / 0 (cens. 1) / 0 |

| Group | Qwen3-8B unattributed; same-SQL observation-change sources | phi-4 unattributed; same-SQL observation-change sources |
|---|---|---|
| raw, 3 physical orders | 0/150; {"raw": 68} | 0/150; {"raw": 53} |
| smart-lex, 3 physical orders | 0/150; {"runtime-error": 1, "smartlex": 3} | 0/150; {"runtime-error": 1, "smartlex": 3} |
| hybrid (certified), 3 physical orders | 0/150; {"UNSUPPORTED": 4, "runtime-error": 1} | 0/150; {"runtime-error": 1, "UNSUPPORTED": 3} |
| strict (fail-closed), 3 physical orders | 0/150; {"runtime-error": 1} | 0/150; {"runtime-error": 1} |
| raw, 1 vs 8 threads | 0/150; {"raw": 33} | 0/150; {"raw": 17} |
| hybrid, 1 vs 8 threads | 0/150; {"UNSUPPORTED": 1} | 0/150; {"UNSUPPORTED": 2} |
| strict, 1 vs 8 threads | 0/150; {} | 0/150; {} |

| Accuracy, set (bag) | Qwen3-8B | phi-4 |
|---|---|---|
| raw (4 conditions) | 0.420–0.447 (0.393–0.440) | 0.413–0.427 (0.393–0.407) |
| smart-lex (3) | 0.440 (0.427) | 0.420 (0.407) |
| hybrid (4) | 0.440–0.447 (0.440–0.447) | 0.420 (0.400) |
| strict (4) | 0.407 (0.400) | 0.387 (0.373) |

| Paired difference (3 physical orders), 95% task-clustered bootstrap CI | Qwen3-8B | phi-4 |
|---|---|---|
| cer-raw | +0.9 pp [-2.0, +3.8] | +0.0 pp [-1.3, +1.3] |
| slx-raw | +0.4 pp [-2.7, +3.6] | +0.0 pp [-1.3, +1.3] |
| cer-slx | +0.4 pp [+0.0, +1.3] | +0.0 pp [+0.0, +0.0] |
| str-raw | -2.9 pp [-7.3, +1.3] | -3.3 pp [-6.7, -0.4] |
| str-cer | -3.8 pp [-7.6, -0.4] | -3.3 pp [-6.7, -0.7] |

- Qwen3-8B: statements under hybrid/strict by verdict {"cer": {"NARROW": 865, "UNSUPPORTED": 543, "ALL": 464, "DET": 624}, "str": {"NARROW": 917, "UNSUPPORTED": 248, "ALL": 476, "DET": 720, "UNSUPPORTED/refused": 503}}
- Qwen3-8B: strict burden (strict_burden.py): 59/150 tasks with >=1 withheld preview; median 1 (max 7) among them; hybrid-correct -> strict-wrong 7, hybrid-wrong -> strict-correct 1
- Qwen3-8B: same-SQL observation changes from CERTIFIED statements: 0
- phi-4: statements under hybrid/strict by verdict {"cer": {"NARROW": 488, "UNSUPPORTED": 420, "ALL": 268, "DET": 412}, "str": {"NARROW": 596, "UNSUPPORTED": 172, "ALL": 276, "UNSUPPORTED/refused": 552, "DET": 504}}
- phi-4: strict burden (strict_burden.py): 55/150 tasks with >=1 withheld preview; median 1 (max 8) among them; hybrid-correct -> strict-wrong 5, hybrid-wrong -> strict-correct 0
- phi-4: same-SQL observation changes from CERTIFIED statements: 0

### Development probes (`cert_probes_v7.jsonl`)

Verdicts (1015): DET 166 (16.4%), NARROW 511 (50.3%), ALL 177 (17.4%), UNSUPPORTED 161 (15.9%)
Repaired 688: mean appended sort columns 1.22 vs smart-lex 2.96; key tie-breaks 464 (non-output key 307)
UNSUPPORTED reasons: {"derived-table": 64, "float-aggregate": 48, "unresolved": 18, "multi-statement": 7, "outer-or-special-join": 6, "nested-limit": 6, "cte": 4, "not-select": 3, "inexact-group-key": 2, "no-base-table": 2, "distinct-order-by-non-output": 1}
No-keys ablation: DET 129, NARROW 296, ALL 429, UNSUPPORTED 161; mean width 2.48

duckdb: statements in file and keep set 1015 of 1015; row() = {"sup": 854, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 378, "uns": 161, "uns_cens": 0, "uns_raw": 69, "uns_slx": 39}
```
duckdb: policy x verdict diverged / complete (censored)
  raw      DET=0/166(0) NARROW=266/511(0) ALL=112/177(0) UNSUPPORTED=69/161(0)
  smartlex DET=0/166(0) NARROW=0/511(0) ALL=0/177(0) UNSUPPORTED=39/161(0)
  certifiedDET=0/166(0) NARROW=0/511(0) ALL=0/177(0) UNSUPPORTED=39/161(0)
```
postgres: statements in file and keep set 1015 of 1015; row() = {"sup": 836, "sup_cens": 17, "cer": 0, "slx": 0, "raw": 285, "uns": 157, "uns_cens": 5, "uns_raw": 51, "uns_slx": 32}
```
postgres: policy x verdict diverged / complete (censored)
  raw      DET=0/155(11) NARROW=228/509(3) ALL=57/172(3) UNSUPPORTED=51/157(5)
  smartlex DET=0/155(11) NARROW=0/509(3) ALL=0/172(3) UNSUPPORTED=32/157(5)
  certifiedDET=0/155(11) NARROW=0/509(3) ALL=0/172(3) UNSUPPORTED=32/157(5)
```

### First held-out (`cert_heldout_kept_v7.jsonl`)

Verdicts (1125): DET 189 (16.8%), NARROW 383 (34.0%), ALL 204 (18.1%), UNSUPPORTED 349 (31.0%)
Repaired 587: mean appended sort columns 1.11 vs smart-lex 2.3; key tie-breaks 400 (non-output key 230)
UNSUPPORTED reasons: {"derived-table": 133, "no-base-table": 85, "float-aggregate": 41, "cte": 34, "outer-or-special-join": 16, "not-select": 14, "volatile": 6, "multi-statement": 5, "construct": 5, "unresolved": 4, "nested-limit": 2, "function": 2, "aggregate": 1, "distinct-order-by-non-output": 1}
No-keys ablation: DET 153, NARROW 205, ALL 418, UNSUPPORTED 349; mean width 1.87

duckdb: statements in file and keep set 1125 of 1125; row() = {"sup": 776, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 292, "uns": 349, "uns_cens": 0, "uns_raw": 134, "uns_slx": 66}
```
duckdb: policy x verdict diverged / complete (censored)
  raw      DET=0/189(0) NARROW=178/383(0) ALL=114/204(0) UNSUPPORTED=134/349(0)
  smartlex DET=0/189(0) NARROW=0/383(0) ALL=0/204(0) UNSUPPORTED=66/349(0)
  certifiedDET=0/189(0) NARROW=0/383(0) ALL=0/204(0) UNSUPPORTED=65/349(0)
```
postgres: statements in file and keep set 1125 of 1125; row() = {"sup": 759, "sup_cens": 10, "cer": 0, "slx": 0, "raw": 237, "uns": 346, "uns_cens": 10, "uns_raw": 77, "uns_slx": 42}
```
postgres: policy x verdict diverged / complete (censored)
  raw      DET=0/183(2) NARROW=155/373(8) ALL=82/203(0) UNSUPPORTED=77/346(10)
  smartlex DET=0/183(2) NARROW=0/373(8) ALL=0/203(0) UNSUPPORTED=42/346(10)
  certifiedDET=0/183(2) NARROW=0/373(8) ALL=0/203(0) UNSUPPORTED=42/346(10)
```

### First task-disjoint (`cert_td_new_v7.jsonl`)

Verdicts (1321): DET 313 (23.7%), NARROW 471 (35.7%), ALL 215 (16.3%), UNSUPPORTED 322 (24.4%)
Repaired 686: mean appended sort columns 1.12 vs smart-lex 2.5; key tie-breaks 430 (non-output key 262)
UNSUPPORTED reasons: {"derived-table": 123, "no-base-table": 85, "cte": 43, "float-aggregate": 37, "nested-limit": 9, "outer-or-special-join": 8, "unresolved": 6, "not-select": 5, "multi-statement": 2, "function": 2, "distinct-order-by-non-output": 2}
No-keys ablation: DET 244, NARROW 220, ALL 535, UNSUPPORTED 322; mean width 2.05

duckdb: statements in file and keep set 1321 of 1321; row() = {"sup": 999, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 394, "uns": 322, "uns_cens": 0, "uns_raw": 92, "uns_slx": 44}
```
duckdb: policy x verdict diverged / complete (censored)
  raw      DET=0/313(0) NARROW=259/471(0) ALL=135/215(0) UNSUPPORTED=92/322(0)
  smartlex DET=0/313(0) NARROW=0/471(0) ALL=0/215(0) UNSUPPORTED=44/322(0)
  certifiedDET=0/313(0) NARROW=0/471(0) ALL=0/215(0) UNSUPPORTED=44/322(0)
```
postgres: statements in file and keep set 1321 of 1321; row() = {"sup": 978, "sup_cens": 16, "cer": 0, "slx": 0, "raw": 301, "uns": 295, "uns_cens": 32, "uns_raw": 61, "uns_slx": 32}
```
postgres: policy x verdict diverged / complete (censored)
  raw      DET=0/304(4) NARROW=221/462(9) ALL=80/213(2) UNSUPPORTED=61/295(32)
  smartlex DET=0/304(4) NARROW=0/461(10) ALL=0/213(2) UNSUPPORTED=32/295(32)
  certifiedDET=0/304(4) NARROW=0/461(10) ALL=0/213(2) UNSUPPORTED=32/295(32)
```

### Second task-disjoint (clean test) (`cert_td2_new.jsonl`)

Verdicts (1267): DET 269 (21.2%), NARROW 457 (36.1%), ALL 219 (17.3%), UNSUPPORTED 322 (25.4%)
Repaired 676: mean appended sort columns 1.11 vs smart-lex 2.58; key tie-breaks 465 (non-output key 277)
UNSUPPORTED reasons: {"derived-table": 118, "no-base-table": 80, "cte": 30, "float-aggregate": 24, "construct": 15, "outer-or-special-join": 13, "unresolved": 12, "not-select": 9, "function": 9, "multi-statement": 3, "nested-limit": 3, "distinct-order-by-non-output": 2, "inexact-group-key": 2, "unknown-table": 2}
No-keys ablation: DET 205, NARROW 211, ALL 529, UNSUPPORTED 322; mean width 2.16

duckdb: statements in file and keep set 1267 of 1267; row() = {"sup": 945, "sup_cens": 0, "cer": 0, "slx": 0, "raw": 344, "uns": 322, "uns_cens": 0, "uns_raw": 79, "uns_slx": 31}
```
duckdb: policy x verdict diverged / complete (censored)
  raw      DET=0/269(0) NARROW=224/457(0) ALL=120/219(0) UNSUPPORTED=79/322(0)
  smartlex DET=0/269(0) NARROW=0/457(0) ALL=0/219(0) UNSUPPORTED=31/322(0)
  certifiedDET=0/269(0) NARROW=0/457(0) ALL=0/219(0) UNSUPPORTED=31/322(0)
```
postgres: statements in file and keep set 1267 of 1267; row() = {"sup": 930, "sup_cens": 9, "cer": 0, "slx": 0, "raw": 276, "uns": 302, "uns_cens": 26, "uns_raw": 58, "uns_slx": 24}
```
postgres: policy x verdict diverged / complete (censored)
  raw      DET=0/267(2) NARROW=201/451(2) ALL=75/212(5) UNSUPPORTED=58/302(26)
  smartlex DET=0/267(2) NARROW=0/451(2) ALL=0/212(5) UNSUPPORTED=24/302(26)
  certifiedDET=0/267(2) NARROW=0/451(2) ALL=0/212(5) UNSUPPORTED=23/302(26)
```

