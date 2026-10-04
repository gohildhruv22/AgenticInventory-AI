# Feature Specification: Supplier Delivery ETA Agent

**Feature Branch**: `004-supplier-delivery-eta-agent`

**Created**: 2026-05-21

**Status**: Draft

**Input**: User description: "now discuss here i want to implement a feature that is our agent can read the response of the supplier that we will ship you goods to this date and our agent will read that and then according to that date and time it will adjust the delivery and show us the updates."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic ETA capture from supplier reply (Priority: P1)

After AgenticInventory AI dispatches a purchase order email to a supplier, the supplier replies in plain English (e.g., "Thanks — we'll ship on Tuesday May 26 and you should receive it by May 29"). A background agent reads that reply, identifies which purchase order it belongs to, extracts the promised ship and/or delivery date, and updates the corresponding Delivery record. The new expected delivery date, the supplier's own words, and the parsed confidence are then visible on the Deliveries page without anyone having to copy-paste anything.

**Why this priority**: This is the core value of the feature. Today the platform places orders but has no idea when goods will actually arrive — admins must read each supplier reply themselves. Closing this loop converts the platform from "fire and forget" to "tracked end-to-end" and is a prerequisite for all downstream updates.

**Independent Test**: Send a synthetic supplier reply to the monitored mailbox referencing a known recent purchase order ID and containing a clear ship date. Within the polling window, verify that the matching Delivery row has its expected delivery date updated, its stage advanced to "confirmed", and a new entry appended to its stage history quoting the parsed date and the original supplier sentence.

**Acceptance Scenarios**:

1. **Given** a purchase order has been emailed to a supplier and the delivery is in stage "pending", **When** the supplier replies with a message containing a recognizable future ship or arrival date and the purchase order ID, **Then** the system updates the matching delivery's expected delivery date to the parsed date, advances its stage to "confirmed", and records a timeline entry with the parsed date, parsed confidence, and a short excerpt of the supplier's message.
2. **Given** a supplier replies with a date range (e.g., "between June 5 and June 9"), **When** the agent parses the reply, **Then** the system stores the later end of the range as the expected delivery date and notes the original range in the timeline entry.
3. **Given** a supplier replies referencing the order but without any parseable date (e.g., "received, working on it"), **When** the agent processes the reply, **Then** the system records an "acknowledged" timeline entry, leaves the expected delivery date unchanged, and does not advance the stage.

---

### User Story 2 - Delivery timeline visible to admin (Priority: P2)

When an admin opens the Deliveries page, each delivery row shows the current stage, the current expected delivery date, and an expandable timeline of every supplier-driven update the agent has recorded — including the original supplier sentence that produced each change. The admin can see at a glance which deliveries have been confirmed by suppliers, which are still waiting for any reply, and which have been pushed out from their originally promised date.

**Why this priority**: Capturing data without surfacing it provides no operational value. Admins need a single place to see "what changed and why" so they can plan around late shipments and trust the autonomous updates.

**Independent Test**: With several deliveries in mixed states (pending, confirmed via agent, manually updated), open the Deliveries page and confirm each row shows the correct current stage, current expected date, and that expanding a row reveals an ordered timeline with timestamps and excerpts. Confirm that a delivery whose ETA was pushed back shows both the original and the revised date.

**Acceptance Scenarios**:

1. **Given** a delivery has received one supplier ETA update from the agent, **When** the admin expands its row, **Then** the timeline shows at least one entry containing the supplier's quoted sentence, the parsed date, and the time the agent processed the email.
2. **Given** a delivery's expected date has been revised twice by the agent, **When** the admin views it, **Then** the row shows the most recent expected date, and the timeline lists both updates in chronological order.
3. **Given** a delivery has had no supplier reply, **When** the admin views the Deliveries page, **Then** the row clearly indicates "awaiting supplier confirmation" rather than showing a stale expected date as confirmed.

---

### User Story 3 - Low-confidence parses are flagged for human review (Priority: P3)

