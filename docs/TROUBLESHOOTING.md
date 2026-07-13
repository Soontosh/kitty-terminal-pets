# Troubleshooting

## No rail appears

First, fully restart Kitty. A regular config reload cannot create the listening socket.

Then check the controller.

Linux:

```bash
systemctl --user status kitty-pet
find "${XDG_RUNTIME_DIR:-/tmp/kitty-pet-$(id -u)}" -maxdepth 1 -type s -name 'kitty-pet-*.sock'
kitty-pet status
```

macOS:

```bash
launchctl print "gui/$(id -u)/io.github.soontosh.kitty-terminal-pets"
find "/tmp/kitty-pet-$(id -u)" -maxdepth 1 -type s -name 'kitty-pet-*.sock'
tail -n 80 ~/Library/Logs/KittyTerminalPets/controller-error.log
~/.local/bin/kitty-pet status
```

If the macOS agent is absent, rerun `./install.sh` from a Kitty window in your logged-in desktop session.

## `kitty-pet: command not found` on macOS

The installed command lives at `~/.local/bin/kitty-pet`. Add that directory to zsh once:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
exec zsh -l
```

The background service and Kitty shortcuts already use the absolute path and are not affected by your shell `PATH`.

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

Linux:

```bash
systemctl --user status kitty-pet
systemd-cgtop --user
```

macOS:

```bash
launchctl print "gui/$(id -u)/io.github.soontosh.kitty-terminal-pets"
ps -axo pid,%cpu,rss,nice,command | grep '[k]itty_pet.py'
```

The controller is nice-level 10 and uses direct socket requests for frequent reads. Helper processes are reserved for rare operations such as opening or closing a rail. On macOS, launchd also marks the controller as a background process with low-priority I/O.

## Emergency off switch

The portable option is:

```bash
kitty-pet disable
```

To stop the controller service too:

```bash
# Linux
systemctl --user disable --now kitty-pet.service

# macOS
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/io.github.soontosh.kitty-terminal-pets.plist
```

This does not alter your pets or delete configuration. Rerunning `./install.sh` restores and starts the service.
