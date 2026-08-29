# ENT-4 — Alarm & Notification Operations
## Planning Prompt (frozen scope — REVIEW BEFORE IMPLEMENTATION)

---

## 0. Gate status

| Field | Value |
|---|---|
| Tranche | ENT-4 |
| Baseline | `main = origin/main = ccd0206f198a1b8ddda7ec851956eff042ae4711` |
| Predecessors | ENT-2 (`4e6d26c`), DEFECT-1 (`d4d23e3`), ENT-3 (`ccd0206`) — pushed |
| Flow | PLAN → **REVIEW GATE (this document)** → IMPLEMENT → TEST/VISUAL VERIFY → IMPLEMENTATION REVIEW → COMMIT → PUSH GATE |
| Rule | Do not implement until this plan is approved. Do not absorb other tranches. |

---

## 1. Problem statement

The Notification Center is functionally correct but not operator-first:

1. **Not newest-first.** The repository returns `event_ts DESC` (newest-first),
   but the service layer re-orders: BR008 rows sorted by device id, then
   event-backed rows appended in stable-key order. An operator scanning for
   "what happened most recently" cannot trust row position
   (`services/notification_service.py:84`, `services/event_semantics.py:252`).
2. **No category presentation.** Categories are plain table text — no neutral
   badges/labels, no scanning hierarchy beyond the raw table.
3. **Dead navigation.** `entity_label` is styled as a link
   (`link_column_id="entity_label"`) but no `active_cell` callback exists;
   clicking does nothing, and the markdown fallback would open a new tab.
4. **Stale empty-state copy** names only ">24-hour data-loss" although
   battery/power-down/sensor-error/startup-check-in categories now render.
5. **Unstyled structure.** `.notification-section`, `.notification-section__desc`,
   `.notification-summary`, `.listing-error` (on this page) have no CSS rules;
   the page does not pass `responsive=True`, and notification columns have no
   mobile record-card labels.

## 2. Evidence base (verified at baseline)

- Sort: `repositories/plant_monitoring_repository.py:2431` orders newest-first;
  `build_no_data_notifications` re-sorts by `device_id`
  (`notification_service.py:84`); `current_notifications` appends event rows in
  stable-key order (`event_semantics.py:252`).
- Summary hook exists: `notification_summary` returns `{"total", "by_type": {}}`
  with `by_type` explicitly reserved (`notification_service.py:179-184`).
- Categories are enumerated and frozen: six in `config/notifications.py:24-85`;
  category→event-type mapping in `event_semantics.py:80-112`; `invalid_uid`
  maps to `None` (admin-only quarantine row, `UNREGISTERED_NOTIFICATION_TYPE`).
- Navigation pattern to copy: `callbacks/listings.py` `active_cell` handling
  (plants/transformers/devices tables) + `components/entity_table.py:54-58`
  markdown-link trap documentation.
- Anti-invention guards already in tests: no severity attribute
  (`test_notification_service.py:86-88`), no ack/suppress/expiry fields, no
  sms/email/mqtt strings, no thresholds in semantics source, old events never
  expire (`test_event_semantics.py:119-129`,
  `test_event_consumption_db.py:281-293`).

## 3. Target shape

```text
Notification Center
  Summary strip        "N current notifications · Battery 2 · Power down 1 · No data 3"
  Formal Notifications (newest-first table)
    occurred_at | entity (link) | type (neutral badge) | notification_type | detail
  Supported Notification Types (unchanged reference table)
```

### 3.1 Newest-first ordering (the core fix)

The merged notification list is ordered by `occurred_at` descending, newest
first, with a deterministic tiebreak (e.g. `key` ascending) so the order is
stable across refreshes. BR008 and event rows compete on equal footing —
a 20-minute-old battery event outranks a 3-day-old no-data row.

Implementation lives in the service/composition layer; the repository query is
already correct and must not change its ORDER BY.

### 3.2 Neutral category presentation

Category labels render as neutral badges/labels (one shared component or class
family), visually distinct from freshness/warning tokens. **No colour-coded
severity**: at most one neutral accent treatment per category family, or plain
tinted-neutral chips identical in weight. The raw DB `severity` column stays
unsurfaced. `is_reportable_alarm` / `forwarding_relevant` flags are never
visualised as priority/importance.

### 3.3 Scanning hierarchy

- Summary strip populated from `by_type` (the reserved hook): total plus
  per-category counts, text-first, no gauges.
- Section heading/description grammar aligned with the device-page idiom
  (eyebrow + H2) — device-page-local precedent, NOT the cross-page ENT-6
  unification.
- Table remains the single list; optional visual grouping (e.g. subtle category
  column emphasis) must not become a tree or accordion.

### 3.4 Row navigation

