#!/usr/bin/env python3
"""Generate the OtterShops seed catalog as a Flyway migration.

Deterministic (fixed seed), so re-running produces the same SQL. Everything here is invented:
product names, sub-labels, stores and reviewers. Photos come from tools/catalog/images.csv.

Usage: python3 tools/catalog/generate.py
Writes services/order-service/src/main/resources/db/migration/V2__catalog_seed.sql
"""
import csv
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "services/order-service/src/main/resources/db/migration/V2__catalog_seed.sql"
rng = random.Random(20261127)
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)

IMAGES = defaultdict(list)
for row in csv.DictReader((ROOT / "tools/catalog/images.csv").open()):
    IMAGES[row["used_for"]].append("/images/" + row["file"])

COLORS = {
    "Black": ("#1f1f1f", "black"), "Navy": ("#1f2f4d", "blue"), "Heather Gray": ("#9a9ea3", "gray"),
    "Ivory": ("#f3efe3", "white"), "Bright White": ("#ffffff", "white"), "Sage": ("#9caf88", "green"),
    "Olive": ("#6b6b3a", "green"), "Rust": ("#b5532d", "orange"), "Blush": ("#e8b4b0", "pink"),
    "Burgundy": ("#6d1f2f", "red"), "Cherry": ("#b3122e", "red"), "Camel": ("#b38a58", "brown"),
    "Chocolate": ("#5a3a26", "brown"), "Cobalt": ("#2350b5", "blue"), "Sky": ("#9cc3e6", "blue"),
    "Mustard": ("#d4a52a", "yellow"), "Lavender": ("#b6a4d4", "purple"), "Oatmeal": ("#d9cbb0", "beige"),
    "Light Wash": ("#a9c1d9", "blue"), "Medium Wash": ("#5d7fa6", "blue"), "Dark Wash": ("#2b3d5c", "blue"),
    "Black Wash": ("#2e2e33", "black"), "Floral Print": ("#d98f8f", "multi"), "Stripe": ("#c9d3df", "multi"),
}
ALPHA = ["XS", "S", "M", "L", "XL", "XXL"]
WOMEN_DENIM = ["24", "25", "26", "27", "28", "29", "30", "31", "32"]
MEN_WAIST = ["28", "30", "32", "34", "36", "38"]
KIDS = ["4", "5", "6", "7", "8", "10", "12", "14"]
BABY = ["0-3M", "3-6M", "6-12M", "12-18M", "18-24M"]

ADJ = ["Harbor", "Willow", "Tidewater", "Saltmarsh", "Riverstone", "Cove", "Driftwood", "Brook", "Meadow",
       "Kelp", "Shoreline", "Sandbar", "Larkspur", "Juniper", "Marina", "Fernhill", "Pebble", "Glacier",
       "Canyon", "Mistral", "Aspen", "Bayside", "Cedar", "Lagoon", "Otterly", "Seaglass", "Wharf", "Estuary"]

