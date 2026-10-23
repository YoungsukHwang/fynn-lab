# Answer model and judge

## Answer models

| Answer model | Passed | Needs a second domain | One domain | Facts present | Median words | Over 250 | Cost per 1,000 (answer + router) |
|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | 34 of 64 | 16 of 33 | 18 of 31 | 223 of 262 | 228.0 | 25 | $0.81 ($0.49 + $0.32) |
| claude-sonnet-5-5 | 47 of 64 | 22 of 33 | 25 of 31 | 243 of 262 | 272.5 | 44 | $9.53 ($9.22 + $0.32) |
| claude-opus-5-5 | 46 of 64 | 21 of 33 | 25 of 31 | 244 of 262 | 266.0 | 42 | $22.10 ($21.78 + $0.32) |

Paired, exact McNemar (up: only the second passes):

- after-haiku to after-sonnet: 17 up, 4 down, p = 0.0072; if replies over 300 words fail: 12 up, 5 down, p = 0.1435
- after-sonnet to after-opus: 7 up, 8 down, p = 1.0; if replies over 300 words fail: 9 up, 5 down, p = 0.424
- after-haiku to after-opus: 19 up, 7 down, p = 0.029; if replies over 300 words fail: 15 up, 4 down, p = 0.0192

## Judges regrading the same replies

| Judge | Replies | Fact agreement with the run's judge | Verdicts changed | Cost per 64-reply run |
|---|---|---|---|---|
| claude-haiku-5-5 | 192 | 96.6% | 17 | $0.04 |
| claude-opus-5-5 (again) | 192 | 98.9% | 6 | $1.16 |
| claude-sonnet-5-5 | 192 | 95.8% | 17 | $0.50 |
