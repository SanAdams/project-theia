import json, re
from pathlib import Path

PRODUCTS_PATH = Path(__file__).parent.parent / "products.json"

with open(PRODUCTS_PATH) as f:
    products = json.load(f)

bad = [p for p in products if re.search(r"\d{6,}", p["name"])]
print(f"Names with long digit runs: {len(bad)}")
for p in bad:
    print(f"  {p['CIC Code']}  {repr(p['name'])}")

print(f"\nTotal: {len(products)}")
print("\nAll entries:")
for p in products:
    print(f"  p{p['page']}  {p['CIC Code']}  {repr(p['name'])}")