# (department, category, pool(s), count, sizes, price range $, fits, colours, nouns, materials, labels, collections)
SPECS = [
    ("women", "Dresses", ["dresses"], 14, ALPHA[:5], (39, 89), ["Fit & Flare", "Slip", "Wrap", "Shirt"],
     ["Black", "Navy", "Floral Print", "Cherry", "Ivory", "Sage", "Rust"], ["Midi Dress", "Maxi Dress", "Mini Dress", "Wrap Dress", "Slip Dress"],
     "100% viscose", "OtterShops", []),
    ("women", "Sweaters", ["sweaters-w"], 10, ALPHA[:5], (34, 69), ["Relaxed", "Regular", "Cropped"],
     ["Oatmeal", "Rust", "Sage", "Camel", "Ivory", "Burgundy"], ["Crewneck Sweater", "Cable-Knit Sweater", "Cardigan", "Mock-Neck Sweater"],
     "60% cotton, 40% acrylic", "OtterShops", []),
    ("women", "Shirts & Blouses", ["shirts-w"], 8, ALPHA[:5], (29, 54), ["Relaxed", "Regular"],
     ["Bright White", "Cherry", "Sky", "Stripe", "Blush"], ["Poplin Shirt", "Satin Blouse", "Linen-Blend Shirt", "Button-Front Blouse"],
     "100% cotton poplin", "OtterShops", []),
    ("women", "Skirts", ["skirts"], 8, ALPHA[:5], (29, 59), ["A-Line", "Pencil", "Pleated"],
     ["Black", "Ivory", "Mustard", "Burgundy", "Light Wash"], ["Midi Skirt", "Denim Mini Skirt", "Pleated Skirt", "Pencil Skirt"],
     "98% cotton, 2% elastane", "OtterShops", []),
    ("women", "Tees & Tanks", ["tees-w"], 10, ALPHA, (12, 24), ["Regular", "Relaxed", "Slim"],
     ["Bright White", "Black", "Heather Gray", "Navy", "Blush", "Sage"], ["Crew Tee", "V-Neck Tee", "Boxy Tee", "Ribbed Tank"],
     "100% cotton jersey", "Everyday Otter", ["essentials-forever"]),
    ("women", "Jeans", ["jeans-w", "jeans-d"], 12, WOMEN_DENIM, (44, 79), ["Skinny", "Straight", "Wide-Leg", "Bootcut", "Mom"],
     ["Light Wash", "Medium Wash", "Dark Wash", "Black Wash"], ["High-Rise Jeans", "Ankle Jeans", "Wide-Leg Jeans", "Bootcut Jeans"],
     "92% cotton, 6% polyester, 2% elastane", "Riverbend Denim", ["denim"]),
    ("women", "Coats & Jackets", ["outerwear-w"], 8, ALPHA[:5], (79, 159), ["Relaxed", "Regular", "Belted"],
     ["Camel", "Black", "Oatmeal", "Navy", "Chocolate"], ["Wool-Blend Coat", "Trench Coat", "Teddy Coat", "Puffer Jacket"],
     "55% wool, 45% polyester", "OtterShops", []),
    ("women", "Activewear", ["active-bottoms", "active-tops"], 13, ALPHA[:5], (24, 64), ["Compression", "Relaxed", "Regular"],
     ["Black", "Navy", "Sage", "Lavender", "Cobalt", "Rust"], ["High-Rise Leggings", "Sports Bra", "Training Tank", "Flare Leggings", "Run Shorts"],
     "78% recycled polyester, 22% elastane", "Otter Active", ["activewear"]),
    ("women", "Sleepwear", ["sleep"], 6, ALPHA[:5], (29, 59), ["Relaxed"],
     ["Sky", "Ivory", "Blush", "Navy"], ["Pajama Set", "Satin Sleep Set", "Lounge Pant"],
     "100% cotton flannel", "OtterShops", []),
    ("men", "Tees", ["tees-m"], 10, ALPHA, (14, 26), ["Regular", "Slim", "Relaxed"],
     ["Black", "Bright White", "Heather Gray", "Navy", "Olive", "Rust"], ["Pocket Tee", "Crew Tee", "Henley", "Heavyweight Tee"],
     "100% cotton jersey", "Everyday Otter", ["essentials-forever"]),
    ("men", "Shirts", ["shirts-m"], 8, ALPHA, (34, 59), ["Slim", "Regular"],
     ["Sky", "Bright White", "Navy", "Stripe", "Burgundy"], ["Oxford Shirt", "Flannel Shirt", "Poplin Shirt", "Linen Shirt"],
     "100% cotton oxford", "OtterShops", []),
    ("men", "Hoodies & Sweatshirts", ["hoodies"], 8, ALPHA, (34, 59), ["Regular", "Relaxed"],
     ["Heather Gray", "Black", "Navy", "Olive", "Oatmeal"], ["Pullover Hoodie", "Zip Hoodie", "Fleece Crew", "Quarter-Zip"],
     "80% cotton, 20% polyester fleece", "Otter Active", []),
    ("men", "Pants & Chinos", ["chinos"], 8, MEN_WAIST, (39, 64), ["Slim", "Straight", "Relaxed"],
     ["Camel", "Navy", "Olive", "Black", "Oatmeal"], ["Stretch Chinos", "Cargo Pants", "Pleated Trousers", "Jogger Pants"],
     "97% cotton, 3% elastane", "OtterShops", []),
    ("men", "Jeans", ["jeans-d"], 8, MEN_WAIST, (49, 79), ["Slim", "Straight", "Athletic Taper", "Relaxed"],
     ["Light Wash", "Medium Wash", "Dark Wash", "Black Wash"], ["Slim Jeans", "Straight Jeans", "Taper Jeans", "Relaxed Jeans"],
     "99% cotton, 1% elastane", "Riverbend Denim", ["denim"]),
    ("men", "Jackets & Coats", ["outerwear-m", "denim-jackets"], 10, ALPHA, (69, 149), ["Regular", "Slim"],
     ["Camel", "Black", "Medium Wash", "Navy", "Olive"], ["Trucker Jacket", "Wool Topcoat", "Moto Jacket", "Chore Coat", "Blazer"],
     "100% cotton twill", "OtterShops", []),
    ("men", "Sweaters", ["sweaters-m"], 6, ALPHA, (39, 69), ["Regular", "Relaxed"],
     ["Navy", "Burgundy", "Heather Gray", "Olive", "Oatmeal"], ["Merino Crew", "Shawl-Collar Cardigan", "Waffle-Knit Sweater"],
     "100% merino wool", "OtterShops", []),
    ("men", "Activewear", ["active-shorts", "active-tops"], 7, ALPHA, (24, 54), ["Regular", "Slim"],
     ["Black", "Navy", "Cobalt", "Heather Gray"], ["Run Shorts", "Training Tee", "Track Pants", "Half-Zip Pullover"],
     "88% recycled polyester, 12% elastane", "Otter Active", ["activewear"]),
    ("kids", "Kids' Clothing", ["kids"], 16, KIDS, (12, 39), ["Regular", "Relaxed"],
     ["Mustard", "Cobalt", "Cherry", "Heather Gray", "Floral Print", "Sage", "Stripe"], ["Hoodie", "Graphic-Free Tee", "Puffer Jacket", "Jogger", "Play Dress", "Denim Jacket"],
     "100% cotton", "Little Otter", []),
    ("baby", "Baby Clothing", ["baby"], 13, BABY, (10, 34), ["Regular"],
     ["Ivory", "Blush", "Sky", "Sage", "Oatmeal", "Stripe"], ["Bodysuit 3-Pack", "Footed One-Piece", "Knit Romper", "Sleep Sack", "Cardigan Set"],
     "100% organic cotton", "Little Otter", []),
    ("maternity", "Maternity", ["maternity"], 9, ALPHA[:5], (29, 79), ["Bump-Friendly", "Relaxed"],
     ["Black", "Navy", "Blush", "Sage", "Burgundy"], ["Maternity Wrap Dress", "Nursing Tee", "Maternity Leggings", "Over-Bump Jeans", "Maternity Cardigan"],
     "95% modal, 5% elastane", "OtterShops Maternity", ["maternity"]),
]

