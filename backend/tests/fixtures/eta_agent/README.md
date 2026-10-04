# ETA Agent Email Fixtures

Twelve canonical supplier-reply scenarios drive the `DeliveryEtaAgent` unit tests
(see research.md §12 and tasks T031, T035 for usage). Each fixture is a single
RFC-5322 email (`.eml`) plus a sibling `.expected.json` containing the
`EtaExtraction` we expect the agent to produce when invoked with that input.

## Scenarios

| # | File slug                     | Intent       | Confidence band | Notes                                                                              |
|---|-------------------------------|--------------|-----------------|------------------------------------------------------------------------------------|
| 1 | `confirm_high_confidence`     | confirm      | ≥ 0.85          | Explicit absolute date, clean subject line with `Order #<uuid>`.                   |
| 2 | `confirm_medium_confidence`   | confirm      | 0.60 – 0.84     | Relative phrase ("by next Tuesday") resolved against the email `Date` header.      |
| 3 | `confirm_low_confidence`      | confirm      | < 0.60          | Vague language ("aiming for end of week"), must route to review.                   |
| 4 | `delay_with_new_date`         | delay        | ≥ 0.70          | Apology + new ETA in same paragraph.                                               |
| 5 | `delay_no_date`               | delay        | any             | "Will be delayed, will advise" — no parseable date → review queue.                 |
| 6 | `cancel_full_order`           | cancel       | any             | Always routed to review (negative-intent rule, §6).                                |
| 7 | `cancel_partial_lineitem`     | cancel       | any             | Cancels one SKU; review queue picks the disposition.                               |
| 8 | `acknowledge_no_eta`          | acknowledge  | any             | "Received your PO, will confirm ETA shortly." — timeline entry only.               |
| 9 | `acknowledge_with_attachment` | acknowledge  | any             | Body is mostly disclaimer; PDF attachment ignored.                                 |
| 10| `unclear_off_topic`           | unclear      | any             | Out-of-office reply or unrelated chatter → routed to review.                       |
| 11| `non_english`                 | unclear      | any             | German-language reply; agent flags `non_english`, raised_reason set accordingly.   |
| 12| `past_date`                   | confirm/delay| any             | Agent extracts a date in the past → routed to review (past-date rule, §6).        |

## Conventions

- File slug stems are reused for any subdirectory (e.g. `confirm_high_confidence.eml`,
  `confirm_high_confidence.expected.json`).
- `Message-ID`, `Date`, and `From` headers are stable per-fixture so dedupe tests
  produce reproducible hashes.
- Expected JSON conforms to `app.schemas.eta_review.EtaExtraction`.
- Where the agent is expected to raise (e.g. malformed JSON regression), the
  fixture omits `.expected.json` and adds `.expected_error.txt`.

## Adding a new fixture

1. Drop a `<slug>.eml` here using the same headers convention.
2. Add a `<slug>.expected.json` (or `<slug>.expected_error.txt`).
3. Append a row to the table above.
4. Wire it into the parametrised test in `tests/unit/test_delivery_eta_agent.py`.
