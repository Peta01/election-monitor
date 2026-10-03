from __future__ import annotations

from html import escape

PALETTE = [
    "#2475b9", "#d9480f", "#2f9e44", "#9c36b5", "#e8a900", "#0c8599",
    "#c2255c", "#5f3dc4", "#66a80f", "#e8590c", "#364fc7", "#868e96",
]


def color_for(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def line_chart_svg(
    series: list[tuple[str, list[tuple[int, float]]]],
    x_max: int,
    y_label: str,
    y_max: float | None = None,
    label: str = "Graf",
) -> str:
    """Čárový graf v SVG; x je počet zpracovaných okrsků, barvy odpovídají pořadí řad."""
    width, height = 760, 340
    left, right, top, bottom = 52, 16, 14, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    highest = max((y for _, points in series for _, y in points), default=0)
    y_top = y_max if y_max is not None else max(highest * 1.1, 1)
    x_top = max(x_max, 1)

    def px(x: float) -> float:
        return left + plot_w * x / x_top

    def py(y: float) -> float:
        return top + plot_h * (1 - min(y, y_top) / y_top)

    parts = [
        (
            f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="{escape(label, quote=True)}">'
        )
    ]
    for step in range(5):
        value = y_top * step / 4
        y = py(value)
        parts.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" '
            'stroke="var(--border-subtle)"/>'
            f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="var(--text-muted)" font-size="11">{value:.0f}</text>'
        )
    tick_count = min(x_top, 8)
    for step in range(tick_count + 1):
        value = round(x_top * step / tick_count)
        parts.append(
            f'<text x="{px(value):.1f}" y="{height - bottom + 16}" text-anchor="middle" '
            f'fill="var(--text-muted)" font-size="11">{value}</text>'
        )
    parts.append(
        f'<text x="{left + plot_w / 2}" y="{height - 6}" text-anchor="middle" '
        'fill="var(--text-muted)" font-size="12">Zpracované okrsky</text>'
        f'<text x="12" y="{top + plot_h / 2}" text-anchor="middle" fill="var(--text-muted)" '
        f'font-size="12" transform="rotate(-90 12 {top + plot_h / 2})">{escape(y_label)}</text>'
    )
    for index, (name, points) in enumerate(series):
        color = color_for(index)
        coords = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in points)
        if len(points) > 1:
            parts.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{coords}"/>'
            )
        parts.extend(
            f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.5" fill="{color}">'
            f"<title>{escape(name)}: {y:g} ({x} okrsků)</title></circle>"
            for x, y in points
        )
    parts.append("</svg>")
    return "".join(parts)


def legend_html(names: list[str]) -> str:
    items = "".join(
        f'<li><span class="swatch" style="background:{color_for(index)}"></span>'
        f"{escape(name)}</li>"
        for index, name in enumerate(names)
    )
    return f'<ul class="legend">{items}</ul>'
