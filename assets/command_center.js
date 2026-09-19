/* CC-FILTER-FAST-1: Command Center clicks that should not cost a server trip.
 *
 * Every poll re-renders the problem list, the cards and the donut. Dash fires
 * a pattern-matching ALL callback whenever its buttons are re-created, with
 * n_clicks 0, so each re-render used to send one no-op request per button
 * family (acknowledge, manage, fold, severity). `realClick` drops those in
 * the browser and hands only a real click on to the server callback.
 *
 * `filterClass` applies the severity filter to the already-rendered page:
 * one class on the page root, which app.css reads to hide the other tones'
 * groups, show that tone's note and press/dim the controls. The decision of
 * WHICH tone is selected stays in Python (callbacks.command_center.
 * severity_selection); this only paints it.
 */
window.dash_clientside = Object.assign({}, window.dash_clientside, {
  command_center: {
    realClick: function () {
      var ctx = window.dash_clientside.callback_context;
      var hit = ctx && ctx.triggered && ctx.triggered[0];
      if (!hit || !hit.value) {
        return window.dash_clientside.no_update;
      }
      var propId = hit.prop_id;
      var id = JSON.parse(propId.slice(0, propId.lastIndexOf(".")));
      // `at` makes two clicks on the same button (whose n_clicks restarts at
      // 1 after a re-render) two distinct store writes.
      return { id: id, n: hit.value, at: Date.now() };
    },

    filterClass: function (selected) {
      // aria-pressed is drawn by Python on each refresh; between refreshes
      // the filter changes here, so keep it current on the live buttons.
      document.querySelectorAll('button[id*="attention-severity"]').forEach(function (button) {
        try {
          var tone = JSON.parse(button.id).tone;
          if (tone && tone !== "all") {
            button.setAttribute("aria-pressed", tone === selected ? "true" : "false");
          }
        } catch (e) { /* not a severity button */ }
      });
      return "attention-page" + (selected ? " attention-filter--" + selected : "");
    }
  }
});
