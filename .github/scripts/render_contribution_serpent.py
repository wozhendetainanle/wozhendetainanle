from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw


W, H = 880, 238
COLS, ROWS = 53, 7
CELL, GAP = 10, 5
PITCH = CELL + GAP
GRID_W = COLS * PITCH - GAP
GRID_H = ROWS * PITCH - GAP
GX = (W - GRID_W) // 2
GY = 53

SOURCE_COLORS = ["#D8D4CC", "#CFDAD5", "#A9C2B9", "#6B8583", "#4E6361"]

PALETTES = {
    "light": {
        "matte": "#FFFFFF",
        "paper": "#F2EFE9",
        "border": "#DDD8CF",
        "empty": "#DDD9D1",
        "levels": ["#CEDBD5", "#ABC4BB", "#76968F", "#506B68"],
        "snake_tail": "#C58B70",
        "snake_head": "#9E5744",
        "shadow": "#D8CDC4",
        "eye": "#352F2C",
        "tongue": "#7F443B",
    },
    "dark": {
        "matte": "#0D1117",
        "paper": "#1B1E1C",
        "border": "#343A36",
        "empty": "#303530",
        "levels": ["#3E4B46", "#607A72", "#8DA99F", "#B8CDC6"],
        "snake_tail": "#B7745B",
        "snake_head": "#E2A083",
        "shadow": "#101311",
        "eye": "#2A2522",
        "tongue": "#F1B8A4",
    },
}


def rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def mix(first: str, second: str, amount: float) -> tuple[int, int, int]:
    a, b = rgb(first), rgb(second)
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))


def contribution_levels(source: Path) -> list[list[int]]:
    image = Image.open(source)
    image.seek(0)
    frame = image.convert("RGB")
    colors = [rgb(color) for color in SOURCE_COLORS]
    levels: list[list[int]] = []

    for row in range(ROWS):
        line = []
        for column in range(COLS):
            sample = frame.getpixel((22 + column * 16, 22 + row * 16))
            level = min(
                range(len(colors)),
                key=lambda index: sum(
                    (sample[channel] - colors[index][channel]) ** 2
                    for channel in range(3)
                ),
            )
            line.append(level)
        levels.append(line)

    return levels


def draw_cell(
    draw: ImageDraw.ImageDraw,
    center_x: float,
    center_y: float,
    fill: str,
) -> None:
    half = CELL / 2
    draw.rounded_rectangle(
        (
            center_x - half,
            center_y - half,
            center_x + half,
            center_y + half,
        ),
        radius=3,
        fill=fill,
    )


def build_closed_route() -> tuple[list[tuple[float, float]], float]:
    points: list[tuple[float, float]] = []
    left = GX + CELL / 2
    right = GX + GRID_W - CELL / 2
    top = GY + CELL / 2
    bottom = GY + GRID_H - CELL / 2
    entry_x = GX - 31

    points.append((entry_x, top))
    for row in range(ROWS):
        y = top + row * PITCH
        points.append((right if row % 2 == 0 else left, y))
        if row < ROWS - 1:
            points.append((right if row % 2 == 0 else left, y + PITCH))

    grid_end_index = len(points) - 1
    points.extend(
        [
            (GX + GRID_W + 30, bottom),
            (GX + GRID_W + 30, H - 28),
            (GX - 31, H - 28),
            (GX - 31, top),
        ]
    )

    route: list[tuple[float, float]] = [points[0]]
    grid_end_distance = 0.0
    total = 0.0
    for index, (start, end) in enumerate(zip(points, points[1:]), start=1):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        steps = max(1, math.ceil(length / 3.0))
        for step in range(1, steps + 1):
            route.append(
                (
                    start[0] + dx * step / steps,
                    start[1] + dy * step / steps,
                )
            )
        total += length
        if index == grid_end_index:
            grid_end_distance = total

    return route, grid_end_distance


def cumulative_distances(points: list[tuple[float, float]]) -> list[float]:
    result = [0.0]
    for start, end in zip(points, points[1:]):
        result.append(result[-1] + math.dist(start, end))
    return result


def point_at(
    points: list[tuple[float, float]],
    distances: list[float],
    distance: float,
) -> tuple[float, float]:
    distance %= distances[-1]
    low, high = 0, len(distances) - 1
    while low + 1 < high:
        middle = (low + high) // 2
        if distances[middle] <= distance:
            low = middle
        else:
            high = middle

    start, end = points[low], points[low + 1]
    span = distances[low + 1] - distances[low]
    amount = 0 if span == 0 else (distance - distances[low]) / span
    return (
        start[0] + (end[0] - start[0]) * amount,
        start[1] + (end[1] - start[1]) * amount,
    )


