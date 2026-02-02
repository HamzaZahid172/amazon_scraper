# Amazon Book Data Extraction Scraper

## Amazon Product & Price Scraper

![Amazon Product & Price Scraper](assets/Amazon%20Data%20Scraper.png)

## Overview

This project implements a **robust data extraction pipeline for Amazon book listings**.  
It reads a list of ASINs from an Excel file, scrapes structured information from Amazon product pages, and outputs the normalized data into an Excel file.

The scraper is designed as a **low-frequency, batch process**, focusing on accuracy, robustness, and handling edge cases rather than speed.

---

## Features

- Extracts data from **Amazon.com**
- Supports dynamic pages using **Playwright (Chromium)**
- Handles JavaScript-rendered content
- Reads input from Excel (`.xlsx`)
- Outputs structured results to Excel (`.xlsx`)
- Designed for large datasets (50,000+ ASINs)
- Rate-limited to reduce blocking risk

---

## Tech Stack

- **Python 3.9+**
- **Playwright (Chromium)** – dynamic page rendering
- **pandas** – data processing
- **openpyxl** – Excel read/write

> Requests + BeautifulSoup is intentionally not used due to Amazon’s aggressive bot detection and dynamic content rendering.

---

## Project Structure

```
amazon-scraper/
│
├── input/
│ └── check.xlsx
│
├── output/
│ └── selection_output.xlsx
│
├── scraper.py
├── requirements.txt
└── README.md
```


---

## Input File Format (`check.xlsx`)

Required columns:

- `ASIN`
- `Title` (optional, used for reference)

Example:

| ASIN       | Title                              |
|------------|------------------------------------|
| B09XXXXXXX | Example Book Title                 |

---

## Output File Format (`selection_output.xlsx`)

Example columns:

- ASIN
- Title
- Format (Paperback, Hardcover, Kindle, Audiobook)
- Lowest New Price
- Product URL

---

## Installation

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # macOS / Linux
venv\Scripts\activate      # Windows
```

### 2. Install dependencies
```bash
pip install playwright pandas openpyxl
```

### 3. Install Playwright browser
```bash
playwright install chromium
```

## Running the Scraper

### Place the input file in:
```bash
input/check.xlsx
```

### Run the script:
```bash
python scraper.py
```

### Output will be generated at:
```bash
output/selection_output.xlsx
```

## Author

Hamza Zahid Butt
Senior Software Engineer
