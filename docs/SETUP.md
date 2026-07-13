# Setup guide

This is the slightly slower, explain-everything version. The README's installer is enough for most people on Linux and macOS.

## 1. Check the basics

Kitty 0.36+ and Python 3.10+ are the supported baseline.

```bash
uname -s
python3 --version
```

Check Kitty on Linux or when it is already on your `PATH`:

```bash
kitty --version
```

The normal macOS app install works even when `kitty` is not on `PATH`:

```bash
/Applications/kitty.app/Contents/MacOS/kitty --version
```

The installer checks for a systemd user session on Linux. On macOS it creates a per-user launchd agent; no `sudo` is needed on either platform.

## 2. Install

```bash
git clone https://github.com/Soontosh/kitty-terminal-pets.git
cd kitty-terminal-pets
./install.sh
```

The installer:

1. Copies the controller into `~/.local/share/kitty-pet`.
2. Creates a private Python virtual environment.
3. Installs Byte Cat under `~/.local/share/terminal-pets/pets`.
4. Creates `~/.local/bin/kitty-pet`.
5. Adds a clearly marked block to `~/.config/kitty/kitty.conf`.
6. Enables the platform service:
   - Linux: `~/.config/systemd/user/kitty-pet.service`
   - macOS: `~/Library/LaunchAgents/io.github.soontosh.kitty-terminal-pets.plist`
7. Validates every discovered pet atlas.
8. Precompiles the controller and prepares the selected pet's animation cache before starting the service.

An existing `kitty.conf` is backed up before it is changed. Re-running the installer is safe and preserves the selected pet, timing, and layout settings.

### macOS command path

The service and Kitty shortcuts use absolute paths, so they work immediately. To type `kitty-pet` in a new zsh session, ensure `~/.local/bin` is on `PATH`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
exec zsh -l
```

Skip this if `command -v kitty-pet` already prints a path.

## 3. Restart Kitty once

Kitty cannot add a new remote-control listening socket during a config reload. Fully exit every Kitty process and start it again.

```bash
pgrep -fl 'kitty|kitty.app'
```

After reopening Kitty, a narrow pet rail should appear on the right.

## 4. Pick a pet

```bash
kitty-pet list
kitty-pet select
```

Existing rails update without another restart.

## Adding a custom pet

Create a directory containing `pet.json` and `spritesheet.webp`:

```text
~/.local/share/terminal-pets/pets/my-pet/
├── pet.json
└── spritesheet.webp
```

Minimal manifest:

```json
{
  "id": "my-pet",
  "displayName": "My Pet",
  "description": "A very serious terminal professional.",
  "spritesheetPath": "spritesheet.webp"
}
```

The default atlas is 1536×1872: eight 192×208 columns and nine rows. See `assets/byte-cat` for a working example.

## Updating

Pull and rerun the installer. It refreshes the systemd unit or launchd agent without changing your pet configuration.

```bash
git pull --ff-only
./install.sh
```
