"""Render LinkedIn carousel slides that match the KPI dashboard's style.

Produces two PNGs (same 13x5.2 @150dpi canvas as reports/kpi_dashboard.png):
    reports/slide_star_schema.png   — the dimensional model
    reports/slide_before_after.png  — raw wide table -> clean star schema

Usage:
    python scripts/make_carousel.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

REPORTS_DIR = config.BASE_DIR / "reports"

# Shared palette (matches scripts/plot_kpis.py).
INK = "#1f2937"
ACCENT = "#2563eb"
ACCENT_FILL = "#dbeafe"
GOOD = "#059669"
GOOD_FILL = "#d1fae5"
BAD = "#dc2626"
AMBER = "#d97706"
MUTED = "#9ca3af"
GRID = "#e5e7eb"

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})


def _new_canvas():
    fig, ax = plt.subplots(figsize=(13, 5.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def _table_box(ax, x, y, w, h, title, rows, edge, fill, title_fill):
    """Draw a rounded 'table' card with a title bar and a list of fields."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.4,rounding_size=2.2",
        linewidth=1.8, edgecolor=edge, facecolor=fill, zorder=2,
    ))
    # Title bar.
    ax.add_patch(FancyBboxPatch(
        (x, y + h - 7), w, 7, boxstyle="round,pad=0.4,rounding_size=2.2",
        linewidth=0, facecolor=title_fill, zorder=3,
    ))
    ax.text(x + w / 2, y + h - 3.5, title, ha="center", va="center",
            fontsize=11, fontweight="bold", color="white", zorder=4)
    # Fields.
    for i, (field, note) in enumerate(rows):
        ry = y + h - 11 - i * 4.3
        weight = "bold" if note == "PK" else "normal"
        col = ACCENT if note == "FK" else INK
        ax.text(x + 3, ry, field, ha="left", va="center",
                fontsize=8.7, color=col, fontweight=weight, zorder=4)
        if note:
            ax.text(x + w - 3, ry, note, ha="right", va="center",
                    fontsize=7.5, color=MUTED, style="italic", zorder=4)


def _arrow(ax, p1, p2, color=ACCENT):
    ax.add_patch(FancyArrowPatch(
        p1, p2, arrowstyle="-|>", mutation_scale=16,
        linewidth=1.8, color=color, zorder=1,
    ))


# --------------------------------------------------------------------------- #
# Slide 1 — Star schema
# --------------------------------------------------------------------------- #
def star_schema() -> Path:
    fig, ax = _new_canvas()
    ax.text(50, 95, "Star Schema — modelo dimensional", ha="center",
            fontsize=17, fontweight="bold")
    ax.text(50, 89, "1 tabla de hechos  +  2 dimensiones  ·  joins baratos, sin redundancia",
            ha="center", fontsize=10.5, color=MUTED)

    # Fact table (center).
    fact_rows = [
        ("order_item_id", "PK"),
        ("order_customer_id", "FK"),
        ("product_id", "FK"),
        ("order_date / ship_date", ""),
        ("quantity · sales · profit", ""),
        ("delivery_delay_days", ""),
        ("is_late_delivery", ""),
    ]
    _table_box(ax, 38, 23, 24, 52, "fact_orders", fact_rows,
               ACCENT, ACCENT_FILL, ACCENT)

    # dim_customers (left).
    cust_rows = [("customer_id", "PK"), ("segment", ""), ("city", ""),
                 ("state", ""), ("country", "")]
    _table_box(ax, 5, 35, 22, 30, "dim_customers", cust_rows,
               GOOD, GOOD_FILL, GOOD)

    # dim_products (right).
    prod_rows = [("product_id", "PK"), ("product_name", ""), ("category", ""),
                 ("department", ""), ("list_price", "")]
    _table_box(ax, 73, 35, 22, 30, "dim_products", prod_rows,
               GOOD, GOOD_FILL, GOOD)

    # Relationships (FK -> PK).
    _arrow(ax, (38, 55), (27, 52), color=GOOD)
    _arrow(ax, (62, 52), (73, 52), color=GOOD)
    ax.text(33, 58, "customer_id", ha="center", fontsize=7.5, color=MUTED, style="italic")
    ax.text(67, 56, "product_id", ha="center", fontsize=7.5, color=MUTED, style="italic")

    ax.text(50, 8, "PK = clave primaria      FK = clave foránea",
            ha="center", fontsize=9, color=MUTED)
    ax.text(50, 2.5, "github.com/sxntnx/supply-chain-etl-pipeline",
            ha="center", fontsize=8, color=MUTED)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "slide_star_schema.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# Slide 2 — Before / After
