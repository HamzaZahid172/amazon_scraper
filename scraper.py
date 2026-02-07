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
            const searchResults = document.querySelectorAll("div[role='listitem'][data-asin]").length;
            const priceEl = Array.from(container.querySelectorAll("div[class='puisg-col-inner']"))
                    .find(x => x.innerText.toLowerCase().includes(`${"paperback"|"kindle"|"hardcover"|"audiobook"}`));

            const url = "https://www.amazon.com" + link.getAttribute("href");

            return {
                searchUrl: searchUrl,
                title: titleEl ? titleEl.innerText.trim() : null,
                url: url,
                asin: url.includes("/dp/") ? url.split("/dp/")[1].split("/")[0] : null,
                searchPrice: priceEl ? priceEl.innerText.trim() : null,
                searchResults: searchResults
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
    
    search_screenshot_path = f"output/screenshots/search/{item['asin']}.png"

    await page.screenshot(
        path=search_screenshot_path,
        full_page=True
    )

    return {
        "Search URL": item["searchUrl"],
        "Title": item["title"],
        "Product URL": item["url"],
        "ASIN": item["asin"],
        "Paperback Price": getPrice(item["searchPrice"], "paperback"),
        "Hardcover Price": getPrice(item["searchPrice"], "hardcover"),
        "Kindle Price": getPrice(item["searchPrice"], "kindle"),
        "AudioBook Price": getPrice(item["searchPrice"], "audiobook"),
        "searchResults": item["searchResults"],
        "Search Screenshot": search_screenshot_path
    }

async def extract_product(page: Page, getSearchData: Dict, inputRowValue: pd.Series) -> Dict:
    asin = getSearchData["ASIN"]
    url = f"https://www.amazon.com/dp/{asin}"

    await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
    await page.wait_for_selector("#tmmSwatches", timeout=15000)

    # title = await page.locator("#productTitle").inner_text()
    swatches = await page.locator("#tmmSwatches").inner_text()

    def get_price(label):
        block = swatches.lower()
        i = block.find(label)
        if i == -1:
            return None
        part = block[i:i+200]
        m = re.search(r"\$\s*(\d+\.\d+)", part)
        return "$" + m.group(1) if m else None

    product_screenshot_path = f"output/screenshots/product/{getSearchData['ASIN']}.png"
    await page.screenshot(
        path=product_screenshot_path,
        full_page=True)

    return {
        "Title": inputRowValue["Title"],
        "ASIN": inputRowValue["ASIN"],
        "Price": inputRowValue["Price"],
        "Input url": inputRowValue["Input_url"],
        "Search url": inputRowValue["SEARCH_URL"],
        "Paperback Min Price": get_price("paperback"),
        "Hardcover Min Price": get_price("hardcover"),
        "Kindle Min Price": get_price("kindle"),
        "AudioBook Min Price": get_price("audio"),
        "Product Page Screenshot": product_screenshot_path,
        "# Search results": getSearchData["searchResults"],
        "Search Title": getSearchData["Title"],
        "Search Asin": getSearchData["ASIN"],
        "Search Paperback Min Price": getSearchData["Paperback Price"],
        "Search Hardcover Min Price": getSearchData["Hardcover Price"],
        "Search Kindle Min Price": getSearchData["Kindle Price"],
        "Search AudioBook Min Price": getSearchData["AudioBook Price"],
        "Search Result Screenshot": getSearchData["Search Screenshot"],
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

    inputFile = pd.read_excel(INPUT_FILE)

    if "SEARCH_URL" not in inputFile.columns:
        raise ValueError("Excel must contain SEARCH_URL column")
    results = []

    async with async_playwright() as p:
        context = await create_browser_context(p)
        page = await context.new_page()

        for _, rowValue in inputFile.iterrows():
            search_url = rowValue["SEARCH_URL"]
            print(f"[INFO] Search: {search_url}")

            getSearchData = await extract_search_result(page, search_url)
            if not getSearchData or not getSearchData["ASIN"]:
                print("[WARN] No product found")
                continue

            print(f"[INFO] Found ASIN: {getSearchData['ASIN']}")

            try:
                row = await extract_product(page, getSearchData, rowValue)
                results.append(row)
                await asyncio.sleep(random.randint(MIN_DELAY, MAX_DELAY))
            except Exception as e:
                print(f"[ERROR] {getSearchData['ASIN']} -> {e}")

        await context.close()

    pd.DataFrame(results).to_excel(OUTPUT_FILE, index=False)
    print(f"[DONE] Saved {len(results)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
