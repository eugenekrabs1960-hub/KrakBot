# UI Redesign Implementation Plan

## Phase checklist

- [x] Phase 1: App shell + navigation foundation
- [x] Phase 2: Design token + reusable component system
- [x] Phase 3: Overview redesign (KPI-first operator summary)
- [x] Phase 4: Strategy comparison redesign (table + edge scoring)
- [x] Phase 5: Strategy detail page (single-strategy deep dive)
- [x] Phase 6: Trades + decision trace inspector UX
- [x] Phase 7: Market detail polish + market registry safety table
- [x] Phase 8: Controls safety UX (arming + typed confirmation for stop)
- [x] Phase 9: Benchmark / wallet intel UI panel
- [x] Phase 10: Mobile optimization + responsive shell

## Validation performed per milestone

- Frontend typecheck/build: `npm run build`
- Smoke checks: UI compiles and navigation renders all redesign pages

## Notes

- The redesign intentionally keeps existing API contracts and endpoint usage.
- Components introduced: `AppShell`, `PageHeader`, `StatCard`, `Badge`.
- Styling standardized via tokenized theme in `src/styles/tokens.css` and `src/styles/app.css`.
