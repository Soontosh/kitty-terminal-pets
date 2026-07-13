# Troubleshooting

## No rail appears

First, fully restart Kitty. A regular config reload cannot create the listening socket.

Then check:

```bash
systemctl --user status kitty-pet
find "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" -maxdepth 1 -type s -name 'kitty-pet-*.sock'
kitty-pet status
```

## The wrong pet is showing

```bash
kitty-pet list
kitty-pet select <pet-id>
```

Pet IDs are the directory/manifest IDs, not necessarily the display names.

## A pet fails validation

```bash
kitty-pet self-test
```

The error normally identifies a missing spritesheet, unexpected atlas dimensions, or an out-of-range animation frame.

## The rail is too wide or the pet is too high

Edit `~/.config/kitty-pet/config.json`:

```json
{
  "pane_percent": 10,
  "pet_rows": 6,
  "cursor_offset_rows": 2
}
```

No restart is needed for these values.

## SSH stays idle

Plain interactive `ssh -t` sessions are treated as idle because the local Kitty instance cannot see individual remote commands. This avoids an endless running animation. Fine-grained remote state would require Kitty shell integration on the remote host.

## Check resource usage

```bash
systemctl --user status kitty-pet
systemd-cgtop --user
```

The controller is nice-level 10 and uses direct socket requests for frequent reads. Helper processes are reserved for rare operations such as opening or closing a rail.

## Emergency off switch

```bash
kitty-pet disable
systemctl --user disable --now kitty-pet.service
```

This does not alter your pets or delete configuration.
