---
name: utilization
description: >-
  Explains revolving credit utilization: card balances divided by credit limits, overall and per card, which balance gets reported, and how to lower it. Use when the user asks about utilization or "credit usage", how much of a limit to use, high card balances, whether to pay off a card, paying before the statement date, why a balance shows even though they pay in full, or whether a loan balance counts. Also use when the user asks how to raise a score quickly by paying down cards, or asks why their score dropped ("why did my score drop", "my score went down", "I lost 20 points"), since a higher reported balance is a common cause of a drop.
type: topic
domain: score-and-reports
---
## Facts
- Utilization is revolving balances divided by revolving credit limits. Scoring models look at the overall ratio and at each card's own ratio.
- Amounts owed, which includes utilization, is about 30% of a FICO score.
- Issuers usually report the statement balance, not the balance on the due date. A user who pays in full every month can still show utilization.
- Paying down a card before the statement closing date lowers the balance that gets reported.
- Common guidance: keep utilization under 30%, and under 10% tends to be better. Forcing 0% on every card brings no real benefit.
- FICO 8 and most scores in use look only at the currently reported balances. Trended-data models (FICO 10T, and VantageScore 4.0 when trended data is used) also look at up to 24 months of balance history.
- Installment loans (auto, student, personal, the app's Credit Builder plan) are not part of revolving utilization.
- Closing a card or having a limit lowered removes available credit and can raise utilization.

## How to answer
- State `credit.utilization` when present and compare it to the 30% and 10% guidance. If the profile lists card balances and limits, compute per-card ratios for open cards only (closed or charged-off accounts are not in credit.utilization) and flag any open card that is high on its own.
- Give concrete levers: pay before the statement date, pay more than once a month, spread balances, keep old no-fee cards open.
- If `products.secured_card` is present, its statement balance counts here (card details belong to secured-card).
- Under most current models, high utilization stops weighing on the score once a lower balance is reported, usually after the next statement; the overall score still depends on everything else reported.
- A limit increase lowers the ratio, but some issuers do a hard inquiry for it; suggest asking first.

## Do not
- Tell the user to carry a balance or pay interest to build credit.
- Promise or estimate any point gain (number or range) from lowering utilization, or say the score will rise.
- Claim past high utilization keeps hurting a FICO 8 score after lower balances report.