When the agent reads a reply but is not confident about which order it refers to, what the promised date actually is, or detects a negative signal (e.g., "we cannot fulfill this order", "delayed indefinitely"), it does not silently update the delivery. Instead, it raises a review item that an admin can confirm, correct, or dismiss. Once the admin acts, the delivery is updated accordingly and the resolution is recorded in the timeline.

**Why this priority**: Suppliers write messy emails. Auto-updating from a wrong parse is worse than not updating at all — it gives admins false confidence. A review queue contains the blast radius of low-confidence parses while still surfacing every supplier signal.

**Independent Test**: Send replies that are deliberately ambiguous (no order ID, conflicting dates, "cannot fulfill" language). Verify the agent creates review items instead of mutating the delivery, that the review items appear in the admin UI with the original email body and the agent's best guess, and that admin actions (approve / correct / dismiss) update the delivery and append to its timeline.

**Acceptance Scenarios**:

1. **Given** a supplier reply does not contain a recognizable order identifier, **When** the agent processes it, **Then** the reply is added to a review queue tagged "unmatched" with the agent's best-effort guess at the candidate order(s), and no delivery record is modified.
2. **Given** a supplier reply contains language indicating cancellation or indefinite delay, **When** the agent processes it, **Then** the matching delivery is moved to an "at-risk" state, a review item is created, and the timeline records the supplier's quoted sentence.
3. **Given** an admin approves a review item, **When** the admin confirms the agent's parsed date, **Then** the delivery is updated using that date and the review item is marked resolved with the admin's identity recorded.

---

### Edge Cases

- **Multiple replies from same supplier on same thread**: Each subsequent reply with a later or different date should be treated as a revision, not a duplicate, and both should appear in the timeline.
- **Reply references multiple purchase order IDs**: The agent should attempt to update each referenced order and, if any cannot be confidently matched, raise review items only for the unmatched ones.
- **Replies in a language other than English**: For v1, non-English replies are routed to the review queue rather than silently dropped.
- **Reply arrives after the goods have already been marked delivered**: The agent should not roll back a "delivered" stage; instead it appends a timeline note and ignores the date.
- **Parsed date is in the past**: Treated as low confidence and sent to the review queue rather than applied.
- **Same email delivered twice by the mail server**: The agent must deduplicate so the same supplier sentence does not produce two timeline entries.
- **Auto-reply / out-of-office messages**: Recognised and ignored, with no timeline entry created.
- **Supplier reply lands outside business hours**: The update should still be applied as soon as the agent next polls; admins should not need to wait for the next business day.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST monitor the configured supplier-correspondence mailbox on a recurring schedule and ingest new replies without manual intervention.
- **FR-002**: System MUST associate each incoming reply with at most one existing purchase order using identifiers found in the reply (such as the order ID echoed in the subject or body) and, where the identifier is missing or ambiguous, attempt a best-effort match using sender address and recent outbound history.
- **FR-003**: System MUST extract from each reply, when present, (a) the supplier's promised ship or delivery date, (b) whether the supplier is confirming, delaying, or cancelling, and (c) a short verbatim excerpt of the supplier's own words that justify the extraction.
- **FR-004**: System MUST attach a confidence score to every extraction and route extractions below a configured confidence threshold to a human review queue instead of mutating the delivery.
- **FR-005**: System MUST update the matching delivery's expected delivery date and stage when extraction confidence is at or above the threshold, AND record a timeline entry containing the parsed date, the confidence, the supplier's verbatim excerpt, and the timestamp of processing.
- **FR-006**: System MUST never silently overwrite a delivery that has already been marked as physically delivered; later supplier messages about such an order are recorded as informational timeline notes only.
- **FR-007**: System MUST deduplicate incoming messages so that the same supplier reply is processed at most once even if the mail server redelivers it.
- **FR-008**: System MUST treat messages identified as automated bounces, out-of-office notices, or read receipts as non-actionable and exclude them from both the timeline and the review queue.
- **FR-009**: System MUST present, on the existing Deliveries page, each delivery's current stage, current expected delivery date, and an expandable chronological timeline of every agent-driven and human-driven update.
- **FR-010**: System MUST allow an admin to open the review queue, see each pending review item with the original message excerpt and the agent's best-effort parse, and either approve, correct, or dismiss it.
- **FR-011**: System MUST, when a reply indicates cancellation, indefinite delay, or any date in the past, move the affected delivery into an "at-risk" state and require human review before any date is applied.
- **FR-012**: System MUST record, for every change to a delivery's expected date or stage, the actor responsible (agent or named admin) and the source message reference, so the audit trail is complete.
- **FR-013**: System MUST surface a visible indicator on the Deliveries page when a delivery has an unresolved review item, so admins are not required to open the review queue separately to know it has pending work.
- **FR-014**: System MUST handle date ranges by selecting the later end of the range as the conservative expected delivery date and preserving the original range text in the timeline entry.
- **FR-015**: System MUST tolerate intermittent failures of the mailbox or extraction step by retrying ingestion of unprocessed messages on the next cycle without losing or double-applying any update.

