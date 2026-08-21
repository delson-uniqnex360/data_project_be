import re
import time
from seleniumbase import Driver


def get_details_from_trackter_spply(sku: str, driver: Driver) -> dict | None:
    search_url = f"https://www.tractorsupply.com/tsc/search/{sku}?isIntSrch=written"
    print("search url", search_url)

    try:
        print(f"Searching for SKU: {sku}...")

        # Use uc_open_with_reconnect without calling driver.get afterwards
        if hasattr(driver, "uc_open_with_reconnect"):
            driver.uc_open_with_reconnect(search_url, reconnect_time=4)
        else:
            driver.get(search_url)

        # Pause briefly to allow initial scripts/hydration to kick off
        time.sleep(3)

        # Check for WAF/Access Denied blocks directly
        status_code = getattr(driver, "status_code", None)
        page_title = driver.get_title()
        page_source = driver.get_page_source()

        if (
            status_code in [403, 429]
            or "Access Denied" in page_title
            or "px-captcha" in page_source
        ):
            print(f"Blocked by WAF with status code {status_code or 'Forbidden'}")
            return None

        # --- Check for Direct Redirect to a Product Page ---
        current_url = driver.get_current_url()
        print("curnt url", current_url)
        product_urls = []

        time.sleep(5)
        print("waits finished")
        if "/tsc/product/" in current_url or "/product/" in current_url:
            print("Directly redirected to product page.")
            product_urls = [current_url]
        else:
            # Trigger page scroll to activate lazy-loading React components
            driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(1)

            # Explicitly wait for React to hydrate and render product cards
            try:
                driver.wait_for_element_present(
                    ".new-product-card-v2, [data-testid*='product'], a[href*='/tsc/product/'], a[href*='/product/'], #no-results-found",
                    timeout=15,
                )
            except Exception:
                print("Timeout waiting for product cards to render in DOM.")

            # Extract links using JavaScript execution to safely reach dynamic DOM nodes
            product_urls = driver.execute_script("""
                const links = Array.from(document.querySelectorAll('a[href*="/tsc/product/"], a[href*="/product/"]'));
                const urls = links.map(a => {
                    let href = a.getAttribute('href');
                    if (!href) return null;
                    return href.startsWith('/') ? 'https://www.tractorsupply.com' + href : href;
                }).filter(Boolean);
                return Array.from(new Set(urls));
                """)

            # Fallback DOM element lookup
            if not product_urls:
                anchor_elements = driver.find_elements(
                    "css selector", 'a[href*="/tsc/product/"], a[href*="/product/"]'
                )
                product_urls = []
                for anchor in anchor_elements:
                    href = anchor.get_attribute("href")
                    if href:
                        full_url = (
                            f"https://www.tractorsupply.com{href}"
                            if href.startswith("/")
                            else href
                        )
                        if full_url not in product_urls:
                            product_urls.append(full_url)

        if not product_urls:
            print(f"No product detail URLs found on the page for SKU: {sku}")
            return None

        print(f"Found {len(product_urls)} candidate product URL(s) for SKU: {sku}")

    except Exception as e:
        print(f"Error fetching search page for SKU {sku}: {e}")
        return None

    # --- Candidate Page Validation (Matching Manufacturer Part Number) ---
    matched_url = None

    for target_url in product_urls:
        try:
            if driver.get_current_url() != target_url:
                driver.get(target_url)

            driver.wait_for_element("h1", timeout=10)

            # Locate element containing "Manufacturer Part Number"
            mfg_part_elements = driver.find_elements(
                "xpath",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'manufacturer part number')]",
            )

            if mfg_part_elements:
                spec_text = driver.execute_script(
                    "return arguments[0].closest('tr, li, div')?.innerText || arguments[0].parentElement.innerText;",
                    mfg_part_elements[0],
                )

                if spec_text and sku.lower() in spec_text.lower():
                    matched_url = target_url
                    break
            elif len(product_urls) == 1:
                # Direct redirect or single match default
                matched_url = target_url
                break

        except Exception as e:
            print(f"Error checking candidate URL {target_url}: {e}")
            continue

    if not matched_url:
        print(f"No exact Manufacturer Part Number match found for SKU {sku}")
        return None

    # --- Data Extraction Logic ---
    data = {"product_url": matched_url}

    title_elements = driver.find_elements("css selector", 'h1[id="product title"]')
    if title_elements:
        data["Product Title"] = title_elements[0].text.strip()
    else:
        first_h1 = driver.find_elements("css selector", "h1")
        data["Product Title"] = first_h1[0].text.strip() if first_h1 else ""

    price_elements = driver.find_elements(
        "css selector",
        "span:has(sup.decimal-price-subscription), [data-testid*='price']",
    )
    if price_elements:
        raw_price = price_elements[0].text
        data["price"] = re.sub(r"\s+", "", raw_price).strip()

    # --- Dynamic Tab Content Extraction ---
    tab_buttons = driver.find_elements(
        "css selector", '[role="tab"], button[id*="tab-"], button[id*="simple-tab"]'
    )

    for tab in tab_buttons:
        try:
            tab_name = tab.text.strip()
            if not tab_name or "Q&A" in tab_name:
                continue

            # Safely trigger click event in case tab is partially off-screen
            driver.execute_script("arguments[0].click();", tab)
            time.sleep(0.4)

            # Locate target panel by aria-controls attribute or active tabpanel
            controls_id = tab.get_attribute("aria-controls")
            if controls_id:
                panels = driver.find_elements("id", controls_id)
            else:
                panels = driver.find_elements("css selector", '[role="tabpanel"]:not([hidden])')

            if not panels:
                continue

            panel = panels[0]
            field_key = tab_name.lower().replace(" ", "_")

            # Special parsing for Specifications key-value pairs
            if "spec" in field_key:
                spec_rows = panel.find_elements("css selector", "tr, div.MuiGrid-item, div.spec-row")
                for row in spec_rows:
                    cells = row.find_elements("css selector", "td, th, p, span")
                    if len(cells) >= 2:
                        k, v = cells[0].text.strip(), cells[1].text.strip()
                        if k and v and k != v:
                            data[k] = v
            else:
                # Capture text for Ingredients, Caloric Content, Feeding Guide, Product Details, etc.
                text_content = panel.text.strip()
                if text_content:
                    data[field_key] = text_content

                # Also grab bullet points if present inside the active panel
                bullets = panel.find_elements("css selector", "ul li")
                if bullets:
                    data[f"{field_key}_bullets"] = [b.text.strip() for b in bullets if b.text.strip()]

        except Exception as e:
            print(f"Error processing tab '{tab.text}': {e}")

    # desc_panels = driver.find_elements(
    #     "css selector", "#simple-tabpanel-0, [id*='tabpanel-description']"
    # )
    # if desc_panels:
    #     paragraphs = desc_panels[0].find_elements("css selector", "p")
    #     p_texts = [p.text.strip() for p in paragraphs if p.text.strip()]
    #     if p_texts:
    #         data["description"] = "\n\n".join(p_texts)

    #     bullets = desc_panels[0].find_elements("css selector", "ul li")
    #     for idx, bullet in enumerate(bullets, start=1):
    #         bullet_text = bullet.text.strip()
    #         if bullet_text:
    #             data[f"feature_{idx}"] = bullet_text

    # doc_panels = driver.find_elements(
    #     "css selector", "#simple-tabpanel-1, [id*='tabpanel-documents']"
    # )
    # if doc_panels:
    #     doc_links = doc_panels[0].find_elements("css selector", "a[href]")
    #     for idx, link in enumerate(doc_links, start=1):
    #         title = link.text.strip()
    #         href = link.get_attribute("href")
    #         if href:
    #             data[f"document_title_{idx}"] = title
    #             data[f"document_url_{idx}"] = href

    # spec_panels = driver.find_elements(
    #     "css selector", "#simple-tabpanel-2, [id*='tabpanel-specifications']"
    # )
    # if spec_panels:
    #     spec_rows = spec_panels[0].find_elements(
    #         "css selector", "tr, div.MuiGrid-item, div.spec-row"
    #     )
    #     for row in spec_rows:
    #         cells = row.find_elements("css selector", "td, th, p, span")
    #         if len(cells) >= 2:
    #             key = cells[0].text.strip()
    #             val = cells[1].text.strip()
    #             if key and val and key != val:
    #                 data[key] = val

    return data

