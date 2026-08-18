# Vibration Metric Contract — TBD

## Status

**Vibration metric support is not yet activated in the UI.**

This document records what we need from the client/backend before vibration can become a real metric.

## Known

- Application supports registry-driven metrics via `config/metrics.py`
- Adding a metric requires only adding to the `METRICS` tuple
- UI components (selector, KPI cards, charts, health grid) are generic
- Vibration support is expected/planned for future phases

## Unknown / Required from Client/Backend

| Question | Why It Matters |
|----------|----------------|
| What is the metric key? | Must match database column/API field |
| What is the operator-facing label? | UI display name |
| What is the unit? | mm/s, m/s², in/s, g, µm, etc. |
| What precision is needed? | Decimal places for display |
| Is it instantaneous or cumulative? | Determines STATISTICS vs DELTA aggregation |
| What is the chart type? | Line, bar, or something else? |
| What is the sampling cadence? | Freshness policy alignment |
| What is the source resolution? | Chart binning and energy-like metrics |
| Is there a valid sensor range? | Future threshold support |
| Do thresholds exist? | Warning/critical states |
| Are there multiple axes? | X/Y/Z or single combined value? |
| Is this continuous data or event data? | Storage and display model |
| What does the value represent? | Displacement, velocity, acceleration, RMS, peak? |
| How is it stored in the database? | Column name, table, schema |
| How is it accessed via API? | Endpoint, query pattern |

## Implementation Rule

**Vibration must not be activated in the UI until its real data contract exists.**

Do not:
- Add vibration to the metric selector
- Show fake vibration values (0.00 mm/s)
- Show vibration as NO_DATA (NO_DATA has a precise meaning: configured metric with no reading)
- Create vibration-specific repository calls
- Add vibration alarm thresholds
- Create vibration-specific freshness logic

## Current Architecture Readiness

The following components are already generic and will work with any metric added to the registry:

- `config/metrics.py` — MetricConfig, ordered_metrics(), get_metric()
- `components/metric_snapshot_strip.py` — renders tiles from ordered_metrics()
- `components/trend_grid.py` — renders cells from ordered_metrics()
- `components/metric_health.py` — renders tiles from metric_health_from_rows()
- `components/metric_chart.py` — line/delta charts driven by MetricConfig
- `callbacks/device.py` — device dashboard uses ordered_metrics()
- `services/monitoring_service.py` — freshness chain uses ordered_metrics()
- `repositories/plant_monitoring_repository.py` — generic metric queries

## What Will Need Change

When vibration becomes real:

1. Add `MetricConfig("vibration", ...)` to `METRICS` tuple
2. Verify database column exists
3. Verify repository query returns vibration data
4. Test freshness evaluation works correctly
5. Verify chart rendering is appropriate
6. Update any threshold logic if vibration thresholds are confirmed

## Temperature Attribution Note

The existing `ATTRIBUTION_METRIC_KEY = "temperature"` is a legitimate business feature (Hottest Device). It is intentionally temperature-specific and should remain so. Vibration will not have attribution behavior unless explicitly confirmed by the client.