### Key Entities

- **Supplier Reply**: A single inbound message from a supplier. Attributes: message identifier, sender, received timestamp, subject, body excerpt, processing status (new, parsed, applied, in review, ignored, failed), dedupe key. Each reply is associated with at most one Delivery (or none, if unmatched).
- **Delivery Timeline Entry**: An ordered record of one event in a delivery's life. Attributes: timestamp, actor (agent or admin identity), event type (acknowledged, ETA confirmed, ETA revised, at-risk, delivered, note), parsed date (where applicable), confidence, supplier excerpt (where applicable), source message reference.
- **ETA Review Item**: A pending decision raised by the agent. Attributes: source Supplier Reply, candidate Delivery (may be empty for unmatched messages), agent's best-effort parsed date, agent's best-effort intent (confirm / delay / cancel / unclear), agent's reasoning, raised timestamp, resolution state (pending, approved, corrected, dismissed), resolving admin identity, resolution timestamp.
- **Delivery (existing, extended)**: Already exists. New required attributes for this feature: current stage including the values "confirmed" and "at-risk", flag indicating whether any review item is unresolved, and the link from each stage history entry back to the Supplier Reply that produced it (when applicable).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 80% of supplier replies that contain a clearly stated ship or delivery date result in an automatic, correct update to the matching delivery, with no admin action required.
- **SC-002**: From the moment a supplier reply arrives in the monitored mailbox to the moment the corresponding delivery row reflects the new expected date, no more than 10 minutes elapse in the 95th percentile.
- **SC-003**: Fewer than 2% of agent-driven delivery updates are reversed or corrected by an admin within 7 days of being applied — i.e., the agent is right almost all the time when it chooses to act.
- **SC-004**: Admins spend at least 75% less time per week reconciling supplier emails with the delivery list compared to the pre-feature baseline, measured by a before/after time-tracking sample.
- **SC-005**: 100% of supplier replies that touch the system can be traced from the Deliveries page back to the original message excerpt that justified the update, with no "phantom" updates lacking a source.
- **SC-006**: The Deliveries page communicates the current expected date and the existence of any pending review item to a first-time admin user within 30 seconds of opening the page, without their needing to consult documentation.

## Assumptions

- The supplier mailbox the agent reads from is the same identity the platform already sends purchase order emails from, so inbound replies on those threads are reachable without provisioning a new mail account.
- Suppliers reply in English in the v1 scope. Non-English messages are not silently dropped — they are sent to the review queue.
- Each purchase order results in a single shipment in the v1 scope. Split shipments (one order delivered in multiple parcels on different dates) are out of scope and will be revisited in a later iteration.
- The existing Deliveries data model already stores current stage, stage history, and expected delivery timestamp and can be extended (without breaking existing rows) to attach review-item references and source-message references.
- The platform already has an admin-authenticated UI surface where the Deliveries page lives; adding a review queue does not require building a new auth or navigation system.
- The autonomous procurement pipeline already embeds an identifier (such as the order ID) in outbound subject lines, which the agent can rely on as the primary matching signal.
- Suppliers who never reply are not, by themselves, a failure of this feature — surfacing that "no reply yet" is itself part of the value (User Story 2).
