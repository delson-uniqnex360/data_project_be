import asyncio
import re
from playwright.async_api import async_playwright

# Import the Stealth class (works in playwright-stealth >= 2.0)
from playwright_stealth import Stealth


async def get_details_from_trackter_spply(sku: str) -> dict | None:
    search_url = f"https://www.tractorsupply.com/tsc/search/{sku}?isIntSrch=written"

    # Instantiate Stealth object
    stealth = Stealth()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-http2",
                "--disable-infobars",
                "--window-size=1920,1080",
            ],
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            has_touch=False,
            is_mobile=False,
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Apply stealth to the context in v2.x
        await stealth.apply_stealth_async(context)

        page = await context.new_page()

        try:
            print(f"Searching for SKU: {sku}...")
            response = await page.goto(
                search_url, wait_until="commit", timeout=30000
            )

            if response and response.status in [403, 429]:
                print(f"Blocked by WAF with status code {response.status}")
                await browser.close()
                return None

            await page.wait_for_selector(
                ".new-product-card-v2, #no-results-found", timeout=15000
            )

        except Exception as e:
            print(f"Failed to load search page for SKU {sku}: {e}")
            await browser.close()
            return None

        # --- Product card matching logic ---
        product_cards = page.locator(".new-product-card-v2")
        card_count = await product_cards.count()

        if card_count == 0:
            print(f"No product cards found for SKU {sku}")
            await browser.close()
            return None

        product_urls = []
        for i in range(card_count):
            card = product_cards.nth(i)
            link_element = card.locator('a[href*="/tsc/product/"]').first
            if await link_element.count() > 0:
                href = await link_element.get_attribute("href")
                if href:
                    full_url = (
                        f"https://www.tractorsupply.com{href}"
                        if href.startswith("/")
                        else href
                    )
                    product_urls.append(full_url)

        matched_url = None

        for target_url in product_urls:
            try:

                await page.goto(
                    target_url, wait_until="commit", timeout=25000
                )
                await page.wait_for_selector("h1", timeout=10000)

                mfg_part_locator = page.locator("text=/Manufacturer Part Number/i")
                if await mfg_part_locator.count() > 0:
                    spec_text = await mfg_part_locator.first.evaluate(
                        "el => el.closest('tr, li, div')?.innerText || el.parentElement.innerText"
                    )

                    if sku.lower() in spec_text.lower():
                        matched_url = target_url
                        break
            except Exception as e:
                print(f"Error checking candidate URL {target_url}: {e}")
                continue

        if not matched_url:
            print(f"No exact Manufacturer Part Number match found for SKU {sku}")
            await browser.close()
            return None

        # --- Extraction logic ---
        data = {"product_url": matched_url}

        title_locator = page.locator('h1[id="product title"]')
        if await title_locator.count() > 0:
            data["Product Title"] = (await title_locator.inner_text()).strip()
        else:
            data["Product Title"] = (await page.locator("h1").first.inner_text()).strip()

        price_locator = page.locator("span:has(sup.decimal-price-subscription)")
        if await price_locator.count() > 0:
            raw_price = await price_locator.first.inner_text()
            data["price"] = re.sub(r"\s+", "", raw_price).strip()

        desc_panel = page.locator("#simple-tabpanel-0")
        if await desc_panel.count() > 0:
            paragraphs = desc_panel.locator("p")
            p_texts = [
                (await paragraphs.nth(p).inner_text()).strip()
                for p in range(await paragraphs.count())
            ]
            if p_texts:
                data["description"] = "\n\n".join([p for p in p_texts if p])

            bullets = desc_panel.locator("ul li")
            for idx in range(await bullets.count()):
                bullet_text = (await bullets.nth(idx).inner_text()).strip()
                if bullet_text:
                    data[f"feature_{idx + 1}"] = bullet_text

        doc_panel = page.locator("#simple-tabpanel-1")
        if await doc_panel.count() > 0:
            doc_links = doc_panel.locator("a[href]")
            for idx in range(await doc_links.count()):
                link = doc_links.nth(idx)
                title = (await link.inner_text()).strip()
                href = await link.get_attribute("href")

                if href:
                    data[f"document_title_{idx + 1}"] = title
                    data[f"document_url_{idx + 1}"] = href

        spec_panel = page.locator("#simple-tabpanel-2")
        if await spec_panel.count() > 0:
            spec_rows = spec_panel.locator("tr, div.MuiGrid-item, div.spec-row")
            for r in range(await spec_rows.count()):
                row = spec_rows.nth(r)
                cells = row.locator("td, th, p, span")

                if await cells.count() >= 2:
                    key = (await cells.nth(0).inner_text()).strip()
                    val = (await cells.nth(1).inner_text()).strip()

                    if key and val and key != val:
                        data[key] = val

        await browser.close()
        return data
