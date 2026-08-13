from services.shopify_client import ShopifyClient
import requests
from collections import defaultdict
import re

c = ShopifyClient()
url = f'{c.base_url}/products.json?limit=250'
prods = []

print("Fetching products...")
while url:
    resp = requests.get(url, headers=c.headers, timeout=15)
    prods.extend(resp.json().get('products', []))
    link = resp.headers.get('Link')
    url = None
    if link and 'rel="next"' in link:
        links = link.split(', ')
        for l in links:
            if 'rel="next"' in l:
                url = l[l.index('<')+1 : l.index('>')]
                break

print(f"Total products: {len(prods)}")

def parse_title(title):
    parts = [p.strip() for p in title.split(' - ')]
    if len(parts) >= 3:
        # Assuming format: Name - Number - [Variant -] Set Name [- Grade]
        name = parts[0]
        # To get the set name, we might just look at parts[-1] if not graded, or parts[-2] if graded.
        # But this might be too complex. Alternatively, just use the first part as name.
        # Actually, let's normalize the title by removing the number if it's mostly digits/slashes
        # Just use name and the last part (usually set)
        set_name = parts[-1]
        
        # If it's graded, the last part might be the grade.
        if any(g in set_name for g in ['PSA', 'BGS', 'CGC', 'Grade']):
            set_name = parts[-2] if len(parts) > 3 else set_name
            
        return name.lower(), set_name.lower()
    return title.lower(), ""

groups = defaultdict(list)
for p in prods:
    # We want to skip exact title duplicates because we already cleaned those up
    # We want to find fuzzy duplicates
    name, set_name = parse_title(p['title'])
    groups[(name, set_name)].append(p)

found = 0
for (name, set_name), group in groups.items():
    if len(group) > 1:
        # Check if titles are actually different (to ignore if there are still exact duplicates)
        titles = set(p['title'] for p in group)
        if len(titles) > 1:
            print(f"\nPotential duplicate group for: {name} | {set_name}")
            for p in group:
                stock = sum(v.get('inventory_quantity', 0) for v in p.get('variants', []))
                print(f"  ID: {p['id']}, Title: '{p['title']}', Stock: {stock}")
            found += 1

if not found:
    print("\nNo fuzzy duplicates found!")
