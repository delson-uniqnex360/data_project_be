import time
import numpy as np
from functools import lru_cache
from sentence_transformers import SentenceTransformer

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# Cosine similarity threshold above which two values are treated as
# duplicates. Raise it to be stricter (keep more, only drop near-exact
# matches); lower it to be more aggressive about merging similar meanings.
SIMILARITY_THRESHOLD = 0.85

# Small, fast, good general-purpose sentence embedding model.
_MODEL_NAME = "all-MiniLM-L6-v2"


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


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    # Loaded once per process and cached. Uses the ONNX backend for
    # faster CPU inference (requires sentence-transformers[onnx]).
    return SentenceTransformer(_MODEL_NAME, backend="onnx")


def dedupe_by_similarity(
    values: list[str],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[str]:
    """Remove values that are semantically equivalent to an earlier value.

    Keeps the first occurrence of each "meaning" and drops any later value
    whose cosine similarity to an already-kept value is >= threshold.
    Order of first-seen (kept) values is preserved.

    Args:
        values: list of raw string values (e.g. all "feature_*" values
            collected for one SKU before renumbering).
        threshold: cosine similarity cutoff, in [-1, 1]. Defaults to
            SIMILARITY_THRESHOLD.

    Returns:
        A new list with semantic duplicates removed.
    """
    if not values:
        return []

    if len(values) == 1:
        return values[:]

    model = _get_model()
    embeddings = model.encode(values, normalize_embeddings=True)

    kept_indices: list[int] = []
    kept_embeddings: list[np.ndarray] = []

    for i, emb in enumerate(embeddings):
        is_duplicate = False
        for kept_emb in kept_embeddings:
            # embeddings are normalized -> dot product == cosine similarity
            similarity = float(np.dot(emb, kept_emb))
            if similarity >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            kept_indices.append(i)
            kept_embeddings.append(emb)

    return [values[i] for i in kept_indices]
