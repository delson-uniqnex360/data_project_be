from typing import Optional

from bs4 import BeautifulSoup
from seleniumbase import Driver


def click_element(driver: Driver, element) -> bool:
    try:
        driver.execute_script(
            "arguments[0].click();",
            element,
        )
        return True
    except Exception as e:
        print(f"Could not click element: {e}")
        return False


def open_section(driver: Driver, section_id: str) -> bool:
    try:
        element = driver.find_element("id", section_id)
        return click_element(driver, element)
    except Exception as e:
        print(f"Could not open section {section_id}: {e}")
        return False


def click_read_more(driver: Driver, section_selector: str) -> bool:
    try:
        section = driver.find_element(
            "css selector",
            section_selector,
        )

        read_more = section.find_element(
            "css selector",
            ".more-label.js-toggle",
        )

        return click_element(driver, read_more)

    except Exception:
        return False


def extract_product_title(soup: BeautifulSoup) -> Optional[str]:
    element = soup.select_one(".product-description")

    if not element:
        return None

    return element.get_text(" ", strip=True)


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    element = soup.select_one(".model-number")

    if not element:
        return None

    status_label = element.select_one(".status-label")

    if status_label:
        status_label.extract()

    return element.get_text(" ", strip=True)


def extract_about(soup: BeautifulSoup) -> dict:
    about_list = [
        text
        for element in soup.select(".detail-about p.dyn-expand")
        if (text := element.get_text(" ", strip=True))
    ]

    return {"About": about_list}


def extract_features(soup: BeautifulSoup) -> dict:
    data = {}

    index = 1

    for element in soup.select(".ul-features li"):
        text = element.get_text(" ", strip=True)

        if not text:
            continue

        data[f"feature_{index}"] = text
        index += 1

    return data


def extract_technology(soup: BeautifulSoup) -> dict:
    data = {}

    section = soup.select_one(".product-detail-innovation")

    if not section:
        return data

    index = 1

    # Each .tech block is its own logo + description pair, and there can
    # be several of them, so iterate over every block instead of only
    # grabbing the first logo/description in the whole section.
    for tech_block in section.select(".tech"):
        logo = tech_block.select_one(".logo-div img")
        description = tech_block.select_one(".tech-description")

        name = ""
        if logo:
            name = (logo.get("alt") or "").strip()

        value = ""
        if description:
            value = description.get_text(" ", strip=True)

        if not name and not value:
            continue

        if name:
            data[f"technology_{index}"] = name

        if value:
            data[f"technology_{index}_description"] = value

        index += 1

    return data


def extract_specs(soup: BeautifulSoup) -> dict:
    data = {}

    for item in soup.select(".detail-specs .spec-name"):
        value_element = item.find_next_sibling(class_="spec-value")

        if not value_element:
            continue

        key = (
            item.get_text(
                " ",
                strip=True,
            )
            .rstrip(":")
            .strip()
        )

        value = value_element.get_text(
            " ",
            strip=True,
        )

        if key and value:
            data[key] = value

    return data


def extract_includes(soup: BeautifulSoup) -> dict:
    data = {}

    for index, element in enumerate(
        soup.select(".detail-includes li"),
        start=1,
    ):
        value = element.get_text(
            " ",
            strip=True,
        )

        if value:
            data[f"includes_{index}"] = value

    return data


def extract_resources(soup: BeautifulSoup) -> dict:
    data = {}

    for index, link in enumerate(
        soup.select(".detail-resources a"),
        start=1,
    ):
        title = (link.get("title") or link.get_text(" ", strip=True)).strip()

        href = link.get("href")

        if title and href:
            data[f"resource_{index}"] = f"{title}: {href}"

    return data


def extract_product_image(soup: BeautifulSoup) -> Optional[str]:
    element = soup.select_one("#js-product-image-shot")

    if not element:
        return None

    return element.get("data-dyn-url") or element.get("src")


def extract_data_from_makita(
    soup: BeautifulSoup,
) -> Optional[dict]:

    product_title = extract_product_title(soup)

    if not product_title:
        return None

    data = {
        "Product Title": product_title,
    }

    model_number = extract_model_number(soup)

    if model_number:
        data["model_number"] = model_number

    image_url = extract_product_image(soup)
 
    if image_url:
        data["image_url"] = image_url

    # Everything is flattened into the same dictionary.
    data.update(extract_about(soup))
    data.update(extract_features(soup))
    data.update(extract_technology(soup))
    data.update(extract_specs(soup))
    data.update(extract_includes(soup))
    data.update(extract_resources(soup))

    return data


def get_data_from_makita(
    sku: str,
    driver: Driver,
):

    try:
        url = f"https://makitatools.com/" f"products/details/{sku}"

        driver.get(url)

        # Open About
        open_section(
            driver,
            "js-about-model",
        )

        click_read_more(
            driver,
            ".detail-about",
        )

        # Open Features
        open_section(
            driver,
            "js-features",
        )

        click_read_more(
            driver,
            ".detail-section:has(.ul-features)",
        )

        # Open Technology
        technology_button = driver.find_elements(
            "css selector",
            ".innovation-wrapper .js-page-nav",
        )

        if technology_button:
            click_element(
                driver,
                technology_button[0],
            )

        # Open Specs
        open_section(
            driver,
            "js-specs",
        )

        # Open Includes
        open_section(
            driver,
            "js-includes",
        )

        # Open Resources
        open_section(
            driver,
            "js-resource-media",
        )

        driver.sleep(1)

        soup = BeautifulSoup(
            driver.get_page_source(),
            "html.parser",
        )

        data = extract_data_from_makita(soup)

        # Only return an error when there is actually an error.
        if data is None:
            return {"error": (f"SKU {sku} not found " "on the MAKITA website")}

        return data

    except Exception as e:
        print(f"Error scraping Makita SKU " f"'{sku}': {e}")

        return {"error": (f"Error scraping SKU {sku} " f"from the MAKITA website: {e}")}
