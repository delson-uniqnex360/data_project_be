import re
from collections import defaultdict
from app.helpers.extract_data.helpers import dedupe_by_similarity

# Matches keys like "feature_1", "Feature 1", "technology_2" -> prefix="feature"/"technology"
_NUMBERED_KEY_RE = re.compile(r"^(?P<prefix>.*?)[\s_]*(?P<num>\d+)$")


def normalize_key(key: str) -> str:
    """Standardize a column name so equivalent keys from different
    sources collapse to the same field, e.g. "SKU" / "sku" and
    "Attribute 1" / "Attribute_1" are treated as identical.
    """
    key = (key or "").strip()
    key = re.sub(r"[\s_]+", " ", key)
    return key.lower()


def numbered_key_prefix(normalized_key: str):
    """Return the prefix of a numbered key (e.g. "feature 1" -> "feature"),
    or None if the key isn't numbered.
    """
    match = _NUMBERED_KEY_RE.match(normalized_key)
    if not match:
        return None
    prefix = match.group("prefix").strip()
    return prefix or None


def merge_sku_items(items: list[dict]) -> dict:
    """Merge multiple per-SKU dicts into a single row.

    - Keys are standardized (case/spacing/underscore insensitive) so
      duplicate columns from different sources don't get split apart.
    - Numbered attributes (feature_1, technology_2, includes_3, ...) are
      NEVER merged into one cell. Every numbered value across all items
      is collected and renumbered sequentially (feature_1, feature_2, ...)
      so nothing gets overwritten or concatenated together.
    - All other fields are deduped (case-insensitive) and joined with
      ", " when values differ.
    """
    plain_values = defaultdict(list)
    numbered_values = defaultdict(list)
    display_keys = {}

    for item in items:
        for raw_key, raw_value in item.items():
            if raw_value is None or str(raw_value).strip() == "":
                continue

            value = str(raw_value).strip()
            normalized = normalize_key(raw_key)
            prefix = numbered_key_prefix(normalized)

            if prefix:
                numbered_values[prefix].append(value)
            else:
                display_keys.setdefault(normalized, raw_key)
                plain_values[normalized].append(value)

    merged = {}

    for normalized, values in plain_values.items():
        seen = set()
        deduped = []
        for v in values:
            v_lower = v.lower()
            if v_lower not in seen:
                seen.add(v_lower)
                deduped.append(v)
        merged[display_keys[normalized]] = ", ".join(deduped)

    for prefix, values in numbered_values.items():
        deduped_values = dedupe_by_similarity(
            values
        )  # e.g. ["Waterproof", "Bluetooth 5.0"]
        for i, value in enumerate(deduped_values, start=1):
            merged[f"{prefix}_{i}"] = value  # merged["feature_1"] = "Waterproof"
            # merged["feature_2"] = "Bluetooth 5.0"

    return merged


from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

import app.core.browser as browser
from app.helpers import (
    create_excel_file,
    read_excel_file,
    redirects_row_data,
)

router = APIRouter()

SUPPORTED_EXTENSIONS = {
    ".xlsx",
}


@router.post("/")
async def extract_excel_file(
    upload_file: UploadFile = File(...),
):
    extension = Path(upload_file.filename or "").suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file format: {extension}. "
                f"Supported formats: "
                f"{', '.join(SUPPORTED_EXTENSIONS)}"
            ),
        )

    temp_path = None

    try:
        with NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temp_file:

            temp_path = Path(temp_file.name)

            while chunk := await upload_file.read(1024 * 1024):
                temp_file.write(chunk)

        # Read Excel
        headers, rows = read_excel_file(temp_path)

        # Process rows
        raw_results = []

        for row in rows:
            # Returns a list of dicts (one per website)
            row_site_results = await redirects_row_data(row, browser)

            sku = row.get("OEM Part Number / SKU")
            for item in row_site_results:
                item["SKU"] = sku
                raw_results.append(item)

        print("raw results", raw_results)
        # -------------------------------------------------------------
        # Group by SKU & merge each SKU's items into a single row.
        # Key names are standardized (case/spacing/underscore) and
        # numbered attributes (feature_1, technology_2, ...) are
        # dynamically renumbered instead of being joined into one cell.
        # See app/helpers/sku_merge.py.
        # -------------------------------------------------------------
        grouped_by_sku = defaultdict(list)
        for item in raw_results:
            sku = item.get("SKU")
            grouped_by_sku[sku].append(item)

        normalized_results = [
            merge_sku_items(items) for items in grouped_by_sku.values()
        ]

        # Union of all columns across every row, preserving first-seen
        # order, so every output row has the exact same set of columns.
        all_keys = list(
            dict.fromkeys(key for row in normalized_results for key in row.keys())
        )

        normalized_results = [
            {key: row.get(key) for key in all_keys} for row in normalized_results
        ]

        print("results", normalized_results)

        # Create Excel in memory
        excel_file, filename = create_excel_file(
            data=normalized_results,
            filename="products.xlsx",
        )

        return StreamingResponse(
            excel_file,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    finally:
        # Delete temporary uploaded file
        if temp_path and temp_path.exists():
            temp_path.unlink()

        # Close uploaded file
        await upload_file.close()
