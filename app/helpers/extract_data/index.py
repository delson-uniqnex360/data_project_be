from typing import Any, Dict, List

from .genuie_parts_factory import get_data_from_genuine_factory_parts
from .home_depot import get_data_from_home_depot
from .stens import get_data_from_stens
from .trackter_supply import get_details_from_trackter_spply
from .oregon import get_data_from_oregon
from .makita import get_data_from_makita
from .dewalt import get_data_from_dewalt


async def redirects_row_data(row: dict, browser) -> List[Dict[str, Any]]:
    oem = str(row.get("OEM Part Number / SKU"))
    brand = row.get("Product Manufacturer / Brand") or row.get("Product Manufacturer")

    completed_brands = {
        "Genuine Factory Parts",
        "Home Depot",
        "Stens",
        "Tractor Supply",
        "Oregon",
        "Makita",
        "DEWALT",
    }

    # Define list of target sites (deduplicated while preserving order)
    raw_websites = [
        # "Genuine Factory Parts",
        "Home Depot",  # -> list to detail check
        # "Stens",
        # "Oregon",
        # "Makita",
        # "DEWALT",
        # "Tractor Supply",
    ]
    websites = list(dict.fromkeys(site for site in raw_websites if site))

    site_results = []
    for site in websites:
        try:
            if site not in completed_brands:
                site_results.append({"error": f"Dev Pending {site}"})

            data = None
            if site == "Stens":
                data = await get_data_from_stens(oem)
            elif site == "Tractor Supply":
                data =  get_details_from_trackter_spply(oem, browser)
            elif site == "Home Depot":
                data = await get_data_from_home_depot(oem, browser)
            elif site == "Genuine Factory Parts":
                data = await get_data_from_genuine_factory_parts(oem, browser)
            elif site == "Oregon":
                data = get_data_from_oregon(oem, browser)
            elif site == "Makita":
                data = get_data_from_makita(oem, browser)
            elif site == "DEWALT":
                data = get_data_from_dewalt(oem, browser)

            # Attach site name if missing, then collect
            if isinstance(data, dict):
                site_results.append(data)
        except Exception as e:
            print("error", e)
            continue

    return site_results
