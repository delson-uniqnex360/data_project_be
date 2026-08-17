from pathlib import Path

import polars as pl


def read_excel_file(file_path: Path) -> tuple[list[str], list[dict]]:
    """
    Read an Excel file and return headers and rows.

    Returns:
        headers: List of column names
        rows: List of dictionaries, one per row
    """

    df = pl.read_excel(
        file_path,
        engine="calamine",
    )

    headers = df.columns
    rows = df.to_dicts()

    return headers, rows