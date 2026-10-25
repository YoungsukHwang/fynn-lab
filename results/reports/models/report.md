# Answer model and judge

## Answer models

| Answer model | Passing runs | Needs a second domain | One domain | Facts present | Same-prompt flip rate | Median words | Over 250 | Cost per 1,000 replies, warm cache (answer + router) |
|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | 129 of 192 | 63 of 99 | 66 of 93 | 711 of 786 | 27% | 238.0 | 84 | $0.82 ($0.50 + $0.32) |
| claude-sonnet-5-5 | 165 of 192 | 78 of 99 | 87 of 93 | 757 of 786 | 10% | 270.5 | 128 | $9.57 ($9.25 + $0.32) |
| claude-opus-5-5 | 174 of 192 | 85 of 99 | 89 of 93 | 767 of 786 | 10% | 269.0 | 141 | $23.49 ($23.17 + $0.32) |

Paired by case (up: the second passes more often):

- after-haiku to after (run_permutation): 31 up, 6 down, p < 0.001
- after to after-opus (run_permutation): 8 up, 6 down, p = 0.0988
- after-haiku to after-opus (run_permutation): 30 up, 3 down, p < 0.001

Passing runs if replies over a cutoff counted as failures (the rules say about 250 words; nothing grades it):

| Cutoff | after-haiku | after | after-opus |
|---|---|---|---|
| 200 words | 50 | 25 | 16 |
| 250 words | 79 | 58 | 50 |
| 300 words | 102 | 137 | 161 |
| 350 words | 121 | 164 | 173 |

## Judges regrading the same replies

| Judge | Replies | Fact agreement with the run's judge | Verdicts changed | Cost per 64-reply run |
|---|---|---|---|---|
| claude-haiku-5-5 | 192 | 96.6% | 17 | $0.04 |
| claude-opus-5-5 (again) | 192 | 98.9% | 6 | $1.16 |
| claude-sonnet-5-5 | 192 | 95.8% | 17 | $0.50 |