COLLECTIONS = [
    ("women", "Women", "women", "Dresses, denim, knits and everything in between.", 1),
    ("men", "Men", "men", "Tees, chinos, layers and jackets built to wear hard.", 2),
    ("kids", "Kids", "kids", "Play-proof clothes for ages 4 to 14.", 3),
    ("baby", "Baby", "baby", "Soft organic basics for 0 to 24 months.", 4),
    ("maternity", "Maternity", "maternity", "Bump-friendly fits for every trimester.", 5),
    ("denim", "Denim", None, "Riverbend Denim in every fit and wash.", 6),
    ("activewear", "Activewear", None, "Otter Active gear for runs, lifts and rest days.", 7),
    ("sale", "Sale", None, "Markdowns across the store. Prices as marked.", 8),
    ("new-arrivals", "New Arrivals", None, "Just landed this week.", 9),
    ("essentials-forever", "Essentials Forever", None, "Everyday tees at an everyday price, never discounted.", 10),
    ("gift-cards", "Gift Cards", None, "Let them pick.", 11),
]

STORES = [
    ("S001", "OtterShops Union Square", "245 Powell St", "San Francisco", "CA", "94102", True),
    ("S002", "OtterShops Bay Street", "5600 Bay St", "Emeryville", "CA", "94608", True),
    ("S003", "OtterShops Santana Plaza", "3055 Olin Ave", "San Jose", "CA", "95128", True),
    ("S004", "OtterShops Grove Commons", "189 Grove Dr", "Los Angeles", "CA", "90036", True),
    ("S005", "OtterShops Mission Valley", "1640 Camino del Rio N", "San Diego", "CA", "92108", False),
    ("S006", "OtterShops Pearl District", "1120 NW Couch St", "Portland", "OR", "97209", True),
    ("S007", "OtterShops Pike Market", "1531 4th Ave", "Seattle", "WA", "98101", True),
    ("S008", "OtterShops Larimer Square", "1430 Larimer St", "Denver", "CO", "80202", True),
    ("S009", "OtterShops Pearl Street", "1200 Pearl St", "Boulder", "CO", "80302", False),
    ("S010", "OtterShops South Congress", "1500 S Congress Ave", "Austin", "TX", "78704", True),
    ("S011", "OtterShops Uptown Park", "1100 Uptown Park Blvd", "Houston", "TX", "77056", True),
    ("S012", "OtterShops Magnificent Mile", "600 N Michigan Ave", "Chicago", "IL", "60611", True),
    ("S013", "OtterShops Lincoln Park", "2240 N Clark St", "Chicago", "IL", "60614", True),
    ("S014", "OtterShops Herald Square", "1360 Broadway", "New York", "NY", "10018", True),
    ("S015", "OtterShops Atlantic Terminal", "139 Flatbush Ave", "Brooklyn", "NY", "11217", False),
    ("S016", "OtterShops Back Bay", "800 Boylston St", "Boston", "MA", "02199", True),
    ("S017", "OtterShops Ponce City", "675 Ponce de Leon Ave NE", "Atlanta", "GA", "30308", True),
    ("S018", "OtterShops Brickell", "701 S Miami Ave", "Miami", "FL", "33131", True),
    ("S019", "OtterShops Scottsdale Quarter", "15279 N Scottsdale Rd", "Scottsdale", "AZ", "85254", True),
    ("S020", "OtterShops Mall of the North", "8100 24th Ave S", "Bloomington", "MN", "55425", True),
    ("S021", "OtterShops Fountain Square", "520 Vine St", "Cincinnati", "OH", "45202", True),
    ("S022", "OtterShops Old Town", "1203 King St", "Alexandria", "VA", "22314", True),
]

