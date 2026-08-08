# UI Specification — Powerplant Dashboard

## Design Intent
Professional industrial monitoring interface for power-plant operators. Prioritise clarity, status awareness and data readability over decorative UI.

## 1. Login Page
Required elements:
- Project/system title: `Power Plant Monitoring System`
- Username field
- Password field
- Show/hide password control
- Login button
- Invalid-login message

For the demo, authentication is local/mock. Do not add registration or forgot-password workflows unless requested.

## 2. App Header (persistent across pages)
- Brand: `Power Plant Monitoring`
- Breadcrumb navigation (e.g., Plants > Plant Name > Transformer > Device)
- Cascading hierarchy selector (Plant → Transformer → Device dropdowns)
- Freshness badge (fresh / stale / no data)
- Logout control

## 3. Plants Overview Page
- Page heading: `Plants`
- DataTable with columns: Plant (link), Country, Fuel, Capacity (MW), Transformers, Devices
- 30 rows; transformer/device columns are counts
- Clicking a plant name navigates to plant detail

## 4. Plant Detail Page
- Breadcrumb: Plants > Plant Name
- DataTable with columns: Transformer (link), Devices, Status
- Clicking a transformer navigates to transformer detail

## 5. Transformer Detail Page
- Breadcrumb: Plants > Plant Name > Transformer Code
- DataTable with columns: Device (link), Status
- Clicking a device navigates to device dashboard

## 6. Device Dashboard Page
The primary operator view.

### 6a. Equipment Context Bar
Shows: Plant Name | Transformer Code | Device Code | Status

### 6b. Metric Snapshot Strip (8 tiles)
One tile per metric showing current value and condition. Clicking a tile selects that metric for the main view.

### 6c. Metric Controls
- Dropdown: metric selector (8 options)
- Radio: 24h / 7d / 30d / Custom
- Custom date range picker (when Custom selected)

### 6d. KPI Row
Aggregation-aware KPIs depend on metric type:
- **Statistics metrics** (temperature, voltage, current, etc.): Current / Minimum / Maximum / Average
- **Delta metric** (energy): Current / Period Change

### 6e. Metric Chart
Plotly line chart:
- X-axis: timestamp
- Y-axis: selected metric value with unit
- Hover: exact timestamp + value
- Zoom/pan supported
- Responsive width

### 6f. Recent Readings Table
Columns: Timestamp, Metric Value
- Newest first
- Clear empty state

### 6g. Auto-Refresh
Configurable refresh interval (default 60 seconds).

## 7. Responsive Behaviour
- Primary target is desktop/laptop.
- KPI cards: 4 columns → 2 columns → 1 column on narrow screens.
- Snapshot strip: 4 columns → 2 columns → horizontal scroll on mobile.
- Header collapses selector on narrow screens.
- Charts resize without horizontal page overflow.

## 8. Visual Rules
- Use restrained industrial styling.
- Make warning states visually distinct without turning the whole interface red.
- Do not overload the dashboard with gauges, pie charts or unnecessary animations.
- Use line charts for time series.
- Keep units visible.

## 9. Status Concepts
Three independent status dimensions:
- **Administrative status**: active / inactive (set by plant operators)
- **Data freshness**: fresh / stale / no_data (computed from last reading timestamp vs. configured threshold)
- **Monitoring condition**: always `UNKNOWN` in this demo (no production thresholds defined)
