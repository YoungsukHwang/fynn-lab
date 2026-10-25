# Judge validation

Human labels on 18 of 32 sampled replies (0 more partly labeled), 13 of them drawn at random. Agreement is fact by fact, on PRESENT against not PRESENT. The original judge is scored on every labeled random reply, any other judge on the ones it graded, with the original judge on those same replies next to it. The interval resamples replies; the weighted rate undoes the stratified draw.

## Judges against the human labels

| Judge | Replies | Facts | Agree | 95% interval | Weighted | Kappa | Stricter | More lenient | Replies agree | Original judge, same replies |
|---|---|---|---|---|---|---|---|---|---|---|
| original (claude-opus-5-5) | 13 | 48 | 92% | 86% to 98% | 94% | 0.62 | 4 | 0 | 9 of 13 |  |
| claude-haiku-5-5 | 13 | 48 | 96% | 90% to 100% | 97% | 0.78 | 2 | 0 | 11 of 13 | 92% (weighted 94%) |
| claude-opus-5-5 (again) | 13 | 48 | 92% | 86% to 98% | 94% | 0.62 | 4 | 0 | 9 of 13 | 92% (weighted 94%) |
| claude-sonnet-5-5 | 13 | 48 | 92% | 85% to 98% | 93% | 0.62 | 4 | 0 | 9 of 13 | 92% (weighted 94%) |

Stricter: the judge failed a fact the human passed. More lenient: the reverse.

## By answering model

| Judge | Source | Facts | Agree | Stricter | More lenient |
|---|---|---|---|---|---|
| original (claude-opus-5-5) | after-haiku | 17 | 94% | 1 | 0 |
| original (claude-opus-5-5) | after-opus | 11 | 82% | 2 | 0 |
| original (claude-opus-5-5) | after-sonnet | 20 | 95% | 1 | 0 |
| claude-haiku-5-5 | after-haiku | 17 | 94% | 1 | 0 |
| claude-haiku-5-5 | after-opus | 11 | 91% | 1 | 0 |
| claude-haiku-5-5 | after-sonnet | 20 | 100% | 0 | 0 |
| claude-opus-5-5 (again) | after-haiku | 17 | 94% | 1 | 0 |
| claude-opus-5-5 (again) | after-opus | 11 | 82% | 2 | 0 |
| claude-opus-5-5 (again) | after-sonnet | 20 | 95% | 1 | 0 |
| claude-sonnet-5-5 | after-haiku | 17 | 88% | 2 | 0 |
| claude-sonnet-5-5 | after-opus | 11 | 82% | 2 | 0 |
| claude-sonnet-5-5 | after-sonnet | 20 | 100% | 0 | 0 |

## Targeted replies

| Item | Source | Case | Fact | Human | original (claude-opus-5-5) | claude-haiku-5-5 | claude-opus-5-5 (again) | claude-sonnet-5-5 |
|---|---|---|---|---|---|---|---|---|
| R01 | after-opus | mi-026 | F1 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R01 | after-opus | mi-026 | F2 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R01 | after-opus | mi-026 | F3 | PRESENT | PRESENT | ABSENT | PRESENT | ABSENT |
| R01 | after-opus | mi-026 | F4 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R01 | after-opus | mi-026 | F5 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R05 | after-sonnet | mi-023 | F1 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R05 | after-sonnet | mi-023 | F2 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R05 | after-sonnet | mi-023 | F3 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R05 | after-sonnet | mi-023 | F4 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R05 | after-sonnet | mi-023 | F5 | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| R10 | after-opus | mi-023 | F1 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R10 | after-opus | mi-023 | F2 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R10 | after-opus | mi-023 | F3 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R10 | after-opus | mi-023 | F4 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R10 | after-opus | mi-023 | F5 | ABSENT | PRESENT | ABSENT | ABSENT | ABSENT |
| R17 | after-haiku | mi-026 | F1 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R17 | after-haiku | mi-026 | F2 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R17 | after-haiku | mi-026 | F3 | PRESENT | ABSENT | PRESENT | PRESENT | ABSENT |
| R17 | after-haiku | mi-026 | F4 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R17 | after-haiku | mi-026 | F5 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R18 | after-opus | st-001 | F1 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R18 | after-opus | st-001 | F2 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |
| R18 | after-opus | st-001 | F3 | PRESENT | PRESENT | ABSENT | PRESENT | PRESENT |
| R18 | after-opus | st-001 | F4 | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| R18 | after-opus | st-001 | F5 | PRESENT | PRESENT | PRESENT | PRESENT | PRESENT |

## Regrades against the original judge, every reply

| Regrade | Source | Replies | Fact agreement | 95% interval | Kappa | Stricter | More lenient | Passes (original, regrade) |
|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | after-haiku | 64 | 95% | 92% to 98% | 0.79 | 3 | 10 | 34, 37 |
| claude-haiku-5-5 | after-opus | 64 | 97% | 95% to 99% | 0.76 | 4 | 4 | 46, 47 |
| claude-haiku-5-5 | after-sonnet | 64 | 98% | 96% to 99% | 0.82 | 2 | 4 | 47, 50 |
| claude-opus-5-5 (again) | after-haiku | 64 | 99% | 97% to 100% | 0.96 | 2 | 1 | 34, 35 |
| claude-opus-5-5 (again) | after-opus | 64 | 98% | 97% to 100% | 0.87 | 1 | 3 | 46, 48 |
| claude-opus-5-5 (again) | after-sonnet | 64 | 99% | 98% to 100% | 0.94 | 0 | 2 | 47, 48 |
| claude-sonnet-5-5 | after-haiku | 64 | 95% | 92% to 97% | 0.81 | 8 | 5 | 34, 31 |
| claude-sonnet-5-5 | after-opus | 64 | 96% | 94% to 98% | 0.72 | 6 | 4 | 46, 45 |
| claude-sonnet-5-5 | after-sonnet | 64 | 96% | 94% to 98% | 0.74 | 7 | 3 | 47, 46 |

Stricter: the regrade failed a fact the original judge passed.
