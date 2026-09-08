"""
seed_mongo.py

Populates the MongoDB source with a realistic sample dataset suitable for
a first end-to-end ETL run: brands, categories, stores, products, stocks,
staffs, customers, orders, and order_items.

Run modes:
  python scripts/python/seed_mongo.py              # seed all collections
  python scripts/python/seed_mongo.py --drop       # drop + recreate all
  python scripts/python/seed_mongo.py --collection brands  # seed one collection

Usage:
  make seed         # Docker
  make local-seed   # Local
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from random import choice, randint, uniform

from pymongo import MongoClient
from pymongo.errors import PyMongoError

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.connection import MONGO_DB, MONGO_URI


def _now() -> datetime:
    return datetime.now(UTC)


def _past(days: int = 0) -> datetime:
    return datetime.now(UTC) - timedelta(days=days, hours=randint(0, 23))


def drop_collections(db) -> None:
    collections = [
        "order_items",
        "orders",
        "stocks",
        "products",
        "staffs",
        "customers",
        "stores",
        "categories",
        "brands",
    ]
    for coll in collections:
        db.drop_collection(coll)


def seed_brands(db) -> list[dict]:
    brands = [
        {"name": "Trek", "description": "High-performance road and mountain bikes"},
        {"name": "Specialized", "description": "Premium cycling gear and accessories"},
        {"name": "Giant", "description": "Value-focused performance bicycles"},
        {"name": "Cannondale", "description": "Innovative aluminum and carbon frames"},
        {"name": "Schwinn", "description": "Classic cruiser and hybrid bikes"},
        {"name": "Diamondback", "description": "Mountain and BMX bikes"},
        {"name": "Brompton", "description": "Folding bikes for urban commuting"},
        {"name": "Bianchi", "description": "Italian racing and endurance bikes"},
        {"name": "Pinarello", "description": "Professional road racing bicycles"},
        {"name": "Santa Cruz", "description": "High-end mountain bikes"},
    ]
    result = db.brands.insert_many(brands)
    print(f"  ✓ brands: {len(result.inserted_ids)} documents")
    return result.inserted_ids


def seed_categories(db) -> list[dict]:
    categories = [
        {"name": "Road Bikes", "description": "Lightweight bikes for paved surfaces"},
        {"name": "Mountain Bikes", "description": "Durable bikes for rough terrain"},
        {"name": "Hybrid Bikes", "description": "Versatile bikes for commuting and leisure"},
        {"name": "Electric Bikes", "description": "Assisted riding with battery power"},
        {"name": "Cruiser Bikes", "description": "Comfort-focused casual riding"},
        {"name": "BMX Bikes", "description": "Compact bikes for tricks and racing"},
        {"name": "Kids Bikes", "description": "Smaller frames for young riders"},
        {"name": "Folding Bikes", "description": "Collapsible bikes for transport"},
        {"name": "Gravel Bikes", "description": "Adventure bikes for mixed terrain"},
        {"name": "Accessories", "description": "Helmets, lights, locks, and more"},
    ]
    result = db.categories.insert_many(categories)
    print(f"  ✓ categories: {len(result.inserted_ids)} documents")
    return result.inserted_ids


def seed_stores(db) -> list[dict]:
    stores = [
        {
            "name": "Downtown Cycles",
            "phone": "(555) 101-0001",
            "email": "downtown@bestbikes.com",
            "street": "123 Main Street",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": 94102,
        },
        {
            "name": "Westside Wheels",
            "phone": "(555) 102-0002",
            "email": "westside@bestbikes.com",
            "street": "456 Ocean Avenue",
            "city": "Los Angeles",
            "state": "CA",
            "zip_code": 90401,
        },
        {
            "name": "Harbor Bicycles",
            "phone": "(555) 103-0003",
            "email": "harbor@bestbikes.com",
            "street": "789 Waterfront Drive",
            "city": "Seattle",
            "state": "WA",
            "zip_code": 98101,
        },
        {
            "name": "Mountain View Cycles",
            "phone": "(555) 104-0004",
            "email": "mountain@bestbikes.com",
            "street": "321 Tech Boulevard",
            "city": "Mountain View",
            "state": "CA",
            "zip_code": 94041,
        },
        {
            "name": "Austin's Pedal Power",
            "phone": "(555) 105-0005",
            "email": "austin@bestbikes.com",
            "street": "555 Congress Avenue",
            "city": "Austin",
            "state": "TX",
            "zip_code": 78701,
        },
    ]
    result = db.stores.insert_many(stores)
    print(f"  ✓ stores: {len(result.inserted_ids)} documents")
    return result.inserted_ids


def seed_staffs(db, store_ids: list) -> list[dict]:
    first_names = [
        "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
        "Iris", "Jack", "Karen", "Leo", "Mia", "Nathan", "Olivia", "Paul",
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson",
        "Anderson", "Thomas", "Taylor",
    ]
    emails_seen: set[str] = set()
    staffs: list[dict] = []
    for i in range(20):
        first = first_names[i % len(first_names)]
        last = last_names[i % len(last_names)]
        email = f"{first.lower()}.{last.lower()}@bestbikes.com"
        while email in emails_seen:
            email = f"{first.lower()}.{last.lower()}{i}@bestbikes.com"
        emails_seen.add(email)
        staffs.append({
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": f"(555) {randint(100, 999)}-{randint(1000, 9999)}",
            "active": 1,
            "store_id": store_ids[i % len(store_ids)],
            "manager_id": None,
        })
    result = db.staffs.insert_many(staffs)
    staff_ids = result.inserted_ids
    print(f"  ✓ staffs: {len(staff_ids)} documents")
    return staff_ids


def seed_products(db, brand_ids: list, category_ids: list) -> list[dict]:
    products = [
        {"name": "Domane AL 2", "model_year": 2024, "list_price": 849.99},
        {"name": "FX 3 Disc", "model_year": 2024, "list_price": 749.99},
        {"name": "Marlin 7", "model_year": 2024, "list_price": 899.99},
        {"name": "Checkpoint ALR 5", "model_year": 2024, "list_price": 1899.99},
        {"name": "Electra Townie 7D", "model_year": 2023, "list_price": 499.99},
        {"name": "Verve 3", "model_year": 2024, "list_price": 799.99},
        {"name": "Fuel EX 8", "model_year": 2024, "list_price": 2499.99},
        {"name": "Rail 9.8", "model_year": 2024, "list_price": 4499.99},
        {"name": "Domane SL 5", "model_year": 2024, "list_price": 3299.99},
        {"name": "Tarmac SL 7", "model_year": 2024, "list_price": 4999.99},
        {"name": "Allez Sprint", "model_year": 2024, "list_price": 2799.99},
        {"name": "Diverge E5", "model_year": 2024, "list_price": 1599.99},
        {"name": "Stumpjumper EVO", "model_year": 2024, "list_price": 3999.99},
        {"name": "Chisel Expert", "model_year": 2024, "list_price": 2199.99},
        {"name": " TCR Advanced 2", "model_year": 2024, "list_price": 2299.99},
        {"name": "Defy Advanced", "model_year": 2024, "list_price": 2599.99},
        {"name": "CAAD 13", "model_year": 2023, "list_price": 1899.99},
        {"name": "Synapse Carbon", "model_year": 2024, "list_price": 2899.99},
        {"name": "SuperSix EVO", "model_year": 2024, "list_price": 3499.99},
        {"name": "Scalpel HT", "model_year": 2024, "list_price": 3299.99},
        {"name": "Highball", "model_year": 2024, "list_price": 2599.99},
        {"name": "Hightower", "model_year": 2024, "list_price": 3799.99},
        {"name": "Brompton C Line", "model_year": 2024, "list_price": 1699.99},
        {"name": "Pista", "model_year": 2023, "list_price": 699.99},
        {"name": "Volta", "model_year": 2024, "list_price": 3299.99},
    ]
    docs = []
    for i, p in enumerate(products):
        docs.append({
            "name": p["name"],
            "brand_id": brand_ids[i % len(brand_ids)],
            "category_id": category_ids[i % len(category_ids)],
            "model_year": p["model_year"],
            "list_price": p["list_price"],
        })
    result = db.products.insert_many(docs)
    print(f"  ✓ products: {len(result.inserted_ids)} documents")
    return result.inserted_ids


def seed_stocks(db, store_ids: list, product_ids: list) -> list[dict]:
    docs: list[dict] = []
    for store_id in store_ids:
        for product_id in product_ids[:10]:  # each store stocks first 10 products
            docs.append({
                "store_id": store_id,
                "product_id": product_id,
                "quantity": randint(0, 50),
            })
    result = db.stocks.insert_many(docs)
    print(f"  ✓ stocks: {len(result.inserted_ids)} documents")
    return result.inserted_ids


def seed_customers(db) -> list[dict]:
    first_names = [
        "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason",
        "Isabella", "William", "Mia", "James", "Charlotte", "Benjamin", "Amelia",
        "Lucas", "Harper", "Henry", "Evelyn", "Alexander",
    ]
    last_names = [
        "Anderson", "Baker", "Carter", "Davis", "Evans", "Foster", "Green",
        "Harris", "Irving", "Jones", "King", "Lee", "Miller", "Nelson",
        "Owens", "Parker", "Quinn", "Roberts", "Scott", "Turner",
    ]
    streets = [
        "100 Oak Street", "200 Pine Avenue", "300 Maple Drive", "400 Elm Court",
        "500 Cedar Lane", "600 Birch Way", "700 Willow Road", "800 Spruce Boulevard",
        "900 Aspen Circle", "1000 Redwood Drive",
    ]
    cities = [
        ("San Francisco", "CA"), ("Los Angeles", "CA"), ("Seattle", "WA"),
        ("Portland", "OR"), ("Austin", "TX"), ("Denver", "CO"),
        ("Chicago", "IL"), ("New York", "NY"), ("Boston", "MA"), ("Miami", "FL"),
    ]
    domains = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "proton.me"]
    docs: list[dict] = []
    for i in range(50):
        fn = first_names[i % len(first_names)]
        ln = last_names[i % len(last_names)]
        city, state = cities[i % len(cities)]
        docs.append({
            "first_name": fn,
            "last_name": ln,
            "email": f"{fn.lower()}.{ln.lower()}{i}@{choice(domains)}",
            "phone": f"(555) {randint(100, 999)}-{randint(1000, 9999)}",
            "street": streets[i % len(streets)],
            "city": city,
            "state": state,
            "zip_code": randint(10000, 99999),
        })
    result = db.customers.insert_many(docs)
    print(f"  ✓ customers: {len(result.inserted_ids)} documents")
    return result.inserted_ids


def seed_orders(
    db,
    customer_ids: list,
    store_ids: list,
    staff_ids: list,
) -> list[tuple]:
    statuses = ["Pending", "Processing", "Completed", "Rejected"]
    order_docs: list[dict] = []
    for i in range(80):
        order_date = _past(days=randint(0, 90))
        required_date = order_date + timedelta(days=randint(3, 14))
        shipped_date = None
        status = choice(statuses)
        if status == "Completed":
            shipped_date = order_date + timedelta(days=randint(1, 5))
        order_docs.append({
            "customer_id": choice(customer_ids),
            "order_status": status,
            "order_date": order_date,
            "required_date": required_date,
            "shipped_date": shipped_date,
            "store_id": choice(store_ids),
            "staff_id": choice(staff_ids),
        })
    result = db.orders.insert_many(order_docs)
    order_ids = result.inserted_ids
    print(f"  ✓ orders: {len(order_ids)} documents")
    return list(zip(order_ids, [d["order_date"] for d in order_docs]))


def seed_order_items(db, orders: list[tuple], product_ids: list) -> list[dict]:
    item_docs: list[dict] = []
    for order_id, order_date in orders:
        num_items = randint(1, 4)
        for item_num in range(1, num_items + 1):
            product_id = choice(product_ids)
            quantity = randint(1, 3)
            list_price = uniform(300.0, 5000.0)
            discount = uniform(0.0, 0.25)
            total_value = round(quantity * list_price * (1 - discount), 2)
            item_docs.append({
                "order_id": order_id,
                "item_id": item_num,
                "product_id": product_id,
                "quantity": quantity,
                "list_price": round(list_price, 2),
                "discount": round(discount, 4),
                "total_value": total_value,
            })
    result = db.order_items.insert_many(item_docs)
    print(f"  ✓ order_items: {len(result.inserted_ids)} documents")
    return result.inserted_ids


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed MongoDB with sample bike store data.")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all collections before seeding (full reset)",
    )
    parser.add_argument(
        "--collection",
        "--collections",
        dest="collection",
        default=None,
        help="Seed only a specific collection",
    )
    args = parser.parse_args()

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[ERROR] Cannot connect to MongoDB at {MONGO_URI}: {exc}")
        sys.exit(1)

    db = client[MONGO_DB]
    print(f"Connected to MongoDB: {MONGO_DB}")

    if args.drop:
        print("Dropping existing collections...")
        drop_collections(db)

    if args.collection:
        collections_map = {
            "brands": lambda: seed_brands(db),
            "categories": lambda: seed_categories(db),
            "stores": lambda: seed_stores(db),
            "staffs": lambda: seed_staffs(db, list(db.stores.distinct("store_id")) or seed_stores(db)),
            "products": lambda: seed_products(
                db,
                list(db.brands.distinct("brand_id")) or seed_brands(db),
                list(db.categories.distinct("category_id")) or seed_categories(db),
            ),
            "stocks": lambda: seed_stocks(
                db,
                list(db.stores.distinct("store_id")),
                list(db.products.distinct("product_id")),
            ),
            "customers": lambda: seed_customers(db),
            "orders": lambda: seed_orders(
                db,
                list(db.customers.distinct("customer_id")),
                list(db.stores.distinct("store_id")),
                list(db.staffs.distinct("staff_id")),
            ),
            "order_items": lambda: seed_order_items(
                db,
                [
                    (d["order_id"], d.get("order_date"))
                    for d in db.orders.find({}, {"order_id": 1, "order_date": 1})
                ],
                list(db.products.distinct("product_id")),
            ),
        }
        if args.collection not in collections_map:
            print(f"[ERROR] Unknown collection: {args.collection}")
            sys.exit(1)
        collections_map[args.collection]()
    else:
        print("Seeding collections...")
        brand_ids = seed_brands(db)
        category_ids = seed_categories(db)
        store_ids = seed_stores(db)
        staff_ids = seed_staffs(db, store_ids)
        product_ids = seed_products(db, brand_ids, category_ids)
        seed_stocks(db, store_ids, product_ids)
        customer_ids = seed_customers(db)
        orders = seed_orders(db, customer_ids, store_ids, staff_ids)
        seed_order_items(db, orders, product_ids)

    client.close()
    print("\n✓ Seed complete.")


if __name__ == "__main__":
    main()
