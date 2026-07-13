#!/usr/bin/env python3
"""Generate the original Byte Cat atlas and the repository demo artwork."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "assets" / "byte-cat" / "spritesheet.webp"
DEMO = ROOT / "demo" / "kitty-terminal-pets.gif"
PREVIEW = ROOT / "demo" / "preview.png"
CELL_W, CELL_H, COLS, ROWS = 192, 208, 8, 9
BG = "#11111b"
PANEL = "#181825"
TEXT = "#cdd6f4"
MUTED = "#6c7086"
MINT = "#94e2d5"
BLUE = "#89b4fa"
PINK = "#f5c2e7"
YELLOW = "#f9e2af"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def rect(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, color: str, scale: int = 4) -> None:
    draw.rectangle((x * scale, y * scale, (x + w) * scale - 1, (y + h) * scale - 1), fill=color)


def byte_cat(index: int) -> Image.Image:
    image = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    row, frame = divmod(index, COLS)
    bob = (frame % 3 == 1) - (frame % 3 == 2)
    lean = 0
    eyes = "open"
    tail = frame % 4
    accent = BLUE
    if row in (1, 2):
        lean = 2 if row == 1 else -2
        bob = frame % 2
    elif row == 4:
        bob = -min(frame, 2)
    elif row == 5:
        bob = 2
        eyes = "sad"
        accent = PINK
    elif row == 6:
        eyes = "blink" if frame in (2, 3) else "open"
        accent = YELLOW
    elif row == 7:
        bob = -1 if frame % 2 else 1
        lean = 2
        accent = BLUE if frame % 2 else PINK
    elif row == 8:
        bob = -1 if frame in (1, 4) else 0
        accent = MINT

    s = 4
    ox, oy = 8 + lean, 15 + bob
    outline = "#313244"
    dark = "#45475a"
    white = "#f5e0dc"

    # Tail, legs, body, head, and ears. Everything is intentionally blocky
    # and original so the repository ships no third-party character artwork.
    tail_x = ox + 29 + (tail == 1) * 2 - (tail == 3) * 2
    rect(draw, tail_x, oy + 20, 3, 10, outline, s)
    rect(draw, tail_x + 2, oy + 17 - tail % 2, 3, 6, MINT, s)
    rect(draw, ox + 11, oy + 30, 5, 6, outline, s)
    rect(draw, ox + 23, oy + 30, 5, 6, outline, s)
    rect(draw, ox + 12, oy + 22, 16, 11, outline, s)
    rect(draw, ox + 13, oy + 21, 14, 11, MINT, s)
    rect(draw, ox + 8, oy + 7, 24, 18, outline, s)
    rect(draw, ox + 9, oy + 8, 22, 16, MINT, s)
    rect(draw, ox + 9, oy + 3, 7, 8, outline, s)
    rect(draw, ox + 25, oy + 3, 7, 8, outline, s)
    rect(draw, ox + 11, oy + 5, 4, 5, PINK, s)
    rect(draw, ox + 26, oy + 5, 4, 5, PINK, s)

    if eyes == "blink":
        rect(draw, ox + 13, oy + 15, 5, 1, dark, s)
        rect(draw, ox + 23, oy + 15, 5, 1, dark, s)
    elif eyes == "sad":
        rect(draw, ox + 13, oy + 15, 4, 1, dark, s)
        rect(draw, ox + 24, oy + 15, 4, 1, dark, s)
        rect(draw, ox + 14, oy + 16, 2, 1, dark, s)
        rect(draw, ox + 25, oy + 16, 2, 1, dark, s)
    else:
        rect(draw, ox + 13, oy + 13, 4, 5, white, s)
        rect(draw, ox + 24, oy + 13, 4, 5, white, s)
        rect(draw, ox + 15, oy + 15, 2, 3, dark, s)
        rect(draw, ox + 24, oy + 15, 2, 3, dark, s)
    rect(draw, ox + 19, oy + 18, 3, 2, PINK, s)
    rect(draw, ox + 15, oy + 27, 11, 2, accent, s)

    if row == 7:
        for n in range(3):
            rect(draw, ox + 3 - n * 3, oy + 16 + n * 5, 3, 1, accent, s)
    elif row == 8:
        rect(draw, ox + 33, oy + 8, 2, 2, YELLOW, s)
        rect(draw, ox + 36, oy + 5, 1, 1, YELLOW, s)
    return image


def make_sheet() -> list[Image.Image]:
    frames = [byte_cat(index) for index in range(COLS * ROWS)]
    sheet = Image.new("RGBA", (CELL_W * COLS, CELL_H * ROWS), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, ((index % COLS) * CELL_W, (index // COLS) * CELL_H))
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(SHEET, "WEBP", lossless=True, method=6)
    return frames


def demo_frame(cat: Image.Image, tick: int, state: str) -> Image.Image:
    canvas = Image.new("RGB", (960, 540), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((28, 24, 932, 516), radius=18, fill=PANEL, outline="#45475a", width=2)
    draw.rectangle((28, 24, 932, 62), fill="#1e1e2e")
    for x, color in ((52, "#f38ba8"), (76, YELLOW), (100, "#a6e3a1")):
        draw.ellipse((x - 6, 43 - 6, x + 6, 43 + 6), fill=color)
    draw.text((124, 34), "kitty — terminal pets, minus the keyboard drama", font=font(16), fill=MUTED)

    draw.text((58, 96), "santosh@kitty  ~", font=font(18), fill=MINT)
    draw.text((58, 128), "$ kitty-pet select byte-cat", font=font(20), fill=TEXT)
    draw.text((58, 172), "Selected Byte Cat. Nice choice.", font=font(17), fill=MUTED)
    draw.text((58, 228), "$ npm test", font=font(20), fill=TEXT)
    if state == "running":
        dots = "." * (tick % 4)
        draw.text((58, 272), f"Running tests{dots:<3}", font=font(18), fill=BLUE)
    elif state == "success":
        draw.text((58, 272), "✓ 42 tests passed", font=font(18), fill="#a6e3a1")
    else:
        draw.text((58, 272), "Ready when you are.", font=font(18), fill=MUTED)
    draw.text((58, 418), "$ ", font=font(20), fill=TEXT)
    if tick % 8 < 5:
        draw.rectangle((82, 419, 94, 441), fill=TEXT)

    # Borderless right rail: it is part of the layout, but deliberately has no
    # internal separator line.
    scaled = cat.resize((144, 156), Image.Resampling.NEAREST)
    canvas.paste(scaled, (750, 286), scaled)
    draw.text((775, 456), state, font=font(15), fill=MUTED)
    return canvas


def make_demo(frames: list[Image.Image]) -> None:
    timeline: list[Image.Image] = []
    for tick in range(72):
        if tick < 16:
            state, indices = "idle", [0, 1, 2, 3, 4, 5]
        elif tick < 52:
            state, indices = "running", [56, 57, 58, 59, 60, 61]
        elif tick < 62:
            state, indices = "success", [64, 65, 66, 67, 68, 69]
        else:
            state, indices = "idle", [0, 1, 2, 3, 4, 5]
        timeline.append(demo_frame(frames[indices[tick % len(indices)]], tick, state))
    DEMO.parent.mkdir(parents=True, exist_ok=True)
    timeline[0].save(DEMO, save_all=True, append_images=timeline[1:], duration=100, loop=0, optimize=True)
    timeline[28].save(PREVIEW, optimize=True)


if __name__ == "__main__":
    generated = make_sheet()
    make_demo(generated)
    print(f"Generated {SHEET.relative_to(ROOT)}, {DEMO.relative_to(ROOT)}, and {PREVIEW.relative_to(ROOT)}")