# import re
# import time
# from seleniumbase import Driver


# def get_details_from_trackter_spply(sku: str, driver: Driver) -> dict | None:
#     search_url = f"https://www.tractorsupply.com/tsc/search/{sku}?isIntSrch=written"
#     print("search url", search_url)

#     try:
#         print(f"Searching for SKU: {sku}...")

#         # Use uc_open_with_reconnect without calling driver.get afterwards
#         if hasattr(driver, "uc_open_with_reconnect"):
#             driver.uc_open_with_reconnect(search_url, reconnect_time=4)
#         else:
#             driver.get(search_url)

#         # Pause briefly to allow initial scripts/hydration to kick off
#         time.sleep(3)

#         # Check for WAF/Access Denied blocks directly
#         status_code = getattr(driver, "status_code", None)
#         page_title = driver.get_title()
#         page_source = driver.get_page_source()

#         if (
#             status_code in [403, 429]
#             or "Access Denied" in page_title
#             or "px-captcha" in page_source
#         ):
#             print(f"Blocked by WAF with status code {status_code or 'Forbidden'}")
#             return None

#         # --- Check for Direct Redirect to a Product Page ---
#         current_url = driver.get_current_url()
#         print("curnt url", current_url)
#         product_urls = []

#         if "/tsc/product/" in current_url or "/product/" in current_url:
#             print("Directly redirected to product page.")
#             product_urls = [current_url]
#         else:
#             # Trigger page scroll to activate lazy-loading React components
#             driver.execute_script("window.scrollTo(0, 400);")
#             time.sleep(1)

