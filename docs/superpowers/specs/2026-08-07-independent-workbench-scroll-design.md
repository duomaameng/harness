# Independent Workbench Scroll Design

## Goal

Make the desktop repository sidebar and workbench content scroll independently, rather than sharing the document scroll position.

## Current state

`harness/webui.py` renders the workbench as a two-column `.dashboard-shell` below the sticky top bar. The shell only has `min-height`, so overflow is owned by the document and both columns move together.

## Chosen design

On viewports wider than 980px, the application shell will occupy the remaining viewport height below the 67px top bar. The sidebar and `.main-view` will each be independently vertically scrollable. The grid columns and existing visual styles remain unchanged.

At 980px and below, the current single-column responsive layout remains document-scrolling. This avoids nested scroll regions on compact touch devices.

## CSS changes

- Replace the desktop shell's `min-height` with a fixed remaining-viewport height and suppress shell-level overflow.
- Add vertical overflow to `.task-sidebar` and `.main-view`, with the grid children allowed to shrink (`min-height: 0`).
- In the existing responsive media query, restore automatic shell height, visible shell overflow, and non-scrolling column behavior.

## Validation

- Add a WebUI HTML contract test that verifies the emitted stylesheet contains the independent desktop scroll rules and responsive restoration rules.
- Run the focused WebUI test module, then the full test suite.

## Non-goals

- No markup, routing, JavaScript, or repository/task behavior changes.
- No changes to the standalone `design/webui-prototype.html` because the live UI is rendered by `harness/webui.py`.
