# --- Bronze Iceberg Tables (thelook_ecommerce) ---

locals {
  biglake_connection_full = "${var.project_id}.${lower(var.bq_location)}.${var.biglake_connection_id}"

  bronze_tables = {
    distribution_centers = [
      { name = "id", type = "INT64" },
      { name = "name", type = "STRING" },
      { name = "latitude", type = "FLOAT64" },
      { name = "longitude", type = "FLOAT64" },
    ]
    events = [
      { name = "id", type = "INT64" },
      { name = "user_id", type = "INT64" },
      { name = "sequence_number", type = "INT64" },
      { name = "session_id", type = "STRING" },
      { name = "created_at", type = "TIMESTAMP" },
      { name = "ip_address", type = "STRING" },
      { name = "city", type = "STRING" },
      { name = "state", type = "STRING" },
      { name = "postal_code", type = "STRING" },
      { name = "browser", type = "STRING" },
      { name = "traffic_source", type = "STRING" },
      { name = "uri", type = "STRING" },
      { name = "event_type", type = "STRING" },
    ]
    inventory_items = [
      { name = "id", type = "INT64" },
      { name = "product_id", type = "INT64" },
      { name = "created_at", type = "TIMESTAMP" },
      { name = "sold_at", type = "TIMESTAMP" },
      { name = "cost", type = "FLOAT64" },
      { name = "product_category", type = "STRING" },
      { name = "product_name", type = "STRING" },
      { name = "product_brand", type = "STRING" },
      { name = "product_retail_price", type = "FLOAT64" },
      { name = "product_department", type = "STRING" },
      { name = "product_sku", type = "STRING" },
      { name = "product_distribution_center_id", type = "INT64" },
    ]
    order_items = [
      { name = "id", type = "INT64" },
      { name = "order_id", type = "INT64" },
      { name = "user_id", type = "INT64" },
      { name = "product_id", type = "INT64" },
      { name = "inventory_item_id", type = "INT64" },
      { name = "status", type = "STRING" },
      { name = "created_at", type = "TIMESTAMP" },
      { name = "shipped_at", type = "TIMESTAMP" },
      { name = "delivered_at", type = "TIMESTAMP" },
      { name = "returned_at", type = "TIMESTAMP" },
      { name = "sale_price", type = "FLOAT64" },
    ]
    orders = [
      { name = "order_id", type = "INT64" },
      { name = "user_id", type = "INT64" },
      { name = "status", type = "STRING" },
      { name = "gender", type = "STRING" },
      { name = "created_at", type = "TIMESTAMP" },
      { name = "returned_at", type = "TIMESTAMP" },
      { name = "shipped_at", type = "TIMESTAMP" },
      { name = "delivered_at", type = "TIMESTAMP" },
      { name = "num_of_item", type = "INT64" },
    ]
    products = [
      { name = "id", type = "INT64" },
      { name = "cost", type = "FLOAT64" },
      { name = "category", type = "STRING" },
      { name = "name", type = "STRING" },
      { name = "brand", type = "STRING" },
      { name = "retail_price", type = "FLOAT64" },
      { name = "department", type = "STRING" },
      { name = "sku", type = "STRING" },
      { name = "distribution_center_id", type = "INT64" },
    ]
    users = [
      { name = "id", type = "INT64" },
      { name = "first_name", type = "STRING" },
      { name = "last_name", type = "STRING" },
      { name = "email", type = "STRING" },
      { name = "age", type = "INT64" },
      { name = "gender", type = "STRING" },
      { name = "state", type = "STRING" },
      { name = "street_address", type = "STRING" },
      { name = "postal_code", type = "STRING" },
      { name = "city", type = "STRING" },
      { name = "country", type = "STRING" },
      { name = "latitude", type = "FLOAT64" },
      { name = "longitude", type = "FLOAT64" },
      { name = "traffic_source", type = "STRING" },
      { name = "created_at", type = "TIMESTAMP" },
    ]
  }
}

resource "google_bigquery_table" "bronze" {
  for_each = local.bronze_tables

  project             = google_project.pipeline.project_id
  dataset_id          = google_bigquery_dataset.bronze.dataset_id
  table_id            = each.key
  deletion_protection = false

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [schema, biglake_configuration]
  }

  biglake_configuration {
    connection_id = local.biglake_connection_full
    storage_uri   = "gs://${google_storage_bucket.iceberg.name}/bronze/${each.key}/"
    file_format   = "PARQUET"
    table_format  = "ICEBERG"
  }

  schema = jsonencode([
    for col in each.value : {
      name = col.name
      type = col.type
      mode = "NULLABLE"
    }
  ])

  depends_on = [
    google_bigquery_connection.biglake_iceberg,
    google_project_iam_member.biglake_connection_storage,
  ]
}
