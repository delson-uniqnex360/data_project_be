from typing import Any, Dict, List

from .genuie_parts_factory import get_data_from_genuine_factory_parts
from .home_depot import get_data_from_home_depot
from .stens import get_data_from_stens
from .trackter_supply import get_details_from_trackter_spply
from .oregon import get_data_from_oregon


async def redirects_row_data(row: dict, browser) -> List[Dict[str, Any]]:
    oem = str(row.get("OEM Part Number / SKU"))
    brand = row.get("Product Manufacturer / Brand") or row.get("Product Manufacturer")

    completed_brands = {
        "Genuine Factory Parts",
        "Home Depot",
        "Stens",
        # "Tractor Supply",
        "Oregon",
    }

    # Define list of target sites (deduplicated while preserving order)
    raw_websites = [
        "Genuine Factory Parts",
        "Home Depot",  # -> list to detail check
        "Stens",
        "Oregon",
    ]
    websites = list(dict.fromkeys(site for site in raw_websites if site))

    site_results = []
    for site in websites:
        if site not in completed_brands:
            site_results.append({"error": f"Dev Pending {site}"})

        data = None
        if site == "Stens":
            data = await get_data_from_stens(oem)
        elif site == "Tractor Supply":
            data = await get_details_from_trackter_spply(oem)
        elif site == "Home Depot":
            data = await get_data_from_home_depot(oem, browser)
        elif site == "Genuine Factory Parts":
            data = await get_data_from_genuine_factory_parts(oem, browser)
        elif site == "Oregon":
            data = get_data_from_oregon(oem, browser)

        # Attach site name if missing, then collect
        if isinstance(data, dict):
            site_results.append(data)
    return site_results
