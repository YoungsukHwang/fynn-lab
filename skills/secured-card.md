---
name: secured-card
description: >-
  Covers the Secured Card: the refundable $50 to $2,000 deposit that sets the limit, APR and fees, the shipping and delivery timeline, what to do when the card has not arrived, activation, how the statement balance is reported, and the upgrade review after 8 on-time payments. Use when the user asks where their card is, when it will arrive, about a card that never came, activating it, a card not working at checkout, the deposit or limit, interest or fees, when the card balance gets reported, or getting the deposit back or moving to an unsecured card. Not for third-party card offers (marketplace-offers) or the Credit Builder plan (credit-builder-account).
type: topic
domain: credit-products
---
## Facts
- Refundable deposit of $50 to $2,000; the credit limit equals the deposit.
- No hard inquiry to apply, and no annual fee. Variable APR of 27.99%, charged on balances carried month to month.
- The card ships 1 to 2 business days after approval. Delivery takes 7 to 10 business days after shipping.
- If the card has not arrived 10 business days after shipping, the user can request a replacement in the app: Card > Report not received.
- The card must be activated in the app before first use.
- The statement balance and payment status are reported monthly to Equifax, Experian and TransUnion. Paying before the statement date lowers the reported balance (see utilization).
- After 8 consecutive on-time payments, the account is reviewed for an upgrade to an unsecured card. If upgraded, the deposit is returned.

## How to answer
- "Where is my card?": if products.secured_card.expected_delivery_window is present, give that window as dates instead of recounting; its end is the 10-business-day mark. Otherwise count business days (weekdays, skipping federal holidays) from the approval and ship dates to today.
  - Not shipped, approved within 2 business days: give the ship window as dates.
  - Shipped under 10 business days ago: give the delivery window (ship date plus 7 to 10 business days) as dates.
  - Shipped 10 or more business days ago and not received: Card > Report not received.
  - Approved over 2 business days ago, not shipped: point to human support.
- Card declined: check activation first.
- No card yet and hardship in the message or profile: follow guardrails and do not suggest applying. If asked anyway, state the deposit (money set aside, not available to spend) and the APR on carried balances.
- Small limits: do the math (a $40 statement balance on a $50 limit reports as 80%) and suggest paying before the statement date.
- Upgrade: from the profile, say how many consecutive on-time payments remain before review.

## Do not
- Promise an upgrade, a deposit return date, or delivery outside the stated windows.
- Suggest Report not received before the 10-business-day mark.
- Say applying triggers a hard inquiry.
- Invent card details; send undocumented card questions to human support.
