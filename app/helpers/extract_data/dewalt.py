from urllib.parse import quote
from bs4 import BeautifulSoup
from seleniumbase import Driver


def clean_text(text: str | None) -> str:
    """Strip redundant whitespace."""
    return " ".join(text.split()) if text else ""


def open_dewalt_elements(driver: Driver):
    """Expand all accordions and click 'See More' in specifications."""
    # 1. Expand all collapsed accordions in one JS call
    driver.execute_script("""
        document.querySelectorAll("[data-testid-key] button[aria-expanded='false']").forEach(b => b.click());
    """)
    driver.sleep(0.3)

    # 2. Click "See More" in specifications if present
    see_more = "[data-testid-key='specifications'] button:has([data-testid='AddIcon'])"
    if driver.is_element_present(see_more):
        driver.click(see_more)
        driver.sleep(0.3)


def extract_data_from_dewalt(soup: BeautifulSoup) -> dict:
    """Parses product page HTML into a clean dictionary."""
    data = {
        "product_title": "",
        "model_number": "",
        "description": "",
        "image_url": "",
        "warranty": "",
        "services": "",
    }

    # Title & Model
    h1 = soup.find("h1")
    if h1:
        data["product_title"] = clean_text(h1.get_text())

    model = soup.select_one("[data-testid='product-label__code']")
    if model:
        data["model_number"] = clean_text(model.get_text())

    # Image
    img = soup.select_one("div[tabindex='-1'] img[src*='assets.dewalt.com']")
    if img and img.get("src"):
        data["image_url"] = img["src"]

    details = soup.select_one("[data-testid='product-details-section']")
    if not details:
        return data

    # Overview Description
    overview = details.select_one("[data-testid-key='overview'] [role='region']")
    if overview:
        data["description"] = clean_text(overview.get_text())

    # Warranty
    warranty = details.select_one("[data-testid-key='warranty'] [role='region']")
    if warranty:
        data["warranty"] = clean_text(warranty.get_text())

    # Services
    services = details.select_one("[data-testid-key='services'] [role='region']")
    if services:
        data["services"] = clean_text(services.get_text())

    # Features (Feature 1, Feature 2, ...)
    features = details.select("[data-testid-key='features'] li")
    for idx, item in enumerate(features, 1):
        txt = clean_text(item.get_text())
        if txt:
            data[f"Feature {idx}"] = txt

    # Specifications (Dynamic Key: Value)
    specs = details.select("[data-testid-key='specifications'] .flex.justify-between")
    for row in specs:
        cols = row.find_all("div", recursive=False)
        if len(cols) == 2:
            k = clean_text(cols[0].get_text())
            v = clean_text(cols[1].get_text())
            if k and v:
                data[k] = v

    # Includes (Include 1, Include 2, ...)
    includes = details.select("[data-testid-key='includes'] li")
    for idx, item in enumerate(includes, 1):
        txt = clean_text(item.get_text())
        if txt:
            data[f"Include {idx}"] = txt

    return data


def get_data_from_dewalt(sku: str, driver: Driver) -> dict:
    """Main scraping routine."""
    search_url = (
        "https://www.dewalt.com/en-us/search"
        f"?prod_main_en-us%5Bquery%5D={quote(sku)}"
        "&prod_main_en-us%5BrefinementList%5D%5Btype%5D%5B0%5D=product"
    )

    try:
        driver.get(search_url)
        driver.wait_for_element(
            "article[data-testid='product-card__container']", timeout=12
        )

        cards = driver.execute_script("""
            return Array.from(document.querySelectorAll("article[data-testid='product-card__container']")).map(c => ({
                sku: c.querySelector("span[data-testid='product-label__code']")?.textContent?.trim() || "",
                href: c.querySelector("a")?.href || ""
            }));
        """)

        target_sku = sku.strip().lower()
        product_url = next(
            (c["href"] for c in cards if c["sku"].lower() == target_sku), None
        )

        if not product_url:
            return {"error": "product not found", "SKU": sku, "url": search_url}

        driver.get(product_url)
        driver.wait_for_element("[data-testid='product-details-section']", timeout=12)

        open_dewalt_elements(driver)

        soup = BeautifulSoup(driver.get_page_source(), "html.parser")
        data = extract_data_from_dewalt(soup)

        data["SKU"] = sku
        data["url"] = product_url
        return data

    except Exception as e:
        return {"error": str(e), "SKU": sku, "url": search_url}
