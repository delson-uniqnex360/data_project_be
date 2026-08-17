import asyncio
import time
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from seleniumbase import Driver

from app.core.browser import driver_lock, get_driver, uc_open_with_reconnect


def extract_stens_sync(sku: str, driver: Driver) -> Dict[str, Any]:
    """Navigates to Stens search page, finds the product, and extracts specifications."""
    search_url = f"https://www.stens.com/search?keywords={sku}"
    error_response = {"error": f"product {sku} not found on the website Stens,"}

    try:
        # 1. Search SKU
        uc_open_with_reconnect(search_url, reconnect_time=4)
        time.sleep(2)

        # 2. Find the first product link
        product_links = driver.find_elements(
            By.CSS_SELECTOR, "a.facets-item-cell-list-link"
        )
        if not product_links:
            return error_response

        href = product_links[0].get_attribute("href")
        if not href:
            return error_response

        # 3. Navigate to product page
        product_url = (
            href if href.startswith("http") else f"https://www.stens.com{href}"
        )
        uc_open_with_reconnect(product_url, reconnect_time=4)
        time.sleep(2)

        # Parse page DOM using BeautifulSoup
        page_source = getattr(driver, "page_source", "") or (
            driver.get_page_source() if hasattr(driver, "get_page_source") else ""
        )
        soup = BeautifulSoup(page_source, "html.parser")

        # 4. Product title
        title_element = soup.select_one("h1.product-details-full-content-header-title")
        if not title_element:
            return error_response

        product_name = title_element.get_text(strip=True)
        data = {
            "Product Title": product_name,
        }

        # 5 & 6. Extract label -> value from description table rows
        rows = soup.select("table.product-details-full-description tbody tr")
        for row in rows:
            label_tag = row.select_one(".product-details-full-description-label")
            value_tag = row.select_one(".product-details-full-description-content")

            if not label_tag or not value_tag:
                continue

            key = label_tag.get_text(strip=True)
            val = value_tag.get_text(strip=True)

            if key:
                data[key] = val

        return data

    except Exception as e:
        print(f"Error processing Stens SKU '{sku}': {e}")
        return error_response


async def get_data_from_stens(
    sku: str, driver: Optional[Driver] = None
) -> Dict[str, Any]:
    """Async wrapper accepting a single `sku` string and optional `driver`."""
    async with driver_lock:
        active_driver = driver if driver is not None else get_driver()
        return await asyncio.to_thread(extract_stens_sync, sku, active_driver)
