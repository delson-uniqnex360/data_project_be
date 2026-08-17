import json
from bs4 import BeautifulSoup

with open("page.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

print("=" * 50)
print("1. CHECKING FOR EMBEDDED JSON DATA")
print("=" * 50)

# Check for Next.js preloaded state
next_data = soup.find("script", id="__NEXT_DATA__")
if next_data:
    print("Found __NEXT_DATA__ script tag!")
    try:
        data = json.loads(next_data.string)
        # Check if product details exist inside JSON
        data_str = json.dumps(data)
        if "identifiers" in data_str or "specs" in data_str:
            print("Product specifications are available directly inside __NEXT_DATA__ JSON.")
    except Exception as e:
        print("Could not parse __NEXT_DATA__ JSON:", e)
else:
    print("No __NEXT_DATA__ tag found.")

# Check for JSON-LD schema
ld_json = soup.find_all("script", type="application/ld+json")
print(f"Found {len(ld_json)} application/ld+json script tag(s).")

print("\n" + "=" * 50)
print("2. LOCATING SPECIFICATIONS / ACCORDION CONTAINERS")
print("=" * 50)

# Find elements containing key target phrases
keywords = ["Product Details", "Specifications", "About This Product", "Highlights"]

for kw in keywords:
    matches = soup.find_all(lambda tag: tag.string and kw.lower() in tag.string.lower())
    print(f"\n--- Searching for keyword: '{kw}' ({len(matches)} found) ---")
    
    for i, tag in enumerate(matches[:2]):  # Limit to first 2 matches
        print(f"\nMatch {i+1}:")
        print(f"Tag: <{tag.name}> | Classes: {tag.get('class')} | Attrs: {tag.attrs}")
        
        # Print parent hierarchy up to 3 levels
        parent = tag.parent
        level = 1
        while parent and level <= 3:
            print(f"  Parent L{level}: <{parent.name}> id='{parent.get('id', '')}' class='{parent.get('class', '')}' data-testid='{parent.get('data-testid', '')}'")
            parent = parent.parent
            level += 1