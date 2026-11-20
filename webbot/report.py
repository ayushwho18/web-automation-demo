"""Excel report: a formatted data sheet, change tracking against the last run, and a summary with a chart."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEAD = PatternFill("solid", fgColor="1F2937")
UP = PatternFill("solid", fgColor="FEE2E2")
DOWN = PatternFill("solid", fgColor="D1FAE5")
NEW = PatternFill("solid", fgColor="DBEAFE")


def compare(rows: list[dict], snapshot: Path) -> list[dict]:
    """Mark each row new / price up / price down / unchanged versus the previous run."""
    old = json.loads(snapshot.read_text(encoding="utf-8")) if snapshot.exists() else {}
    for r in rows:
        prev = old.get(r["upc"])
        if prev is None:
            r["change"] = "new"
            r["previous_price"] = None
        else:
            r["previous_price"] = prev["price_gbp"]
            r["change"] = ("price up" if r["price_gbp"] > prev["price_gbp"] else
                           "price down" if r["price_gbp"] < prev["price_gbp"] else "unchanged")
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps({r["upc"]: {"price_gbp": r["price_gbp"], "in_stock": r["in_stock"]} for r in rows}),
                        encoding="utf-8")
    return rows


def write(rows: list[dict], out: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Products"
    cols = ["title", "category", "price_gbp", "previous_price", "change", "in_stock", "rating", "upc", "url"]
    ws.append([c.replace("_", " ").title() for c in cols])
    for c in ws[1]:
        c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), HEAD, Alignment(vertical="center")
    for r in rows:
        ws.append([r.get(c) for c in cols])
        fill = {"price up": UP, "price down": DOWN, "new": NEW}.get(r.get("change"))
        if fill:
            ws.cell(row=ws.max_row, column=cols.index("change") + 1).fill = fill
    for i, width in enumerate([48, 16, 11, 14, 12, 10, 8, 18, 60], 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows(min_row=2, min_col=3, max_col=4):
        for c in row:
            c.number_format = "£#,##0.00"
    n = ws.max_row
    ws.conditional_formatting.add(f"F2:F{n}", ColorScaleRule(start_type="min", start_color="FCA5A5",
                                                             end_type="max", end_color="86EFAC"))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{n}"

    s = wb.create_sheet("Summary", 0)
    prices = [r["price_gbp"] for r in rows]
    stats = [
        ("Report generated", datetime.now().strftime("%d %b %Y, %H:%M")),
        ("Products checked", len(rows)),
        ("Average price", sum(prices) / len(prices) if prices else 0),
        ("Cheapest", min(prices) if prices else 0),
        ("Most expensive", max(prices) if prices else 0),
        ("Low stock (≤ 3 left)", sum(1 for r in rows if r["in_stock"] <= 3)),
        ("New since last run", sum(1 for r in rows if r.get("change") == "new")),
        ("Price changes", sum(1 for r in rows if r.get("change") in ("price up", "price down"))),
    ]
    s["A1"] = "Catalogue monitor"
    s["A1"].font = Font(bold=True, size=16)
    for i, (k, v) in enumerate(stats, 3):
        s.cell(row=i, column=1, value=k).font = Font(bold=True)
        c = s.cell(row=i, column=2, value=v)
        if k in ("Average price", "Cheapest", "Most expensive"):
            c.number_format = "£#,##0.00"
    s.column_dimensions["A"].width, s.column_dimensions["B"].width = 26, 22

    # Products per star rating, with a bar chart.
    s["D3"], s["E3"] = "Rating", "Products"
    for c in (s["D3"], s["E3"]):
        c.font = Font(bold=True)
    for i, stars in enumerate(range(1, 6), 4):
        s.cell(row=i, column=4, value=f"{stars} star")
        s.cell(row=i, column=5, value=sum(1 for r in rows if r["rating"] == stars))
    chart = BarChart()
    chart.title, chart.y_axis.title, chart.legend = "Products by rating", "Products", None
    chart.add_data(Reference(s, min_col=5, min_row=3, max_row=8), titles_from_data=True)
    chart.set_categories(Reference(s, min_col=4, min_row=4, max_row=8))
    chart.height, chart.width = 7.5, 14
    s.add_chart(chart, "D11")
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
