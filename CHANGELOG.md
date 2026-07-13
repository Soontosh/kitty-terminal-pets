# Changelog

## 1.2.0 — 2026-07-13

- Replaced five-times-per-second renderer polling with Linux `inotify` events.
- Cached pet discovery and stopped rewriting unchanged position files.
- Lazy-loaded Pillow and moved cache misses into locked, short-lived workers.
- Switched local image transfer from terminal streaming to shared memory.
- Removed cursor/image churn while command output is streaming.
- Used Kitty's socket protocol directly for pane management and skipped cursor-text queries for unfocused windows.
- Precompiled the app and prepared animations before starting the user service.

## 1.1.0 — 2026-07-13

- Added live global, per-state, per-pet, and per-frame animation timing overrides.
- Added configurable success, failure, and waiting display durations per pet.
- Added `kitty-pet timing` for inspecting, changing, and resetting overrides.
- Kept running and idle state lifetimes tied to real terminal activity.

## 1.0.0 — 2026-07-13

- First public release.
- Right-side, cursor-following Kitty pet rail.
- Per-tab idle, running, success, and failure states.
- Shared Codex/Petdex-compatible catalog.
- Socket-only controller with no shell traps or TTY readers.
- Original Byte Cat starter pet and animated demo.
