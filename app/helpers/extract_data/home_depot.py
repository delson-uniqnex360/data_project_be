import asyncio
import time
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    ElementNotInteractableException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from app.core.browser import driver_lock, get_driver, uc_open_with_reconnect
from .helpers import open_all_accordions

# Exceptions that mean "element was there but we couldn't interact with it"
# -> treat the same as "product not found"
INTERACTION_EXCEPTIONS = (
    ElementNotInteractableException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)


def extract_specifications(soup: BeautifulSoup) -> Dict[str, str]:
    """Dynamically extracts all spec sections (Dimensions, Details,
    Warranty / Certifications, etc.) as flat key-value pairs.
    """
    specs: Dict[str, str] = {}

    spec_section = soup.find("section", id="product-section-specifications")
    if not spec_section:
        return specs

    tables = spec_section.find_all("table", attrs={"name": True})

    for table in tables:
        section_name = table.get("name", "General").strip()

        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not th or not td:
                continue

            label = th.get_text(strip=True)
            value = td.get_text(strip=True)
            if not label:
                continue

            specs[f"{section_name} - {label}"] = value

    return specs


def extract_about_highlights_info(soup: BeautifulSoup) -> Dict[str, Any]:
    """Dynamically extracts the 'About This Product' description,
    the 'Highlights' bullet list, and the 'Product Information' bar.
    """
    result: Dict[str, Any] = {}

    # --- About This Product ---
    about_h3 = soup.find("h3", string=lambda s: s and "About This Product" in s)
    if about_h3:
        container = about_h3.find_parent("div")
        p_tag = container.find("p") if container else None
        if p_tag:
            result["About This Product"] = p_tag.get_text(strip=True)

    # --- Highlights ---
    highlights_h3 = soup.find("h3", string=lambda s: s and "Highlights" in s)
    if highlights_h3:
        container = highlights_h3.find_parent("div")
        ul_tag = container.find("ul") if container else None
        if ul_tag:
            highlights = []
            for li in ul_tag.find_all("li"):
                text = li.get_text(" ", strip=True)
                if not text:
                    continue
                skip_markers = ("Return Policy", "Prop 65", "California residents")
                if any(marker in text for marker in skip_markers):
                    continue
                highlights.append(text)
            if highlights:
                result["Highlights"] = "\n".join(highlights)

    # --- Product Information bar ---
    info_div = soup.find("div", attrs={"data-testid": "productInfo"})
    if info_div:
        for h2 in info_div.find_all("h2"):
            span_tag = h2.find("span")
            if not span_tag:
                continue
            value = span_tag.get_text(strip=True)
            full_text = h2.get_text(" ", strip=True)
            label = full_text.replace(value, "").strip()
            if label and value:
                result[label] = value

    return result


import traceback