def route_distance_for_cell(row: int, column: int) -> float:
    row_width = GRID_W - CELL
    distance = 31 + CELL / 2
    for _ in range(row):
        distance += row_width + PITCH
    position = (
        column * PITCH
        if row % 2 == 0
        else (COLS - 1 - column) * PITCH
    )
    return distance + position


def draw_frame(
    theme: str,
    progress: float,
    levels: list[list[int]],
    route: list[tuple[float, float]],
    distances: list[float],
    grid_end: float,
) -> Image.Image:
    palette = PALETTES[theme]
    image = Image.new("RGB", (W, H), palette["matte"])
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (7, 7, W - 8, H - 8),
        radius=18,
        fill=palette["paper"],
        outline=palette["border"],
        width=1,
    )

    total = distances[-1]
    return_phase = max(
        0.0,
        min(1.0, (progress - grid_end) / max(1.0, total - grid_end)),
    )

    for row in range(ROWS):
        for column in range(COLS):
            center_x = GX + CELL / 2 + column * PITCH
            center_y = GY + CELL / 2 + row * PITCH
            level = levels[row][column]
            eaten = (
                progress < grid_end
                and route_distance_for_cell(row, column) <= progress
            )
            regrown = (
                progress >= grid_end
                and column / max(1, COLS - 1) <= return_phase
            )
            visible = not eaten if progress < grid_end else regrown
            color = (
                palette["empty"]
                if level == 0 or not visible
                else palette["levels"][level - 1]
            )
            draw_cell(draw, center_x, center_y, color)

    body_count = 21
    spacing = 10.2
    body = [
        point_at(route, distances, progress - index * spacing)
        for index in range(body_count)
    ]

    for index in range(body_count - 1, -1, -1):
        x, y = body[index]
        taper = 1.0 - (index / body_count) * 0.42
        radius = 6.7 * taper
        draw.ellipse(
            (x - radius + 1, y - radius + 2, x + radius + 1, y + radius + 2),
            fill=palette["shadow"],
        )

    for index in range(body_count - 1, -1, -1):
        x, y = body[index]
        taper = 1.0 - (index / body_count) * 0.42
        radius = 6.5 * taper
        color = mix(
            palette["snake_head"],
            palette["snake_tail"],
            index / (body_count - 1),
        )
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=color,
        )

    head_x, head_y = body[0]
    next_x, next_y = point_at(route, distances, progress + 7)
    direction_x, direction_y = next_x - head_x, next_y - head_y
    norm = max(0.001, math.hypot(direction_x, direction_y))
    direction_x, direction_y = direction_x / norm, direction_y / norm
    perpendicular_x, perpendicular_y = -direction_y, direction_x

    for side in (-1, 1):
        eye_x = head_x + direction_x * 2.8 + perpendicular_x * side * 3.0
        eye_y = head_y + direction_y * 2.8 + perpendicular_y * side * 3.0
        draw.ellipse(
            (eye_x - 1.25, eye_y - 1.25, eye_x + 1.25, eye_y + 1.25),
            fill=palette["eye"],
        )

    if int(progress / 18) % 7 in (0, 1):
        tongue_x = head_x + direction_x * 10.5
        tongue_y = head_y + direction_y * 10.5
        tongue_base_x = head_x + direction_x * 6.2
        tongue_base_y = head_y + direction_y * 6.2
        draw.line(
            (tongue_base_x, tongue_base_y, tongue_x, tongue_y),
            fill=palette["tongue"],
            width=1,
        )
        draw.line(
            (
                tongue_x,
                tongue_y,
                tongue_x + direction_x * 3 + perpendicular_x * 2,
                tongue_y + direction_y * 3 + perpendicular_y * 2,
            ),
            fill=palette["tongue"],
            width=1,
        )
        draw.line(
            (
                tongue_x,
                tongue_y,
                tongue_x + direction_x * 3 - perpendicular_x * 2,
                tongue_y + direction_y * 3 - perpendicular_y * 2,
            ),
            fill=palette["tongue"],
            width=1,
        )

    return image


def render(
    target: Path,
    theme: str,
    levels: list[list[int]],
    route: list[tuple[float, float]],
    distances: list[float],
    grid_end: float,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    frame_count = 300
    frames = [
        draw_frame(
            theme,
            distances[-1] * index / frame_count,
            levels,
            route,
            distances,
            grid_end,
        )
        for index in range(frame_count)
    ]
    frames[0].save(
        target,
        save_all=True,
        append_images=frames[1:],
        duration=55,
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

    levels = contribution_levels(args.source)
    route, grid_end = build_closed_route()
    distances = cumulative_distances(route)
    render(args.light_output, "light", levels, route, distances, grid_end)
    render(args.dark_output, "dark", levels, route, distances, grid_end)


if __name__ == "__main__":
    main()
