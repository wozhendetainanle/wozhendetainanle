from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageSequence


W, H, SCALE = 880, 240, 2
COLS, ROWS = 53, 7
CELL, PITCH = 5, 8
GX, GY = 202, 75
GRID_W = (COLS - 1) * PITCH
GRID_H = (ROWS - 1) * PITCH

SOURCE_COLORS = ["#D8D4CC", "#CFDAD5", "#A9C2B9", "#6B8583", "#4E6361"]

PALETTES = {
    "light": {
        "bg": "#F1EEE8",
        "ink": "#4E5552",
        "muted": "#A9A49A",
        "faint": "#D8D4CC",
        "grid": "#D8D4CC",
        "levels": ["#CEDBD5", "#A9C2B9", "#6B8583", "#4E6361"],
        "terracotta": "#A96049",
        "terracotta_soft": "#C98B70",
        "teal": "#5F7C76",
        "teal_soft": "#9CB6AE",
        "gold": "#C49A55",
        "shadow": "#D7CFC5",
    },
    "dark": {
        "bg": "#141816",
        "ink": "#C7CEC9",
        "muted": "#76817B",
        "faint": "#303732",
        "grid": "#2D342F",
        "levels": ["#3E4B46", "#607A72", "#8DA99F", "#B8CDC6"],
        "terracotta": "#E0A083",
        "terracotta_soft": "#B8745C",
        "teal": "#8DA99F",
        "teal_soft": "#536D66",
        "gold": "#D5AC69",
        "shadow": "#0B0E0C",
    },
}


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def mix(first: str, second: str, amount: float) -> tuple[int, int, int]:
    a, b = rgb(first), rgb(second)
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))


def levels_from_source(source: Path) -> list[list[int]]:
    image = Image.open(source)
    colors = [rgb(color) for color in SOURCE_COLORS]
    levels = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    for source_frame in ImageSequence.Iterator(image):
        frame = source_frame.convert("RGB")
        for row in range(ROWS):
            for column in range(COLS):
                sample = frame.getpixel((22 + column * 16, 22 + row * 16))
                distances = [
                    sum((sample[channel] - color[channel]) ** 2 for channel in range(3))
                    for color in colors
                ]
                candidate = min(range(5), key=distances.__getitem__)
                if distances[candidate] <= 12**2 * 3:
                    levels[row][column] = max(levels[row][column], candidate)
    return levels


def build_grid_route() -> tuple[list[tuple[float, float]], list[float]]:
    left, right = GX, GX + GRID_W
    top = GY
    route = [(left - 22, top)]

    def append_line(end: tuple[float, float], wave_phase: float = 0) -> None:
        start = route[-1]
        length = math.dist(start, end)
        steps = max(1, math.ceil(length / 2))
        for step in range(1, steps + 1):
            amount = step / steps
            envelope = math.sin(math.pi * amount)
            route.append(
                (
                    start[0] + (end[0] - start[0]) * amount,
                    start[1]
                    + (end[1] - start[1]) * amount
                    + math.sin(amount * math.tau * 2 + wave_phase) * envelope * 1.1,
                )
            )

    for row in range(ROWS):
        y = top + row * PITCH
        append_line((right if row % 2 == 0 else left, y), row * 0.8)
        if row < ROWS - 1:
            center_x = right if row % 2 == 0 else left
            center_y = y + PITCH / 2
            for step in range(1, 17):
                angle = -math.pi / 2 + math.pi * step / 16
                direction = 1 if row % 2 == 0 else -1
                route.append(
                    (
                        center_x + direction * PITCH / 2 * math.cos(angle),
                        center_y + PITCH / 2 * math.sin(angle),
                    )
                )

    distances = [0.0]
    for start, end in zip(route, route[1:]):
        distances.append(distances[-1] + math.dist(start, end))
    return route, distances


