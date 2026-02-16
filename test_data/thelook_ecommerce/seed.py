"""Seed bronze Iceberg tables from BigQuery public thelook_ecommerce dataset.

Reads from bigquery-public-data.thelook_ecommerce and inserts into the user's
bronze-layer BigQuery Iceberg tables. Tables must already exist (run DDL first).

Usage:
    python3 seed.py --project-id YOUR_PROJECT_ID
    python3 seed.py  # reads PROJECT_ID from .env
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google.cloud import bigquery # type: ignore

SOURCE_DATASET = "bigquery-public-data.thelook_ecommerce"

# Column mappings: bronze table columns in order.
# The public dataset column names match 1:1 with our bronze DDL.
TABLES = {
    "distribution_centers": [
        "id", "name", "latitude", "longitude",
    ],
    "users": [
        "id", "first_name", "last_name", "email", "age", "gender",
        "state", "street_address", "postal_code", "city", "country",
        "latitude", "longitude", "traffic_source", "created_at",
    ],
    "products": [
        "id", "cost", "category", "name", "brand",
        "retail_price", "department", "sku", "distribution_center_id",
    ],
    "orders": [
        "order_id", "user_id", "status", "gender",
        "created_at", "returned_at", "shipped_at",
        "delivered_at", "num_of_item",
    ],
    "order_items": [
        "id", "order_id", "user_id", "product_id",
        "inventory_item_id", "status", "created_at",
        "shipped_at", "delivered_at", "returned_at", "sale_price",
    ],
    "inventory_items": [
        "id", "product_id", "created_at", "sold_at", "cost",
        "product_category", "product_name", "product_brand",
        "product_retail_price", "product_department", "product_sku",
        "product_distribution_center_id",
    ],
    "events": [
        "id", "user_id", "sequence_number", "session_id",
        "created_at", "ip_address", "city", "state",
        "postal_code", "browser", "traffic_source", "uri",
        "event_type",
    ],
}


def load_env_values() -> dict[str, str]:
    """Load values from .env if it exists."""
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    values = {}
    if not env_file.exists():
        return values
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                # Handle comments and trailing whitespace
                line = line.split("#")[0].strip()
                key, val = line.split("=", 1)
                key = key.strip()
                if key.startswith("export "):
                    key = key.replace("export ", "", 1).strip()
                values[key] = val.strip().strip('"').strip("'")
    return values


def seed_table(
    client: bigquery.Client,
    project_id: str,
    table_name: str,
    columns: list[str],
) -> None:
    """Insert data from public dataset into bronze Iceberg table."""
    col_list = ", ".join(columns)

    query = f"""
    INSERT INTO `{project_id}.bronze.{table_name}` ({col_list})
    SELECT {col_list}
    FROM `{SOURCE_DATASET}.{table_name}`
    """

    job = client.query(query)
    job.result()
    print(f"  {table_name}: {job.num_dml_affected_rows:,} rows inserted")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed bronze Iceberg tables from BigQuery public dataset"
    )
    parser.add_argument(
        "--project-id",
        help="GCP project ID (reads from .env if not provided)",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=list(TABLES.keys()),
        help="Seed only specific tables (default: all)",
    )
    args = parser.parse_args()

    env = load_env_values()
    project_id = args.project_id or env.get("PROJECT_ID")
    if not project_id:
        print("ERROR: --project-id required or set PROJECT_ID in .env")
        sys.exit(1)

    location = env.get("BQ_LOCATION", "US")
    tables_to_seed = args.tables or list(TABLES.keys())

    print(f"Seeding bronze tables in project: {project_id}")
    print(f"Location: {location}")
    print(f"Source: {SOURCE_DATASET}")
    print(f"Tables: {', '.join(tables_to_seed)}")
    print()

    client = bigquery.Client(project=project_id, location=location)

    for table_name in tables_to_seed:
        columns = TABLES[table_name]
        seed_table(client, project_id, table_name, columns)

    print()
    print("Seed complete.")


if __name__ == "__main__":
    main()
