# Judge validation

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