def point_at(route, distances, distance):
    distance = max(0.0, min(distance, distances[-1]))
    low, high = 0, len(distances) - 1
    while low + 1 < high:
        middle = (low + high) // 2
        if distances[middle] <= distance:
            low = middle
        else:
            high = middle
    span = distances[low + 1] - distances[low]
    amount = 0 if span == 0 else (distance - distances[low]) / span
    start, end = route[low], route[low + 1]
    return (
        start[0] + (end[0] - start[0]) * amount,
        start[1] + (end[1] - start[1]) * amount,
    )


def cell_distance(row: int, column: int) -> float:
    row_width = GRID_W
    distance = 22
    for _ in range(row):
        distance += row_width + math.pi * PITCH / 2
    position = column * PITCH if row % 2 == 0 else (COLS - 1 - column) * PITCH
    return distance + position


def scale_points(points):
    return [(x * SCALE, y * SCALE) for x, y in points]


def draw_monogram(draw: ImageDraw.ImageDraw, palette, phase: float) -> None:
    center_x, center_y, radius = 92, 94, 47
    box = tuple(value * SCALE for value in (
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius,
    ))
    draw.arc(
        box,
        start=38,
        end=322,
        fill=palette["terracotta"],
        width=6 * SCALE,
    )

    # The L doubles as a two-link embodied trajectory.
    draw.line(
        scale_points([(104, 55), (104, 132), (148, 132)]),
        fill=palette["teal"],
        width=5 * SCALE,
        joint="curve",
    )
    for x, y in ((104, 55), (104, 132), (148, 132)):
        pulse = 3.3 + 0.45 * math.sin(phase * math.tau * 2 + x)
        draw.ellipse(
            tuple(value * SCALE for value in (x - pulse, y - pulse, x + pulse, y + pulse)),
            fill=palette["gold"] if (x, y) == (148, 132) else palette["bg"],
            outline=palette["teal"],
            width=2 * SCALE,
        )

    font_name = ImageFont.load_default(size=18 * SCALE)
    draw.text((45 * SCALE, 157 * SCALE), "CHENGTAI LI", font=font_name, fill=palette["ink"])


GRAPH_NODES = [(661, 66), (693, 51), (722, 78), (684, 103), (727, 119), (751, 91)]
GRAPH_EDGES = [(0, 1), (0, 3), (1, 2), (1, 3), (2, 5), (3, 4), (4, 5), (2, 4)]


def draw_reasoning(draw: ImageDraw.ImageDraw, palette, phase: float) -> tuple[float, float]:
    active = max(0.0, min(1.0, (phase - 0.70) / 0.18))
    for edge_index, (first, second) in enumerate(GRAPH_EDGES):
        a, b = GRAPH_NODES[first], GRAPH_NODES[second]
        edge_color = mix(palette["faint"], palette["teal"], active * 0.72)
        draw.line(scale_points([a, b]), fill=edge_color, width=SCALE)
        if active > 0:
            amount = (active * 2.1 - edge_index * 0.13) % 1
            pulse_x = a[0] + (b[0] - a[0]) * amount
            pulse_y = a[1] + (b[1] - a[1]) * amount
            radius = 1.7 * SCALE
            draw.ellipse(
                (
                    pulse_x * SCALE - radius,
                    pulse_y * SCALE - radius,
                    pulse_x * SCALE + radius,
                    pulse_y * SCALE + radius,
                ),
                fill=palette["gold"],
            )
    for index, (x, y) in enumerate(GRAPH_NODES):
        node_active = max(0, min(1, active * 7 - index * 0.8))
        radius = (3 + node_active * 1.4) * SCALE
        draw.ellipse(
            (x * SCALE - radius, y * SCALE - radius, x * SCALE + radius, y * SCALE + radius),
            fill=mix(palette["bg"], palette["teal_soft"], node_active),
            outline=palette["teal"],
            width=2 * SCALE,
        )
    return GRAPH_NODES[-1]