#             # Wait for EITHER product cards OR the no-results marker to show up.
#             # We check which one it was, instead of assuming "present" == products found.
#             found_no_results = False
#             try:
#                 driver.wait_for_element_present(
#                     ".new-product-card-v2, [data-testid*='product'], "
#                     "a[href*='/tsc/product/'], a[href*='/product/'], #no-results-found",
#                     timeout=15,
#                 )
#             except Exception:
#                 print("Timeout waiting for product cards to render in DOM.")

#             no_results_elements = driver.find_elements(
#                 "css selector", "#no-results-found"
#             )
#             if no_results_elements:
#                 found_no_results = True
#                 print(f"Site explicitly reported no results for SKU: {sku}")

#             if not found_no_results:
#                 # Give React a moment longer in case the grid is still hydrating
#                 time.sleep(3)
#                 print("waits finished")

#                 # Extract links using JavaScript execution to safely reach dynamic DOM nodes
#                 product_urls = driver.execute_script("""
#                     const links = Array.from(document.querySelectorAll('a[href*="/tsc/product/"], a[href*="/product/"]'));
#                     const urls = links.map(a => {
#                         let href = a.getAttribute('href');
#                         if (!href) return null;
#                         return href.startsWith('/') ? 'https://www.tractorsupply.com' + href : href;
#                     }).filter(Boolean);
#                     return Array.from(new Set(urls));
#                     """)

#                 # Fallback DOM element lookup
#                 if not product_urls:
#                     anchor_elements = driver.find_elements(
#                         "css selector", 'a[href*="/tsc/product/"], a[href*="/product/"]'
#                     )
#                     product_urls = []
#                     for anchor in anchor_elements:
#                         href = anchor.get_attribute("href")
#                         if href:
#                             full_url = (
#                                 f"https://www.tractorsupply.com{href}"
#                                 if href.startswith("/")
#                                 else href
#                             )
#                             if full_url not in product_urls:
#                                 product_urls.append(full_url)

#         if not product_urls:
#             # Dump diagnostics so failures are debuggable instead of a guessing game
#             print("Page title:", driver.get_title())
#             print("Current URL:", driver.get_current_url())
#             try:
#                 driver.save_screenshot(f"/tmp/debug_{sku}.png")
#                 with open(f"/tmp/debug_{sku}.html", "w", encoding="utf-8") as f:
#                     f.write(driver.get_page_source())
#                 print(
#                     f"Saved diagnostics to /tmp/debug_{sku}.png and /tmp/debug_{sku}.html"
#                 )
#             except Exception as diag_err:
#                 print(f"Could not save diagnostics: {diag_err}")

