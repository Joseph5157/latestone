# CC-11 Dark / Light Theme

## Purpose
Support both control-room and field environments while keeping the Command Center visually coherent with the persistent app chrome.

## Architectural decision
Theme is route-scoped whole-shell behavior, not page-body-only styling.

While `/command-center` is active:
- sidebar
- main content
- utility / Asset Navigator chrome

all use the selected Command Center appearance.

When leaving `/command-center`, the existing application appearance is restored unchanged.

## Light
Reuse existing application light tokens where possible. The current `#F4F6F8` family is already aligned with the desired light canvas.

## Dark
Add Command Center route-scoped dark token overrides; do not perform a global dark-mode rewrite of unrelated pages.

## Rules
- preserve semantic colors
- status never depends on color alone
- persist choice per session
- route-scoped root/shell hook is allowed and expected
- shared shell changes must be minimal and regression-tested on `/plants`, Reports and Notifications