def extract_home_depot_sync(
    sku: str, driver: Any, debug: bool = False
) -> Dict[str, Any]:
    """Navigates to Home Depot, performs a SKU search, handles direct product landings,

    grid matching, or 'no product found' cases, then extracts specs.

    Args:
        sku: The SKU to search for.
        driver: The webdriver instance.
        debug: If True, prints step-by-step progress/diagnostic info to help
            pinpoint exactly where a failure occurs.
    """

    def dbg(msg: str) -> None:
        if debug:
            print(f"[DEBUG][SKU={sku}] {msg}")

    search_input_selector = "#typeahead-search-field-input"
    search_button_selector = "#typeahead-search-icon-button"
    error_response = {"error": f"product {sku} not found on the website Home Depot"}

    try:
        # 1. Open Home Depot homepage
        dbg("STEP 1: Opening homedepot.com homepage")
        uc_open_with_reconnect("https://www.homedepot.com", reconnect_time=4)
        dbg("STEP 1: Homepage loaded (or reconnect wait completed)")

        # 2. Perform search
        dbg("STEP 2: Waiting for search box to be clickable")
        try:
            search_box = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, search_input_selector))
            )
            search_box.clear()
            search_box.send_keys(sku)
            dbg(f"STEP 2: Typed SKU '{sku}' into search box via send_keys")
        except INTERACTION_EXCEPTIONS as e:
            print(f"Normal interaction blocked for SKU '{sku}', using JS: {e}")
            dbg(
                f"STEP 2: send_keys blocked ({type(e).__name__}: {e}); falling back to JS injection"
            )
            try:
                search_box = driver.find_element(By.CSS_SELECTOR, search_input_selector)
                driver.execute_script("arguments[0].value = '';", search_box)
                driver.execute_script(
                    "arguments[0].value = arguments[1];", search_box, sku
                )
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                    search_box,
                )
                dbg("STEP 2: JS injection of SKU into search box succeeded")
            except Exception as js_e:
                print(f"Search box completely un-interactable for SKU '{sku}': {js_e}")
                dbg(
                    f"STEP 2: JS fallback FAILED ({type(js_e).__name__}: {js_e}) -> returning error_response"
                )
                return error_response

        # Execute Search
        dbg("STEP 3: Attempting to click search button")
        try:
            search_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, search_button_selector))
            )
            search_button.click()
            dbg("STEP 3: Search button clicked")
        except INTERACTION_EXCEPTIONS as e:
            dbg(
                f"STEP 3: Search button click failed ({type(e).__name__}: {e}); falling back to ENTER key"
            )
            try:
                search_box.send_keys(Keys.ENTER)
                dbg("STEP 3: ENTER key sent to search box")
            except Exception as enter_e:
                print(f"Could not submit search for SKU '{sku}': {enter_e}")
                dbg(
                    f"STEP 3: ENTER key fallback FAILED ({type(enter_e).__name__}: {enter_e}) -> returning error_response"
                )
                return error_response

        dbg("STEP 4: Sleeping 4s for search results to load")
        time.sleep(4)

        # Check for WAF Block
        dbg("STEP 5: Checking page title for WAF/Access Denied block")
        page_title = getattr(driver, "title", "") or (
            driver.get_title() if hasattr(driver, "get_title") else ""
        )
        dbg(f"STEP 5: page_title = '{page_title}'")
        if "Access Denied" in page_title:
            dbg(
                "STEP 5: WAF block detected ('Access Denied' in title) -> returning error_response"
            )
            return error_response

        # 3. Handle Navigation & Scenarios
        current_url = getattr(driver, "current_url", "") or (
            driver.get_current_url() if hasattr(driver, "get_current_url") else ""
        )
        dbg(f"STEP 6: current_url after search = '{current_url}'")

        # SCENARIO A: Direct product page landing
        if "/p/" in current_url:
            print(f"Direct landing on product page for SKU '{sku}'")
            dbg("STEP 6: SCENARIO A - direct landing on product page")

        # SCENARIO B & C: Landed on Search List Page or No Products Found
        else:
            dbg(
                "STEP 6: SCENARIO B/C - landed on search list / no-products page, parsing page_source"
            )
            page_source = getattr(driver, "page_source", "") or (
                driver.get_page_source() if hasattr(driver, "get_page_source") else ""
            )
            dbg(
                f"STEP 6: page_source length = {len(page_source) if page_source else 0}"
            )
            soup = BeautifulSoup(page_source, "html.parser")

            # Check explicit 'no products' banner
            no_products_banner = soup.select_one("div.results-wrapped--no-products")
            if no_products_banner:
                print(f"Explicit 'no products found' banner present for SKU '{sku}'")
                dbg(
                    "STEP 6: 'no products found' banner detected -> returning error_response"
                )
                return error_response

            # Process PLP (Product Listing Page) pods
            pods = driver.find_elements(
                By.CSS_SELECTOR, "div[data-testid='product-pod']"
            )
            dbg(f"STEP 7: Found {len(pods)} product pod(s) on listing page")
            matched_link = None

            for i, pod in enumerate(pods):
                pod_html = pod.get_attribute("outerHTML")
                pod_soup = BeautifulSoup(pod_html, "html.parser")

                # Extract Model / SKU text inside the pod
                # Home Depot displays it as: "Model# XE40M06ST45U1"
                text_content = pod_soup.get_text()

                if f"Model# {sku}".lower() in text_content.lower() or (
                    sku.lower() in text_content.lower()
                ):
                    dbg(
                        f"STEP 7: Pod #{i} text matched SKU '{sku}'; locating clickable link"
                    )
                    # Locate the clickable title link inside this specific matched pod
                    try:
                        matched_link = pod.find_element(
                            By.CSS_SELECTOR,
                            "div[data-testid='product-header'] a, a[aria-label='Link']",
                        )
                        dbg(f"STEP 7: Clickable link found in pod #{i}")
                        break
                    except Exception as link_e:
                        dbg(
                            f"STEP 7: Pod #{i} matched text but link lookup failed ({type(link_e).__name__}: {link_e}); continuing to next pod"
                        )
                        continue

            if matched_link:
                print(
                    f"Found matching Model# for SKU '{sku}' in search results. Navigating..."
                )
                dbg("STEP 8: Clicking matched product link")
                try:
                    matched_link.click()
                    time.sleep(4)
                    current_url = getattr(driver, "current_url", "") or (
                        driver.get_current_url()
                        if hasattr(driver, "get_current_url")
                        else ""
                    )
                    dbg(
                        f"STEP 8: Navigated to '{current_url}' after clicking matched link"
                    )
                except INTERACTION_EXCEPTIONS as e:
                    print(f"Failed to click matched product link for SKU '{sku}': {e}")
                    dbg(
                        f"STEP 8: Click FAILED ({type(e).__name__}: {e}) -> returning error_response"
                    )
                    return error_response
            else:
                print(f"No matching Model# found in search result list for SKU '{sku}'")
                dbg(
                    "STEP 8: No matched_link found among pods -> returning error_response"
                )
                return error_response

        # Final Verification: Ensure we are on a valid product detail page (/p/)
        dbg(f"STEP 9: Final URL check before scraping: '{current_url}'")
        if "/p/" not in current_url:
            dbg("STEP 9: URL does not contain '/p/' -> returning error_response")
            return error_response

        # 4. Expand Accordions & Scrape Product
        dbg("STEP 10: Attempting to open all accordions")
        try:
            open_all_accordions(driver)
            dbg("STEP 10: Accordions opened successfully")
        except INTERACTION_EXCEPTIONS as e:
            print(f"Could not open accordions for SKU '{sku}': {e}")
            dbg(
                f"STEP 10: open_all_accordions FAILED ({type(e).__name__}: {e}); continuing anyway"
            )

        dbg("STEP 11: Fetching page_source for final scrape")
        page_source = getattr(driver, "page_source", "") or (
            driver.get_page_source() if hasattr(driver, "get_page_source") else ""
        )
        dbg(f"STEP 11: page_source length = {len(page_source) if page_source else 0}")
        soup = BeautifulSoup(page_source, "html.parser")

        # Product Title Validation
        dbg("STEP 12: Looking for product title <h1>")
        product_title_class_h1 = (
            "sui-h4-bold sui-line-clamp-unset sui-font-normal sui-text-primary"
        )
        product_title_element = soup.find("h1", class_=product_title_class_h1)

        if not product_title_element:
            dbg("STEP 12: Primary h1 class not found; trying fallback generic <h1>")
            # Secondary fallback check for H1
            product_title_element = soup.find("h1")
            if not product_title_element:
                dbg("STEP 12: No <h1> found at all -> returning error_response")
                return error_response
            dbg("STEP 12: Fallback <h1> found")
        else:
            dbg("STEP 12: Primary product title <h1> found")

        result = {
            "sku": sku,
            "url": current_url,
            "Product Title": product_title_element.get_text(strip=True),
        }
        dbg(f"STEP 12: Product Title = '{result['Product Title']}'")

        # Brand
        dbg("STEP 13: Looking for brand <h2>")
        h2_target_class = (
            "sui-font-regular sui-text-base sui-underline sui-tracking-normal "
            "sui-normal-case sui-line-clamp-unset sui-font-normal sui-text-primary"
        )
        brand_element = soup.find("h2", class_=h2_target_class)
        result["brand"] = brand_element.get_text(strip=True) if brand_element else ""
        dbg(f"STEP 13: brand = '{result['brand']}'")

        # Product Features
        dbg("STEP 14: Looking for product features <ul>")
        ul_element = soup.find(
            "ul",
            class_=lambda c: c and "sui-text-base sui-list-disc sui-list-inside" in c,
        )

        if ul_element:
            li_items = ul_element.find_all("li")
            dbg(f"STEP 14: Found features <ul> with {len(li_items)} <li> item(s)")
            feature_index = 1
            for li in li_items:
                text = li.get_text(strip=True)
                if "View More" in text or li.find("a"):
                    continue
                result[f"feature {feature_index}"] = text
                feature_index += 1
            dbg(f"STEP 14: Extracted {feature_index - 1} feature(s)")
        else:
            dbg("STEP 14: No features <ul> found")

        # External helper parsing calls
        dbg("STEP 15: Calling extract_about_highlights_info(soup)")
        try:
            highlights = extract_about_highlights_info(soup)
            dbg(
                f"STEP 15: extract_about_highlights_info returned keys: {list(highlights.keys())}"
            )
            result.update(highlights)
        except Exception as e:
            dbg(
                f"STEP 15: extract_about_highlights_info FAILED ({type(e).__name__}: {e})"
            )
            raise

        dbg("STEP 16: Calling extract_specifications(soup)")
        try:
            specs = extract_specifications(soup)
            dbg(f"STEP 16: extract_specifications returned keys: {list(specs.keys())}")
            result.update(specs)
        except Exception as e:
            dbg(f"STEP 16: extract_specifications FAILED ({type(e).__name__}: {e})")
            raise

        dbg("STEP 17: Extraction complete, returning result")
        return result

    except Exception as e:
        print(f"Error processing SKU '{sku}': {e}")
        if debug:
            print(f"[DEBUG][SKU={sku}] Exception occurred: {type(e).__name__}: {e}")
            traceback.print_exc()
        return error_response


async def get_data_from_home_depot(
    sku: str, driver: Optional[Driver] = None
) -> Dict[str, Any]:
    """Async wrapper accepting a single `sku` string and optional `driver`."""
    async with driver_lock:
        active_driver = driver if driver is not None else get_driver()
        return await asyncio.to_thread(extract_home_depot_sync, sku, active_driver)