FIRST = ["Ava", "Liam", "Noor", "Mateo", "Priya", "Jonah", "Sofia", "Kai", "Elena", "Marcus", "Hana", "Diego",
         "Grace", "Omar", "Talia", "Felix", "Mei", "Ruth", "Andre", "Lena", "Sam", "Iris", "Theo", "Zara"]
CITIES = ["Portland, OR", "Austin, TX", "Chicago, IL", "Denver, CO", "Raleigh, NC", "Oakland, CA", "Tucson, AZ",
          "Madison, WI", "Boise, ID", "Richmond, VA", "Columbus, OH", "Sacramento, CA"]
REVIEW_TEXT = {
    5: [("Instant favorite", "Washed it twice and it still looks new. Bought a second color."),
        ("Worth every penny", "Great weight, great color, and it fits exactly like the size chart says.")],
    4: [("Really nice", "Lovely fabric. Runs a touch long on me but I'm 5'3\"."),
        ("Good everyday piece", "Comfortable and easy to style. Wish there were more colors.")],
    3: [("It's fine", "Nice color, but the fabric is thinner than I expected."),
        ("Mixed feelings", "Fit is good, though it wrinkles easily.")],
    2: [("Not for me", "The cut was boxier than the photos suggest. Returned it.")],
}
FIT_NOTES = ["Runs small", "True to size", "True to size", "True to size", "Runs large"]


def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def values(rows):
    return ",\n".join("(" + ", ".join(q(v) for v in r) + ")" for r in rows)


def price_cents(lo, hi):
    return rng.randrange(lo, hi + 1) * 100 - 1  # $xx.99


