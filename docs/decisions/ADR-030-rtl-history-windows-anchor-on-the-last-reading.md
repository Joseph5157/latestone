# ADR-030: RTL temperature history windows anchor on the RTL's last reading

Status: Approved
Date: 2026-09-30
Evidence: `docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md` §10 (source
cutoffs) and §7 (telemetry facts); `docs/audit/client-terminology-nav-01/nav-1366-administrator.png`
(observed last-reading dates on the registered fleet);
`repositories/rtl_temperature_repository.py:377` (`get_temperature_range`);
`services/rtl_detail_service.py`
Implemented-by: not yet

## Context

`/rtls/<uid>` offers 24-hour, 7-day and 30-day temperature history for one
registered client RTL. A window needs two bounds, and the obvious choice —
`now - span` to `now` — is wrong for this data.

The knowledge base records that client telemetry in `master_temperature` runs
**through 17 September 2026** (§10), and the registered fleet's observed last
readings are far older still: the RTL-UID-DETAIL-01 baseline screenshot shows
registered RTLs whose latest reading is dated 2016, 2017, 2019, 2020 and 2022.
Twenty of the 339 registered RTLs have no reading at all.

Measured from wall-clock now, therefore, "last 24 hours" is empty for
effectively every RTL in the directory, and "last 30 days" is empty for
almost all of them. That is a true statement and a useless one: it describes
the gap between today's date and the data export, not the RTL.

A second problem compounds it. Source timestamps are naive SAST values
(ADR-029) with no offset, while `now` is a server clock. Comparing them
requires a conversion, and every conversion is a place the two-hour offset can
be applied once, twice, or in the wrong direction without any test noticing —
because a window that is two hours wrong still returns plausible rows.

## Decision

A history window **ends at that RTL's own latest source reading** and begins
one span earlier:

```
window_end   = latest master_temperature timestamp for this UID
window_start = window_end - span        # 24h | 7d | 30d
```

Consequences of the choice, all deliberate:

- **Both bounds are source-clock values**, so the range query involves no
  timezone arithmetic at all. The naive SAST values go to SQL Server exactly
  as they came from it.
- **The exact range is stated on screen**, with its SAST label. The page says
  which period it is showing rather than implying recency.
- **An RTL with no reading has no anchor**, and therefore no window. That is
  reported as an explicit no-data state, never as an arbitrary range around
  today that happens to be empty.
- **A window that genuinely contains no readings** — an RTL whose only reading
  is its latest one — still reports no data explicitly. There is no fallback
  to synthetic readings, ever.

Rejected alternatives:

- `now - span` to `now`: empty for the whole fleet, and needs a SAST
  conversion to be even arguably correct.
- Anchoring to the fleet-wide maximum timestamp (17 Sep 2026): still empty for
  an RTL that stopped reporting in 2017, and invents a fleet-level concept the
  source does not carry.
- An "all time" window: an unbounded read of a 2.4M-row heap with no index we
  are permitted to add. The gate forbids unbounded fetches, and it would be
  the slowest query in the application.

This ADR governs presentation of history only. It sets no communication,
freshness, lifecycle or Online/Offline rule, and it must not be read as one:
the age of a reading still says nothing about whether an RTL is operating.
That remains CDB-01/CDB-02, unanswered.

## Consequences

Comparing two RTLs' 24-hour windows compares two different wall-clock periods.
That is correct for "what did this RTL record", which is the question the page
answers, and wrong for "what happened across the fleet at time T" — a
fleet-wide time axis is a Network/Dashboard concern and will need its own
decision when a gate builds one.

If the client later supplies live telemetry, the anchor becomes the live
latest reading automatically and the window silently becomes "the last 24
hours" in the ordinary sense. No code change is required for that transition,
which is the main reason this rule is expressed as "anchor on the last
reading" rather than as a hard-coded date.
