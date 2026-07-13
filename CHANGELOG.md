# Changelog

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
