from services.shopify_client import ShopifyClient
import requests
from collections import defaultdict

c = ShopifyClient()
url = f"{c.base_url}/products.json?limit=250&status=active,draft,archived"
all_products = []

print("Fetching all products...")
while url:
    resp = requests.get(url, headers=c.headers, timeout=15)
    products = resp.json().get('products', [])
    all_products.extend(products)
    
    link_header = resp.headers.get('Link')
    url = None
    if link_header:
        links = link_header.split(', ')
        for link in links:
            if 'rel="next"' in link:
                url = link[link.index('<')+1 : link.index('>')]
                break

print(f"Total products fetched: {len(all_products)}")

# Group by title
by_title = defaultdict(list)
for p in all_products:
    by_title[p['title']].append(p)

to_delete = []

for title, prods in by_title.items():
    if len(prods) > 1:
        print(f"\nFound {len(prods)} duplicates for: {title}")
        # Sort by id (oldest first)
        prods.sort(key=lambda x: x['id'])
        
        # Pick the one to keep. Prefer one with stock, then images, then oldest.
        def get_stock(prod):
            return sum(v.get('inventory_quantity', 0) for v in prod.get('variants', []))
            
        prods.sort(key=lambda x: (get_stock(x) > 0, len(x.get('images', [])) > 0, -x['id']), reverse=True)
        keep_prod = prods[0]
                
        print(f"  Keeping: {keep_prod['id']} (Images: {len(keep_prod.get('images', []))})")
        
        for p in prods:
            if p['id'] != keep_prod['id']:
                print(f"  Deleting: {p['id']} (Images: {len(p.get('images', []))})")
                to_delete.append(p['id'])

if not to_delete:
    print("\nNo duplicates found!")
else:
    print(f"\nReady to delete {len(to_delete)} products.")
    # Actually delete them
    for pid in to_delete:
        print(f"Deleting product {pid}...")
        resp = requests.delete(f"{c.base_url}/products/{pid}.json", headers=c.headers)
        if resp.status_code == 200:
            print("  Success")
        else:
            print(f"  Failed: {resp.status_code}")
