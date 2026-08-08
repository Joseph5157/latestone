# UI Specification — Powerplant Dashboard Demo

## Design Intent
Professional industrial monitoring interface. Prioritise clarity, status awareness and data readability over decorative UI.

## 1. Login Page
Required elements:
- Project/system title: `Power Plant Monitoring System`
- Username field
- Password field
- Show/hide password control
- Login button
- Invalid-login message

For the demo, authentication is local/mock. Do not add registration or forgot-password workflows unless requested.

## 2. Dashboard Header
Show:
- Power Plant Monitoring System
- Transformer: `AA12`
- Device: `29017`
- Connection/data state where useful
- Last successful data timestamp
- Logout control

## 3. Context / Filters
For the one-device demo, transformer/device selectors may be displayed but only contain the known demo values:

```text
Transformer [AA12]
Device      [29017]
```

Time controls:
- 24 Hours
- 7 Days
- 30 Days
- Custom

## 4. KPI Row
Four cards:

```text
Current Temperature | Minimum | Maximum | Average
       36 °C         |  19 °C  |  48 °C  | 33.4 °C
```

Actual values must come from the selected database range. Current means the latest available reading, not the current wall-clock temperature.

## 5. Status
Display a concise status such as:
- Normal
- Warning
- No data

Warning threshold is a configurable demo setting. Do not imply it is an official operating threshold.

## 6. Temperature Trend
Plotly line chart:
- X-axis: timestamp
- Y-axis: temperature (°C if confirmed/assumed for demo; label demo assumptions clearly)
- Hover: exact timestamp + value
- Zoom/pan supported
- Responsive width
- Selected period controls the series

Optionally display the demo warning threshold as a reference line if it improves comprehension.

## 7. Recent Readings Table
Columns:
- Timestamp
- Temperature
- Status

Behaviour:
- Newest first
- Clear empty state
- Avoid overwhelming the page; show a sensible recent subset/pagination

## 8. Layout Sketch

```text
+---------------------------------------------------------------+
| POWER PLANT MONITORING                     User       Logout   |
+---------------------------------------------------------------+
| Transformer: AA12 | Device: 29017 | Last data: 10:30          |
| [24 Hours] [7 Days] [30 Days] [Custom]                        |
+---------------------------------------------------------------+
| Current       | Minimum       | Maximum       | Average        |
| 36 °C         | 19 °C         | 48 °C         | 33.4 °C        |
+---------------------------------------------------------------+
| Temperature Trend                                  [Normal]    |
|                                                               |
|                     Plotly chart                              |
|                                                               |
+---------------------------------------------------------------+
| Recent Readings                                               |
| Timestamp             Temperature           Status             |
| ...                   ...                   ...                |
+---------------------------------------------------------------+
```

## 9. Responsive Behaviour
Primary target is desktop/laptop. KPI cards may wrap on narrower screens. Charts must resize without horizontal page overflow.

## 10. Visual Rules
- Use restrained industrial styling.
- Make warning states visually distinct without turning the whole interface red.
- Do not overload the demo with gauges, pie charts or unnecessary animations.
- Use line charts for temperature time series.
- Keep units visible.
