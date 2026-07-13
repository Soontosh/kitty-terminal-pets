# Performance

Kitty Terminal Pets is designed to be asleep almost all the time. The animation itself is played by Kitty; the helper processes only need to react when terminal state, cursor placement, configuration, or pet assets change.

## What version 1.2 changed

- Renderers block in Linux `inotify` instead of waking five times per second.
- Petdex directories and manifests are read only at startup or when their files change.
- Position JSON is replaced only when meaningful state actually changes.
- Cursor placement is captured when a command starts and updated when it finishes; streaming output no longer retransfers the image every row.
- Pillow is never imported into a long-lived controller or renderer. A cache miss uses a locked worker that exits after building the animation.
- Cached images use Kitty's local shared-memory transfer instead of streaming encoded bytes through the terminal.
- Frequent reads and pane management use Kitty's Unix socket protocol directly, without spawning `kitty @` processes.
- Cursor text is queried only for the focused Kitty OS window.

## Measured result

Measurements were taken on the original development machine with Kitty 0.47.4, Python 3.12, Killua, and four Kitty processes. Values vary by machine, but the direction is the important part.

| Measurement | Before | After |
| --- | ---: | ---: |
| Total idle CPU, controller + four panes | about 6.0% of one core | about 0.3% |
| Reads per idle renderer | about 90/sec | 0/sec while unchanged |
| Renderer CPU while unchanged | 1.2–1.4% each | below 0.01% observed |
| Renderer RSS | 28–54 MiB | about 20 MiB |
| Python module startup | about 214 ms | about 131 ms |
| Four-socket controller scan | about 318 ms | about 217 ms |

The optimized service also runs with low CPU and I/O weights, idle-class I/O scheduling, and nice level 10 so real terminal work wins under contention.

## Tuning

`~/.config/kitty-pet/config.json` accepts:

```json
{
  "controller_poll_seconds": 1.0,
  "startup_delay_seconds": 0.75
}
```

- `controller_poll_seconds` (`0.25`–`10`) trades state-detection latency for socket activity. `1.0` means completion is normally noticed within one second.
- `startup_delay_seconds` (`0`–`10`) is the minimum age of a new Kitty window before its rail is created. It lets the shell reach a usable prompt before the split changes its dimensions.

Existing renderers react to configuration through `inotify`; no restart is needed for ordinary config changes. Changing service installation itself still requires rerunning `install.sh`.

## Why this is not Rust or C

A native helper was considered. It would reduce the remaining Python memory footprint, but profiling showed the lag came from repeated work rather than the language runtime. After removing that work, renderers consumed no measurable CPU while unchanged. Shipping a native executable would add compiler requirements or architecture-specific binaries for a much smaller gain, so this version keeps the portable, auditable Python implementation.

The controller retains a low-frequency socket scan rather than loading a global watcher into Kitty's own process. Kitty watchers can receive command events, but putting integration code inside the terminal process increases the blast radius of a bug and does not cover every non-shell foreground program. The current socket-only boundary remains deliberately boring and safe.
