# Setup guide

This is the slightly slower, explain-everything version. The README's installer is enough for most people.

## 1. Check the basics

```bash
kitty --version
python3 --version
systemctl --user --version
```

Kitty 0.36+ and Python 3.10+ are the supported baseline.

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
6. Enables `~/.config/systemd/user/kitty-pet.service`.
7. Validates every discovered pet atlas.

An existing `kitty.conf` is backed up before it is changed.

## 3. Restart Kitty once

Kitty cannot add a new remote-control listening socket during a config reload. Fully exit every Kitty process and start it again.

```bash
pgrep -a kitty
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

Pull and rerun the installer. It is idempotent and preserves the selected pet and layout settings.

```bash
git pull --ff-only
./install.sh
```
