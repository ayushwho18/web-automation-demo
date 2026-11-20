"""
Browser automation demo: two everyday client jobs, done with Selenium.

  python run.py catalog            # crawl a catalogue -> formatted Excel report with change tracking
  python run.py forms              # submit a web form once per Excel row, write status back
  python run.py all --record       # both, and save a captioned MP4 + GIF of the run
  python run.py all --show         # watch the browser do it (not headless)

Options: --limit N (products), --category URL, --record, --show
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from webbot import catalog, forms, notify, report
from webbot.browser import Recorder, make_driver

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
SAMPLE = HERE / "data" / "form_entries.xlsx"
log = logging.getLogger("webbot")


def setup_logging():
    OUT.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(OUT / "run.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def make_sample(path: Path):
    """Create the example input sheet for the forms task (only if missing)."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Entries"
    ws.append(["name", "reference", "notes", "plan", "city", "newsletter", "priority", "date", "status"])
    rows = [
        ("Priya Sharma", "REF-1041", "Requested a callback about pricing", "One", "New York", "yes", "high", "11/20/2026"),
        ("Arjun Mehta", "REF-1042", "Wants the annual plan", "Two", "Los Angeles", "no", "normal", "11/20/2026"),
        ("Sara Khan", "REF-1043", "Existing customer, upgrade", "Three", "Seattle", "yes", "normal", "11/21/2026"),
        ("Rohan Iyer", "REF-1044", "Trial ended, follow up", "One", "San Francisco", "no", "high", "11/21/2026"),
        ("Meera Nair", "REF-1045", "Asked for an invoice copy", "Two", "Chicago", "yes", "normal", "11/22/2026"),
    ]
    for r in rows:
        ws.append(list(r) + [None])
    for col, w in zip("ABCDEFGHI", (16, 12, 36, 8, 16, 11, 10, 12, 22)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", choices=["catalog", "forms", "all"])
    ap.add_argument("--category", default="https://books.toscrape.com/catalogue/category/books/mystery_3/index.html")
    ap.add_argument("--limit", type=int, default=0, help="max products to open (0 = all)")
    ap.add_argument("--record", action="store_true", help="save a captioned MP4 + GIF of the run")
    ap.add_argument("--show", action="store_true", help="show the browser window")
    args = ap.parse_args()
    setup_logging()

    started = time.time()
    driver = make_driver(headless=not args.show)
    rec = Recorder(driver, OUT / "frames", enabled=args.record)
    summary = []
    try:
        if args.task in ("catalog", "all"):
            log.info("Task 1: catalogue monitor -> %s", args.category)
            rows = catalog.as_rows(catalog.collect(driver, args.category, rec, limit=args.limit))
            rows = report.compare(rows, OUT / "last_run.json")
            xlsx = report.write(rows, OUT / f"catalog_report_{datetime.now():%Y%m%d_%H%M}.xlsx")
            low = sum(1 for r in rows if r["in_stock"] <= 3)
            changed = sum(1 for r in rows if r["change"] in ("price up", "price down"))
            summary.append(f"Catalogue: {len(rows)} products, {changed} price changes, {low} low on stock")
            log.info("Report saved: %s", xlsx.name)
        if args.task in ("forms", "all"):
            make_sample(SAMPLE)
            log.info("Task 2: bulk form entry from %s", SAMPLE.name)
            ok, fail = forms.run(driver, SAMPLE, rec)
            summary.append(f"Forms: {ok} submitted, {fail} failed (status written back to {SAMPLE.name})")
    finally:
        driver.quit()

    took = time.time() - started
    summary.append(f"Finished in {took:.0f}s")
    for line in summary:
        log.info(line)
    if notify.telegram("Automation run complete\n" + "\n".join(summary)):
        log.info("Telegram summary sent")
    if args.record:
        video = rec.to_video(OUT / "demo_run.mp4")
        if video:
            log.info("Video saved: %s (+ .gif)", video.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
