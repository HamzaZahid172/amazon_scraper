import asyncio
import random
from pathlib import Path
from typing import List, Dict
import re
from typing import Optional

import pandas as pd
from playwright.async_api import async_playwright, Page, BrowserContext


INPUT_FILE = "input/check.xlsx"
OUTPUT_FILE = "output/selection_output.xlsx"

AMAZON_PRODUCT_URL = "https://www.amazon.com/dp/{}"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)"
]

MIN_DELAY = 5
MAX_DELAY = 8

def extract_price_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r'(?:\$|EUR)\s?\d+(?:\.\d+)?', text)
    return match.group(0) if match else None



async def extract_product(page: Page, asin: str,) -> List[Dict]:
    url = AMAZON_PRODUCT_URL.format(asin)

    await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    
    title = await page.locator("span[id='productTitle']").first.inner_text()

    price_format_texts = await page.evaluate("""
        () => Array.from(
            document.querySelectorAll("div#tmmSwatches div[role='listitem']")
        ).map(el => el.innerText)
    """)

    def find_text(label: str):
        return next((t for t in price_format_texts if label in t.lower()),None)

    result = {
        "Product URL": page.url,
        "ASIN": asin,
        "Title": title,
        "Paperback Min Price": extract_price_from_text(find_text("paperback")),
        "Hardcover Min Price": extract_price_from_text(find_text("hardcover")),
        "Kindle Min Price": extract_price_from_text(find_text("kindle")),
        "AudioBook Min Price": extract_price_from_text(find_text("audio")),
        }

    return [result]


async def create_browser_context(p) -> BrowserContext:

    browser = await p.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"]
    )

    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800}
    )

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    return context

async def run() -> None:

    df = pd.read_excel(INPUT_FILE)

    df.columns = df.columns.str.strip().str.upper()

    required_columns = {"ASIN", "TITLE"}
    if not required_columns.issubset(df.columns):
        raise ValueError("Input file must contain ASIN and TITLE columns")

    output_rows: List[Dict] = []

    async with async_playwright() as p:
        context = await create_browser_context(p)
        page = await context.new_page()

        for row in df.itertuples(index=False):
            asin = row.ASIN

            print(f"[INFO] Processing ASIN: {asin}")

            try:
                rows = await extract_product(page, asin)
                output_rows.extend(rows)

                await asyncio.sleep(random.randint(MIN_DELAY, MAX_DELAY))

            except Exception as exc:
                print(f"[ERROR] ASIN failed: {asin} | {exc}")

        await context.close()

    Path("output").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output_rows).to_excel(OUTPUT_FILE, index=False)

    print(f"[DONE] Extraction complete. Rows saved: {len(output_rows)}")


if __name__ == "__main__":
    asyncio.run(run())
