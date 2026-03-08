"""Generate dirty incremental-batch CSVs for pipeline testing.

Produces synthetic data with intentional quality issues that exercise the data
agent's full cleaning protocol (whitespace, mixed case, null sentinels,
currency symbols, date formats, within-file duplicates).

Initial data is loaded from BigQuery public dataset via seed.py.
This script generates only incremental batches for testing the pipeline's
append/incremental behavior.

Usage:
    python3 generate.py                # generate 3 incremental batches (default)
    python3 generate.py --batches 5    # generate 5 batches
    python3 generate.py --seed 123     # custom random seed
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker # type: ignore

# ---------------------------------------------------------------------------
# Domain constants (from bigquery-public-data.thelook_ecommerce)
# ---------------------------------------------------------------------------

ORDER_STATUSES = ["Cancelled", "Complete", "Processing", "Returned", "Shipped"]
EVENT_TYPES = ["department", "product", "cancel", "home", "cart", "purchase"]
PRODUCT_CATEGORIES = [
    "Accessories", "Active", "Blazers & Jackets", "Clothing Sets",
    "Dresses", "Fashion Hoodies & Sweatshirts", "Intimates", "Jeans",
    "Jumpsuits & Rompers", "Leggings", "Maternity", "Outerwear & Coats",
    "Pants", "Pants & Capris", "Plus", "Shorts", "Skirts",
    "Sleep & Lounge", "Socks", "Socks & Hosiery", "Suits",
    "Suits & Sport Coats", "Sweaters", "Swim", "Tops & Tees", "Underwear",
]
DEPARTMENTS = ["Women", "Men"]
GENDERS = ["M", "F"]
TRAFFIC_SOURCES = ["Display", "Search", "Organic", "Facebook", "Email"]
BROWSERS = ["Chrome", "Firefox", "Safari", "IE", "Other"]
COUNTRIES = [
    "United States", "Brasil", "Japan", "China", "Australia",
    "France", "Germany", "United Kingdom", "Spain", "South Korea",
    "Colombia", "Poland", "Belgium", "Austria",
]
DISTRIBUTION_CENTERS = [
    (1, "Memphis TN", 35.1174, -89.9711),
    (2, "Chicago IL", 41.8369, -87.6847),
    (3, "Houston TX", 29.7604, -95.3698),
    (4, "Los Angeles CA", 34.05, -118.25),
    (5, "New Orleans LA", 29.95, -90.0667),
    (6, "Port Authority of New York/New Jersey NY/NJ", 40.634, -73.7834),
    (7, "Philadelphia PA", 39.95, -75.1667),
    (8, "Mobile AL", 30.6944, -88.0431),
    (9, "Charleston SC", 32.7833, -79.9333),
    (10, "Savannah GA", 32.0167, -81.1167),
]
PRODUCT_BRANDS = [
    "Allegra K", "Calvin Klein", "Carhartt", "Columbia", "Dockers",
    "DKNY", "Free People", "Hanes", "J.Crew", "Levi's",
    "Nike", "Nordstrom", "Patagonia", "Ray-Ban", "Tommy Hilfiger",
    "Under Armour", "Volcom", "Wrangler", "MG", "True Religion",
]
NULL_SENTINELS = ["N/A", "n/a", "NA", "none", "None", "null", "NULL", "-", "--", "missing", "#N/A"]
CURRENCY_SYMBOLS = ["$", "EUR", "£", "¥"]
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",       # 2026-01-15 14:30:00 (correct)
    "%m/%d/%Y %H:%M:%S",       # 01/15/2026 14:30:00
    "%b %d %Y %H:%M:%S",       # Jan 15 2026 14:30:00
    "%B %d, %Y %H:%M:%S",      # January 15, 2026 14:30:00
    "%Y/%m/%d %H:%M:%S",       # 2026/01/15 14:30:00
    "%m-%d-%Y %H:%M:%S",       # 01-15-2026 14:30:00
    "%d %b %Y %H:%M:%S",       # 15 Jan 2026 14:30:00
]
US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class Config:
    seed: int = 42
    date_start: str = "2024-01-01"
    date_end: str = "2026-02-14"
    incremental_date_start: str = "2026-02-01"
    incremental_batches: int = 3
    incremental_dirty_rates: list[float] = field(
        default_factory=lambda: [0.05, 0.03, 0.02]
    )
    overlap_batch_index: int = 1  # batch_002 has overlapping IDs
    overlap_rate: float = 0.05
    initial_counts: dict[str, int] = field(default_factory=lambda: {
        "distribution_centers": 10,
        "products": 300,
        "users": 1000,
        "orders": 1200,
        "order_items": 2000,
        "inventory_items": 3000,
        "events": 5000,
    })
    incremental_counts: dict[str, int] = field(default_factory=lambda: {
        "products": 30,
        "users": 100,
        "orders": 120,
        "order_items": 200,
        "inventory_items": 300,
        "events": 500,
    })


# ---------------------------------------------------------------------------
# Dirty data injector
# ---------------------------------------------------------------------------

class DirtyInjector:
    """Randomly applies data quality issues to field values."""

    def __init__(self, rate: float):
        self.rate = rate

    def _should_dirty(self) -> bool:
        return random.random() < self.rate

    def inject_whitespace(self, value: str) -> str:
        pad = random.choice(["  ", " ", "   "])
        side = random.choice(["left", "right", "both"])
        if side == "left":
            return pad + value
        if side == "right":
            return value + pad
        return pad + value + pad

    def inject_mixed_case(self, value: str) -> str:
        choice = random.choice(["upper", "lower", "title"])
        if choice == "upper":
            return value.upper()
        if choice == "lower":
            return value.lower()
        return value.title()

    def inject_null_sentinel(self) -> str:
        return random.choice(NULL_SENTINELS)

    def inject_currency(self, value: float) -> str:
        symbol = random.choice(CURRENCY_SYMBOLS)
        formatted = f"{value:.2f}"
        if symbol in ("$", "£", "¥"):
            return f"{symbol}{formatted}"
        return f"{symbol}{formatted}"

    def inject_date_format(self, dt: datetime) -> str:
        formats = DATE_FORMATS
        fmt = random.choice(formats[1:])  # type: ignore
        return dt.strftime(fmt)

    def maybe_dirty_string(self, value: str) -> str:
        if not self._should_dirty() or not value:
            return value
        ops = ["whitespace", "case", "null", "empty"]
        weights = [0.35, 0.35, 0.20, 0.10]
        op = random.choices(ops, weights=weights, k=1)[0]
        if op == "whitespace":
            return self.inject_whitespace(value)
        if op == "case":
            return self.inject_mixed_case(value)
        if op == "null":
            return self.inject_null_sentinel()
        return ""

    def maybe_dirty_numeric(self, value: float) -> str:
        if value is None:
            return ""
        if not self._should_dirty():
            return str(value)
        ops = ["currency", "null", "empty"]
        weights = [0.50, 0.35, 0.15]
        op = random.choices(ops, weights=weights, k=1)[0]
        if op == "currency":
            return self.inject_currency(value)
        if op == "null":
            return self.inject_null_sentinel()
        return ""

    def maybe_dirty_timestamp(self, dt: datetime | None) -> str:
        if dt is None:
            return ""
        if not self._should_dirty():
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        ops = ["format", "null", "empty"]
        weights = [0.60, 0.25, 0.15]
        op = random.choices(ops, weights=weights, k=1)[0]
        if op == "format":
            return self.inject_date_format(dt)
        if op == "null":
            return self.inject_null_sentinel()
        return ""

    def maybe_dirty_int(self, value: int | None) -> str:
        if value is None:
            return ""
        if not self._should_dirty():
            return str(value)
        ops = ["null", "empty"]
        weights = [0.70, 0.30]
        op = random.choices(ops, weights=weights, k=1)[0]
        if op == "null":
            return self.inject_null_sentinel()
        return ""


# ---------------------------------------------------------------------------
# Data generator
# ---------------------------------------------------------------------------

class TheLookGenerator:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.fake = Faker()
        Faker.seed(self.config.seed)
        random.seed(self.config.seed)

        self.base_dir = Path(__file__).parent
        self.date_start = datetime.strptime(self.config.date_start, "%Y-%m-%d")
        self.date_end = datetime.strptime(self.config.date_end, "%Y-%m-%d")
        self.incr_date_start = datetime.strptime(
            self.config.incremental_date_start, "%Y-%m-%d"
        )

        # ID pools for referential integrity
        self.dc_ids: list[int] = []
        self.product_ids: list[int] = []
        self.product_data: list[dict] = []
        self.user_ids: list[int] = []
        self.order_ids: list[int] = []
        self.order_user_map: dict[int, int] = {}
        self.inventory_ids: list[int] = []
        self.inventory_product_map: dict[int, int] = {}

        # Track max IDs for incremental generation
        self._max_ids: dict[str, int] = {}

    def _random_datetime(
        self, start: datetime | None = None, end: datetime | None = None,
    ) -> datetime:
        s = start or self.date_start
        e = end or self.date_end
        delta = (e - s).total_seconds()
        offset = random.random() * delta
        return s + timedelta(seconds=offset)

    def _random_price(self, min_p: float = 0.50, max_p: float = 500.0) -> float:
        return float(f"{random.uniform(min_p, max_p):.2f}")

    def _random_cost(self, retail: float) -> float:
        margin = random.uniform(0.3, 0.7)
        return float(f"{retail * margin:.2f}")

    def _sku(self) -> str:
        return hashlib.md5(uuid.uuid4().bytes).hexdigest().upper()

    def _inject_duplicates(self, rows: list[dict], rate: float) -> list[dict]:
        n_dups = max(1, int(len(rows) * rate))
        sources = random.sample(range(len(rows)), min(n_dups, len(rows)))
        dups = [rows[i].copy() for i in sources]
        combined = rows + dups
        random.shuffle(combined)
        return combined

    # ------ Table generators ------

    def _gen_distribution_centers(self, dirty: DirtyInjector) -> list[dict]:
        rows = []
        for dc_id, name, lat, lon in DISTRIBUTION_CENTERS:
            self.dc_ids.append(dc_id)
            rows.append({
                "id": str(dc_id),
                "name": dirty.maybe_dirty_string(name),
                "latitude": str(lat),
                "longitude": str(lon),
            })
        self._max_ids["distribution_centers"] = 10
        return rows

    def _gen_products(self, count: int, dirty: DirtyInjector,
                      start_id: int = 1) -> list[dict]:
        rows = []
        for i in range(count):
            pid = start_id + i
            self.product_ids.append(pid)
            category = random.choice(PRODUCT_CATEGORIES)
            department = random.choice(DEPARTMENTS)
            brand = random.choice(PRODUCT_BRANDS)
            retail = self._random_price(5.0, 999.0)
            cost = self._random_cost(retail)
            name = f"{brand} {category} {self.fake.word().title()}"
            dc_id = random.choice(self.dc_ids)

            product = {
                "id": pid, "category": category, "department": department,
                "brand": brand, "retail_price": retail, "cost": cost,
                "name": name, "sku": self._sku(), "dc_id": dc_id,
            }
            self.product_data.append(product)

            rows.append({
                "id": str(pid),
                "cost": dirty.maybe_dirty_numeric(cost),
                "category": dirty.maybe_dirty_string(category),
                "name": dirty.maybe_dirty_string(name),
                "brand": dirty.maybe_dirty_string(brand),
                "retail_price": dirty.maybe_dirty_numeric(retail),
                "department": dirty.maybe_dirty_string(department),
                "sku": self._sku(),
                "distribution_center_id": dirty.maybe_dirty_int(dc_id),
            })
        self._max_ids["products"] = start_id + count - 1
        return rows

    def _gen_users(self, count: int, dirty: DirtyInjector,
                   start_id: int = 1) -> list[dict]:
        rows = []
        for i in range(count):
            uid = start_id + i
            self.user_ids.append(uid)
            gender = random.choice(GENDERS)
            country = random.choice(COUNTRIES)
            state = random.choice(US_STATES) if country == "United States" else self.fake.state()
            created = self._random_datetime()

            rows.append({
                "id": str(uid),
                "first_name": dirty.maybe_dirty_string(self.fake.first_name()),
                "last_name": dirty.maybe_dirty_string(self.fake.last_name()),
                "email": self.fake.email(),
                "age": dirty.maybe_dirty_int(random.randint(12, 70)),
                "gender": dirty.maybe_dirty_string(gender),
                "state": dirty.maybe_dirty_string(state),
                "street_address": dirty.maybe_dirty_string(self.fake.street_address()),
                "postal_code": dirty.maybe_dirty_string(self.fake.postcode()),
                "city": dirty.maybe_dirty_string(self.fake.city()),
                "country": dirty.maybe_dirty_string(country),
                "latitude": f"{random.uniform(-60, 70):.6f}",
                "longitude": f"{random.uniform(-180, 180):.6f}",
                "traffic_source": dirty.maybe_dirty_string(random.choice(TRAFFIC_SOURCES)),
                "created_at": dirty.maybe_dirty_timestamp(created),
            })
        self._max_ids["users"] = start_id + count - 1
        return rows

    def _gen_orders(self, count: int, dirty: DirtyInjector,
                    start_id: int = 1) -> list[dict]:
        rows = []
        for i in range(count):
            oid = start_id + i
            uid = random.choice(self.user_ids)
            self.order_ids.append(oid)
            self.order_user_map[oid] = uid

            status = random.choice(ORDER_STATUSES)
            gender = random.choice(GENDERS)
            created = self._random_datetime()
            num_items = random.randint(1, 5)

            shipped = None
            delivered = None
            returned = None
            if status in ("Shipped", "Complete", "Returned"):
                shipped = created + timedelta(hours=random.randint(4, 72))
            if status in ("Complete", "Returned"):
                delivered = shipped + timedelta(days=random.randint(1, 7)) if shipped else None
            if status == "Returned":
                returned = delivered + timedelta(days=random.randint(1, 14)) if delivered else None

            rows.append({
                "order_id": str(oid),
                "user_id": dirty.maybe_dirty_int(uid),
                "status": dirty.maybe_dirty_string(status),
                "gender": dirty.maybe_dirty_string(gender),
                "created_at": dirty.maybe_dirty_timestamp(created),
                "returned_at": dirty.maybe_dirty_timestamp(returned),
                "shipped_at": dirty.maybe_dirty_timestamp(shipped),
                "delivered_at": dirty.maybe_dirty_timestamp(delivered),
                "num_of_item": dirty.maybe_dirty_int(num_items),
            })
        self._max_ids["orders"] = start_id + count - 1
        return rows

    def _gen_inventory_items(self, count: int, dirty: DirtyInjector,
                             start_id: int = 1) -> list[dict]:
        rows = []
        for i in range(count):
            iid = start_id + i
            product = random.choice(self.product_data)
            pid = product["id"]
            self.inventory_ids.append(iid)
            self.inventory_product_map[iid] = pid

            created = self._random_datetime()
            sold = None
            if random.random() < 0.6:
                sold = created + timedelta(days=random.randint(1, 90))

            rows.append({
                "id": str(iid),
                "product_id": dirty.maybe_dirty_int(pid),
                "created_at": dirty.maybe_dirty_timestamp(created),
                "sold_at": dirty.maybe_dirty_timestamp(sold),
                "cost": dirty.maybe_dirty_numeric(product["cost"]),
                "product_category": dirty.maybe_dirty_string(product["category"]),
                "product_name": dirty.maybe_dirty_string(product["name"]),
                "product_brand": dirty.maybe_dirty_string(product["brand"]),
                "product_retail_price": dirty.maybe_dirty_numeric(product["retail_price"]),
                "product_department": dirty.maybe_dirty_string(product["department"]),
                "product_sku": self._sku(),
                "product_distribution_center_id": dirty.maybe_dirty_int(product["dc_id"]),
            })
        self._max_ids["inventory_items"] = start_id + count - 1
        return rows

    def _gen_order_items(self, count: int, dirty: DirtyInjector,
                         start_id: int = 1) -> list[dict]:
        rows = []
        for i in range(count):
            item_id = start_id + i
            oid = random.choice(self.order_ids)
            uid = self.order_user_map.get(oid, random.choice(self.user_ids))
            pid = random.choice(self.product_ids)
            inv_id = random.choice(self.inventory_ids)

            status = random.choice(ORDER_STATUSES)
            created = self._random_datetime()
            sale_price = self._random_price(0.50, 999.0)

            shipped = None
            delivered = None
            returned = None
            if status in ("Shipped", "Complete", "Returned"):
                shipped = created + timedelta(hours=random.randint(4, 72))
            if status in ("Complete", "Returned"):
                delivered = shipped + timedelta(days=random.randint(1, 7)) if shipped else None
            if status == "Returned":
                returned = delivered + timedelta(days=random.randint(1, 14)) if delivered else None

            rows.append({
                "id": str(item_id),
                "order_id": dirty.maybe_dirty_int(oid),
                "user_id": dirty.maybe_dirty_int(uid),
                "product_id": dirty.maybe_dirty_int(pid),
                "inventory_item_id": dirty.maybe_dirty_int(inv_id),
                "status": dirty.maybe_dirty_string(status),
                "created_at": dirty.maybe_dirty_timestamp(created),
                "shipped_at": dirty.maybe_dirty_timestamp(shipped),
                "delivered_at": dirty.maybe_dirty_timestamp(delivered),
                "returned_at": dirty.maybe_dirty_timestamp(returned),
                "sale_price": dirty.maybe_dirty_numeric(sale_price),
            })
        self._max_ids["order_items"] = start_id + count - 1
        return rows

    def _gen_events(self, count: int, dirty: DirtyInjector,
                    start_id: int = 1) -> list[dict]:
        rows = []
        eid: int = start_id
        session_flow: list[str] = ["home", "department", "product", "cart", "purchase"]

        while eid < (start_id + count): # type: ignore
            uid = random.choice(self.user_ids)
            session_id = str(uuid.uuid4())
            remaining = (start_id + count) - eid # type: ignore
            session_len = random.randint(2, max(2, min(8, remaining)))
            session_start = self._random_datetime()
            ip = self.fake.ipv4()
            city = self.fake.city()
            state = random.choice(US_STATES)
            postal = self.fake.postcode()
            browser = random.choice(BROWSERS)
            traffic = random.choice(TRAFFIC_SOURCES)

            for seq in range(1, session_len + 1):
                if seq <= len(session_flow):
                    event_type = str(session_flow[seq - 1]) # type: ignore
                else:
                    event_type = random.choice(EVENT_TYPES)

                created = session_start + timedelta(seconds=seq * random.randint(5, 120))
                uri = f"/{event_type}" if event_type != "home" else "/"

                rows.append({
                    "id": str(eid),
                    "user_id": dirty.maybe_dirty_int(uid),
                    "sequence_number": dirty.maybe_dirty_int(seq),
                    "session_id": dirty.maybe_dirty_string(session_id),
                    "created_at": dirty.maybe_dirty_timestamp(created),
                    "ip_address": dirty.maybe_dirty_string(ip),
                    "city": dirty.maybe_dirty_string(city),
                    "state": dirty.maybe_dirty_string(state),
                    "postal_code": dirty.maybe_dirty_string(postal),
                    "browser": dirty.maybe_dirty_string(browser),
                    "traffic_source": dirty.maybe_dirty_string(traffic),
                    "uri": dirty.maybe_dirty_string(uri),
                    "event_type": dirty.maybe_dirty_string(event_type),
                })
                eid += 1 # type: ignore
                if eid >= start_id + count:
                    break

        self._max_ids["events"] = eid - 1 # type: ignore
        return rows

    # ------ CSV writer ------

    def _write_csv(self, rows: list[dict], filepath: Path) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"  wrote {len(rows):>6,} rows → {filepath}")

    # ------ Generation orchestrator ------

    def _bootstrap_id_pools(self) -> None:
        """Initialize ID pools and reference data for incremental generation.

        Since initial data comes from BigQuery (seed.py), we bootstrap the
        internal state needed for referential integrity in incremental batches.
        """
        dirty = DirtyInjector(0.0)  # no dirtying — just populate internal state
        self._gen_distribution_centers(dirty)
        self._gen_products(
            self.config.initial_counts["products"], dirty,
        )
        self._gen_users(
            self.config.initial_counts["users"], dirty,
        )
        self._gen_orders(
            self.config.initial_counts["orders"], dirty,
        )
        self._gen_inventory_items(
            self.config.initial_counts["inventory_items"], dirty,
        )

    def generate_incremental(self) -> None:
        self._bootstrap_id_pools()
        print("Generating incremental batch data...")
        incr_counts = self.config.incremental_counts
        base = self.base_dir / "incremental"

        for batch_idx in range(self.config.incremental_batches):
            batch_num = batch_idx + 1
            dirty_rate = self.config.incremental_dirty_rates[batch_idx]
            dirty = DirtyInjector(dirty_rate)
            print(f"\n  Batch {batch_num:03d} (dirty rate: {dirty_rate:.0%})")

            # Advance date window for each batch
            batch_start = self.incr_date_start + timedelta(days=batch_idx * 5)
            batch_end = batch_start + timedelta(days=5)
            self.date_start = batch_start
            self.date_end = batch_end

            for table_name, count in incr_counts.items():
                start_id = self._max_ids.get(table_name, 0) + 1

                if table_name == "products":
                    rows = self._gen_products(count, dirty, start_id)
                elif table_name == "users":
                    rows = self._gen_users(count, dirty, start_id)
                elif table_name == "orders":
                    rows = self._gen_orders(count, dirty, start_id)
                elif table_name == "order_items":
                    rows = self._gen_order_items(count, dirty, start_id)
                elif table_name == "inventory_items":
                    rows = self._gen_inventory_items(count, dirty, start_id)
                elif table_name == "events":
                    rows = self._gen_events(count, dirty, start_id)
                else:
                    continue

                filename = f"{table_name}_batch_{batch_num:03d}.csv"
                self._write_csv(rows, base / table_name / filename)

        print("\nIncremental batch generation complete.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate dirty incremental batch CSVs for pipeline testing"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--batches", type=int, default=3, help="Number of batches (default: 3)",
    )

    args = parser.parse_args()
    config = Config(seed=args.seed, incremental_batches=args.batches)
    gen = TheLookGenerator(config)
    gen.generate_incremental()

    print("Done.")


if __name__ == "__main__":
    main()
