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
        # Group by SKU & Merge into a single row per SKU
        # -------------------------------------------------------------
        grouped_by_sku = defaultdict(list)
        for item in raw_results:
            sku = item.get("SKU")
            grouped_by_sku[sku].append(item)

        # Gather ALL unique keys across EVERY item, globally,
        # so every output row has the exact same set of columns.
        all_keys = list(
            dict.fromkeys(key for item in raw_results for key in item.keys())
        )

        normalized_results = []

        for sku, items in grouped_by_sku.items():
            merged_dict = {}

            for key in all_keys:
                # Collect all non-None, non-empty values for this key
                # across this SKU's items, trimming whitespace so that
                # values differing only in stray spaces are still
                # recognized as duplicates.
                values = [
                    str(item[key]).strip()
                    for item in items
                    if item.get(key) is not None and str(item[key]).strip() != ""
                ]

                if not values:
                    merged_dict[key] = None
                else:
                    # Dedupe case-insensitively while preserving the
                    # first-seen casing and order, then join any
                    # remaining distinct values with a comma.
                    seen_lower = set()
                    deduped_values = []
                    for v in values:
                        v_lower = v.lower()
                        if v_lower not in seen_lower:
                            seen_lower.add(v_lower)
                            deduped_values.append(v)

                    merged_dict[key] = ", ".join(deduped_values)

            normalized_results.append(merged_dict)

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