def draw_robot(draw: ImageDraw.ImageDraw, palette, phase: float) -> tuple[float, float]:
    action = max(0.0, min(1.0, (phase - 0.84) / 0.12))
    eased = action * action * (3 - 2 * action)
    base = (783, 190)
    shoulder = (793, 165)
    elbow = (820 - 8 * eased, 137 - 8 * eased)
    wrist = (842 - 5 * eased, 107 + 3 * eased)
    target = (851, 91)

    draw.ellipse(tuple(value * SCALE for value in (765, 186, 801, 201)), fill=palette["faint"])
    draw.line(scale_points([shoulder, elbow, wrist]), fill=palette["teal"], width=8 * SCALE, joint="curve")
    for x, y in (shoulder, elbow, wrist):
        radius = 5 * SCALE
        draw.ellipse(
            (x * SCALE - radius, y * SCALE - radius, x * SCALE + radius, y * SCALE + radius),
            fill=palette["bg"],
            outline=palette["teal"],
            width=3 * SCALE,
        )

    direction_x, direction_y = target[0] - wrist[0], target[1] - wrist[1]
    norm = max(0.001, math.hypot(direction_x, direction_y))
    direction_x, direction_y = direction_x / norm, direction_y / norm
    perpendicular_x, perpendicular_y = -direction_y, direction_x
    opening = 6 * (1 - eased) + 2
    palm = (wrist[0] + direction_x * 7, wrist[1] + direction_y * 7)
    draw.line(scale_points([wrist, palm]), fill=palette["terracotta"], width=4 * SCALE)
    for side in (-1, 1):
        start = (
            palm[0] + perpendicular_x * opening * side,
            palm[1] + perpendicular_y * opening * side,
        )
        end = (
            target[0] - direction_x * 2 + perpendicular_x * opening * 0.45 * side,
            target[1] - direction_y * 2 + perpendicular_y * opening * 0.45 * side,
        )
        draw.line(scale_points([start, end]), fill=palette["terracotta"], width=3 * SCALE)

    target_radius = (3.5 + 0.6 * math.sin(phase * math.tau * 4)) * SCALE
    draw.ellipse(
        (
            target[0] * SCALE - target_radius,
            target[1] * SCALE - target_radius,
            target[0] * SCALE + target_radius,
            target[1] * SCALE + target_radius,
        ),
        fill=palette["gold"],
    )
    return target