#             print(f"No product detail URLs found on the page for SKU: {sku}")
#             return None

#         print(f"Found {len(product_urls)} candidate product URL(s) for SKU: {sku}")

#     except Exception as e:
#         print(f"Error fetching search page for SKU {sku}: {e}")
#         return None

#     # --- Candidate Page Validation (Matching Manufacturer Part Number) ---
#     matched_url = None

#     for target_url in product_urls:
#         try:
#             if driver.get_current_url() != target_url:
#                 driver.get(target_url)

#             driver.wait_for_element("h1", timeout=10)

#             # Locate element containing "Manufacturer Part Number"
#             mfg_part_elements = driver.find_elements(
#                 "xpath",
#                 "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'manufacturer part number')]",
#             )

#             if mfg_part_elements:
#                 spec_text = driver.execute_script(
#                     "return arguments[0].closest('tr, li, div')?.innerText || arguments[0].parentElement.innerText;",
#                     mfg_part_elements[0],
#                 )

#                 if spec_text and sku.lower() in spec_text.lower():
#                     matched_url = target_url
#                     break
#             elif len(product_urls) == 1:
#                 # Direct redirect or single match default
#                 matched_url = target_url
#                 break

#         except Exception as e:
#             print(f"Error checking candidate URL {target_url}: {e}")
#             continue

#     if not matched_url:
#         print(f"No exact Manufacturer Part Number match found for SKU {sku}")
#         return None

#     # --- Data Extraction Logic ---
#     data = {"product_url": matched_url}

#     title_elements = driver.find_elements("css selector", 'h1[id="product title"]')
#     if title_elements:
#         data["Product Title"] = title_elements[0].text.strip()
#     else:
#         first_h1 = driver.find_elements("css selector", "h1")
#         data["Product Title"] = first_h1[0].text.strip() if first_h1 else ""

#     price_elements = driver.find_elements(
#         "css selector",
#         "span:has(sup.decimal-price-subscription), [data-testid*='price']",
#     )
#     if price_elements:
#         raw_price = price_elements[0].text
#         data["price"] = re.sub(r"\s+", "", raw_price).strip()

#     # --- Dynamic Tab Content Extraction ---
#     tab_buttons = driver.find_elements(
#         "css selector", '[role="tab"], button[id*="tab-"], button[id*="simple-tab"]'
#     )

#     for tab in tab_buttons:
#         try:
#             tab_name = tab.text.strip()
#             if not tab_name or "Q&A" in tab_name:
#                 continue

#             # Safely trigger click event in case tab is partially off-screen
#             driver.execute_script("arguments[0].click();", tab)
#             time.sleep(0.4)

#             # Locate target panel by aria-controls attribute or active tabpanel
#             controls_id = tab.get_attribute("aria-controls")
#             if controls_id:
#                 panels = driver.find_elements("id", controls_id)
#             else:
#                 panels = driver.find_elements(
#                     "css selector", '[role="tabpanel"]:not([hidden])'
#                 )

#             if not panels:
#                 continue

#             panel = panels[0]
#             field_key = tab_name.lower().replace(" ", "_")

#             # Special parsing for Specifications key-value pairs
#             if "spec" in field_key:
#                 spec_rows = panel.find_elements(
#                     "css selector", "tr, div.MuiGrid-item, div.spec-row"
#                 )
#                 for row in spec_rows:
#                     cells = row.find_elements("css selector", "td, th, p, span")
#                     if len(cells) >= 2:
#                         k, v = cells[0].text.strip(), cells[1].text.strip()
#                         if k and v and k != v:
#                             data[k] = v
#             else:
#                 # Capture text for Ingredients, Caloric Content, Feeding Guide, Product Details, etc.
#                 text_content = panel.text.strip()
#                 if text_content:
#                     data[field_key] = text_content

#                 # Also grab bullet points if present inside the active panel
#                 bullets = panel.find_elements("css selector", "ul li")
#                 if bullets:
#                     data[f"{field_key}_bullets"] = [
#                         b.text.strip() for b in bullets if b.text.strip()
#                     ]

#         except Exception as e:
#             print(f"Error processing tab '{tab.text}': {e}")

#     return data
