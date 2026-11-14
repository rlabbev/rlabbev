#!/usr/bin/env python3
"""Genera la tarjeta de contribuciones (claro y oscuro) desde el calendario público de GitHub.

El calendario público incluye las contribuciones privadas cuando está activado
"Include private contributions on my profile", así que no hace falta ningún token.

Uso: python3 contrib_card.py <usuario> <carpeta_salida> [archivo_html_local]
"""
import datetime as dt
import html
import re
import sys
import urllib.request
from pathlib import Path

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

THEMES = {
    "light": {
        "bg": "#FFFFFF", "border": "#E5E7EB", "text": "#1F2328", "muted": "#57606A",
        "accent": "#C2410C", "levels": ["#EEF0F3", "#FED7AA", "#FDBA74", "#F97316", "#EC4899"],
    },
    "dark": {
        "bg": "#0D1117", "border": "#30363D", "text": "#E6EDF3", "muted": "#8B949E",
        "accent": "#FB923C", "levels": ["#1F242C", "#7C2D12", "#C2410C", "#F97316", "#EC4899"],
    },
}


def fetch(user: str) -> str:
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "contrib-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse(page: str) -> list[tuple[dt.date, int, int]]:
    """Devuelve [(fecha, contribuciones, nivel 0-4)] ordenado por fecha."""
    counts = {}
    for cid, text in re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        m = re.match(r"\s*(\d[\d,]*) contributions?", text)
        counts[cid] = int(m.group(1).replace(",", "")) if m else 0
    days = []
    for td in re.findall(r"<td[^>]*data-date=[^>]*>", page):
        date = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', td).group(1)
        cid = re.search(r'\bid="([^"]+)"', td).group(1)
        level = int(re.search(r'data-level="(\d)"', td).group(1))
        days.append((dt.date.fromisoformat(date), counts.get(cid, 0), level))
    if not days:
        sys.exit("No se encontraron días en el calendario: ¿cambió el HTML de GitHub?")
    return sorted(days)


def stats(days):
    total = sum(c for _, c, _ in days)
    longest = run = 0
    for _, c, _ in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    # Racha actual: si hoy aún no hay contribuciones, se cuenta desde ayer.
    current = 0
    seq = [c for _, c, _ in days]
    if seq and seq[-1] == 0:
        seq = seq[:-1]
    for c in reversed(seq):
        if c == 0:
            break
        current += 1
    best_date, best = max(((d, c) for d, c, _ in days), key=lambda x: x[1])
    active = sum(1 for _, c, _ in days if c > 0)
    return total, current, longest, best, best_date, active


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def render(days, theme: dict, user: str) -> str:
    total, current, longest, best, best_date, active = stats(days)
    cell, gap, left, top = 11, 3, 24, 128
    start = days[0][0]
    first_sunday = start - dt.timedelta(days=(start.weekday() + 1) % 7)
    weeks = (days[-1][0] - first_sunday).days // 7 + 1
    width = left + weeks * (cell + gap) + 21
    height = top + 7 * (cell + gap) + 34
    t = theme

    def stat(x, value, label):
        return (
            f'<text x="{x}" y="64" class="num">{value}</text>'
            f'<text x="{x}" y="86" class="lbl">{label}</text>'
        )

    col = (width - 2 * left) / 4
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Contribuciones de {user}">',
        "<style>"
        f".num{{font:700 26px 'Segoe UI',Ubuntu,sans-serif;fill:{t['accent']}}}"
        f".lbl{{font:500 12px 'Segoe UI',Ubuntu,sans-serif;fill:{t['muted']}}}"
        f".ttl{{font:600 15px 'Segoe UI',Ubuntu,sans-serif;fill:{t['text']}}}"
        f".sm{{font:400 10px 'Segoe UI',Ubuntu,sans-serif;fill:{t['muted']}}}"
        "</style>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<text x="{left}" y="28" class="ttl">Contribuciones del último año</text>',
        stat(left, fmt(total), "contribuciones totales"),
        stat(left + col, f"{current} días", "racha actual"),
        stat(left + 2 * col, f"{longest} días", "racha más larga"),
        stat(left + 3 * col, f"{active} días", "con actividad"),
    ]
    last_month = None
    for d, c, lvl in days:
        w = (d - first_sunday).days // 7
        x = left + w * (cell + gap)
        y = top + ((d.weekday() + 1) % 7) * (cell + gap)
        if d.day <= 7 and d.month != last_month and w < weeks - 1:
            parts.append(f'<text x="{x}" y="{top - 8}" class="sm">{MESES[d.month - 1]}</text>')
            last_month = d.month
        label = html.escape(f"{c} contribuciones el {d.day} {MESES[d.month - 1]} {d.year}")
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{t["levels"][lvl]}"><title>{label}</title></rect>'
        )
    lx = width - left - 5 * (cell + gap) - 70
    ly = height - 18
    parts.append(f'<text x="{lx}" y="{ly + 9}" class="sm">Menos</text>')
    for i, color in enumerate(t["levels"]):
        parts.append(
            f'<rect x="{lx + 34 + i * (cell + gap)}" y="{ly}" width="{cell}" height="{cell}" '
            f'rx="2" fill="{color}"/>'
        )
    parts.append(f'<text x="{lx + 34 + 5 * (cell + gap) + 4}" y="{ly + 9}" class="sm">Más</text>')
    parts.append(
        f'<text x="{left}" y="{ly + 9}" class="sm">Día más activo: '
        f"{best_date.day} {MESES[best_date.month - 1]} ({best} contribuciones) · incluye repos privados</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    user, out = sys.argv[1], Path(sys.argv[2])
    page = Path(sys.argv[3]).read_text(encoding="utf-8") if len(sys.argv) > 3 else fetch(user)
    days = parse(page)
    out.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (out / f"contributions-{name}.svg").write_text(render(days, theme, user), encoding="utf-8")
    total, current, longest, best, _, active = stats(days)
    print(f"{len(days)} días · total={total} · racha={current} · más larga={longest} · activos={active}")


if __name__ == "__main__":
    main()