def draw_frame(theme: str, phase: float, levels, route, distances) -> Image.Image:
    p = PALETTES[theme]
    image = Image.new("RGB", (W * SCALE, H * SCALE), p["bg"])
    draw = ImageDraw.Draw(image)

    # One quiet baseline binds identity, learning, reasoning, and action.
    draw.line(scale_points([(178, 211), (855, 211)]), fill=p["faint"], width=SCALE)
    draw_monogram(draw, p, phase)

    font = ImageFont.load_default(size=8 * SCALE)
    draw.text((GX * SCALE, 48 * SCALE), "LEARN", font=font, fill=p["muted"])

    snake_phase = min(1.0, phase / 0.70)
    progress = distances[-1] * snake_phase
    for row in range(ROWS):
        for column in range(COLS):
            x, y = GX + column * PITCH, GY + row * PITCH
            level = levels[row][column]
            passed = cell_distance(row, column) <= progress
            fill = p["grid"] if level == 0 or passed else p["levels"][level - 1]
            wake = progress - cell_distance(row, column)
            if 0 < wake < 80 and level == 0:
                fill = mix(fill, p["teal_soft"], 0.5 * (1 - wake / 80))
            half = CELL * SCALE / 2
            draw.rounded_rectangle(
                (x * SCALE - half, y * SCALE - half, x * SCALE + half, y * SCALE + half),
                radius=2 * SCALE,
                fill=fill,
            )

    body = [point_at(route, distances, progress - index * 4.8) for index in range(25)]
    for index in range(23, -1, -1):
        amount = index / 24
        width = round((3.5 + 7 * (1 - amount)) * SCALE)
        start, end = body[index + 1], body[index]
        color = mix(p["terracotta"], p["terracotta_soft"], amount)
        draw.line(scale_points([start, end]), fill=color, width=width)
        radius = width / 2
        draw.ellipse(
            (end[0] * SCALE - radius, end[1] * SCALE - radius, end[0] * SCALE + radius, end[1] * SCALE + radius),
            fill=color,
        )

    head_x, head_y = body[0]
    next_x, next_y = point_at(route, distances, min(progress + 6, distances[-1]))
    dx, dy = next_x - head_x, next_y - head_y
    norm = max(0.001, math.hypot(dx, dy))
    dx, dy = dx / norm, dy / norm
    px, py = -dy, dx
    for side in (-1, 1):
        eye_x = head_x + dx * 2.2 + px * side * 2.2
        eye_y = head_y + dy * 2.2 + py * side * 2.2
        radius = 1.1 * SCALE
        draw.ellipse(
            (eye_x * SCALE - radius, eye_y * SCALE - radius, eye_x * SCALE + radius, eye_y * SCALE + radius),
            fill=p["bg"],
        )

    graph_out = draw_reasoning(draw, p, phase)
    robot_target = draw_robot(draw, p, phase)

    # A single signal visibly turns accumulated activity into reasoning and action.
    if phase >= 0.68:
        signal_phase = min(1.0, (phase - 0.68) / 0.25)
        signal_path = [
            (GX + GRID_W, GY + GRID_H),
            (642, 128),
            *GRAPH_NODES,
            (772, 116),
            robot_target,
        ]
        segment_lengths = [math.dist(a, b) for a, b in zip(signal_path, signal_path[1:])]
        total_length = sum(segment_lengths)
        target_distance = total_length * signal_phase
        traversed = 0.0
        signal = signal_path[0]
        for start, end, length in zip(signal_path, signal_path[1:], segment_lengths):
            if traversed + length >= target_distance:
                amount = (target_distance - traversed) / max(0.001, length)
                signal = (
                    start[0] + (end[0] - start[0]) * amount,
                    start[1] + (end[1] - start[1]) * amount,
                )
                break
            traversed += length
        radius = 3.2 * SCALE
        draw.ellipse(
            (signal[0] * SCALE - radius, signal[1] * SCALE - radius, signal[0] * SCALE + radius, signal[1] * SCALE + radius),
            fill=p["gold"],
        )

    # Keep the 2x drawing surface in the exported GIF. GitHub displays the
    # image at roughly 880 CSS pixels wide, so 1760 physical pixels preserve
    # crisp type, graph edges, joints, and rounded contribution cells on
    # Retina/HiDPI screens.
    return image


def render(target: Path, theme: str, levels, route, distances) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    frames = [draw_frame(theme, index / 360, levels, route, distances) for index in range(360)]

    # A shared palette avoids the large per-frame color tables that would
    # otherwise make the 2x GIF unnecessarily heavy. Sampling the beginning,
    # reasoning, and action phases preserves every semantic accent color.
    palette_source = Image.new("RGB", (W * SCALE, H * SCALE * 4))
    for slot, frame_index in enumerate((0, 180, 285, 345)):
        palette_source.paste(frames[frame_index], (0, slot * H * SCALE))
    shared_palette = palette_source.quantize(
        colors=160,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    quantized_frames = [
        frame.quantize(palette=shared_palette, dither=Image.Dither.NONE)
        for frame in frames
    ]

    quantized_frames[0].save(
        target,
        save_all=True,
        append_images=quantized_frames[1:],
        duration=70,
        loop=0,
        optimize=True,
        disposal=1,
    )
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--light-output", type=Path, required=True)
    parser.add_argument("--dark-output", type=Path, required=True)
    args = parser.parse_args()

    levels = levels_from_source(args.source)
    route, distances = build_grid_route()
    render(args.light_output, "light", levels, route, distances)
    render(args.dark_output, "dark", levels, route, distances)


if __name__ == "__main__":
    main()
