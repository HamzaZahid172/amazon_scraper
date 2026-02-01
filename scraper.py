import asyncio
import random
import re
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from playwright.async_api import async_playwright, Page, BrowserContext


INPUT_FILE = "input/Check.xlsx"
OUTPUT_FILE = "output/selection_output.xlsx"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)"
]

MIN_DELAY = 5
MAX_DELAY = 8


def extract_price(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"\$\s*(\d+\.\d+)", text)
    return "$" + m.group(1) if m else None

async def extract_search_result(page: Page, search_url: str) -> Optional[Dict]:
    await page.goto(search_url, timeout=60_000, wait_until="domcontentloaded")
    await page.wait_for_selector("a.a-link-normal.s-no-outline", timeout=15000)
    await page.wait_for_timeout(3000)

    item = await page.evaluate("""
        (searchUrl) => {
            const link = document.querySelector("a.a-link-normal.s-no-outline");
            if (!link) return null;

            const container = link.closest("div[data-component-type='s-search-result']");
            if (!container) return null;

            const titleEl = container.querySelector("h2 span");
            const priceEl = Array.from(container.querySelectorAll("div[class='puisg-col-inner']"))
                    .find(x => x.innerText.toLowerCase().includes(`${"paperback"|"kindle"|"hardcover"|"audiobook"}`));

            const url = "https://www.amazon.com" + link.getAttribute("href");

            return {
                searchUrl: searchUrl,
                title: titleEl ? titleEl.innerText.trim() : null,
                url: url,
                asin: url.includes("/dp/") ? url.split("/dp/")[1].split("/")[0] : null,
                searchPrice: priceEl ? priceEl.innerText.trim() : null
            };
        }
    """, search_url)
    
    if not item:
        return []

    def getPrice(block, label):
        if not block:
            return None

        block = block.lower()
        label = label.lower()

        i = block.find(label)
        if i == -1:
            return None

        after = block[i + len(label): i + len(label) + 300]

        next_format = re.search(r"\b(kindle|paperback|hardcover|audiobook)\b", after)
        price = re.search(r"\$\s*(\d+\.\d+)", after)

        if not price:
            return None

        if next_format and next_format.start() < price.start():
            return None 

        return "$" + price.group(1)

    return {
        "Search URL": item["searchUrl"],
        "Title": item["title"],
        "Product URL": item["url"],
        "ASIN": item["asin"],
        "Paperback Price": getPrice(item["searchPrice"], "paperback"),
        "Hardcover Price": getPrice(item["searchPrice"], "hardcover"),
        "Kindle Price": getPrice(item["searchPrice"], "kindle"),
        "AudioBook Price": getPrice(item["searchPrice"], "audiobook")
    }

async def extract_product(page: Page, search_data: Dict) -> Dict:
    asin = search_data["ASIN"]
    url = f"https://www.amazon.com/dp/{asin}"

    await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
    await page.wait_for_selector("#tmmSwatches", timeout=15000)

    title = await page.locator("#productTitle").inner_text()
    swatches = await page.locator("#tmmSwatches").inner_text()

    def get_price(label):
        block = swatches.lower()
        i = block.find(label)
        if i == -1:
            return None
        part = block[i:i+200]
        m = re.search(r"\$\s*(\d+\.\d+)", part)
        return "$" + m.group(1) if m else None

    return {
        "Search URL": search_data["Search URL"],
        "Search Title": search_data["Title"],
        "Search ASIN": search_data["ASIN"],
        "Search Page Paperback Price": search_data["Paperback Price"],
        "Search Page Hardcover Price": search_data["Hardcover Price"],
        "Search Page Kindle Price": search_data["Kindle Price"],
        "Search Page AudioBook Price": search_data["AudioBook Price"],
        "Product URL": url,
        "ASIN": asin,
        "Title": title.strip(),
        "Paperback Price": get_price("paperback"),
        "Hardcover Price": get_price("hardcover"),
        "Kindle Price": get_price("kindle"),
        "AudioBook Price": get_price("audio"),
    }

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

async def run():
    Path("output").mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(INPUT_FILE)

    if "SEARCH_URL" not in df.columns:
        raise ValueError("Excel must contain SEARCH_URL column")

    search_urls = df["SEARCH_URL"].dropna().tolist()
    results = []

    async with async_playwright() as p:
        context = await create_browser_context(p)
        page = await context.new_page()

        for search_url in search_urls:
            print(f"[INFO] Search: {search_url}")

            search_data = await extract_search_result(page, search_url)
            if not search_data or not search_data["ASIN"]:
                print("[WARN] No product found")
                continue

            print(f"[INFO] Found ASIN: {search_data['ASIN']}")

            try:
                row = await extract_product(page, search_data)
                results.append(row)
                await asyncio.sleep(random.randint(MIN_DELAY, MAX_DELAY))
            except Exception as e:
                print(f"[ERROR] {search_data['ASIN']} -> {e}")

        await context.close()

    pd.DataFrame(results).to_excel(OUTPUT_FILE, index=False)
    print(f"[DONE] Saved {len(results)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