# --------------------------------------------------------------------------- #
def before_after() -> Path:
    fig, ax = _new_canvas()
    ax.text(50, 95, "De datos crudos a un modelo limpio", ha="center",
            fontsize=17, fontweight="bold")
    ax.text(50, 89, "El 80% del trabajo de un analista vive acá: en la transformación",
            ha="center", fontsize=10.5, color=MUTED)

    # --- ANTES: messy wide table -------------------------------------------
    ax.text(15, 80, "ANTES", ha="center", fontsize=12, fontweight="bold", color=BAD)
    ax.text(15, 75.5, "1 tabla  ×  53 columnas", ha="center", fontsize=9, color=MUTED)

    gx, gy, cw, ch = 3, 30, 2.2, 3.6
    ncols, nrows = 11, 11
    for r in range(nrows):
        for c in range(ncols):
            x = gx + c * cw
            y = gy + (nrows - 1 - r) * ch
            face = "#f9fafb"
            edge = GRID
            if c in (1, 2) and r > 0:          # PII columns
                face = "#fee2e2"; edge = BAD
            elif (r, c) in {(3, 5), (6, 8), (8, 3), (2, 9)}:  # nulls
                face = "#fef3c7"; edge = AMBER
            elif r == 9:                        # duplicate row
                face = "#fee2e2"; edge = BAD
            ax.add_patch(FancyBboxPatch(
                (x, y), cw * 0.9, ch * 0.8, boxstyle="square,pad=0",
                linewidth=0.6, edgecolor=edge, facecolor=face, zorder=2))

    # Legend for the messy table.
    ax.text(3, 26, "■ PII (email, password…)", fontsize=8, color=BAD)
    ax.text(3, 22.5, "■ valores nulos", fontsize=8, color=AMBER)
    ax.text(3, 19, "■ filas duplicadas", fontsize=8, color=BAD)

    # --- ARROW with transformations ----------------------------------------
    _arrow(ax, (40, 50), (60, 50))
    steps = ["drop PII", "parse fechas", "normalizar texto",
             "rellenar nulos", "deduplicar", "+ KPIs derivados"]
    for i, s in enumerate(steps):
        ax.text(50, 70 - i * 5.4, s, ha="center", fontsize=8.6,
                color=INK, zorder=5,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=ACCENT, lw=1.1))
    ax.text(50, 36, "TRANSFORM", ha="center", fontsize=9.5,
            fontweight="bold", color=ACCENT)

    # --- DESPUÉS: 3 clean tables -------------------------------------------
    ax.text(85, 80, "DESPUÉS", ha="center", fontsize=12, fontweight="bold", color=GOOD)
    ax.text(85, 75.5, "star schema  ·  3 tablas", ha="center", fontsize=9, color=MUTED)

    clean = [("fact_orders", ACCENT, ACCENT_FILL, 58),
             ("dim_customers", GOOD, GOOD_FILL, 45),
             ("dim_products", GOOD, GOOD_FILL, 32)]
    for name, edge, fill, y in clean:
        ax.add_patch(FancyBboxPatch(
            (72, y), 26, 10, boxstyle="round,pad=0.3,rounding_size=1.6",
            linewidth=1.8, edgecolor=edge, facecolor=fill, zorder=2))
        ax.text(85, y + 5, name, ha="center", va="center",
                fontsize=11, fontweight="bold", color=edge, zorder=3)

    ax.text(85, 22, "✓ sin PII   ✓ sin duplicados\n✓ tipado y consultable",
            ha="center", fontsize=9, color=GOOD)

    ax.text(50, 2.5, "github.com/sxntnx/supply-chain-etl-pipeline",
            ha="center", fontsize=8, color=MUTED)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "slide_before_after.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    print(f"Wrote {star_schema()}")
    print(f"Wrote {before_after()}")


if __name__ == "__main__":
    main()
