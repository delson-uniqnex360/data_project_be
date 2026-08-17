import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


from bs4 import BeautifulSoup


def extract_data_from_html(soup: BeautifulSoup) -> dict:
    data = {}

    # --------------------------------------------------
    # Product Title
    # --------------------------------------------------
    product_title = soup.select_one("#header-wrapper h1")

    if product_title:
        data["Product Title"] = product_title.get_text(" ", strip=True)

    # --------------------------------------------------
    # Product Description
    # --------------------------------------------------
    product_desc = soup.select_one("#product-description")

    if product_desc:
        data["Description"] = product_desc.get_text(" ", strip=True)

    # --------------------------------------------------
    # Product Details
    # --------------------------------------------------
    product_details = soup.select_one("#product-details")

    if product_details:
        data["Detail"] = ", ".join(
            li.get_text(" ", strip=True) for li in product_details.find_all("li")
        )

    # --------------------------------------------------
    # Specification Tables
    # Automatically extracts:
    # <th>Volume</th> -> <td>78.43 in³</td>
    # --------------------------------------------------
    for row in soup.select(".spec-table tr"):
        key = row.find("th")
        value = row.find("td")

        if key and value:
            key = key.get_text(" ", strip=True)
            value = value.get_text(" ", strip=True)

            if key:
                data[key] = value

    # --------------------------------------------------
    # Guides
    # Automatically extracts Fit Guide / Replacement Guide
    # --------------------------------------------------
    for container in soup.select(".js-accordion-container"):

        # Example: Fit Guide / Replacement Guide
        guide_name = container.find("h3")

        if not guide_name:
            continue

        guide_name = guide_name.get_text(" ", strip=True)

        # Each subsection, e.g. Tecumseh / Rotary
        for section in container.select(":scope > section"):

            button = section.select_one(".js-accordion-header")

            if not button:
                continue

            # Get the manufacturer/category name
            spans = button.find_all("span")

            if not spans:
                continue

            category = spans[-1].get_text(" ", strip=True)

            # Get all values
            values = [li.get_text(" ", strip=True) for li in section.select("li")]

            values = [value for value in values if value]

            if not values:
                continue

            # Create dynamic key
            key = f"{guide_name} - {category}"

            data[key] = ", ".join(values)

    return data


def get_data_from_oregon(sku: str, driver) -> dict:
    # 1. Open Oregon homepage
    driver.get("https://www.oregonproducts.com/en/")
    time.sleep(2)

    # 2. Type SKU into search box and press Enter
    search_input = driver.find_element(By.ID, "js-autocomplete-SearchBox")
    search_input.clear()
    search_input.send_keys(sku, Keys.ENTER)
    time.sleep(3)

    # 3. Find all product items in the search results list
    items = driver.find_elements(
        By.CSS_SELECTOR, "ul.js-result-list li.js-result-list-item"
    )

    # Clean the target SKU for strict comparison
    clean_sku = sku.strip().lower()

    # 4. Iterate through items to match Part# with target SKU
    for item in items:
        try:
            part_element = item.find_element(By.CSS_SELECTOR, ".js-product-code")
            # Extract number from text like "Part# 50-641" -> "50-641"
            part_number = part_element.text.replace("Part#", "").strip().lower()

            if part_number == clean_sku:
                title_link = item.find_element(By.CSS_SELECTOR, "a.js-result-title")
                title_link.click()
                time.sleep(3)

                soup = BeautifulSoup(driver.get_page_source())

                return extract_data_from_html(soup)
        except Exception as e:
            print("e", e)
            continue

    # 5. Fallback if no matching product was found
    return {"error": f"product {sku} not found on Oregon website"}
