import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains


def open_all_accordions(driver):
    selector = 'div[role="button"][aria-expanded="false"]'
    opened_count = 0

    while True:
        # Re-fetch remaining collapsed accordions to prevent StaleElementReferenceException
        accordions = driver.find_elements(By.CSS_SELECTOR, selector)

        # Stop if no collapsed accordions remain
        if not accordions:
            break

        accordion = accordions[0]
        title = accordion.text.split("\n")[0].strip() or "Accordion"
        print(f"Attempting to open: '{title}'...")

        try:
            # 1. Scroll the element into the center of the viewport
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", accordion
            )
            time.sleep(0.5)

            # 2. Try standard Selenium click
            accordion.click()

        except Exception:
            try:
                # Fallback 1: ActionChains move & click
                ActionChains(driver).move_to_element(accordion).click().perform()
            except Exception:
                try:
                    # Fallback 2: Send ENTER key (works natively on tabindex="0" buttons)
                    accordion.send_keys(Keys.ENTER)
                except Exception:
                    # Fallback 3: JavaScript click
                    driver.execute_script("arguments[0].click();", accordion)

        opened_count += 1

        # Wait for React to fetch and inject the newly opened content into the DOM
        time.sleep(1.5)

    print(f"Successfully opened {opened_count} accordion(s).")
