# Timing customization

Pet timing is deliberately a separate layer from task detection. You can make an animation dramatically slower, faster, snappier, or more uneven without making a finished command look busy forever.

## Quick commands

Show the fully resolved timing for the selected pet:

```bash
kitty-pet timing
```

Set one scope:

```bash
kitty-pet timing all all --speed 0.8
kitty-pet timing all idle --fps 3
kitty-pet timing byte-cat all --speed 1.25
kitty-pet timing byte-cat running --fps 8
kitty-pet timing byte-cat failed --display-seconds 12
```

The first argument is a pet ID or `all`. The second is `idle`, `running`, `success`, `failed`, `waiting`, or `all`.

Use one duration for every frame:

```bash
kitty-pet timing byte-cat running --frame-ms 180
```

Or tune every frame individually. The number of values must match that animation's frame count:

```bash
kitty-pet timing byte-cat running --frame-ms 100,100,160,100,100,320
```

Reset exactly one scope:

```bash
kitty-pet timing byte-cat running --reset
```

Reset every custom timing:

```bash
kitty-pet timing all all --reset
```

## What the controls mean

- `--fps`: gives every frame in the scope an even rate.
- `--frame-ms`: sets one shared duration or an exact duration for each frame.
- `--speed`: multiplies the resolved speed. `2` is twice as fast; `0.5` is half speed.
- `--display-seconds`: controls how long success, failure, or waiting remains visible.

If both inherited FPS and a more-specific `frame_ms` exist, the more-specific setting wins. The same is true in reverse.

## Precedence

The most specific value wins:

1. Global defaults
2. Global state
3. Pet defaults
4. Pet state

For example, a global `speed` still applies if a pet only overrides `fps`. A pet-state `speed` replaces a pet or global speed.

## Direct JSON configuration

The CLI writes `~/.config/kitty-pet/config.json`. You can edit the same structure yourself:

```json
{
  "timings": {
    "speed": 0.9,
    "states": {
      "idle": { "fps": 3 }
    },
    "pets": {
      "killua": {
        "speed": 0.75,
        "states": {
          "running": {
            "frame_ms": [100, 100, 140, 100, 100, 300]
          },
          "success": {
            "fps": 6,
            "display_seconds": 8
          }
        }
      }
    }
  }
}
```

Changes are detected by existing pet rails automatically.

## Safety boundaries

Frame duration is limited to 17–60000 ms, FPS to 0.1–60, speed to 0.05–20, and completion display time to 0–86400 seconds. These wide bounds allow everything from frantic to practically meditative without generating invalid animation files.

`running` always starts and stops with actual foreground work. `idle` lasts until work begins. `display_seconds` therefore only changes completion states (`success`, `failed`, and `waiting`); it cannot make the pet report a command as running after it ends.