def main():
    products, pcols, images, skus, reviews = [], [], [], [], []
    used_names = set()
    counter = 10001
    by_dept = defaultdict(list)
    for dept, cat, pools, count, sizes, (lo, hi), fits, colors, nouns, material, label, cols in SPECS:
        pool = [img for p in pools for img in IMAGES[p]]
        assert pool, f"no images for {pools}"
        offset = rng.randrange(len(pool))
        for i in range(count):
            pid = f"P{counter}"
            counter += 1
            noun = nouns[i % len(nouns)]
            while True:
                name = f"{rng.choice(ADJ)} {noun}"
                if name not in used_names:
                    used_names.add(name)
                    break
            fit = fits[i % len(fits)]
            list_cents = price_cents(lo, hi)
            markdown = None
            collections = [dept] + cols
            if rng.random() < 0.22 and "essentials-forever" not in cols and "maternity" not in cols:
                markdown = int(list_cents * rng.choice([0.7, 0.6, 0.5])) // 100 * 100 + 99
                collections.append("sale")
            created = NOW - timedelta(days=rng.randrange(0, 150), hours=rng.randrange(24))
            is_new = (NOW - created).days < 21
            if is_new:
                collections.append("new-arrivals")
            n_colors = min(len(colors), rng.choice([2, 3, 3, 4]))
            chosen = rng.sample(colors, n_colors)
            for pos, color in enumerate(chosen):
                url = pool[(offset + i * 2 + pos) % len(pool)]
                images.append((pid, pos, url, f"{name} in {color}", color))
            images.append((pid, n_colors, pool[(offset + i * 2 + n_colors) % len(pool)], f"{name}, alternate view", None))
            fate = rng.random()
            for color in chosen:
                hexv, family = COLORS[color]
                for so, size in enumerate(sizes):
                    if fate < 0.025:
                        stock = 0  # whole product sold out
                    elif fate < 0.08:
                        stock = rng.choice([0, 1, 1, 2])  # low-stock product
                    else:
                        r = rng.random()
                        stock = 0 if r < 0.08 else rng.randint(1, 5) if r < 0.18 else rng.randint(6, 60)
                    code = color.upper().replace(" ", "")[:6]
                    skus.append((f"{pid}-{code}-{size}", pid, color, hexv, family, size, so, stock))
            rating_target = rng.choice([4.8, 4.6, 4.5, 4.4, 4.2, 4.0, 3.8, 4.7])
            n_reviews = rng.randint(3, 6)
            stars = []
            for _ in range(n_reviews):
                s = max(2, min(5, round(rng.gauss(rating_target, 0.7))))
                stars.append(s)
                title, body = rng.choice(REVIEW_TEXT[s])
                reviews.append((pid, f"{rng.choice(FIRST)} {rng.choice('ABCDEFGHJKLMNPRSTW')}.", rng.choice(CITIES), s,
                                title, body, rng.choice(FIT_NOTES),
                                (created + timedelta(days=rng.randrange(1, 40))).isoformat()))
            review_count = rng.randint(n_reviews, 900)
            rating = round(sum(stars) / len(stars) * 0.4 + rating_target * 0.6, 1)
            desc = (f"Our {noun.lower()} in {material.split(',')[0].lower()} with a {fit.lower()} fit. "
                    f"Made to layer, wash and wear on repeat.")
            details = "\n".join([f"{fit} fit", f"{material}", "Machine wash cold, tumble dry low", f"Style #{pid}"])
            products.append((pid, name, label, dept, cat, fit, desc, details, material, list_cents, markdown,
                             rating, review_count, is_new, created.isoformat()))
            for c in dict.fromkeys(collections):
                pcols.append((pid, c))
            by_dept[(dept, cat)].append(pid)

    links = []
    all_by_dept = defaultdict(list)
    for (dept, cat), ids in by_dept.items():
        all_by_dept[dept].extend((cat, i) for i in ids)
    for (dept, cat), ids in by_dept.items():
        others = [i for c, i in all_by_dept[dept] if c != cat]
        for pid in ids:
            for pos, rid in enumerate(rng.sample(others, min(4, len(others)))):
                links.append((pid, rid, pos))

    editorial = IMAGES["editorial"]
    collections = [(slug, name, dept, desc, editorial[i % len(editorial)], order)
                   for i, (slug, name, dept, desc, order) in enumerate(COLLECTIONS)]
    stores = []
    for sid, name, addr, city, state, zip_, pickup in STORES:
        lat = round(rng.uniform(25, 48), 4)
        lng = round(rng.uniform(-123, -71), 4)
        stores.append((sid, name, addr, city, state, zip_, f"(555) 01{sid[-2:]}-{rng.randint(1000, 9999)}",
                       "Mon-Sat 10am-9pm, Sun 11am-7pm", lat, lng, pickup, rng.choice([1, 2, 2, 4])))

    sql = ["-- Generated by tools/catalog/generate.py. Do not edit by hand; edit the generator and re-run.",
           f"-- {len(products)} products, {len(skus)} SKUs, {len(stores)} stores.", ""]
    sql += ["INSERT INTO collections (slug, name, department, description, hero_image, sort_order) VALUES",
            values(collections) + ";", ""]
    sql += ["INSERT INTO products (id, name, label, department, category, fit, description, details, materials, "
            "list_price_cents, markdown_price_cents, rating, review_count, is_new, created_at) VALUES",
            values(products) + ";", ""]
    sql += ["INSERT INTO product_collections (product_id, collection_slug) VALUES", values(pcols) + ";", ""]
    sql += ["INSERT INTO product_images (product_id, position, url, alt, color) VALUES", values(images) + ";", ""]
    sql += ["INSERT INTO skus (sku, product_id, color, color_hex, color_family, size, size_order, stock) VALUES",
            values(skus) + ";", ""]
    sql += ["INSERT INTO product_links (product_id, related_id, position) VALUES", values(links) + ";", ""]
    sql += ["INSERT INTO reviews (product_id, author, location, rating, title, body, fit_note, created_at) VALUES",
            values(reviews) + ";", ""]
    sql += ["INSERT INTO stores (id, name, address, city, state, zip, phone, hours, latitude, longitude, "
            "pickup_enabled, pickup_ready_hours) VALUES", values(stores) + ";", ""]
    OUT.write_text("\n".join(sql))
    sold_out = sum(1 for p in products if all(s[7] == 0 for s in skus if s[1] == p[0]))
    print(f"{len(products)} products, {len(skus)} skus, {sold_out} sold out, "
          f"{sum(1 for p in products if p[10])} marked down -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
