import asyncio
import time
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from seleniumbase import Driver

from app.core.browser import driver_lock, get_driver, uc_open_with_reconnect


def extract_data_from_html(soup: BeautifulSoup) -> dict:
    data = {}

    # 1. Extract Product Title
    product_title_class = "h1 product-name hidden-sm-down"
    product_title_ele = soup.find("div", class_=product_title_class)
    data["Product Title"] = (
        product_title_ele.get_text(strip=True) if product_title_ele else ""
    )

    # 2. Extract Long Description & Features (bullet points)
    desc_container = soup.find("div", class_="long-description")
    if desc_container:
        paragraphs = [
            p.get_text(strip=True)
            for p in desc_container.find_all("p")
            if p.get_text(strip=True)
        ]

        if paragraphs:
            data["Description"] = paragraphs[0]
            for p_text in paragraphs[1:]:
                if "Fits" in p_text:
                    data["Deck & Fitment Specifications"] = p_text

        bullet_list = desc_container.find("ul")
        if bullet_list:
            items = bullet_list.find_all("li")
            for idx, item in enumerate(items, start=1):
                feature_key = f"feature_{idx}"
                data[feature_key] = item.get_text(strip=True)

    # 3. Extract Blade Specifications
    specs_container = soup.find("div", class_="specs-content")
    if specs_container:
        for li in specs_container.find_all("li", class_="attribute-values"):
            span = li.find("span")
            if span:
                label = span.get_text(strip=True)
                # Remove label from total li text to isolate the spec value
                value = li.get_text(strip=True).replace(label, "", 1).strip()
                data[label] = value

    # 4. Extract "Part Replaces" OEM Numbers
    replaces_container = soup.find("div", class_="part-replaces")
    if replaces_container:
        replaces_text = replaces_container.get_text(strip=True)
        if ":" in replaces_text:
            _, parts_list = replaces_text.split(":", 1)
            data["Replaces Parts"] = parts_list.strip()
        else:
            data["Replaces Parts"] = replaces_text.strip()

    return data


def extract_genuine_factory_parts_sync(sku: str, driver: Driver) -> Dict[str, Any]:
    """Navigates to Genuine Factory Parts, performs a targeted SKU search,
    matches the exact product tile by data-pid, and returns the PDP URL and product data.
    """
    search_input_selector = "form[name='simpleSearch'] input[name='q']"
    search_button_selector = "form[name='simpleSearch'] .search-icon"

    error_response = {"error": f"product{sku} not found on the website Genuine Factory Parts"}

    try:
        # 1. Open homepage
        uc_open_with_reconnect("https://www.genuinefactoryparts.com", reconnect_time=4)

        # 2. Locate search input
        input_elements = driver.find_elements(By.CSS_SELECTOR, search_input_selector)

        if not input_elements or not input_elements[0].is_displayed():
            return error_response

        search_box = input_elements[0]

        # Thoroughly clear existing text using hotkeys to trigger JS change events
        search_box.click()
        search_box.send_keys(Keys.CONTROL + "a")
        search_box.send_keys(Keys.BACKSPACE)
        time.sleep(0.5)

        # Type exact SKU
        search_box.send_keys(sku)
        time.sleep(1)

        # Click search icon explicitly to bypass autocomplete overlay traps
        button_elements = driver.find_elements(By.CSS_SELECTOR, search_button_selector)
        if button_elements and button_elements[0].is_displayed():
            button_elements[0].click()
        else:
            search_box.send_keys(Keys.ENTER)

        time.sleep(4)

        # Check for block pages
        page_title = getattr(driver, "title", "") or (
            driver.get_title() if hasattr(driver, "get_title") else ""
        )
        if "Access Denied" in page_title or "403" in page_title:
            return error_response

        current_url = getattr(driver, "current_url", "") or (
            driver.get_current_url() if hasattr(driver, "get_current_url") else ""
        )

        # Direct hit check: if already redirected straight to PDP for this SKU
        clean_sku = sku.strip().upper()
        is_direct_hit = (
            clean_sku.lower() in current_url.lower() and ".html" in current_url
        )

        if not is_direct_hit:
            # 3. Locate tile using exact data-pid attributes from Demandware HTML
            exact_tile_selectors = [
                f"div[data-pid='{sku}']",
                f"div[data-pid='{clean_sku}']",
                f"div[data-monetate-pid='{sku}']",
                f"div[data-monetate-pid='{clean_sku}']",
            ]

            target_link = None
            for selector in exact_tile_selectors:
                matched_tiles = driver.find_elements(By.CSS_SELECTOR, selector)
                if matched_tiles:
                    # Find PDP anchor inside the matched tile
                    links = matched_tiles[0].find_elements(
                        By.CSS_SELECTOR, ".pdp-link a, a.link, .image-container a"
                    )
                    if links:
                        target_link = links[0]
                        break

            # Secondary check: search for link containing the SKU in href
            if not target_link:
                href_links = driver.find_elements(
                    By.CSS_SELECTOR, f"a[href*='{sku}'], a[href*='{sku.lower()}']"
                )
                if href_links:
                    target_link = href_links[0]

            # Navigate to target page if link was found
            if target_link:
                target_link.click()
                time.sleep(3)
                current_url = getattr(driver, "current_url", "") or (
                    driver.get_current_url()
                    if hasattr(driver, "get_current_url")
                    else ""
                )
            else:
                return error_response

        # Check if final URL looks like a valid PDP page
        if ".html" not in current_url:
            return error_response

        # 4. Parse HTML and extract data
        page_source = getattr(driver, "page_source", "") or (
            driver.get_page_source() if hasattr(driver, "get_page_source") else ""
        )
        soup = BeautifulSoup(page_source, "html.parser")

        extracted_data = extract_data_from_html(soup)

        if not extracted_data:
            return error_response

        result = {
            "sku": sku,
            "url": current_url,
        }
        result.update(extracted_data)

        return result

    except Exception as e:
        print(f"Error processing SKU '{sku}' on Genuine Factory Parts: {e}")
        return error_response


async def get_data_from_genuine_factory_parts(
    sku: str, driver: Optional[Driver] = None
) -> Dict[str, Any]:
    """Async wrapper accepting a single `sku` string and optional `driver`."""
    async with driver_lock:
        active_driver = driver if driver is not None else get_driver()
        return await asyncio.to_thread(
            extract_genuine_factory_parts_sync, sku, active_driver
        )
