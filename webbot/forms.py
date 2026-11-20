"""Task 2: fill and submit a web form once per row of an Excel sheet, then write the result back.

Target: Selenium's official practice form (selenium.dev/selenium/web/web-form.html).
This is the classic "type my spreadsheet into a web portal" job.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

from .browser import Recorder, wait

log = logging.getLogger("webbot")
FORM_URL = "https://www.selenium.dev/selenium/web/web-form.html"
OK = PatternFill("solid", fgColor="D1FAE5")
FAIL = PatternFill("solid", fgColor="FEE2E2")


def fill_one(driver, row: dict, rec: Recorder, show: bool):
    driver.get(FORM_URL)
    w = wait(driver)
    w.until(EC.presence_of_element_located((By.NAME, "my-text")))
    by = lambda name: driver.find_element(By.NAME, name)
    by("my-text").send_keys(str(row["name"]))
    by("my-password").send_keys(str(row["reference"]))
    by("my-textarea").send_keys(str(row["notes"]))
    Select(by("my-select")).select_by_visible_text(str(row["plan"]))
    by("my-datalist").send_keys(str(row["city"]))
    want_newsletter = str(row["newsletter"]).strip().lower() in ("yes", "y", "true", "1")
    box = driver.find_element(By.ID, "my-check-1")
    if box.is_selected() != want_newsletter:
        box.click()
    driver.find_element(By.ID, "my-radio-2" if str(row["priority"]).lower() == "high" else "my-radio-1").click()
    date = by("my-date")
    date.send_keys(str(row["date"]))
    date.send_keys(Keys.ESCAPE)
    if show:
        rec.shot(f"Row {row['_n']}: form filled for {row['name']}")
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    msg = w.until(EC.presence_of_element_located((By.ID, "message"))).text
    if show:
        rec.shot(f"Row {row['_n']}: submitted, site replied '{msg}'")
    if msg.strip() != "Received!":
        raise RuntimeError(f"unexpected reply: {msg!r}")
    return msg


def run(driver, xlsx: Path, rec: Recorder) -> tuple[int, int]:
    """Process every row whose Status is empty. Writes Status + time back to the same file."""
    wb = load_workbook(xlsx)
    ws = wb.active
    headers = [str(c.value).strip().lower() for c in ws[1]]
    if "status" not in headers:
        ws.cell(row=1, column=len(headers) + 1, value="status")
        headers.append("status")
    if "processed_at" not in headers:
        ws.cell(row=1, column=len(headers) + 1, value="processed_at")
        headers.append("processed_at")
    s_col, t_col = headers.index("status") + 1, headers.index("processed_at") + 1
    ok = fail = 0
    for r in range(2, ws.max_row + 1):
        row = {h: ws.cell(row=r, column=i + 1).value for i, h in enumerate(headers)}
        if not row.get("name") or row.get("status"):
            continue
        row["_n"] = r - 1
        try:
            fill_one(driver, row, rec, show=(ok + fail) < 2)
            ws.cell(row=r, column=s_col, value="Submitted").fill = OK
            ok += 1
            log.info("  row %d: submitted (%s)", r - 1, row["name"])
        except Exception as ex:  # keep going; the sheet shows which rows failed and why
            ws.cell(row=r, column=s_col, value=f"Failed: {ex}"[:120]).fill = FAIL
            fail += 1
            log.error("  row %d failed: %s", r - 1, ex)
        ws.cell(row=r, column=t_col, value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        wb.save(xlsx)  # save after every row so a crash never loses progress
    return ok, fail
