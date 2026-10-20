---
name: collections
description: >-
  Covers collection accounts on credit reports: how long they stay, what paying does and does not change, medical collection rules, how scoring models treat paid collections, disputing a collection entry that is wrong or not theirs, requesting debt validation from a collector, and state statutes of limitations for lawsuits. Use when the user mentions a collection, a collection agency or debt collector contacting them, an old or unrecognized debt, a medical bill on their report, whether to pay a collection, "pay for delete", when a collection will fall off, or being sued or threatened with a lawsuit over a debt. Not for negotiating to pay less through the app's service (debt-settlement).
type: topic
domain: debt-and-collections
---
## Facts
- A collection can stay on reports up to 7 years from the original date of first delinquency; neither payment nor resale to another collector restarts that clock.
- Paying a non-medical collection does not remove it; it shows as paid.
- For medical collections, the three bureaus remove paid ones, skip those under $500, and wait a year before reporting unpaid ones.
- FICO 9, FICO 10 and VantageScore 3.0 and 4.0 ignore paid collections. FICO 8 counts them unless the original balance was under $100.
- A collector's validation notice lists the creditor, itemized balance and validation period end date (30 days after the user receives it). If the user disputes in writing within that period, the collector must stop collecting the disputed amount until it sends verification of the debt or a copy of a judgment.
- The statute of limitations is a separate state deadline for suing over a debt, commonly 3 to 6 years. In many states a partial payment or written promise to pay can restart it. Once it expires, collectors in most states may still ask for payment but cannot sue or threaten to sue. If sued anyway, the user usually must raise the expired deadline in court.

## How to answer
- Use the collection entries in credit.negative_items (balance, medical, original_delinquency, paid); estimate drop-off as original_delinquency plus 7 years.
- "Should I pay it?": give that account's trade-offs and let the user decide.
- Unrecognized debt or wrong amount: suggest requesting validation and disputing the entry with the bureau (process: see payment-history).
- Old debt: before any payment or written promise to pay, flag the restart risk, suggest a legal aid office or attorney to check the state deadline, and let the user decide.
- Lawsuits or court papers: say not to ignore them, since missing the response deadline can lead to a default judgment, and suggest promptly contacting an attorney or local legal aid office.

## Do not
- Promise deletion after payment, including "pay for delete".
- Say the debt is no longer owed once it leaves the report or becomes time-barred.
- Say whether a debt is time-barred or what the state deadline is.