Clicking a row's entity cell navigates to the entity's device dashboard via the
existing `active_cell` + `device_href` pattern used by the other listings.
No new URL parameters. Unregistered-UID rows (no device route) render the
entity as plain text, not a dead link.

### 3.5 Copy and states

- Empty state updated to cover all categories truthfully, e.g.
  "No current notifications." — no severity language, no expiry framing.
- Prototype banner wording reviewed for honesty; must not drift toward
  delivery promises (no "will send", "delivered", "retry").
- Error path unchanged in behaviour (generic message, logged detail).

### 3.6 Responsive

`responsive=True` on the notification table plus record-card `::before` column
labels for its five columns, following the existing `entity_table` responsive
pattern. Summary strip wraps to stacked text on narrow widths. Verified at
1366 / 768 / 390 px.

## 4. Frozen invariants (must hold after implementation)

- One repository query per render for events (`list_recent_device_events`,
  limit 500 unchanged) + the existing BR008 `latest_reading_rows` call; no new
  queries, no N+1 enrichment.
- No changes to `config/notifications.py` category set, labels, or flags.
- No severity/acknowledgement/escalation/suppression/expiry/retention/channel
  fields or vocabulary anywhere in UI, services, or tests.
- `NotificationRow` may gain presentation-only derived fields (e.g. a category
  key for badge classes) but no lifecycle fields.
- Events never expire from the list (no `since` bound introduced).
- Role scoping unchanged: technician/general see only scoped devices; only
  administrators see unregistered-UID rows.
- No SQL in callbacks/components; hierarchy/entity resolution through services.
- No routing structure, authorization, or scope-policy changes.
- No new dependencies.

## 5. Explicitly out of scope

- Acknowledgement, escalation, suppression, expiry, retention (client-gated).
- SMS/email/channel delivery or the forwarding pipeline (C-05 gated; ENT-5
  owns forwarding-scope clarity in Device Management).
- Date-range filtering of the list (technically supported by data but reads as
  retention framing; deferred unless the reviewer explicitly wants it).
- Plant/transformer enrichment columns on `NotificationRow` (requires new
  joins; defer unless the reviewer asks — entity link already gives drill-through).
- Report Center, drawer grammar, device management, cross-page heading
  unification (ENT-5/ENT-6).
- Sidebar unread counts (no read-state model exists; inventing one is forbidden).

## 6. Known test impact

| Test file | Expected movement |
|---|---|
| `tests/test_notification_service.py` | Ordering tests change (device-id order → newest-first); layout/empty-copy assertions updated; anti-invention guards must keep passing |
| `tests/test_event_semantics.py` | Stable-key ordering test updated IF composition ordering moves to occurred_at (the collapse keying itself is untouched) |
| `tests/test_event_consumption_db.py` | Composition assertions may need order updates; scoping/expiry tests must pass UNCHANGED |
| `tests/test_app_sidebar.py`, `test_authorization.py`, `test_routing.py` | Expected green without edits |

New/updated tests must lock:

1. newest-first merged ordering with deterministic tiebreak;
2. a battery event newer than a no-data row ranks above it;
3. neutral badge classes carry no warning/danger/stale tokens (CSS source guard);
4. row navigation callback targets the correct `device_href`; unregistered rows
   produce no link;
5. empty-state copy covers all categories and names no severity;
6. summary strip counts equal table contents (`by_type` populated);
7. responsive record-card labels exist for all five columns (CSS source guard);
8. all existing anti-invention guards pass unchanged.

## 7. Verification requirements

1. Focused: `python -m pytest tests/test_notification_service.py tests/test_event_semantics.py tests/test_event_consumption_db.py tests/test_app_sidebar.py tests/test_authorization.py -q`
2. Full suite: `python -m pytest -q`.
3. `git diff --check`; `git status --short`.
4. Browser verification at 1366 / 768 / 390 px with screenshots: newest-first
   visible, badges neutral, row click navigates, empty/error states sane.
5. Review report states: single event query per render; zero diffs under
   `repositories/` ORDER BY / `config/notifications.py`; no forbidden vocabulary
   (grep evidence).
6. Stop before commit. Commit after approval. Push separately.

## 8. Suggested commit message (post-approval)

```text
feat(notifications): operator-first ordering and category presentation (ENT-4)
```

---

## 9. Decision requests for the reviewer

1. **Badge treatment**: neutral tinted chips (one shared neutral style, category
   name only) vs per-category muted tints. Plan leans **one shared neutral
   chip** — zero risk of reading as severity.
2. **Date filter**: include a client-side occurred-at sort/filter via the
   existing native DataTable controls only (no new UI), or add nothing? Plan
   leans **native controls only** — they already exist and add no retention
   framing.
3. **Plant/transformer enrichment**: defer (plan's lean) or add columns this
   tranche?
4. **Summary strip**: text line ("N current notifications · Battery 2 · …") vs
   count chips. Plan leans text-first.
