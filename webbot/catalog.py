"""Task 1: walk a product catalogue (all pages), open each product, collect price and stock.

Target: books.toscrape.com, a public sandbox built for automation practice.
Swap the selectors in SELECTORS for a client's site; the flow stays the same.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, asdict

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .browser import Recorder, wait

log = logging.getLogger("webbot")

BASE = "https://books.toscrape.com/"
SELECTORS = {
    "card": "article.product_pod",
    "card_link": "h3 a",
    "next": "li.next a",
    "title": "div.product_main h1",
    "price": "div.product_main p.price_color",
    "stock": "div.product_main p.availability",
    "rating": "div.product_main p.star-rating",
    "upc": "table.table tr:first-child td",
    "category": "ul.breadcrumb li:nth-child(3) a",
}
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


@dataclass
class Product:
    upc: str
    title: str
    category: str
    price_gbp: float
    in_stock: int
    rating: int
    url: str


def _retry(fn, attempts: int = 3, delay: float = 2.0):
    for i in range(attempts):
        try:
            return fn()
        except (TimeoutException, WebDriverException) as ex:
            if i == attempts - 1:
                raise
            log.warning("  retry %d/%d after: %s", i + 1, attempts - 1, type(ex).__name__)
            time.sleep(delay * (i + 1))


def collect(driver, category_url: str, rec: Recorder, limit: int = 0, pause: float = 0.5) -> list[Product]:
    """Visit every listing page of a category, then every product page in it."""
    links: list[str] = []
    url = category_url
    page = 1
    while url:
        _retry(lambda: driver.get(url))
        wait(driver).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, SELECTORS["card"])))
        cards = driver.find_elements(By.CSS_SELECTOR, SELECTORS["card"])
        links += [c.find_element(By.CSS_SELECTOR, SELECTORS["card_link"]).get_attribute("href") for c in cards]
        log.info("listing page %d: %d products", page, len(cards))
        rec.shot(f"Listing page {page}: found {len(cards)} products")
        nxt = driver.find_elements(By.CSS_SELECTOR, SELECTORS["next"])
        url = nxt[0].get_attribute("href") if nxt else None
        page += 1
    if limit:
        links = links[:limit]

    products = []
    for i, link in enumerate(links, 1):
        _retry(lambda: driver.get(link))
        wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["title"])))
        q = lambda key: driver.find_element(By.CSS_SELECTOR, SELECTORS[key])
        stock_text = q("stock").text
        m = re.search(r"\((\d+) available\)", stock_text)
        rating_word = next((c for c in q("rating").get_attribute("class").split() if c in RATINGS), "")
        p = Product(
            upc=q("upc").text.strip(),
            title=q("title").text.strip(),
            category=q("category").text.strip(),
            price_gbp=float(re.sub(r"[^\d.]", "", q("price").text)),
            in_stock=int(m.group(1)) if m else 0,
            rating=RATINGS.get(rating_word, 0),
            url=link,
        )
        products.append(p)
        log.info("  %2d/%d  £%6.2f  stock %2d  %s", i, len(links), p.price_gbp, p.in_stock, p.title[:50])
        if i in (1, 2) or i == len(links):
            rec.shot(f"Product {i}/{len(links)}: £{p.price_gbp:.2f}, {p.in_stock} in stock")
        time.sleep(pause)  # be gentle with the site
    return products


def as_rows(products: list[Product]) -> list[dict]:
    return [asdict(p) for p in products]
